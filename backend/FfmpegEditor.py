import subprocess
import os
import random
from SrtEdit import *

def EditVid(directory=None, music=None, video=None):
    if not directory:
        dir = "frames/03_16_13-42-03"
    else:
        dir = directory
    audio = f"{dir}/story.mp3"
    
    # Use the selected background video if provided, otherwise default to minecraft.mp4
    if video and video != "none":
        rot_roll = f"backend/Resources/Rot/{video}"
    else:
        rot_roll = "backend/Resources/Rot/minecraft.mp4"
        
    srt_file = f"{dir}/story.srt"
    if music and music != "none":
        background_music = f"backend/Resources/Music/{music}"
    else:
        background_music = "backend/Resources/Music/Espresso.mp3"
    
    # Output file path - save in the directory
    output_file = f"{dir}/output.mp4"
    
    #rewrite srt file to ass
    srt_to_ass(srt_file)
    ass_file = f"{dir}/story.ass"
    
    # Set absolute font directory path for the fontconfig
    cwd = os.getcwd()
    font_dir = os.path.join(cwd, "backend/Resources/fonts/static")
    font_file = os.path.join(font_dir, "Montserrat-BlackItalic.ttf")
    
    # Get audio duration using ffprobe
    duration_cmd = f'ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 {audio}'
    duration = float(subprocess.check_output(duration_cmd, shell=True).decode('utf-8').strip())
    
    # Check if there's a custom duration.txt file, and use that instead if available
    duration_file = f"{dir}/duration.txt"
    if os.path.exists(duration_file):
        try:
            with open(duration_file, 'r') as f:
                custom_duration = float(f.read().strip())
                # Only override if it's within a reasonable range (10-60 seconds)
                if 10 <= custom_duration <= 60:
                    print(f"Using custom duration: {custom_duration} seconds")
                    # Set the actual duration to the minimum of audio duration and custom duration
                    duration = min(duration, custom_duration)
                else:
                    print(f"Custom duration {custom_duration} out of range (10-60), using audio duration: {duration} seconds")
        except (ValueError, IOError) as e:
            print(f"Error reading custom duration: {e}, using audio duration: {duration} seconds")
    
    # Cap max duration at 60 seconds
    if duration > 60: 
        duration = 60
    print(f"Final video duration: {duration} seconds")
    
    # Count the number of PNG files in the directory
    number_frames = len([file for file in os.listdir(dir) if file.lower().endswith('.png')])
    
    # Get rot_roll video duration using ffprobe
    rot_roll_duration_cmd = f'ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 {rot_roll}'
    rot_roll_duration = float(subprocess.check_output(rot_roll_duration_cmd, shell=True).decode('utf-8').strip())
    
    # Calculate random start time for rot_roll video
    max_start_time = max(0, rot_roll_duration - duration)
    rot_start = random.uniform(0, max_start_time) if max_start_time > 0 else 0

    # New: Calculate random start time for background music
    bg_duration_cmd = f'ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 {background_music}'
    bg_duration = float(subprocess.check_output(bg_duration_cmd, shell=True).decode('utf-8').strip())
    max_bg_start = max(0, bg_duration - duration)
    bg_start = random.uniform(0, max_bg_start) if max_bg_start > 0 else 0
    print(f"Background music start: {bg_start} seconds")

    duration_each_frame = duration / number_frames
    frame_rate = 1/duration_each_frame
    
    # Get image files
    image_files = get_image_files_from_directory(dir)
    # Sort image files to ensure correct order
    image_files.sort()
    
    # Create a temporary file list for ffmpeg
    temp_file_list = "temp_file_list.txt"
    with open(temp_file_list, 'w') as f:
        for img in image_files:
            f.write(f"file '{img}'\n")
            f.write(f"duration {duration_each_frame}\n")
    
    print(f"Number of images: {len(image_files)}")
    # Print out key values
    print(f"Rot start: {rot_start} seconds")
    print(f"Duration per frame: {duration_each_frame} seconds")
    print(f"Frame rate: {frame_rate} fps")
    print(f"Using font: {font_file}")
    
    # Create a temporary fonts.conf file to help FFmpeg find the font
    fonts_conf = "temp_fonts.conf"
    with open(fonts_conf, 'w') as f:
        f.write(f'''<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "fonts.dtd">
<fontconfig>
    <dir>{font_dir}</dir>
    <match target="pattern">
        <test qual="any" name="family"><string>Montserrat-BlackItalic</string></test>
        <edit name="family" mode="assign" binding="same"><string>Montserrat-BlackItalic</string></edit>
    </match>
</fontconfig>''')
    
    # Set environment variable for fontconfig
    os.environ['FONTCONFIG_FILE'] = os.path.abspath(fonts_conf)
    
    # Fixed command with proper stream indexing and output to the correct directory
    command = (f'ffmpeg -ss {rot_start} -i {rot_roll} '  # Input 0: rot_roll video
               f'-f concat -safe 0 -i {temp_file_list} '  # Input 1: image sequence from file list
               f'-i {audio} '  # Input 2: story audio
               f'-ss {bg_start} -i {background_music} '  # Input 3: background music with random start
               f'-filter_complex "'
               f'[0:v]scale=1080:-2[scaled_video];'  # Scale rot_roll to 1080 width and ensure even height
               f'[1:v]scale=1080:-2[scaled_images];'  # Scale images to 1080 width and ensure even height
               f'[scaled_video][scaled_images]vstack=inputs=2[stacked];'  # Stack them vertically
               f'[stacked]pad=iw:ih+mod(ih\,2):0:0[temp];'  # Pad height to make it even if needed
               f'[temp]ass={ass_file}:fontsdir={font_dir}[v];'  # Apply subtitles with font directory
               f'[3:a]volume=0.3[quietbg];'  # Background music volume
               f'[2:a][quietbg]amix=inputs=2:duration=first[a]" '  # Mix audio
               f'-map "[v]" -map "[a]" -t {duration} {output_file}')
               
    print(command)
    # Execute the command
    result = subprocess.run(command, shell=True)
    
    if result.returncode != 0:
        print(f"Error creating video, ffmpeg returned code {result.returncode}")
        return None
    
    # Clean up temp files
    if os.path.exists(temp_file_list):
        os.remove(temp_file_list)
    if os.path.exists(fonts_conf):
        os.remove(fonts_conf)
    
    print(f"Video created successfully at: {output_file}")
    return output_file

def get_image_files_from_directory(directory):
    image_files = []
    for file_name in os.listdir(directory):
        if file_name.lower().endswith(('.png', '.jpg', '.jpeg')):
            image_files.append(os.path.join(directory, file_name))
    return image_files

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        directory = sys.argv[1]
        music = None if len(sys.argv) <= 2 else sys.argv[2]
        video = None if len(sys.argv) <= 3 else sys.argv[3]
        
        # Don't pass 'none' string values
        if music == 'none':
            music = None
        if video == 'none':
            video = None
            
        output_path = EditVid(directory, music, video)
        if output_path:
            print(output_path)
    else:
        EditVid()



