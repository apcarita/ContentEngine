import sys
import time
import os
from google import genai
import dotenv
from together import Together
import base64
import requests
import random
import concurrent.futures
from datetime import datetime
from google.cloud import texttospeech
import assemblyai as aai
from moviepy.editor import AudioFileClip, ImageClip, concatenate_videoclips, CompositeAudioClip, VideoFileClip, clips_array, CompositeVideoClip, TextClip
import re
import tempfile
import shutil

def get_image_promt(story, duration=30):
    story = story.upper()
    print(f"Processing story: {story}", flush=True)
    prompt_text = f"""
   Create a concise image generation prompt (around 300-400 characters) based on the following video script text. The prompt should visualize the essence of the text for image generation purposes for a {duration}-second video.

Think visually and focus on clear representation. Consider:

* **Visual Keywords:** Extract the key nouns, verbs, and adjectives from the script text that are visually representable.  Focus on the core subjects, actions, and descriptive elements. Avoid text overlays, it is ok to have text in the image, just not as an overlay.
* **Story Elements:** Identify the main subject or event being described in the text and ensure the image prompt captures this central theme.  The image should visually summarize the text's narrative or message.
* **Clear and Understandable Imagery:**  The image prompt should aim for imagery that is easily understood and directly relates to the text. Avoid overly abstract or obscure concepts unless they are explicitly present in the script.
* **Video Pacing:** Create images that will work well for a {duration}-second video sequence.
* **Concise Language:** Use clear and concise language in the image prompt. Focus on essential details and avoid unnecessary jargon or overly complex descriptions.

**Video Script Text:**
{story}


**Image Prompt (around 300-400 characters):**
"""


    client = genai.Client(api_key=os.getenv("GOOGLE_AI"))
    response = client.models.generate_content(
    model="gemini-2.0-flash", contents=prompt_text
    )
    image_promt = response.text
    print(image_promt, flush=True)
    
    return image_promt

def process_snippet(index, prompt_text, set_seed, client, directory):
    response = client.images.generate(
        prompt=prompt_text,
        model="black-forest-labs/FLUX.1-schnell",
        width=768,
        height=640,
        steps=4,
        n=1,
        seed=set_seed,
    )
    image_url = response.data[0].url
    image_bytes = requests.get(image_url).content
    filename = f'{directory}/fram_{index-3}.png'
    with open(filename, 'wb') as f:
        f.write(image_bytes)
    print(f"Saved {filename}", flush=True)


def gen_art(image_promt, directory):
    
    api_key = os.environ.get("TOGETHER_AI")
    set_seed = random.randint(1, 10000)
    client = Together(api_key=api_key)
    snippets = [image_promt[i:i+17] for i in range(0, len(image_promt), 17)]
    string = ""
    tasks = []
    with concurrent.futures.ThreadPoolExecutor() as executor:
        for index, snippet in enumerate(snippets):
            string += snippet
            print(f"{index} ||| {set_seed} ||| {string}", flush=True)
            if index < 3:
                continue
            tasks.append(executor.submit(process_snippet, index, string, set_seed, client, directory))
        for future in concurrent.futures.as_completed(tasks):
            future.result()
    print("done with images...", flush=True)
    return directory

def testimages():
    image_folder = 'frames/02_24_11-23-56'
    image_paths = [os.path.join(image_folder, img) for img in os.listdir(image_folder) if img.endswith(('.png', '.jpg', '.jpeg'))]
    
    return image_folder

