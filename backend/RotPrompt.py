import sys
from google import genai
import dotenv
import os

if __name__ == "__main__":
    if len(sys.argv) > 1:
        story = sys.argv[1]
        dotenv.load_dotenv()

        script_dir = os.path.dirname(os.path.abspath(__file__))
        dict_path = os.path.join(script_dir, 'Dictionary.txt')
        with open(dict_path, 'r') as file:
            dictionary_words = file.read()

        prompt_text = f"""
    I want you to act as a video script writer who specializes in "brain rot" style content.

    **Task:** Create a short video script (50-80 words) from the text I will provide.

    **Video Script Style:**
    * **Brain Rot:**  Heavily incorporate modern internet memes and slang to the point of being almost nonsensical and hyper-stimulating, but still somewhat understandable and funny.
    * **Educational:**  Convey a simple educational message or fact (even loosely).
    * **Optimistic:** The tone should be positive and upbeat.
    * **Story-Driven:**  Tell a very brief story or convey a simple message with a narrative arc (beginning, middle, end - even if very loose).
    * **Dictionary Words:**  Use words from the provided dictionary whenever contextually possible, especially "af/asf" (or "asf").

    **Dictionary of Words:**
    {dictionary_words}


    **Input Text:**
    {story}


    **Output Format:**
    **Video Script Output (50-80 words, brain rot style, no emojis, educational, optimistic, story-driven, using dictionary words, especially \"af/asf\"). Something that can be spoken in under 60 seconds. Return just the story- not title or lable:**
    """
        client = genai.Client(api_key=os.getenv("GOOGLE_AI"))
        response = client.models.generate_content(
        model="gemini-2.0-flash", contents=prompt_text
        )
        rot_output = response.text
        print(rot_output)
    else:
        print("No story provided.")