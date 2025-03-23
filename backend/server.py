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
import uuid
import json
from datetime import datetime

app = Flask(__name__)
# Update CORS to be more permissive - allow requests from any localhost port
CORS(app, resources={r"/*": {"origins": ["http://localhost:3000", "http://localhost:*", "http://127.0.0.1:*"]}})

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
dotenv.load_dotenv()

# In-memory store for jobs (in production, use a database)
jobs = {}

# Standard API response structure
def api_response(success, data=None, message=None, error=None, status_code=200):
    response = {
        "success": success,
        "timestamp": datetime.now().isoformat(),
    }
    
    if data is not None:
        response["data"] = data
    if message is not None:
        response["message"] = message
    if error is not None:
        response["error"] = error
        
    return jsonify(response), status_code

# API Resources
@app.route('/api/v1/stories', methods=['POST'])
def create_story():
    """Create a new story and start processing"""
    data = request.get_json()
    story_text = data.get('text', '')
    
    if not story_text:
        return api_response(False, error="Story text is required", status_code=400)
    
    try:
        # Generate a unique job ID
        job_id = str(uuid.uuid4())
        
        # Store job details
        jobs[job_id] = {
            "id": job_id,
            "story": story_text,
            "status": "processing",
            "created_at": datetime.now().isoformat(),
            "rot_output": None,
            "images_status": "pending",
            "video_status": "pending",
        }
        
        # Run RotPrompt.py and capture its output
        script_path = os.path.join(os.path.dirname(__file__), 'RotPrompt.py')
        result_rot = subprocess.run(['python', script_path, story_text], capture_output=True, text=True)
        
        if result_rot.stderr:
            logger.error(f"RotPrompt error: {result_rot.stderr}")
            jobs[job_id]["status"] = "failed"
            jobs[job_id]["error"] = result_rot.stderr
            return api_response(False, error=result_rot.stderr, status_code=500)
        
        rot_output = result_rot.stdout.strip()
        logger.debug(f"RotPrompt output: {rot_output}")
        
        # Update job with rot output
        jobs[job_id]["rot_output"] = rot_output
        jobs[job_id]["status"] = "processing_images"
        jobs[job_id]["images_status"] = "processing"
        
        # Define a background function to run Images.py and Editor.py
        def run_images_editor(job_id, story_param):
            try:
                images_path = os.path.join(os.path.dirname(__file__), 'Images.py')
                jobs[job_id]["images_status"] = "processing"
                
                # We are now using the processed "brain rot" story for both images and audio generation
                logger.debug(f"Running Images.py with processed 'brain rot' story: {story_param[:30]}...")
                result_images = subprocess.run(['python', images_path, story_param], capture_output=True, text=True)
                
                if result_images.stderr:
                    logger.error(f"Images.py error: {result_images.stderr}")
                    jobs[job_id]["images_status"] = "failed"
                    jobs[job_id]["error"] = result_images.stderr
                    jobs[job_id]["status"] = "failed"
                    return
                
                images_output = result_images.stdout.strip()
                logger.debug(f"Images.py output: {images_output}")
                jobs[job_id]["images_status"] = "completed"
                jobs[job_id]["video_status"] = "processing"
                jobs[job_id]["status"] = "processing_video"  # Update status to reflect video processing
                
                # Store the directory path for later use
                jobs[job_id]["directory"] = images_output
                
                # Ensure the directory exists before proceeding
                if not os.path.isdir(images_output):
                    absolute_path = os.path.abspath(images_output)
                    logger.debug(f"Converting to absolute path: {absolute_path}")
                    if not os.path.isdir(absolute_path):
                        logger.error(f"Directory does not exist: {absolute_path}")
                        jobs[job_id]["video_status"] = "failed"
                        jobs[job_id]["error"] = f"Directory not found: {absolute_path}"
                        jobs[job_id]["status"] = "failed"
                        return
                    else:
                        images_output = absolute_path
                
                # Allow time for file system operations to complete
                time.sleep(2)
                
                editor_path = os.path.join(os.path.dirname(__file__), 'Editor.py')
                logger.debug(f"Running Editor.py with directory: {images_output}")
                
                # Use a timeout for the Editor.py process (5 minutes)
                try:
                    # Run Editor.py with a timeout (300 seconds = 5 minutes)
                    result_editor = subprocess.run(
                        ['python', editor_path, images_output], 
                        capture_output=True, 
                        text=True, 
                        timeout=600  # 10 minute timeout
                    )
                    
                    if result_editor.stderr:
                        logger.error(f"Editor.py error: {result_editor.stderr}")
                        jobs[job_id]["video_status"] = "failed"
                        jobs[job_id]["error"] = result_editor.stderr
                        jobs[job_id]["status"] = "failed"
                    else:
                        editor_output = result_editor.stdout.strip()
                        logger.debug(f"Editor output: {editor_output}")
                        
                        # Look for specific output paths in the output
                        output_path = None
                        for line in editor_output.split('\n'):
                            if "Created video with subtitles" in line:
                                parts = line.split(':')
                                if len(parts) > 1:
                                    output_path = parts[1].strip()
                                    break
                        
                        if not output_path:
                            # If no specific path found, use default pattern
                            output_path = os.path.join(images_output, "test_subtitled.mp4")
                        
                        # Check if the file exists
                        if os.path.exists(output_path):
                            logger.debug(f"Video file found at: {output_path}")
                            jobs[job_id]["video_path"] = output_path
                        else:
                            # Try alternative path
                            alt_path = os.path.join(images_output, "combined_output.mp4")
                            if os.path.exists(alt_path):
                                logger.debug(f"Video file found at alternative path: {alt_path}")
                                jobs[job_id]["video_path"] = alt_path
                            else:
                                logger.error(f"Cannot find video file at {output_path} or {alt_path}")
                                jobs[job_id]["error"] = f"Video file not found at expected locations"
                                jobs[job_id]["status"] = "completed_with_errors"
                                jobs[job_id]["video_status"] = "missing"
                                return
                        
                        jobs[job_id]["video_status"] = "completed"
                        jobs[job_id]["status"] = "completed"
                        
                except subprocess.TimeoutExpired:
                    logger.error("Editor.py process timed out after 10 minutes")
                    jobs[job_id]["video_status"] = "timeout"
                    jobs[job_id]["error"] = "Video processing timed out after 10 minutes"
                    jobs[job_id]["status"] = "failed"
            except Exception as e:
                logger.exception("Processing error")
                jobs[job_id]["status"] = "failed"
                jobs[job_id]["error"] = str(e)
        
        # Start background thread
        thread = threading.Thread(target=run_images_editor, args=(job_id, rot_output))
        thread.start()
        
        # Return the RotPrompt output immediately with job ID
        return api_response(
            True, 
            data={
                "job_id": job_id,
                "rot_output": rot_output,
                "status": jobs[job_id]["status"]
            },
            message="Story processing started - audio will be generated from the 'brain rot' version of the story"
        )
    
    except Exception as e:
        logger.exception("An exception occurred")
        return api_response(False, error=str(e), status_code=500)


