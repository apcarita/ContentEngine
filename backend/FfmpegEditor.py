import subprocess
import os
import random
from SrtEdit import *
def EditVid():
    dir = "frames/03_16_13-42-03"
    audio = f"{dir}/story.mp3"
    rot_roll = "backend/Resources/Rot/minecraft.mp4"
    srt_file = f"{dir}/story.srt"
    background_music = "backend/Resources/Music/Espresso.mp3"

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
    if duration > 60: 
        duration = 60
    print(f"Audio duration: {duration} seconds")

    # Count the number of PNG files in the directory
    number_frames = len([file for file in os.listdir(dir) if file.lower().endswith('.png')])

    # Get rot_roll video duration using ffprobe
    rot_roll_duration_cmd = f'ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 {rot_roll}'
    rot_roll_duration = float(subprocess.check_output(rot_roll_duration_cmd, shell=True).decode('utf-8').strip())

    # Calculate random start time
    max_start_time = max(0, rot_roll_duration - duration)
    rot_start = random.uniform(0, max_start_time) if max_start_time > 0 else 0
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
    
    # Fixed command with proper stream indexing
    command = (f'ffmpeg -ss {rot_start} -i {rot_roll} '  # Input 0: rot_roll video
               f'-f concat -safe 0 -i {temp_file_list} '  # Input 1: image sequence from file list
               f'-i {audio} '  # Input 2: story audio
               f'-i {background_music} '  # Input 3: background music
               f'-filter_complex "'
               f'[0:v]scale=1080:-1[scaled_video];'  # Scale rot_roll to 1080 width
               f'[1:v]scale=1080:-1[scaled_images];'  # Scale images to 1080 width
               f'[scaled_video][scaled_images]vstack=inputs=2[temp];'  # Stack them vertically
               f'[temp]ass={ass_file}:fontsdir={font_dir}[v];'  # Apply subtitles with font directory
               f'[3:a]volume=0.3[quietbg];'  # Background music volume
               f'[2:a][quietbg]amix=inputs=2:duration=first[a]" '  # Mix audio
               f'-map "[v]" -map "[a]" -t {duration} output.mp4')
               
    print(command)
    # Execute the command
    subprocess.run(command, shell=True)
    
    # Clean up temp files
    if os.path.exists(temp_file_list):
        os.remove(temp_file_list)
    if os.path.exists(fonts_conf):
        os.remove(fonts_conf)

def get_image_files_from_directory(directory):
    images = [os.path.join(directory, f) for f in os.listdir(directory) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    return images

if __name__ == "__main__":
    EditVid()



