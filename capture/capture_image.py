import os
import datetime
import logging
import ffmpeg
from flask import Flask, jsonify, request

# Flask app setup
app = Flask(__name__)
# Create a console handler
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)

# Now load environment variables
DEFAULT_CAMERA_URL = os.getenv('CAMERA_URL1')

def image_capture(output_dir='/images', camera_url=None):
    # Determine which camera URL to use
    target_camera_url = camera_url if camera_url else DEFAULT_CAMERA_URL

    if not target_camera_url:
        app.logger.error('No camera URL provided and CAMERA_URL1 env var not set')
        return False

    # Make sure output directory exists
    if not output_dir or not os.path.exists(output_dir):
        app.logger.error('Output directory does not exist or is not set')
        return

    # Timestamped filename and output path
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    output_path = os.path.join(output_dir, f'tr_{timestamp}.jpg')

    app.logger.debug(f'Capturing from: {target_camera_url}')
    app.logger.debug(f'Saving to: {output_path}')

    try:
        (
            ffmpeg
            .input(
                target_camera_url, 
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
        return True
    except ffmpeg.Error as e:
        app.logger.error("FFmpeg error occurred:")
        app.logger.error(e.stderr.decode())
        return False

@app.route('/capture-now', methods=["GET", "POST"])
def capture_now():
    output_dir = '/images'
    camera_url = None

    if request.method == 'POST':
        data = request.get_json()
        if data:
            output_dir = data.get('output_dir', '/images')
            camera_url = data.get('camera_url')
    else:
        output_dir = request.args.get('output_dir', '/images')
        camera_url = request.args.get('camera_url')

    success = image_capture(output_dir, camera_url)
    if success:
        return jsonify({"status": "success", "message": "Image saved to output directory"}), 200
    else:
        return jsonify({"status": "error", "message": "Failed to capture image"}), 500

@app.route('/', methods=["GET"])
def load():
    return 'Capture application is running. Use /capture-now to capture an image.'

if __name__ == "__main__":
    app.logger.info("Starting capture service...")
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(host="0.0.0.0", port=5000, debug=debug_mode)