@app.route('/api/v1/stories/<job_id>', methods=['GET'])
def get_story_status(job_id):
    """Get the status of a story processing job"""
    if job_id not in jobs:
        return api_response(False, error="Job not found", status_code=404)
    
    job = jobs[job_id]
    return api_response(True, data=job)


@app.route('/api/v1/stories', methods=['GET'])
def list_stories():
    """List all story processing jobs"""
    return api_response(True, data=list(jobs.values()))


@app.route('/api/v1/stories/<job_id>', methods=['DELETE'])
def delete_story(job_id):
    """Delete a story processing job"""
    if job_id not in jobs:
        return api_response(False, error="Job not found", status_code=404)
    
    del jobs[job_id]
    return api_response(True, message="Job deleted successfully")


@app.route('/api/v1/videos/<job_id>', methods=['GET'])
def get_video(job_id):
    """Get the generated video for a story"""
    if job_id not in jobs:
        return api_response(False, error="Job not found", status_code=404)
    
    job = jobs[job_id]
    if job["status"] != "completed" and job["status"] != "completed_with_errors":
        return api_response(False, error="Video not ready yet", status_code=400)
    
    video_path = job.get("video_path")
    if not video_path or not os.path.exists(video_path):
        # Try to construct the path from the directory
        directory = job.get("directory")
        if directory:
            # Only look for FFmpeg output file
            ffmpeg_path = os.path.join(directory, "ffmpeg_output.mp4")
            if os.path.exists(ffmpeg_path):
                logger.debug(f"Found FFmpeg video file at: {ffmpeg_path}")
                video_path = ffmpeg_path
                # Update job record with the actual path used
                job["video_path"] = video_path
    
    if video_path and os.path.exists(video_path):
        logger.debug(f"Sending video file: {video_path}")
        return send_file(video_path, mimetype='video/mp4')
    else:
        # If no specific path found, try looking in the current directory
        current_dir_path = os.path.join(os.getcwd(), "ffmpeg_output.mp4")
        if os.path.exists(current_dir_path):
            logger.debug(f"Found video file in current directory: {current_dir_path}")
            return send_file(current_dir_path, mimetype='video/mp4')
        
        # Try looking in the job directory again with broader search
        directory = job.get("directory")
        if directory:
            # Look for any .mp4 file in the directory
            mp4_files = [f for f in os.listdir(directory) if f.lower().endswith('.mp4')]
            if mp4_files:
                # Use the first found mp4 file
                video_path = os.path.join(directory, mp4_files[0])
                logger.debug(f"Found alternative mp4 file: {video_path}")
                return send_file(video_path, mimetype='video/mp4')
        
        # If all fails, return error
        logger.error(f"Video file not found. Tried path: {video_path}")
        return api_response(False, error=f"Video file not found. Please check server logs.", status_code=404)


# For backward compatibility
@app.route('/run-script', methods=['POST'])
def run_script():
    """Legacy endpoint for backward compatibility"""
    data = request.get_json()
    story = data.get('story', '')
    
    # Create a new request object with the expected format
    request_data = {'text': story}
    
    # Use the new API endpoint
    response = create_story()
    return response


@app.route('/check-status', methods=['GET'])
def check_status():
    """Legacy endpoint for backward compatibility"""
    try:
        # Check if Images.py is running
        images_running = False
        for proc in psutil.process_iter(['name', 'cmdline']):
            if proc.info['cmdline'] and 'Images.py' in ' '.join(proc.info['cmdline']):
                images_running = True
                break
        
        return jsonify({
            'images_running': images_running
        })
    except Exception as e:
        logger.exception("Error checking status")
        return api_response(False, error=str(e), status_code=500)


# Serve frontend static files
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