def cheapSpeak(input_text, output_path):
    # Set explicit path to the credentials file
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.abspath("backend/Google.json")
    
    client = texttospeech.TextToSpeechClient()

    # Google TTS has a limit of 5000 bytes per request
    # Split the text into smaller chunks
    def split_text(text, max_length=4000):
        # Split by sentences to keep natural pauses
        sentences = re.split(r'(?<=[.!?])\s+', text)
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            # If adding this sentence would exceed max_length, start a new chunk
            if len(current_chunk) + len(sentence) > max_length:
                if current_chunk:  # Don't add empty chunks
                    chunks.append(current_chunk)
                current_chunk = sentence
            else:
                if current_chunk:
                    current_chunk += " " + sentence
                else:
                    current_chunk = sentence
        
        # Add the last chunk if it's not empty
        if current_chunk:
            chunks.append(current_chunk)
            
        return chunks
    
    # Split the text into chunks
    chunks = split_text(input_text)
    print(f"Split text into {len(chunks)} chunks for TTS processing", flush=True)
    
    # Create temporary directory for audio chunks
    temp_dir = tempfile.mkdtemp()
    
    # Process each chunk and save to temporary files
    temp_files = []
    for i, chunk in enumerate(chunks):
        chunk_file = os.path.join(temp_dir, f"chunk_{i}.wav")
        temp_files.append(chunk_file)
        
        # Process this chunk
        chunk_input = texttospeech.SynthesisInput(text=chunk)
        
        voice = texttospeech.VoiceSelectionParams(
            language_code="en-US",
            name='en-US-Wavenet-A'
        )
        
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,  # Changed to MP3 for direct output
            speaking_rate=1.3
        )
        
        try:
            response = client.synthesize_speech(
                request={"input": chunk_input, "voice": voice, "audio_config": audio_config}
            )
            
            # If this is the first chunk, write directly to output
            if i == 0:
                with open(output_path, "wb") as out:
                    out.write(response.audio_content)
                print(f"Created initial audio file", flush=True)
            else:
                # For subsequent chunks, create temporary files
                with open(chunk_file, "wb") as out:
                    out.write(response.audio_content)
                print(f"Created chunk {i} audio file", flush=True)
        except Exception as e:
            print(f"Error processing chunk {i}: {str(e)}", flush=True)
            # If a chunk fails, continue with the others
            continue
    
    # If we have more than one chunk, concatenate using moviepy
    if len(chunks) > 1:
        try:
            # Use the first file as base
            audio_clips = [AudioFileClip(output_path)]
            
            # Add all other chunks
            for i in range(1, len(chunks)):
                temp_file = temp_files[i-1]  # -1 because we start from index 1
                if os.path.exists(temp_file):
                    audio_clips.append(AudioFileClip(temp_file))
            
            # Concatenate all audio clips
            final_audio = concatenate_audioclips(audio_clips)
            
            # Write to output path
            final_audio.write_audiofile(output_path, fps=44100, nbytes=2, buffersize=2000)
            
            # Close all clips to free resources
            for clip in audio_clips:
                clip.close()
                
        except Exception as e:
            print(f"Error concatenating audio: {str(e)}", flush=True)
            print(f"Using first chunk only for audio", flush=True)
    
    # Clean up temporary files
    shutil.rmtree(temp_dir)
    
    print(f'Created audio file: {output_path}', flush=True)
    return output_path

def concatenate_audioclips(clips):
    """Concatenate audio clips together"""
    durations = [c.duration for c in clips]
    tt = sum(durations)
    
    def make_frame(t):
        d = 0
        for i, clip in enumerate(clips):
            if d <= t < d + durations[i]:
                return clip.make_frame(t - d)
            d += durations[i]
        return 0 * clips[0].make_frame(0)
    
    result = AudioFileClip(make_frame=make_frame, duration=tt)
    result.fps = max([clip.fps for clip in clips if hasattr(clip, 'fps')] or [44100])
    return result

def transcribe(audio_path, srt_output_path):
    aai.settings.api_key = os.getenv('ASSEMBLYAI_API_KEY')
    transcriber = aai.Transcriber()
    transcript = transcriber.transcribe(audio_path)
    words = transcript.words
    
    audio = AudioFileClip(audio_path)

    srt_lines = []
    for i, word in enumerate(words, 1):
        start_time = f"{(word.start) // 3600000:02}:{((word.start) % 3600000) // 60000:02}:{((word.start) % 60000) // 1000:02},{(word.start) % 1000:03}"
        end_time = f"{(word.end) // 3600000:02}:{((word.end) % 3600000) // 60000:02}:{((word.end) % 60000) // 1000:02},{(word.end) % 1000:03}"

        srt_lines.append(f"{i}\n{start_time} --> {end_time}\n{word.text}\n")

    srt_content = "\n".join(srt_lines)
    with open(srt_output_path, "w") as f:
        f.write(srt_content)        
    return srt_output_path

if __name__ == "__main__":
    dotenv.load_dotenv()

    if len(sys.argv) > 1:
        story = sys.argv[1]
        
        # Get duration parameter if provided, default to 30 seconds
        duration = 30
        if len(sys.argv) > 2:
            try:
                duration = int(sys.argv[2])
            except ValueError:
                print("Invalid duration value, using default of 30 seconds")
                
        print(f"Creating video with duration: {duration} seconds")
        
        image_promt = get_image_promt(story, duration)
        
        base_dir = "frames"
        # Use hyphens instead of colons to avoid invalid filename characters
        current_time = datetime.now().strftime("%m_%d_%H-%M-%S")
        directory = os.path.join(base_dir, current_time)
        
        # Ensure the directory exists before generating images
        os.makedirs(directory, exist_ok=True)
        
        # Generate images synchronously and wait for completion
        directory = gen_art(image_promt, directory)

        # Generate audio synchronously
        audio_file = cheapSpeak(story, f"{directory}/story.mp3")

        # Transcribe audio synchronously
        srt_file = transcribe(audio_file, f"{directory}/story.srt")

        # Make sure all files are written to disk before returning
        time.sleep(1)

        # Use absolute path to ensure the directory can be found by Editor.py
        abs_directory = os.path.abspath(directory)
        
        # Save duration to a file in the directory for FfmpegEditor.py to use
        with open(f"{directory}/duration.txt", "w") as f:
            f.write(str(duration))
            
        print(abs_directory)
            
    else:
        print("ERROR No story provided.")

