import os
import threading
import time
import requests
import base64
import json
import logging
import io
from typing import Optional, Dict, Any

from PIL import Image

from flask import Flask, request, jsonify, send_from_directory, abort
from flask_cors import CORS
from functools import wraps
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
CORS(app)

# --- Configuration ---
class Config:
    INTERVAL = int(os.getenv("INTERVAL", 10))
    HOST_IMAGE_DIR = os.getenv("HOST_IMAGE_DIR", "/images")
    OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://host.docker.internal:11434")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma4:e4b")
    CAPTURE_SERVICE_URL = os.getenv("CAPTURE_SERVICE_URL", "http://capture:5000")
    # Seconds to wait for a single frame grab. Low-framerate cameras need longer:
    # ffmpeg must wait for a keyframe, so an 8fps stream can take ~4s vs ~1.5s at 30fps.
    CAPTURE_TIMEOUT = int(os.getenv("CAPTURE_TIMEOUT", 60))
    
    # Twilio
    TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
    TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
    TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
    RECIPIENT_PHONE_NUMBER = os.getenv("RECIPIENT_PHONE_NUMBER")

    # API auth — set API_KEY in your override to secure external-facing endpoints
    API_KEY = os.getenv("API_KEY")

    # TurtleVision push — set both to enable automatic result publishing
    TURTLEVISION_WEBHOOK_URL = os.getenv("TURTLEVISION_WEBHOOK_URL")
    TURTLEVISION_INGEST_KEY = os.getenv("TURTLEVISION_INGEST_KEY")

    @classmethod
    def get_camera_urls(cls):
        urls = []
        i = 1
        while True:
            url = os.getenv(f"CAMERA_URL{i}")
            if url:
                urls.append(url)
                i += 1
            else:
                break
        return urls

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

def run_capture(camera_url: Optional[str] = None) -> Optional[str]:
    """
    Triggers the capture service to take a snapshot.
    Returns the path of the image the capture service wrote, or None on failure.
    """
    logger.debug(f'Triggering camera capture for {camera_url}...')
    target_url = f"{Config.CAPTURE_SERVICE_URL}/capture-now"
    
    params = {"output_dir": Config.HOST_IMAGE_DIR}
    if camera_url:
        params["camera_url"] = camera_url

    try:
        response = requests.post(target_url, json=params, timeout=Config.CAPTURE_TIMEOUT)
        response.raise_for_status()
        image_path = (response.json() or {}).get("image_path")
        logger.info(f"Capture command sent successfully. Image: {image_path}")
        return image_path
    except requests.exceptions.RequestException as e:
        logger.error(f"Error calling capture service: {e}")
        return None
    except ValueError:
        logger.error("Capture service returned a non-JSON response.")
        return None

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

MAX_IMAGE_WIDTH = 1280  # px — resize before pushing to keep payload small

def _encode_image_for_push(image_path: str) -> Optional[str]:
    """
    Resize the image to at most MAX_IMAGE_WIDTH wide and return a base64-encoded JPEG string.
    Returns None if the file can't be read.
    """
    try:
        with Image.open(image_path) as img:
            img = img.convert("RGB")
            if img.width > MAX_IMAGE_WIDTH:
                ratio = MAX_IMAGE_WIDTH / img.width
                img = img.resize((MAX_IMAGE_WIDTH, int(img.height * ratio)), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=82)
            return base64.b64encode(buf.getvalue()).decode("utf-8")
    except Exception as e:
        logger.warning(f"Could not encode image {image_path} for push: {e}")
        return None

def push_to_turtlevision(cameras: list) -> None:
    """
    Push scan results (including resized images) to TurtleVision's ingest endpoint.
    Fires-and-forgets — a failure here never interrupts the scan loop.
    """
    if not Config.TURTLEVISION_WEBHOOK_URL or not Config.TURTLEVISION_INGEST_KEY:
        return

    # Attach encoded images to each camera entry
    cameras_with_images = []
    for cam in cameras:
        entry = dict(cam)
        if cam.get("image_path") and not cam.get("error"):
            encoded = _encode_image_for_push(cam["image_path"])
            if encoded:
                entry["image_data"] = encoded
                entry["image_filename"] = os.path.basename(cam["image_path"])
        cameras_with_images.append(entry)

    payload = {
        "scannedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "cameras": cameras_with_images,
    }
    try:
        response = requests.post(
            Config.TURTLEVISION_WEBHOOK_URL,
            json=payload,
            headers={"X-Ingest-Key": Config.TURTLEVISION_INGEST_KEY},
            timeout=30,
        )
        response.raise_for_status()
        logger.info(f"Pushed scan results to TurtleVision ({response.status_code}).")
    except requests.exceptions.RequestException as e:
        logger.warning(f"Failed to push results to TurtleVision: {e}")

