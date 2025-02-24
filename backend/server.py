import logging
import os
from flask import Flask, request, jsonify, send_file, send_from_directory
from subprocess import Popen, PIPE
from flask_cors import CORS
import dotenv
import psutil
import time
import subprocess
import threading

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "http://localhost:3000"}})  # Enable CORS for specific origin

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
dotenv.load_dotenv()

@app.route('/run-script', methods=['POST'])
def run_script():
    data = request.get_json()
    story = data.get('story', '')
    logger.debug(f"Received story: {story}")
    try:
        # Run RotPrompt.py and capture its output
        script_path = os.path.join(os.path.dirname(__file__), 'RotPrompt.py')
        result_rot = subprocess.run(['python', script_path, story], capture_output=True, text=True)
        if result_rot.stderr:
            logger.error(f"RotPrompt error: {result_rot.stderr}")
            return jsonify({'error': result_rot.stderr}), 500
        rot_output = result_rot.stdout.strip()
        logger.debug(f"RotPrompt output: {rot_output}")

        # Define a background function to run Images.py and Editor.py
        def run_images_editor(story_param):
            images_path = os.path.join(os.path.dirname(__file__), 'Images.py')
            result_images = subprocess.run(['python', images_path, story_param], capture_output=True, text=True)
            if result_images.stderr:
                logger.error(f"Images.py error: {result_images.stderr}")
                return
            images_output = result_images.stdout.strip()
            
            editor_path = os.path.join(os.path.dirname(__file__), 'Editor.py')
            result_editor = subprocess.run(['python', editor_path, images_output], capture_output=True, text=True)
            if result_editor.stderr:
                logger.error(f"Editor.py error: {result_editor.stderr}")
            else:
                editor_output = result_editor.stdout.strip()
                logger.debug(f"Editor output: {editor_output}")

        # Start background thread
        thread = threading.Thread(target=run_images_editor, args=(story,))
        thread.start()

        # Return the RotPrompt output immediately and indicate that images are being processed
        return jsonify({
            'rot_output': rot_output,
            'status': 'images_started'
        })
    except Exception as e:
        logger.exception("An exception occurred")
        return jsonify({'error': str(e)}), 500

@app.route('/check-status', methods=['GET'])
def check_status():
    try:
        # Check if Images.py is running
        images_running = False
        for proc in psutil.process_iter(['name', 'cmdline']):
            if 'Images.py' in (proc.info['cmdline'] or []):
                images_running = True
                break
        
        return jsonify({
            'images_running': images_running
        })
    except Exception as e:
        logger.exception("Error checking status")
        return jsonify({'error': str(e)}), 500

@app.route('/')
def serve_index():
    # Use absolute path to the frontend folder
    frontend_dir = os.path.join(os.path.dirname(__file__), '..', 'frontend')
    return send_from_directory(frontend_dir, 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    # Use absolute path to the frontend folder
    frontend_dir = os.path.join(os.path.dirname(__file__), '..', 'frontend')
    return send_from_directory(frontend_dir, path)

if __name__ == '__main__':
    dotenv.load_dotenv()  # ensure env is loaded
    app.run(debug=True, port=8000, use_reloader=True)
