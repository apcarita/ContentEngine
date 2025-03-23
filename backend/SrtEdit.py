#!/usr/bin/env python3
import os
import pysrt
from datetime import timedelta
import re

def timestamp_to_ass(timestamp):
    """Convert SRT timestamp to ASS format (h:mm:ss.cc)"""
    hours = timestamp.hours
    minutes = timestamp.minutes
    seconds = timestamp.seconds
    centiseconds = timestamp.milliseconds // 10
    
    return f"{hours}:{minutes:02d}:{seconds:02d}.{centiseconds:02d}"

def srt_to_ass(srt_path):
    """
    Convert an SRT file with per-word timestamps to an ASS file with TikTok-style animated subtitles.
    Words appear progressively using ASS override tags to control visibility.
    """
    # Get the directory and filename from the path
    directory = os.path.dirname(srt_path)
    filename = os.path.basename(srt_path).rsplit('.', 1)[0]
    ass_path = os.path.join(directory, f"{filename}.ass")
    
    # Get absolute path to the font file
    cwd = os.getcwd()
    font_path = os.path.join(cwd, "backend/Resources/fonts/static/Montserrat-BlackItalic.ttf")
    font_name = "Montserrat-BlackItalic"
    
    # Read the SRT file
    subs = pysrt.open(srt_path)
    
    # Parameters for text wrapping
    max_chars = 30  # Maximum characters in a chunk
    char_wrap = 30  # Characters per line
    
    header = f"""[Script Info]
Title: TikTok Style Subtitles
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: None
PlayResX: 1080
PlayResY: 1920

[Aegisub Project Garbage]
Audio File: ?video
Video File: ?dummy
Video AR Mode: 4
Video AR Value: 1.777778
Video Zoom Percent: 0.500000

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},200,&H0002c2e8,&H000000FF,&H00000000,&H00000000,1,1,0,0,100,100,0,0,1,4,0,5,10,10,200,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    # Collect all the words with their timestamps
    words = []
    for i in range(len(subs)):
        words.append({
            'text': subs[i].text.strip(),
            'start': subs[i].start,
            'end': subs[i].end
        })
    
    # Group words into subtitle chunks that fit within max_chars
    subtitle_chunks = []
    current_chunk = []
    current_length = 0
    
    for word in words:
        # If adding this word would exceed max_chars, start a new chunk
        if current_length + len(word['text']) + (1 if current_length > 0 else 0) > max_chars and current_chunk:
            subtitle_chunks.append(current_chunk)
            current_chunk = []
            current_length = 0
        
        current_chunk.append(word)
        current_length += len(word['text']) + (1 if current_length > 0 else 0)  # +1 for space
    
    # Add the last chunk if it's not empty
    if current_chunk:
        subtitle_chunks.append(current_chunk)
    
    lines = []
    
    # Helper function to calculate visible length (without ASS tags)
    def visible_length(text):
        # Remove all ASS tags (like {\\alpha&HFF&}) for length calculation
        return len(re.sub(r'{\\.*?}', '', text))
    
    # Process each subtitle chunk
    for chunk_idx, chunk in enumerate(subtitle_chunks):
        # Generate the full text for this chunk
        chunk_text = ' '.join(word['text'] for word in chunk)
        
        # Calculate the duration this chunk should be visible
        start_time = chunk[0]['start']
        
        # End time calculation
        if chunk_idx < len(subtitle_chunks) - 1:
            end_time = subtitle_chunks[chunk_idx + 1][0]['start']
        else:
            last_word_end = chunk[-1]['end']
            extended_end = pysrt.SubRipTime(
                hours=last_word_end.hours,
                minutes=last_word_end.minutes,
                seconds=last_word_end.seconds + 2,
                milliseconds=last_word_end.milliseconds
            )
            # Handle overflow
            if extended_end.seconds >= 60:
                extended_end.minutes += extended_end.seconds // 60
                extended_end.seconds = extended_end.seconds % 60
                if extended_end.minutes >= 60:
                    extended_end.hours += extended_end.minutes // 60
                    extended_end.minutes = extended_end.minutes % 60
            
            end_time = extended_end
        
        # Get the complete list of words for this chunk
        chunk_words = [word['text'] for word in chunk]
        
        # Now create a sequence of lines for this chunk, each revealing one more word
        for i in range(len(chunk)):
            # Create full text with visible and transparent words
            complete_text = ""
            for j, word in enumerate(chunk_words):
                if j < i:  # Previous words are visible
                    complete_text += word + " "
                elif j == i:  # Current word is visible
                    complete_text += word + " "
                else:  # Future words are transparent
                    complete_text += f"{{\\alpha&HFF&}}{word}{{\\alpha&H00&}} "
            
            complete_text = complete_text.strip()
            
            # Wrap text into exactly 2 lines
            # First, create a non-styled version to find line breaks correctly
            plain_text = ' '.join(chunk_words)
            
            # Break into words without any styling
            plain_words = plain_text.split()
            
            # Calculate where to break lines
            line1_words = []
            line2_words = []
            current_line_length = 0
            
            for word in plain_words:
                if current_line_length + len(word) + (1 if current_line_length > 0 else 0) <= char_wrap:
                    line1_words.append(word)
                    current_line_length += len(word) + (1 if current_line_length > 0 else 0)
                else:
                    line2_words.append(word)
            
            # If all words fit on one line, move some to the second line for balance
            if not line2_words and len(line1_words) > 1:
                # Move roughly half the words to the second line
                midpoint = len(line1_words) // 2
                line2_words = line1_words[midpoint:]
                line1_words = line1_words[:midpoint]
                
            # Now we know where the line breaks should be, apply this to the styled text
            styled_words = complete_text.split()
            
            # Make sure we have enough styled words (should match plain_words)
            if len(styled_words) == len(plain_words):
                # Build the two lines with proper styling
                line1 = ' '.join(styled_words[:len(line1_words)])
                line2 = ' '.join(styled_words[len(line1_words):]) if styled_words[len(line1_words):] else ""
                
                styled_text = f"{line1}\\N{line2}"
            else:
                # Fallback - just use the complete text and add a line break
                middle = len(complete_text) // 2
                # Find a space near the middle to break at
                break_pos = complete_text.rfind(' ', 0, middle)
                if break_pos == -1:
                    break_pos = complete_text.find(' ', middle)
                
                if break_pos != -1:
                    styled_text = complete_text[:break_pos] + "\\N" + complete_text[break_pos+1:]
                else:
                    # No spaces found, force an arbitrary break
                    styled_text = complete_text[:middle] + "\\N" + complete_text[middle:]
            
            # Determine timing for this specific word
            word_start = chunk[i]['start']
            
            # Word end time is either the start of the next word or this word's end time
            if i < len(chunk) - 1:
                word_end = chunk[i+1]['start']
            else:
                word_end = end_time
            
            # Format the subtitle line for ASS
            line = f"Dialogue: 0,{timestamp_to_ass(word_start)},{timestamp_to_ass(word_end)},Default,,0,0,0,,{styled_text}"
            lines.append(line)
    
    # Write the ASS file
    with open(ass_path, 'w', encoding='utf-8') as f:
        f.write(header)
        for line in lines:
            f.write(line + '\n')
    
    print(f"Successfully converted {srt_path} to {ass_path}")
    return ass_path

def main():
    """
    Command-line interface for the SrtEdit script.
    Usage: python SrtEdit.py <srt_file_path>
    """
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python SrtEdit.py <srt_file_path>")
        sys.exit(1)
    
    srt_path = sys.argv[1]
    
    if not os.path.exists(srt_path):
        print(f"Error: File not found: {srt_path}")
        sys.exit(1)
    
    if not srt_path.lower().endswith('.srt'):
        print(f"Error: File must be an SRT file: {srt_path}")
        sys.exit(1)
    
    ass_path = srt_to_ass(srt_path)
    print(f"ASS subtitle file created: {ass_path}")

if __name__ == "__main__":
    main()