def schedule_loop():
    """
    Main loop for the scheduler.
    """
    logger.info(f"Scheduler started. Interval: {Config.INTERVAL} minutes.")
    
    while True:
        try:
            logger.info('Starting scheduled check...')
            camera_results = []

            camera_urls = Config.get_camera_urls()
            if not camera_urls:
                logger.warning("No camera URLs configured.")

            for i, cam_url in enumerate(camera_urls):
                logger.info(f"Processing camera {i+1}...")

                # 1. Capture Image
                captured_image = run_capture(cam_url)
                if captured_image:
                    # Give it a moment to save
                    time.sleep(2)

                    # 2. Use the exact file the capture service reported
                    if not os.path.exists(Config.HOST_IMAGE_DIR):
                        logger.error(f"Image directory {Config.HOST_IMAGE_DIR} does not exist.")
                        camera_results.append({
                            "camera_index": i + 1, "camera_url": cam_url,
                            "image_path": None, "analysis": {}, "alert_sent": False,
                            "error": f"Image directory {Config.HOST_IMAGE_DIR} not found",
                        })
                        continue

                    if os.path.exists(captured_image):
                        latest_image = captured_image

                        # 3. Analyze Image
                        logger.info(f"Analyzing image: {latest_image}")
                        analysis_result = run_image_analysis(latest_image)
                        logger.info(f"Analysis result: {analysis_result}")

                        # 4. Alert if needed
                        alert_sent = analysis_result.get("turtle_well_being") == "distressed"
                        if alert_sent:
                            logger.warning("Turtle in distress detected!")
                            alert_msg = format_alert_message(analysis_result)
                            send_twilio_notification(alert_msg)

                        camera_results.append({
                            "camera_index": i + 1,
                            "camera_url": cam_url,
                            "image_path": latest_image,
                            "analysis": analysis_result,
                            "alert_sent": alert_sent,
                            "error": None,
                        })
                    else:
                        logger.warning(f"Captured image {captured_image} not found on disk.")
                        camera_results.append({
                            "camera_index": i + 1, "camera_url": cam_url,
                            "image_path": None, "analysis": {}, "alert_sent": False,
                            "error": f"Captured image {captured_image} not found",
                        })
                else:
                    camera_results.append({
                        "camera_index": i + 1, "camera_url": cam_url,
                        "image_path": None, "analysis": {}, "alert_sent": False,
                        "error": "Capture failed",
                    })

            # 5. Push all results to TurtleVision
            if camera_results:
                push_to_turtlevision(camera_results)

        except Exception as e:
            logger.error(f"Unexpected error in scheduler loop: {e}", exc_info=True)
        
        # Wait for next interval
        logger.info(f'Sleeping for {Config.INTERVAL} minutes...')
        time.sleep(Config.INTERVAL * 60)

# --- Auth ---

def require_api_key(f):
    """Decorator that enforces API key auth when API_KEY is configured."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if Config.API_KEY:
            provided = request.headers.get("X-API-Key")
            if provided != Config.API_KEY:
                return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated

# --- Routes ---

@app.route('/scan', methods=["POST"])
@require_api_key
def api_scan():
    """
    On-demand capture + analysis across all configured cameras.
    Returns a list of per-camera results and fires Twilio alerts for any distress detected.

    Response shape:
    {
        "cameras": [
            {
                "camera_index": 1,
                "camera_url": "rtsp://...",
                "image_path": "/images/...",
                "analysis": { ...LLM JSON... },
                "alert_sent": true | false,
                "error": null | "message"
            },
            ...
        ]
    }
    """
    camera_urls = Config.get_camera_urls()
    if not camera_urls:
        return jsonify({"error": "No camera URLs configured"}), 503

    results = []

    for i, cam_url in enumerate(camera_urls):
        entry = {
            "camera_index": i + 1,
            "camera_url": cam_url,
            "image_path": None,
            "analysis": {},
            "alert_sent": False,
            "error": None
        }

        # 1. Capture
        latest_image = run_capture(cam_url)
        if not latest_image:
            entry["error"] = "Capture failed"
            results.append(entry)
            continue

        time.sleep(2)  # allow file system to flush

        # 2. Use the exact file the capture service reported
        if not os.path.exists(Config.HOST_IMAGE_DIR):
            entry["error"] = f"Image directory {Config.HOST_IMAGE_DIR} not found"
            results.append(entry)
            continue

        if not os.path.exists(latest_image):
            entry["error"] = f"Captured image {latest_image} not found"
            results.append(entry)
            continue

        entry["image_path"] = latest_image

        # 3. Analyze
        analysis = run_image_analysis(latest_image)
        entry["analysis"] = analysis

        # 4. Alert if distressed
        if analysis.get("turtle_well_being") == "distressed":
            alert_msg = format_alert_message(analysis)
            send_twilio_notification(alert_msg)
            entry["alert_sent"] = True

        results.append(entry)

    # Push results to TurtleVision (non-blocking)
    push_to_turtlevision(results)

    return jsonify({"cameras": results})

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

@app.route('/images/<path:filename>', methods=["GET"])
@require_api_key
def serve_image(filename: str):
    """
    Serve a captured image by filename from HOST_IMAGE_DIR.
    Used by TurtleVision to display thumbnails alongside scan results.
    Example: GET /images/snapshot_cam1_20260504_120000.jpg
    """
    image_dir = Config.HOST_IMAGE_DIR
    if not image_dir or not os.path.isdir(image_dir):
        abort(404)
    return send_from_directory(image_dir, filename)

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