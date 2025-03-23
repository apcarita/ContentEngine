import os
import random
from datetime import datetime
import pysrt
import time
import sys
import traceback  # Added for better error reporting
import logging
import glob
import subprocess
from PIL import Image
import PIL
from PIL import ExifTags
import math
# Import the FFmpegEditor
from FfmpegEditor import EditVid

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def fetch_audio_and_srt(dir):
        audio_file = None
        srt_file = None
        for file in os.listdir(dir):
            if file.endswith(".mp3") and audio_file is None:
                audio_file = os.path.join(dir, file)
            elif file.endswith(".srt") and srt_file is None:
                srt_file = os.path.join(dir, file)
            if audio_file and srt_file:
                break
        return audio_file, srt_file


if __name__ == "__main__":
    import sys
    import time
    if len(sys.argv) > 1:
        image_folder = sys.argv[1]
        print(f"Received image folder path: {image_folder}", flush=True)
        
        # Check if path is relative and convert to absolute if needed
        if not os.path.isabs(image_folder):
            image_folder = os.path.abspath(image_folder)
            print(f"Converted to absolute path: {image_folder}", flush=True)
        
        # Wait up to 25 seconds for the folder to exist
        timeout = 25
        interval = 1
        waited = 0
        
        while not os.path.isdir(image_folder) and waited < timeout:
            print(f"Waiting for directory to exist: {image_folder}", flush=True)
            time.sleep(interval)
            waited += interval
            
        if not os.path.isdir(image_folder):
            print(f"Error: Directory {image_folder} does not exist after waiting {timeout} seconds.", flush=True)
            sys.exit(1)
        
        # List all files in directory to debug
        print(f"Directory contents: {os.listdir(image_folder)}", flush=True)
        
        # Get image paths
        image_paths = [os.path.join(image_folder, img) for img in os.listdir(image_folder)
                      if img.lower().endswith(('.png'))]
        
        if not image_paths:
            print(f"Warning: No PNG images found in directory {image_folder}", flush=True)
            sys.exit(1)
        
        print(f"Found {len(image_paths)} images in: {image_folder}", flush=True)
    else:
        print("No image folder provided.", flush=True)
        sys.exit(1)

    # Update loader text: signal that video combining is starting.
    print("combining video...", flush=True)
    
    # Get audio and SRT files
    audio_path, srt = fetch_audio_and_srt(image_folder)
    
    if not audio_path:
        print(f"Error: No audio file found in {image_folder}", flush=True)
        sys.exit(1)
        
    if not srt:
        print(f"Error: No SRT file found in {image_folder}", flush=True)
        sys.exit(1)
        
    print(f"Using audio: {audio_path}", flush=True)
    print(f"Using subtitles: {srt}", flush=True)
    
    # Run the FFmpeg approach for video creation
    try:
        print("Creating video with FFmpeg...", flush=True)
        ffmpeg_output_path = os.path.join(image_folder, "ffmpeg_output.mp4")
        ffmpeg_result = EditVid(image_folder, ffmpeg_output_path)
        print(f"FFmpeg video created at: {ffmpeg_result}", flush=True)
    except Exception as e:
        print(f"Error with FFmpeg approach: {str(e)}", flush=True)
        print(traceback.format_exc(), flush=True)
        print("Video creation failed. Exiting.", flush=True)
        sys.exit(1)
    
    print("Video processing complete!", flush=True)

