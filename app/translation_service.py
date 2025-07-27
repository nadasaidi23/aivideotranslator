from transformers import pipeline
from typing import Optional, List, Dict
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load multilingual translation pipeline (can take 20s on first run)
print("🔄 Loading translation model (this may take a moment)...")
translator = pipeline("translation", model="facebook/nllb-200-distilled-600M")
print("✅ Translation model loaded successfully!")

# NLLB language codes: https://huggingface.co/facebook/nllb-200-distilled-600M#languages
LANG_MAP = {
    "en": "eng_Latn",      # English
    "fr": "fra_Latn",      # French
    "es": "spa_Latn",      # Spanish
    "de": "deu_Latn",      # German
    "ar": "arb_Arab",      # Arabic
    "zh": "zho_Hans",      # Chinese (Simplified)
    "hi": "hin_Deva",      # Hindi
    "ru": "rus_Cyrl",      # Russian
    "pt": "por_Latn",      # Portuguese
    "ja": "jpn_Jpan",      # Japanese
    "ko": "kor_Hang",      # Korean
    "tr": "tur_Latn",      # Turkish
    "it": "ita_Latn",      # Italian
    "pl": "pol_Latn",      # Polish
    "vi": "vie_Latn",      # Vietnamese
    "th": "tha_Thai",      # Thai
    "uk": "ukr_Cyrl",      # Ukrainian
    "id": "ind_Latn",      # Indonesian
    "ro": "ron_Latn",      # Romanian
    "fa": "pes_Arab",      # Persian
    "nl": "nld_Latn",      # Dutch
    "bn": "ben_Beng",      # Bengali
    "sw": "swh_Latn",      # Swahili
    "he": "heb_Hebr",      # Hebrew
}

def get_supported_languages():
    """Return list of supported language codes."""
    return list(LANG_MAP.keys())

def translate_text(text: str, target_lang: str, source_lang: str = "en") -> str:
    """
    Translate the given text to the specified target language.
    
    Args:
        text: Text to translate
        target_lang: Target language code (e.g., 'es', 'fr')
        source_lang: Source language code (default: 'en')
    
    Returns:
        Translated text string
    """
    if not text or not text.strip():
        return ""
    
    # Get NLLB language codes
    source_code = LANG_MAP.get(source_lang.lower())
    target_code = LANG_MAP.get(target_lang.lower())
    
    if not target_code:
        raise ValueError(f"Unsupported target language: {target_lang}")
    
    if not source_code:
        logger.warning(f"Unsupported source language: {source_lang}, defaulting to English")
        source_code = "eng_Latn"
    
    try:
        # Clean and prepare text
        clean_text = text.strip()
        if len(clean_text) > 512:  # Split long texts
            return translate_long_text(clean_text, source_code, target_code)
        
        # Translate
        result = translator(
            clean_text, 
            src_lang=source_code, 
            tgt_lang=target_code, 
            max_length=1024
        )
        
        if isinstance(result, list) and len(result) > 0:
            return result[0]["translation_text"]
        else:
            logger.error(f"Unexpected translation result format: {result}")
            return clean_text  # Return original text if translation fails
            
    except Exception as e:
        logger.error(f"Translation error: {e}")
        return text  # Return original text on error

def translate_long_text(text: str, source_code: str, target_code: str) -> str:
    """
    Translate long text by splitting it into chunks.
    """
    sentences = text.split('. ')
    translated_sentences = []
    
    current_chunk = ""
    for sentence in sentences:
        if len(current_chunk + sentence) < 400:
            current_chunk += sentence + ". "
        else:
            if current_chunk:
                try:
                    result = translator(
                        current_chunk.strip(), 
                        src_lang=source_code, 
                        tgt_lang=target_code, 
                        max_length=1024
                    )
                    translated_sentences.append(result[0]["translation_text"])
                except Exception as e:
                    logger.error(f"Chunk translation error: {e}")
                    translated_sentences.append(current_chunk.strip())
            
            current_chunk = sentence + ". "
    
    # Handle remaining chunk
    if current_chunk:
        try:
            result = translator(
                current_chunk.strip(), 
                src_lang=source_code, 
                tgt_lang=target_code, 
                max_length=1024
            )
            translated_sentences.append(result[0]["translation_text"])
        except Exception as e:
            logger.error(f"Final chunk translation error: {e}")
            translated_sentences.append(current_chunk.strip())
    
    return " ".join(translated_sentences)

