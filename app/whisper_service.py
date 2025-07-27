import whisper
from pathlib import Path
from typing import Union

# Load the Whisper model once at startup
model = whisper.load_model("base")  # You can change to "small", "medium", or "large"

def transcribe_audio(audio_path: Path, lang: str = None) -> dict:
    """
    Transcribe a given audio file using Whisper.
    If 'lang' is provided, it guides the model for better results.
    Returns the full result dict including segments with timestamps.
    """
    print(f"🔍 Transcribing: {audio_path.name} (lang={lang})")

    result = model.transcribe(str(audio_path), language=lang, verbose=False)
    return result  # Includes: 'text', 'segments', etc.
