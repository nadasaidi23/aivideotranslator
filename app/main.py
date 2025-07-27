from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
import shutil
import uuid
from app.utils import extract_audio, write_srt, burn_subtitles
from app.whisper_service import transcribe_audio
from app.translation_service import translate_text, get_supported_languages

# Create uploads directory if it doesn't exist
UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="AI Video Translator",
    description="Upload videos and get live AI-based translations",
    version="1.0.0",
)

# Allow CORS (for frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files (frontend)
app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/")
def root():
    """Serve the main HTML page"""
    return FileResponse('frontend/index.html')

@app.get("/api/")
def api_root():
    return {"message": "Video Translator API is running"}

@app.post("/upload/")
async def upload_video(file: UploadFile = File(...)):
    file_ext = Path(file.filename).suffix
    if file_ext.lower() not in [".mp4", ".mov", ".mkv", ".avi"]:
        return {"error": "Unsupported file format"}

    # Generate a unique filename
    unique_name = f"{uuid.uuid4().hex}{file_ext}"
    save_path = UPLOAD_DIR / unique_name

    # Save file
    with save_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return {"message": "✅ Video uploaded successfully", "filename": unique_name}

@app.post("/transcribe/")
async def transcribe_video(filename: str = Form(...), lang: str = Form(None)):
    """
    Transcribes the uploaded video to text using Whisper.
    Returns both full transcript and timed segments for subtitles.
    """
    video_path = UPLOAD_DIR / filename
    if not video_path.exists():
        return {"error": "❌ Video file not found."}

    try:
        # Extract audio from video
        audio_path = extract_audio(video_path, UPLOAD_DIR)

        # Transcribe audio to text with segments
        result = transcribe_audio(audio_path, lang=lang)
        
        # Create SRT file for subtitles
        srt_path = UPLOAD_DIR / (video_path.stem + ".srt")
        write_srt(result["segments"], srt_path)

        return {
            "message": "✅ Transcription complete",
            "filename": filename,
            "transcript": result["text"],  # Full transcript text
            "segments": result["segments"],  # Timed segments for subtitles
            "srt_file": srt_path.name
        }
    except Exception as e:
        return {"error": str(e)}

@app.post("/translate/")
async def translate_transcript(
    transcript: str = Form(...),
    target_lang: str = Form(...),
    segments: str = Form(None)  # JSON string of segments if provided
):
    """
    Translate transcript and individual segments into another language.
    """
    try:
        # Translate the full transcript
        translated_full = translate_text(transcript, target_lang)
        
        # If segments are provided, translate each segment individually
        translated_segments = None
        if segments:
            import json
            try:
                segments_data = json.loads(segments)
                translated_segments = []
                
                for segment in segments_data:
                    translated_text = translate_text(segment['text'], target_lang)
                    translated_segments.append({
                        'start': segment['start'],
                        'end': segment['end'],
                        'text': translated_text
                    })
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Error processing segments: {e}")
        
        return {
            "message": f"✅ Translation to '{target_lang}' complete",
            "translated_text": translated_full,
            "translated_segments": translated_segments
        }
    except ValueError as ve:
        return {"error": str(ve)}
    except Exception as e:
        return {"error": f"Translation failed: {e}"}

@app.get("/languages/")
def supported_languages():
    """List all supported translation language codes."""
    return {"supported_languages": get_supported_languages()}

@app.post("/burn/")
async def burn_subtitle_to_video(filename: str = Form(...), srt_file: str = Form(...)):
    """Burn translated subtitles directly into the video file."""
    video_path = UPLOAD_DIR / filename
    srt_path = UPLOAD_DIR / srt_file
    output_path = UPLOAD_DIR / f"{video_path.stem}_subtitled.mp4"

    if not video_path.exists():
        return {"error": "❌ Video file not found."}
    
    if not srt_path.exists():
        return {"error": "❌ SRT file not found."}

    try:
        burn_subtitles(video_path, srt_path, output_path)
        return {
            "message": "✅ Subtitled video ready", 
            "output": output_path.name,
            "download_url": f"/download/{output_path.name}"
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/download/{filename}")
async def download_file(filename: str):
    """Download processed files."""
    file_path = UPLOAD_DIR / filename
    if not file_path.exists():
        return {"error": "File not found"}
    
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type='application/octet-stream'
    )