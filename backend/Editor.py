import os
import random
from datetime import datetime
from moviepy import *
import pysrt


# Take in audio and an array of images (paths) and then stitch them all together to create 1 video
def stitch_and_rot(audio_path, images, output_path, background_music, rot_path, rot_factor=0.5):
    # Stitch part
    images.sort(key=lambda x: int(os.path.splitext(os.path.basename(x))[0].split('_')[-1]))
    audio = AudioFileClip(audio_path)
    if audio.duration >= 59:
        print("WARNING VIDEO IS LONGER THAN 59 SECONDS")
    img_duration = (audio.duration) / len(images)
    clips = [ImageClip(img).with_duration(img_duration) for img in images]
 
    bg_music = AudioFileClip(background_music)
    random_time = random.uniform(0, bg_music.duration - audio.duration)
    bg_music = bg_music.subclipped(random_time, random_time + audio.duration)
    bg_music = bg_music.with_effects([afx.MultiplyVolume(0.36)])

    final_audio = CompositeAudioClip([audio, bg_music])
    stitched_video = concatenate_videoclips(clips, method="compose").with_audio(final_audio)
    
    # Rot part
    duration = stitched_video.duration

    start_point = random.randint(1, 480)
    minecraft_clip = VideoFileClip(rot_path).subclipped(start_point, start_point + duration)
    target_height = 1920
    target_width = 1080
    minecraft_clip = minecraft_clip.resized(height=target_height * rot_factor)
    minecraft_clip = minecraft_clip.cropped(x_center=minecraft_clip.w/2, width=target_width)
    
    stitched_video = stitched_video.resized(width=target_width)
    mch_clip_height = minecraft_clip.h
    new_height = target_height - mch_clip_height
    stitched_video = stitched_video.cropped(x_center=stitched_video.w/2, y_center=new_height/2, width=target_width, height=new_height)
    
    final_clip = clips_array([[stitched_video], [minecraft_clip]])
    final_clip.write_videofile(output_path, codec='hevc_videotoolbox', fps=24, remove_temp=True, threads=12)
    final_clip.close()  # Added: release resources
    
    return output_path

# Take in video, and SRT then save a video with subtitels added to outputpath
def addSubtitles(video_path, srt_path, output_path, max_chars_per_line):
    video = VideoFileClip(video_path)
    subtitles = pysrt.open(srt_path)
    subtitle_clips = []

    line = ""
    last_end_time = 0
    char_count = 0
    for subtitle in subtitles:
        start_time = subtitle.start.hours * 3600 + subtitle.start.minutes * 60 + subtitle.start.seconds + subtitle.start.milliseconds / 1000
        end_time = subtitle.end.hours * 3600 + subtitle.end.minutes * 60 + subtitle.end.seconds + subtitle.end.milliseconds / 1000

        char_count += len(subtitle.text)

        if(char_count < 19):
            line = line + " " + subtitle.text
            char_count += len(subtitle.text)
        else:
            line = line + "\n" + subtitle.text
            char_count = len(subtitle.text)
            
        if len(line) > max_chars_per_line or line == "":
            line = "\"" + subtitle.text
        
        if(len(line) > 3):
            add = "\""
        else: add = ""

        #font = 'October-Condensed-Devanagari-Heavy'
        #font = 'Big-Caslon-Medium' Old Font
        font = 'Montserrat-Black-Italic'
        fontSize = 100
        txtCol = '#dbaf00'
        stroke_color = 'Black'  # Define stroke color
        stroke_width = 10        # Define stroke width (adjust as needed)


        next_start_time = subtitles[subtitles.index(subtitle) + 1].start.hours * 3600 + subtitles[subtitles.index(subtitle) + 1].start.minutes * 60 + subtitles[subtitles.index(subtitle) + 1].start.seconds + subtitles[subtitles.index(subtitle) + 1].start.milliseconds / 1000 if subtitles.index(subtitle) + 1 < len(subtitles) else video.duration
        text_clip_stroke = TextClip(line + add, 
                             fontsize=fontSize, 
                             font=font, color=txtCol, 
                             bg_color='none', size=(video.size[0]*11/12, video.size[1]/2), 
                             stroke_color=stroke_color,
                             stroke_width=stroke_width,
                             #method='caption', 
                             align='north')
        text_clip_stroke = text_clip_stroke.set_start(start_time).set_duration(next_start_time - start_time)
        text_clip = TextClip(line + add, 
                             fontsize=fontSize,
                             font=font, color=txtCol, 
                             bg_color='none', size=(video.size[0]*11/12, video.size[1]/2), 
                             #method='caption', 
                             align='north')
        text_clip = text_clip.set_start(start_time).set_duration(next_start_time - start_time)

        #full_text_clip = CompositeVideoClip([text_clip_stroke, text_clip])

        print(f"adding subtitle {line} {last_end_time} to {next_start_time}")
        last_end_time = end_time
        text_clip = text_clip.set_position(('center', 'center'))
        text_clip_stroke = text_clip_stroke.set_position(('center', 'center'))

        subtitle_clips.append(text_clip_stroke)
        subtitle_clips.append(text_clip)

    final_video = CompositeVideoClip([video] + subtitle_clips)
    final_video.write_videofile(output_path, codec='hevc_videotoolbox', remove_temp=True, fps = 24, threads=12)
    final_video.close()  # Added: release resources
    
    return output_path

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
        # Wait up to 10 seconds for the folder to exist
        timeout = 25
        interval = 1
        waited = 0
        while not os.path.isdir(image_folder) and waited < timeout:
            time.sleep(interval)
            waited += interval
        if not os.path.isdir(image_folder):
            print(f"Error: Directory {image_folder} does not exist.")
            sys.exit(1)
        image_paths = [os.path.join(image_folder, img) for img in os.listdir(image_folder)
                       if img.lower().endswith(('.png'))]
        print(f"Using images from: {image_folder}", flush=True)
    else:
        print("No image folder provided.", flush=True)
        sys.exit(1)

    # Update loader text: signal that video combining is starting.
    print("combining video...", flush=True)
    
    audio_path, srt = fetch_audio_and_srt(image_folder)              # update path as needed
    background_music = "backend/Music/Espresso.mp3.mp3"   # update path as needed
    output_path = "combined_output.mp4"
    rot_path = "backend/Rot/minecraft.mp4"
    number_of_lines = 5                   # adjust as needed
    pause_length = 2                      # adjust as needed
    stitched_video_path = stitch_and_rot(audio_path, image_paths, output_path, background_music, rot_path)
    print(f"Created combined video: {stitched_video_path}", flush=True)

    video_path = "trimmed_rotTest.mp4"
    srt_path = os.path.join(image_folder, "story.srt")
    output_subtitled = "test_subtitled.mp4"
    
    # Add subtitles
    addSubtitles(video_path, srt_path, output_subtitled, max_chars_per_line=40)
    print(f"Created test video with subtitles: {output_subtitled}", flush=True)

