import sys
from google import genai
import dotenv
import os
from together import Together
import base64
import requests
import random
import concurrent.futures
from datetime import datetime
from google.cloud import texttospeech
import assemblyai as aai
from moviepy import (AudioFileClip, ImageClip, concatenate_videoclips,
                            CompositeAudioClip, VideoFileClip, clips_array, CompositeVideoClip, TextClip)

def get_image_promt(story):
    story = story.upper()
    print(f"Processing story: {story}", flush=True)
    dotenv.load_dotenv()

    prompt_text = f"""
   Create a concise image generation prompt (around 300-400 characters) based on the following video script text. The prompt should visualize the essence of the text for image generation purposes.

Think visually and focus on clear representation. Consider:

* **Visual Keywords:** Extract the key nouns, verbs, and adjectives from the script text that are visually representable.  Focus on the core subjects, actions, and descriptive elements. Avoid text overlays, it is ok to have text in the image, just not as an overlay.
* **Story Elements:** Identify the main subject or event being described in the text and ensure the image prompt captures this central theme.  The image should visually summarize the text's narrative or message.
* **Clear and Understandable Imagery:**  The image prompt should aim for imagery that is easily understood and directly relates to the text. Avoid overly abstract or obscure concepts unless they are explicitly present in the script.
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
    client = texttospeech.TextToSpeechClient()

    input_text = texttospeech.SynthesisInput(text=input_text)

    # Note: the voice can also be specified by name.
    # Names of voices can be retrieved with client.list_voices().
    voice = texttospeech.VoiceSelectionParams(
        language_code="en-US",
        #name="en-US-Journey-F",
        name='en-US-Wavenet-A'
    )

    audio_config = texttospeech.AudioConfig(
     audio_encoding=texttospeech.AudioEncoding.LINEAR16,
     speaking_rate=1.3
    )

    response = client.synthesize_speech(
        request={"input": input_text, "voice": voice, "audio_config": audio_config}
    )

    with open(output_path, "wb") as out:
        out.write(response.audio_content)
        print(f'{output_path}')
    return output_path

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
    if len(sys.argv) > 1:
        story = sys.argv[1]
        image_promt = get_image_promt(story)
        
        base_dir = "frames"
        # Use hyphens instead of colons to avoid invalid filename characters
        current_time = datetime.now().strftime("%m_%d_%H-%M-%S")
       #directory = os.path.join(base_dir, current_time)
       # os.makedirs(directory, exist_ok=True)

        # Generate images synchronously and wait for completion
       # directory = gen_art(image_promt, directory)

        # Generate audio synchronously
        #audio_file = cheapSpeak(story, f"{directory}/story.mp3")

        # Transcribe audio synchronously
       # srt_file = transcribe(audio_file, f"{directory}/story.srt")


        time.sleep(5)
        directory = 'frames/02_24_13-17-28'



        while not os.path.exists(directory):
            time.sleep(0.5)


        print(f"Processing complete. Output directory: {directory}")
        print(directory)

            
    else:
        print("ERROR No story provided.")