def translate_segments(segments: List[Dict], target_lang: str, source_lang: str = "en") -> List[Dict]:
    """
    Translate a list of subtitle segments.
    
    Args:
        segments: List of segments with 'start', 'end', 'text' keys
        target_lang: Target language code
        source_lang: Source language code (default: 'en')
    
    Returns:
        List of translated segments
    """
    if not segments:
        return []
    
    translated_segments = []
    
    for i, segment in enumerate(segments):
        try:
            # Validate segment structure
            if not all(key in segment for key in ['start', 'end', 'text']):
                logger.warning(f"Segment {i} missing required fields, skipping")
                continue
            
            original_text = segment['text'].strip()
            if not original_text:
                continue
            
            # Translate the text
            translated_text = translate_text(original_text, target_lang, source_lang)
            
            # Create translated segment
            translated_segment = {
                'start': segment['start'],
                'end': segment['end'],
                'text': translated_text
            }
            
            translated_segments.append(translated_segment)
            
            # Log progress for long lists
            if len(segments) > 10 and (i + 1) % 10 == 0:
                logger.info(f"Translated {i + 1}/{len(segments)} segments")
                
        except Exception as e:
            logger.error(f"Error translating segment {i}: {e}")
            # Keep original segment on error
            translated_segments.append(segment)
    
    logger.info(f"✅ Successfully translated {len(translated_segments)}/{len(segments)} segments")
    return translated_segments

def batch_translate_segments(segments: List[Dict], target_lang: str, source_lang: str = "en", batch_size: int = 5) -> List[Dict]:
    """
    Translate segments in batches for better performance.
    """
    if not segments:
        return []
    
    translated_segments = []
    
    # Process in batches
    for i in range(0, len(segments), batch_size):
        batch = segments[i:i + batch_size]
        batch_texts = [seg['text'].strip() for seg in batch if seg.get('text', '').strip()]
        
        if not batch_texts:
            continue
        
        try:
            # Combine texts for batch translation
            combined_text = " [SEP] ".join(batch_texts)
            translated_combined = translate_text(combined_text, target_lang, source_lang)
            
            # Split back
            translated_texts = translated_combined.split(" [SEP] ")
            
            # If split doesn't work as expected, fall back to individual translation
            if len(translated_texts) != len(batch_texts):
                logger.warning(f"Batch split mismatch, falling back to individual translation")
                for j, segment in enumerate(batch):
                    if segment.get('text', '').strip():
                        translated_text = translate_text(segment['text'].strip(), target_lang, source_lang)
                        translated_segments.append({
                            'start': segment['start'],
                            'end': segment['end'],
                            'text': translated_text
                        })
            else:
                # Use batch results
                for j, segment in enumerate(batch):
                    if j < len(translated_texts) and segment.get('text', '').strip():
                        translated_segments.append({
                            'start': segment['start'],
                            'end': segment['end'],
                            'text': translated_texts[j].strip()
                        })
            
            logger.info(f"Processed batch {i//batch_size + 1}/{(len(segments) + batch_size - 1)//batch_size}")
            
        except Exception as e:
            logger.error(f"Batch translation error: {e}, falling back to individual translation")
            # Fall back to individual translation for this batch
            for segment in batch:
                if segment.get('text', '').strip():
                    try:
                        translated_text = translate_text(segment['text'].strip(), target_lang, source_lang)
                        translated_segments.append({
                            'start': segment['start'],
                            'end': segment['end'],
                            'text': translated_text
                        })
                    except Exception as individual_error:
                        logger.error(f"Individual translation error: {individual_error}")
                        translated_segments.append(segment)  # Keep original
    
    return translated_segments