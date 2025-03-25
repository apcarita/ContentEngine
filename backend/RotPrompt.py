import sys
from google import genai
import dotenv
import os

if __name__ == "__main__":
    style = "none"
    if len(sys.argv) > 1:
        story = sys.argv[1]
        dotenv.load_dotenv()

        # Get duration from arguments if provided, default to 30 seconds
        duration = 30
        if len(sys.argv) > 2:
            try:
                duration = int(sys.argv[2])
            except ValueError:
                print("Invalid duration value, using default of 30 seconds")
                
        # Get style if provided, default to brain-rot
        if len(sys.argv) > 3:
            style = sys.argv[3]

        script_dir = os.path.dirname(os.path.abspath(__file__))
        dict_path = os.path.join(script_dir, 'Dictionary.txt')
        with open(dict_path, 'r') as file:
            dictionary_words = file.read()

        rot = f"""
         I want you to act as a video script writer who specializes in "brain rot" style content.

        **Task:** Create a short video script for a {duration}-second video from the text I will provide.

        **Video Script Style:**
        * **Brain Rot:**  Heavily incorporate modern internet memes and slang to the point of being almost nonsensical and hyper-stimulating, but still somewhat understandable and funny.
        * **Educational:**  Convey a simple educational message or fact (even loosely).
        * **Optimistic:** The tone should be positive and upbeat.
        * **Story-Driven:**  Tell a very brief story or convey a simple message with a narrative arc (beginning, middle, end - even if very loose).
        * **Dictionary Words:**  Use words from the provided dictionary whenever contextually possible, especially "af/asf" (or "asf").
        brain rot style, no emojis, educational, optimistic, story-driven, using dictionary words, especially \"af/asf\"). Something that can be spoken in {duration} seconds. Return just the story- not title or lables.

        **Dictionary of Words:**
            {dictionary_words}
        """
        
        educational = f"""
        I want you to act as a video script writer who specializes in educational content.

        **Task:** Create a short video script for a {duration}-second educational video from the text I will provide.

        **Video Script Style:**
        * **Educational:** Clearly explain concepts in a straightforward, informative way.
        * **Engaging:** Use an engaging, enthusiastic tone to capture interest.
        * **Clear:** Use simple language that's easy to understand.
        * **Concise:** Be brief and to the point - this needs to be spoken in {duration} seconds.
        * **Structured:** Present information in a logical flow.
        """
        
        scary = f"""
        I want you to act as a video script writer who specializes in creepy, unsettling content.

        **Task:** Create a short video script for a {duration}-second creepy/scary video from the text I will provide. Keep it PG-13 though.

        **Video Script Style:**
        * **Unsettling:** Create an eerie, uncomfortable atmosphere.
        * **Suspenseful:** Build tension through your word choices and pacing.
        * **Mysterious:** Leave some things unexplained to create unease.
        * **Descriptive:** Use vivid, dark imagery. Nothing to greusome or graphic, should NOT be NSFW.
        * **Concise:** Be brief and impactful - this needs to be spoken in {duration} seconds.
        """
        
        # Default to brain rot style
        chosen_style = rot
        
        # Select style based on input
        if style == "educational":
            chosen_style = educational
        elif style == "scary":
            chosen_style = scary

        prompt_text = f"""
        {chosen_style}

        **Input Text:**
        {story}

        **Output Format is just the script. nothing else. no lables. no titles. just return the script. Should only be words, no instructions about clips or sound effects:**
        """
        client = genai.Client(api_key=os.getenv("GOOGLE_AI"))
        response = client.models.generate_content(
        model="gemini-2.0-flash", contents=prompt_text
        )
        rot_output = response.text
        print(rot_output)
    else:
        print("No story provided.")