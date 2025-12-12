import os
import threading
import time
import requests
import base64
import json
import logging
from typing import Optional, Dict, Any

from flask import Flask, request, jsonify
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from langchain_ollama import OllamaLLM
from json_repair import repair_json
from prompts import TEXT_PROMPT

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Flask app setup
app = Flask(__name__)

# --- Configuration ---
class Config:
    INTERVAL = int(os.getenv("INTERVAL", 10))
    HOST_IMAGE_DIR = os.getenv("HOST_IMAGE_DIR", "/images")
    OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://host.docker.internal:11434")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:27b")
    CAPTURE_SERVICE_URL = os.getenv("CAPTURE_SERVICE_URL", "http://capture:5000")
    
    # Twilio
    TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
    TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
    TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
    RECIPIENT_PHONE_NUMBER = os.getenv("RECIPIENT_PHONE_NUMBER")

    @classmethod
    def validate(cls):
        missing = []
        if not cls.HOST_IMAGE_DIR: missing.append("HOST_IMAGE_DIR")
        # Twilio is optional but recommended for alerts
        if not all([cls.TWILIO_ACCOUNT_SID, cls.TWILIO_AUTH_TOKEN, cls.TWILIO_PHONE_NUMBER, cls.RECIPIENT_PHONE_NUMBER]):
            logger.warning("Twilio configuration missing. SMS alerts will be disabled.")
        
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

Config.validate()

# --- LLM Setup ---

try:
    llm = OllamaLLM(
        model=Config.OLLAMA_MODEL,
        base_url=Config.OLLAMA_HOST,
        num_ctx=10000,
    )
except Exception as e:
    logger.error(f"Failed to initialize Ollama LLM: {e}")
    llm = None

# --- Services ---

def run_image_analysis(image_path: str) -> Dict[str, Any]:
    """
    Analyzes the given image of a turtle using the configured LLM.
    """
    if not llm:
        logger.error("LLM not initialized. Skipping analysis.")
        return {}

    if not os.path.exists(image_path):
        logger.error(f"Image file not found: {image_path}")
        return {}

    try:
        with open(image_path, 'rb') as test_image:
            image_data = base64.b64encode(test_image.read()).decode('utf-8')
            
        llm_with_image = llm.bind(images=[image_data])
        response = llm_with_image.invoke(TEXT_PROMPT)
        
        # Parse JSON
        repaired_json = repair_json(response)
        return json.loads(repaired_json)
    except Exception as e:
        logger.error(f"Error during image analysis: {e}")
        return {}

def run_capture() -> bool:
    """
    Triggers the capture service to take a snapshot.
    """
    logger.debug('Triggering camera capture...')
    target_url = f"{Config.CAPTURE_SERVICE_URL}/capture-now"
    
    try:
        response = requests.get(target_url, params={"output_dir": Config.HOST_IMAGE_DIR}, timeout=10)
        response.raise_for_status()
        logger.info("Capture command sent successfully.")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Error calling capture service: {e}")
        return False

def send_twilio_notification(message_body: str) -> None:
    """
    Sends a notification via Twilio SMS if configured.
    """
    if not all([Config.TWILIO_ACCOUNT_SID, Config.TWILIO_AUTH_TOKEN, Config.TWILIO_PHONE_NUMBER, Config.RECIPIENT_PHONE_NUMBER]):
        logger.info(f"Twilio not configured. Skipping notification: {message_body}")
        return

    try:
        client = Client(Config.TWILIO_ACCOUNT_SID, Config.TWILIO_AUTH_TOKEN)
        message = client.messages.create(
            from_=Config.TWILIO_PHONE_NUMBER,
            body=message_body,
            to=Config.RECIPIENT_PHONE_NUMBER
        )
        logger.info(f'Twilio notification sent: {message.sid}')
    except TwilioRestException as e:
        logger.error(f"Twilio API error: {e}")
    except Exception as e:
        logger.error(f"Failed to send notification: {e}")

def format_alert_message(analysis: Dict[str, Any]) -> str:
    return (
        f"🐢 Turtle Alert detected at: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Status: {analysis.get('turtle_well_being', 'unknown')}\n"
        f"Carapace Up: {analysis.get('carapace_up', False)}\n"
        f"Entrapment: {analysis.get('entrapment', False)}\n"
        f"Notes: {analysis.get('additional_notes', 'N/A')}"
    )

def schedule_loop():
    """
    Main loop for the scheduler.
    """
    logger.info(f"Scheduler started. Interval: {Config.INTERVAL} minutes.")
    
    while True:
        try:
            logger.info('Starting scheduled check...')
            
            # 1. Capture Image
            if run_capture():
                # Give it a moment to save (though the request should block until done, 
                # file system latency might be a thing)
                time.sleep(2) 
                
                # 2. Find latest image
                if not os.path.exists(Config.HOST_IMAGE_DIR):
                     logger.error(f"Image directory {Config.HOST_IMAGE_DIR} does not exist.")
                     continue

                image_files = [f for f in os.listdir(Config.HOST_IMAGE_DIR) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
                
                if image_files:
                    latest_image = max(
                        [os.path.join(Config.HOST_IMAGE_DIR, f) for f in image_files],
                        key=os.path.getctime
                    )
                    
                    # 3. Analyze Image
                    logger.info(f"Analyzing image: {latest_image}")
                    analysis_result = run_image_analysis(latest_image)
                    logger.info(f"Analysis result: {analysis_result}")

                    # 4. Alert if needed
                    if analysis_result.get("turtle_well_being") == "distressed":
                        logger.warning("Turtle in distress detected!")
                        alert_msg = format_alert_message(analysis_result)
                        send_twilio_notification(alert_msg)
                else:
                    logger.warning("No images found in directory after capture.")
            
        except Exception as e:
            logger.error(f"Unexpected error in scheduler loop: {e}", exc_info=True)
        
        # Wait for next interval
        logger.info(f'Sleeping for {Config.INTERVAL} minutes...')
        time.sleep(Config.INTERVAL * 60)

# --- Routes ---

@app.route('/image-analysis', methods=["GET"])
def api_image_analysis():
    image_path = request.args.get("image_path")
    if not image_path:
        return jsonify({"error": "Missing image_path parameter"}), 400
    
    result = run_image_analysis(image_path)
    return jsonify(result)

@app.route('/start-scheduler', methods=["GET"])
def api_start_scheduler():
    # Note: In a real production app, you'd want to ensure only one thread runs.
    # For this simple script, we assume it's called once or managed externally.
    if any(t.name == "SchedulerThread" for t in threading.enumerate()):
         return jsonify({"status": "already_running"}), 200

    thread = threading.Thread(target=schedule_loop, name="SchedulerThread", daemon=True)
    thread.start()
    return jsonify({"status": "started", "interval_minutes": Config.INTERVAL})

@app.route('/health', methods=["GET"])
def health_check():
    return jsonify({"status": "healthy"}), 200

@app.route('/', methods=["GET"])
def index():
    return 'Scheduler application is running.'

if __name__ == "__main__":
    logger.info("Starting scheduler service...")
    
    # Auto-start scheduler on launch
    scheduler_thread = threading.Thread(target=schedule_loop, name="SchedulerThread", daemon=True)
    scheduler_thread.start()
    
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(host="0.0.0.0", port=5000, debug=debug_mode)