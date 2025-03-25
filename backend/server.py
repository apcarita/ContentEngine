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

# Helper function to count images in a directory
def count_images_in_directory(directory_path):
    if not directory_path or not os.path.isdir(directory_path):
        return 0
    
    image_count = 0
    for file in os.listdir(directory_path):
        if file.lower().endswith(('.png', '.jpg', '.jpeg')):
            image_count += 1
    
    return image_count

# API Resources
@app.route('/api/v1/stories', methods=['POST'])
def create_story():
    """Create a new story and start processing"""
    data = request.get_json()
    story_text = data.get('text', '')
    
    # Get duration from the request, default to 30 seconds
    duration = data.get('duration', 30)
    try:
        duration = int(duration)
        # Ensure duration is within allowed range
        if duration < 10:
            duration = 10
        elif duration > 60:
            duration = 60
    except (TypeError, ValueError):
        duration = 30  # Default if invalid
    
    # Get style from the request, default to brain-rot
    style = data.get('style', 'brain-rot')
    # Validate style
    valid_styles = ['brain-rot', 'educational', 'scary']
    if style not in valid_styles:
        style = 'brain-rot'  # Default to brain-rot if invalid
        
    logger.debug(f"Received story request with duration: {duration}s and style: {style}")
    
    if not story_text:
        return api_response(False, error="Story text is required", status_code=400)
    
    try:
        # Generate a unique job ID
        job_id = str(uuid.uuid4())
        
        # Store job details
        jobs[job_id] = {
            "id": job_id,
            "story": story_text,
            "duration": duration,  # Store duration in job details
            "style": style,        # Store style in job details
            "status": "processing",
            "created_at": datetime.now().isoformat(),
            "rot_output": None,
            "images_status": "pending",
            "video_status": "pending",
            "image_count": 0,  # Initialize image count
            "total_images_expected": 0,  # Will be updated when we know how many to expect
            "music": data.get('music', None),  # Store selected music
            "video": data.get('video', None)   # Store selected video
        }
        
        # Run RotPrompt.py and capture its output
        script_path = os.path.join(os.path.dirname(__file__), 'RotPrompt.py')
        result_rot = subprocess.run(['python', script_path, story_text, str(duration), style], capture_output=True, text=True)
        
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
        def run_images_editor(job_id, story_param, duration):
            try:
                images_path = os.path.join(os.path.dirname(__file__), 'Images.py')
                jobs[job_id]["images_status"] = "processing"
                
                # Pass the duration parameter to Images.py
                logger.debug(f"Running Images.py with processed '{style}' story and duration: {duration}s")
                result_images = subprocess.run(
                    ['python', images_path, story_param, str(duration)], 
                    capture_output=True, 
                    text=True
                )
                
                if result_images.stderr:
                    logger.error(f"Images.py error: {result_images.stderr}")
                    jobs[job_id]["images_status"] = "failed"
                    jobs[job_id]["error"] = result_images.stderr
                    jobs[job_id]["status"] = "failed"
                    return
                
                # Get the last line which should contain only the directory path
                images_output = result_images.stdout.strip().split('\n')[-1]
                logger.debug(f"Images.py output directory: {images_output}")
                
                # Verify this is a valid directory path, not the full stdout which may contain debugging info
                if not os.path.isdir(images_output) and "Processing story:" in images_output:
                    # Extract the actual directory path from the full output
                    output_lines = result_images.stdout.strip().split('\n')
                    # Find the line that represents a valid directory path
                    for line in reversed(output_lines):
                        if os.path.isdir(line.strip()):
                            images_output = line.strip()
                            logger.debug(f"Found valid directory path: {images_output}")
                            break
                        elif line.strip().startswith("frames/"):
                            potential_path = os.path.abspath(line.strip())
                            if os.path.isdir(potential_path):
                                images_output = potential_path
                                logger.debug(f"Found frames directory: {images_output}")
                                break
                
                # Final check to ensure we have a valid directory
                if not os.path.isdir(images_output):
                    logger.error(f"Directory not found in Images.py output: {images_output}")
                    logger.error(f"Full output: {result_images.stdout}")
                    # Look for any frames directory in the output
                    for line in result_images.stdout.split('\n'):
                        if "frames/" in line:
                            potential_dir = line.strip()
                            logger.debug(f"Trying potential directory: {potential_dir}")
                            if os.path.isdir(potential_dir):
                                images_output = potential_dir
                                logger.debug(f"Using directory: {images_output}")
                                break
                
                # Count final images in the directory
                image_count = count_images_in_directory(images_output)
                jobs[job_id]["image_count"] = image_count
                jobs[job_id]["total_images_expected"] = image_count  # Now we know how many to expect
                logger.debug(f"Final image count: {image_count} images in {images_output}")
                
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
                        logger.debug(f"Using absolute path for processing: {absolute_path}")
                        images_output = absolute_path
                
                # Allow time for file system operations to complete
                time.sleep(2)
                
                editor_path = os.path.join(os.path.dirname(__file__), 'FfmpegEditor.py')
                logger.debug(f"Running FfmpegEditor.py with directory: {images_output}")
                
                # Assume success until proven otherwise
                editor_success = False
                
                # Use a timeout for the Editor.py process
                try:
                    # Run FfmpegEditor.py with a timeout and pass music and video parameters
                    result_editor = subprocess.run(
                        [
                            'python', 
                            editor_path, 
                            images_output,
                            jobs[job_id].get('music', 'none'),  # Pass music parameter
                            jobs[job_id].get('video', 'none')   # Pass video parameter
                        ], 
                        capture_output=True, 
                        text=True, 
                        timeout=200  # 10 minute timeout
                    )
                    
                    # Even if stderr is not empty, we may still have a successful video output
                    # Log errors but continue checking for the output file
                    if result_editor.stderr:
                        logger.error(f"FfmpegEditor.py error (might be non-fatal): {result_editor.stderr}")
                    
                    editor_output = result_editor.stdout.strip()
                    logger.debug(f"FfmpegEditor output: {editor_output}")
                    
                    # Parse the FfmpegEditor output to find the video path from the last line
                    output_lines = editor_output.split('\n')
                    # Look for the last line which should contain the final output path
                    output_path = None
                    
                    # Check for the output file directly first - this is the most reliable method
                    expected_path = os.path.join(images_output, "output.mp4")
                    if os.path.exists(expected_path):
                        output_path = expected_path
                        logger.debug(f"Found video at expected path: {output_path}")
                        editor_success = True
                    else:
                        # Parse the output for path information
                        for line in reversed(output_lines):
                            line = line.strip()
                            if line and "Video created successfully at:" in line:
                                # Extract path after the colon and any spaces
                                path_part = line.split("Video created successfully at:")[-1].strip()
                                if os.path.exists(path_part) and path_part.endswith(".mp4"):
                                    output_path = path_part
                                    logger.debug(f"Found output path from success message: {output_path}")
                                    editor_success = True
                                    break
                            elif line and os.path.exists(line) and line.endswith(".mp4"):
                                output_path = line
                                logger.debug(f"Found output path from raw output: {output_path}")
                                editor_success = True
                                break
                        
                        # If still no path, check for expected output file in the directory
                        if not output_path:
                            # Check common output paths
                            potential_paths = [
                                os.path.join(images_output, "test_subtitled.mp4"),
                                os.path.join(images_output, "combined_output.mp4"),
                                os.path.join(images_output, "ffmpeg_output.mp4"),
                                os.path.join(os.getcwd(), "combined_output.mp4"),
                                os.path.join(os.getcwd(), "output.mp4")
                            ]
                            
                            for path in potential_paths:
                                if os.path.exists(path):
                                    output_path = path
                                    logger.debug(f"Found video at standard path: {output_path}")
                                    editor_success = True
                                    break
                        
                        # Final direct directory scan for any MP4 file
                        if not output_path and os.path.exists(images_output):
                            mp4_files = [f for f in os.listdir(images_output) if f.lower().endswith('.mp4')]
                            if mp4_files:
                                # Sort by modification time to get the newest one
                                mp4_files.sort(key=lambda f: os.path.getmtime(os.path.join(images_output, f)), reverse=True)
                                output_path = os.path.join(images_output, mp4_files[0])
                                logger.debug(f"Found video by directory scan: {output_path}")
                                editor_success = True
                    
                    if output_path:
                        jobs[job_id]["video_path"] = output_path
                        jobs[job_id]["video_status"] = "completed"
                        jobs[job_id]["status"] = "completed"
                        logger.info(f"Video processing completed successfully: {output_path}")
                    else:
                        logger.error("Cannot find video output file in any expected location")
                        jobs[job_id]["video_status"] = "missing"
                        jobs[job_id]["error"] = "Video file not found at expected locations"
                        jobs[job_id]["status"] = "completed_with_errors"
                    
                except subprocess.TimeoutExpired:
                    logger.error("FfmpegEditor.py process timed out after 10 minutes")
                    jobs[job_id]["video_status"] = "timeout"
                    jobs[job_id]["error"] = "Video processing timed out after 10 minutes"
                    jobs[job_id]["status"] = "failed"
                    
                    # Even after timeout, check if video was created
                    expected_path = os.path.join(images_output, "output.mp4")
                    if os.path.exists(expected_path):
                        jobs[job_id]["video_path"] = expected_path
                        jobs[job_id]["status"] = "completed_with_errors"
                        logger.info(f"Found video despite timeout: {expected_path}")
                        
            except Exception as e:
                logger.exception("Processing error")
                jobs[job_id]["status"] = "failed"
                jobs[job_id]["error"] = str(e)
                
                # Final attempt to find a video file even after an exception
                try:
                    directory = jobs[job_id].get("directory")
                    if directory and os.path.exists(directory):
                        expected_path = os.path.join(directory, "output.mp4")
                        if os.path.exists(expected_path):
                            jobs[job_id]["video_path"] = expected_path
                            jobs[job_id]["status"] = "completed_with_errors"
                            logger.info(f"Found video despite processing error: {expected_path}")
                except:
                    pass
        
        # Start background thread with the duration parameter
        thread = threading.Thread(target=run_images_editor, args=(job_id, rot_output, duration))
        thread.start()

        # Start a separate thread to monitor image generation progress
        def monitor_image_progress(job_id):
            # Set directory immediately so we can start counting ASAP
            base_dir = "frames"
            current_time = datetime.now().strftime("%m_%d_%H-%M-%S")
            temp_dir = os.path.join(base_dir, current_time)
            os.makedirs(temp_dir, exist_ok=True)
            jobs[job_id]["directory"] = temp_dir
            
            logger.debug(f"Starting image monitoring for job {job_id} in directory {temp_dir}")
            
            # Initially count images to make sure we're not starting with zero when there might be existing images
            initial_count = count_images_in_directory(temp_dir)
            if initial_count > 0:
                jobs[job_id]["image_count"] = initial_count
                logger.debug(f"Initial image count for job {job_id}: {initial_count} images")
            
            # Monitor image count while images are being generated
            while jobs[job_id].get("images_status") == "processing" or jobs[job_id].get("images_status") == "pending":
                directory = jobs[job_id].get("directory")
                if directory and os.path.isdir(directory):
                    # Count all PNG, JPG, JPEG files in the directory using our helper function
                    current_count = count_images_in_directory(directory)
                    
                    # Only update if count has changed to avoid unnecessary updates
                    if current_count != jobs[job_id].get("image_count", 0):
                        jobs[job_id]["image_count"] = current_count
                        logger.debug(f"Updated image count for job {job_id}: {current_count} images")
                        
                time.sleep(0.5)  # Check frequently (every 0.5 seconds)
                
            # Final check after processing completes
            directory = jobs[job_id].get("directory")
            if directory and os.path.isdir(directory):
                final_count = count_images_in_directory(directory)
                jobs[job_id]["image_count"] = final_count
                logger.debug(f"Final image count for job {job_id}: {final_count} images")
        
        image_monitor_thread = threading.Thread(target=monitor_image_progress, args=(job_id,))
        image_monitor_thread.daemon = True  # Make this a daemon thread so it doesn't block process exit
        image_monitor_thread.start()
        
        # Return the RotPrompt output immediately with job ID
        return api_response(
            True, 
            data={
                "job_id": job_id,
                "rot_output": rot_output,
                "status": jobs[job_id]["status"],
                "duration": duration,  # Return the selected duration
                "style": style,        # Return the selected style
                "image_count": 0  # Initial image count
            },
            message=f"Story processing started - audio will be generated from the '{style}' version of the story"
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
    
    # Check the current image count in the directory before sending the status
    directory = job.get("directory")
    if directory and os.path.isdir(directory):
        current_image_count = count_images_in_directory(directory)
        # Only update if count has changed to avoid unnecessary updates
        if current_image_count != job.get("image_count", 0):
            job["image_count"] = current_image_count
            logger.debug(f"Updated image count for job {job_id} in status check: {current_image_count} images")
    
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
            # Check all mp4 files in the directory
            if os.path.exists(directory):
                mp4_files = [f for f in os.listdir(directory) if f.endswith('.mp4')]
                if mp4_files:
                    # Sort by modification time to get the newest one
                    mp4_files.sort(key=lambda f: os.path.getmtime(os.path.join(directory, f)), reverse=True)
                    video_path = os.path.join(directory, mp4_files[0])
                    logger.debug(f"Using newest video file: {video_path}")
                    job["video_path"] = video_path
    
    if video_path and os.path.exists(video_path):
        logger.debug(f"Sending video file: {video_path}")
        return send_file(video_path, mimetype='video/mp4')
    else:
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


# New endpoint to list available background music files
@app.route('/api/v1/music', methods=['GET'])
def list_music():
    try:
        music_dir = os.path.join(os.path.dirname(__file__), 'Resources', 'Music')
        music_files = [f for f in os.listdir(music_dir) if f.lower().endswith('.mp3')]
        return api_response(True, data=music_files)
    except Exception as e:
        return api_response(False, error=str(e), status_code=500)

# New endpoint to list available background video files
@app.route('/api/v1/videos/backgrounds', methods=['GET'])
def list_background_videos():
    try:
        video_dir = os.path.join(os.path.dirname(__file__), 'Resources', 'Rot')
        video_files = [f for f in os.listdir(video_dir) if f.lower().endswith(('.mp4', '.mov'))]
        return api_response(True, data=video_files)
    except Exception as e:
        return api_response(False, error=str(e), status_code=500)

if __name__ == '__main__':
    dotenv.load_dotenv()  # ensure env is loaded
    app.run(debug=True, port=8000, use_reloader=True)
