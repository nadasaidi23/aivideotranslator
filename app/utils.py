import subprocess
from pathlib import Path

def extract_audio(video_path: Path, output_dir: Path) -> Path:
    """
    Extract audio from a video file and save it as a mono WAV file with 16kHz.
    This format is compatible with Whisper.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    audio_path = output_dir / (video_path.stem + ".wav")

    command = [
        "ffmpeg", "-y",                     # Overwrite if exists
        "-i", str(video_path),             # Input video
        "-vn",                             # Disable video
        "-acodec", "pcm_s16le",            # Output format
        "-ar", "16000",                    # Sample rate
        "-ac", "1",                        # Mono channel
        str(audio_path)
    ]

    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"❌ FFmpeg error: {result.stderr}")

    return audio_path

def write_srt(segments, srt_path: Path):
    """
    Write subtitle segments to an SRT file.
    """
    def format_timestamp(seconds):
        """Convert seconds to SRT timestamp format (HH:MM:SS,mmm)"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        milliseconds = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"

    try:
        with open(srt_path, "w", encoding="utf-8") as f:
            for i, segment in enumerate(segments, 1):
                # Ensure segment has required fields
                if not all(key in segment for key in ['start', 'end', 'text']):
                    print(f"Warning: Segment {i} missing required fields")
                    continue
                
                start_time = format_timestamp(segment['start'])
                end_time = format_timestamp(segment['end'])
                text = segment['text'].strip()
                
                # Write SRT entry
                f.write(f"{i}\n")
                f.write(f"{start_time} --> {end_time}\n")
                f.write(f"{text}\n\n")
        
        print(f"✅ SRT file created: {srt_path}")
        
    except Exception as e:
        raise RuntimeError(f"❌ Error writing SRT file: {e}")

def write_translated_srt(translated_segments, srt_path: Path):
    """
    Write translated subtitle segments to an SRT file.
    """
    def format_timestamp(seconds):
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        milliseconds = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"

    try:
        with open(srt_path, "w", encoding="utf-8") as f:
            for i, segment in enumerate(translated_segments, 1):
                start_time = format_timestamp(segment['start'])
                end_time = format_timestamp(segment['end'])
                text = segment['text'].strip()
                
                f.write(f"{i}\n")
                f.write(f"{start_time} --> {end_time}\n")
                f.write(f"{text}\n\n")
        
        print(f"✅ Translated SRT file created: {srt_path}")
        
    except Exception as e:
        raise RuntimeError(f"❌ Error writing translated SRT file: {e}")

def burn_subtitles(video_path: Path, srt_path: Path, output_path: Path):
    """
    Burn SRT subtitles directly into the video using FFmpeg.
    This creates a new video file with burned-in subtitles.
    """
    try:
        # Ensure paths exist
        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")
        if not srt_path.exists():
            raise FileNotFoundError(f"SRT file not found: {srt_path}")

        # FFmpeg command to burn subtitles
        command = [
            "ffmpeg", "-y",  # Overwrite output file
            "-i", str(video_path),  # Input video
            "-vf", f"subtitles={str(srt_path)}:force_style='Alignment=2,FontSize=24,PrimaryColour=&H00ffffff,OutlineColour=&H00000000,Outline=2'",  # Video filter with subtitle styling
            "-c:a", "copy",  # Copy audio without re-encoding
            "-c:v", "libx264",  # Video codec
            "-preset", "medium",  # Encoding preset (balance between speed and quality)
            "-crf", "23",  # Video quality (lower = better quality)
            str(output_path)
        ]
        
        print(f"🔥 Burning subtitles into video...")
        print(f"   Input: {video_path.name}")
        print(f"   Subtitles: {srt_path.name}")
        print(f"   Output: {output_path.name}")
        
        result = subprocess.run(command, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise RuntimeError(f"❌ FFmpeg subtitle burn error: {result.stderr}")
        
        if not output_path.exists():
            raise RuntimeError("❌ Output video file was not created")
        
        print(f"✅ Subtitled video created successfully: {output_path.name}")
        
    except Exception as e:
        raise RuntimeError(f"❌ Error burning subtitles: {e}")

def get_video_info(video_path: Path) -> dict:
    """
    Get basic information about a video file using FFprobe.
    """
    try:
        command = [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_format", "-show_streams",
            str(video_path)
        ]
        
        result = subprocess.run(command, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise RuntimeError(f"FFprobe error: {result.stderr}")
        
        import json
        info = json.loads(result.stdout)
        
        # Extract basic video info
        video_stream = next((s for s in info['streams'] if s['codec_type'] == 'video'), None)
        format_info = info.get('format', {})
        
        return {
            'duration': float(format_info.get('duration', 0)),
            'size': int(format_info.get('size', 0)),
            'width': int(video_stream.get('width', 0)) if video_stream else 0,
            'height': int(video_stream.get('height', 0)) if video_stream else 0,
            'codec': video_stream.get('codec_name', 'unknown') if video_stream else 'unknown'
        }
        
    except Exception as e:
        print(f"Warning: Could not get video info: {e}")
        return {}