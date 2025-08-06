import os
import subprocess
import datetime
import ffmpeg
import os
import logging
from flask import Flask

# Flask app setup
app = Flask(__name__)
# Create a console handler
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)

# Now load environment variables
CAMERA_URL = os.getenv('CAMERA_URL')

if not CAMERA_URL:
    raise EnvironmentError('CAMERA_URL environment variable not set')

def image_capture(output_dir='/images'):
    # Make sure output directory exists
    if not output_dir or not os.path.exists(output_dir):
        app.logger.error('Output directory does not exist or is not set')
        return

    # Timestamped filename and output path
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    output_path = os.path.join(output_dir, f'tr_{timestamp}.jpg')

    app.logger.debug(f'Capturing from: {CAMERA_URL}')
    app.logger.debug(f'Saving to: {output_path}')

    try:
        (
            ffmpeg
            .input(
                CAMERA_URL, 
                rtsp_transport='tcp'
            )  
            .output(
                output_path, 
                vframes=1, 
                format='image2', 
                update=1,
                **{'q:v': 2}
            )
            .run(capture_stdout=True, capture_stderr=True)
        )
        app.logger.debug(f"Image saved to {output_path}")
    except ffmpeg.Error as e:
        app.logger.error("FFmpeg error occurred:")
        app.logger.error(e.stderr.decode())

@app.route('/capture-now', methods=["GET"])
def capture_now():
    image_capture()
    return 'Image saved to output directory.\n'

@app.route('/', methods=["GET"])
# ‘/’ URL is bound with load() function.
def load():
    return 'Capture application is running. Use /capture-now to capture an image.'

if __name__ == "__main__":
    app.logger.info("Starting capture service...")
    # DEBUG: Run capture immediately for testing
    #image_capture()
    # Run the Flask app
    app.run(host="0.0.0.0", port=5000, debug=True)