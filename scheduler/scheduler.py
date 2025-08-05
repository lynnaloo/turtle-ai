import os
import threading
import time
import requests
import base64
import json
import logging
from json_repair import repair_json
from twilio.rest import Client
from flask import request
from flask import jsonify
from flask import Flask
from langchain_ollama import OllamaLLM
from langchain_core.messages import HumanMessage, SystemMessage

# Flask app setup
app = Flask(__name__)
# Create a console handler
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)

# Add the handler to the Flask logger
app.logger.addHandler(ch)
app.logger.setLevel(logging.DEBUG) # Set the logger level as well

# Now load environment variables
INTERVAL = int(os.getenv("INTERVAL", 10))
HOST_IMAGE_DIR = os.getenv("HOST_IMAGE_DIR")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://host.docker.internal:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:27b")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
RECIPIENT_PHONE_NUMBER = os.getenv("RECIPIENT_PHONE_NUMBER")

# Find your Account SID and Auth Token at twilio.com/console
# and set the environment variables. See http://twil.io/secure
account_sid = os.getenv('TWILIO_ACCOUNT_SID')
auth_token = os.getenv('TWILIO_AUTH_TOKEN')

# Create a text prompt to decribe the turtles in an image and to return 
# if any of the turtles seem to be in distress
text_prompt = """
You are an expert in analyzing images of reptiles, specifically turtles.
Your task is to analyze the given image of a turtle habitat and provide detailed information 
about its characteristics and the well-being of the turtles. Identify indicators such as instances of 
carapace-up positioning, entrapment, unusual inactivity, or aggressive interactions.

Response Format: JSON

Fill out the following JSON structure with your analysis:
{
    "turtle_well_being": "good" | "distressed",
    "carapace_up": true | false,
    "entrapment": true | false,
    "unusual_inactivity": true | false,
    "aggressive_interactions": true | false,
    "eggs_present": true | false,
    "additional_notes": "Any other observations or notes about the turtle."
}
"""
llm = OllamaLLM(
    model=OLLAMA_MODEL,
    base_url=OLLAMA_HOST,
    num_ctx=10000,  # Set the context length to 10,000 tokens
)

def run_image_analysis(image_path):
    """
    Analyzes the given image of a turtle and provides detailed information
    about its well-being and characteristics.

    Args:
        image_path (str): The file path to the image to be analyzed.

    Returns:
        dict: A JSON-like dictionary containing the analysis results.
    """
    with open(image_path, 'rb') as test_image:
        image_data = base64.b64encode(test_image.read()).decode('utf-8')
        llm_with_image = llm.bind(images=[image_data])
        return (llm_with_image.invoke(text_prompt))

def run_capture():
    """
    Captures an image from the camera and saves it to the specified directory.

    This function interacts with the camera capture service to take a snapshot
    and store it in the designated output directory.

    Returns:
        None
    """
    app.logger.debug(f'Capturing from camera')
    app.logger.debug(f'Saving to: {HOST_IMAGE_DIR}')
    
    # Call the capture service
    target_url = "http://capture:5000/capture-now"
    try:
        app.logger.info(f"Calling capture image service")
        response = requests.get(target_url, params={"output_dir": HOST_IMAGE_DIR})
        response.raise_for_status()  # Raise an exception for bad status codes
        app.logger.info(f"Capture image service response: {response.text}")
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Error calling camera_capture service: {e}")
    return

def send_twilio_notification(body):
    """
    Sends a notification via Twilio SMS.

    Args:
        body (str): The message to be sent via SMS.

    Returns:
        None
    """

    client = Client(account_sid, auth_token)
    message = client.messages.create(
        from_=TWILIO_PHONE_NUMBER,  # Twilio WhatsApp sandbox number
        body= body,
        to=RECIPIENT_PHONE_NUMBER
    )
    app.logger.info(f'Twilio notification has been sent: {message.sid}')

def schedule_loop():
    """
    Continuously captures images from the camera at specified intervals,
    analyzes the images for turtle well-being, and sends notifications
    if any turtles are found to be in distress.
    """
    while True:
        app.logger.info('Starting first image capture in the scheduler')
        run_capture()
        # get the path for the latest image that was added to HOST_IMAGE_DIR
        image_files = os.listdir(HOST_IMAGE_DIR)
        if not image_files:
            app.logger.error('No images found.')
            continue
        latest_image = max(
            [os.path.join(HOST_IMAGE_DIR, f) for f in image_files],
            key=os.path.getctime
        )
        # run image analysis on the latest image
        app.logger.debug(f'Running image analysis on {latest_image}')

        imageanalysis_result = run_image_analysis(latest_image)
        # print the result of the image analysis
        app.logger.info(imageanalysis_result)

        imageanalysis_result = repair_json(imageanalysis_result)
        # Convert imageanalysis_result to JSON
        imageanalysis_result = json.loads(imageanalysis_result)

        # If the turtle_well_being is distressed, send a notification
        if imageanalysis_result.get("turtle_well_being") == "distressed":
            app.logger.warning("Turtle in distress detected! Sending notification...")
            # send a notification text via Twilio
            send_twilio_notification('A turtle event has been detected at: ' + time.strftime("%Y-%m-%d %H:%M:%S") + '\n' +
                                'Turtle Well Being: ' + imageanalysis_result.get("turtle_well_being", "distressed") + '\n' +
                                'Carapace Up: ' + str(imageanalysis_result.get("carapace_up", False)) + '\n' +
                                'Entrapment: ' + str(imageanalysis_result.get("entrapment", False)) + '\n' +
                                'Unusual Inactivity: ' + str(imageanalysis_result.get("unusual_inactivity", False)) + '\n' +
                                'Aggressive Interactions: ' + str(imageanalysis_result.get("aggressive_interactions", False)) + '\n' +
                                'Eggs Present: ' + str(imageanalysis_result.get("eggs_present", False)) + '\n' +
                                'Additional Notes: ' + imageanalysis_result.get("additional_notes", "No additional notes") + '\n')

        # Wait for the specified interval before the next capture
        app.logger.info(f'Waiting {INTERVAL} minutes for next capture...\n')
        time.sleep(INTERVAL * 60)

@app.route('/image-analysis', methods=["GET"])
def image_analysis():
    image_path = request.args.get("image_path")
    return run_image_analysis(image_path)

@app.route('/start-scheduler', methods=["GET"])
def start_scheduler():
    app.logger.info('Starting scheduler...')
    threading.Thread(target=schedule_loop, daemon=True).start()
    return 'Scheduler started. It will capture images every {} minutes.\n'.format(INTERVAL)

@app.route('/', methods=["GET"])
# ‘/’ URL is bound with load() function.
def load():
    return 'Scheduler application is running.'

if __name__ == "__main__":
    # DEBUG: Run capture immediately for testing
    #run_capture()
    app.logger.info("Starting scheduler service...")
    # Start the scheduler in a separate thread
    threading.Thread(target=schedule_loop, daemon=True).start()
    # Run the Flask app
    app.logger.info("Starting Flask web app...")
    app.run(host="0.0.0.0", port=5000)