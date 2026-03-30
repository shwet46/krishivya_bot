import os
import re
import base64
import io
import tempfile
from typing import Any

import requests

SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "")
SARVAM_STT_API_URL = os.getenv("SARVAM_STT_API_URL", "https://api.sarvam.ai/speech-to-text")
SARVAM_TTS_API_URL = os.getenv("SARVAM_TTS_API_URL", "https://api.sarvam.ai/text-to-speech")
SARVAM_STT_MODEL = os.getenv("SARVAM_STT_MODEL", "saaras:v3")
SARVAM_TTS_MODEL = os.getenv("SARVAM_TTS_MODEL", "bulbul:v3")
SARVAM_TTS_SPEAKER = os.getenv("SARVAM_TTS_SPEAKER", "shubh")

OPEN_SOURCE_STT_MODEL = os.getenv("OPEN_SOURCE_STT_MODEL", "openai/whisper-tiny")
OPEN_SOURCE_TTS_MODEL_EN = os.getenv("OPEN_SOURCE_TTS_MODEL_EN", "facebook/mms-tts-eng")
OPEN_SOURCE_TTS_MODEL_HI = os.getenv("OPEN_SOURCE_TTS_MODEL_HI", "facebook/mms-tts-hin")
OPEN_SOURCE_TTS_MODEL_MR = os.getenv("OPEN_SOURCE_TTS_MODEL_MAR", "facebook/mms-tts-mar")

_LOCAL_ASR_PIPELINE = None
_LOCAL_TTS_MODELS: dict[str, tuple[Any, Any]] = {}


def _is_low_quality_transcript(text: str) -> bool:
    cleaned = (text or "").strip()
    if len(cleaned) < 2:
        return True
    non_punct = re.sub(r"[\W_]+", "", cleaned, flags=re.UNICODE)
    return len(non_punct) < 2


def _get_local_asr_pipeline():
    global _LOCAL_ASR_PIPELINE
    if _LOCAL_ASR_PIPELINE is not None:
        return _LOCAL_ASR_PIPELINE

    from transformers import pipeline

    _LOCAL_ASR_PIPELINE = pipeline(
        "automatic-speech-recognition",
        model=OPEN_SOURCE_STT_MODEL,
        device=-1,
    )
    return _LOCAL_ASR_PIPELINE


def _local_stt_process(ogg_bytes: bytes) -> str:
    asr = _get_local_asr_pipeline()
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp_file:
            tmp_file.write(ogg_bytes)
            tmp_path = tmp_file.name

        result = asr(
            tmp_path,
            chunk_length_s=25,
            generate_kwargs={"task": "transcribe"},
        )
        if isinstance(result, dict):
            return (result.get("text") or "").strip()
        return str(result).strip()
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def _sarvam_stt_process(ogg_bytes: bytes) -> str:
    if not SARVAM_API_KEY:
        raise ValueError("Missing SARVAM_API_KEY for STT fallback")

    response = requests.post(
        SARVAM_STT_API_URL,
        headers={"api-subscription-key": SARVAM_API_KEY},
        files={"file": ("voice.ogg", ogg_bytes, "audio/ogg")},
        data={
            "model": SARVAM_STT_MODEL,
            "mode": "transcribe",
            "language_code": "unknown",
        },
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()
    transcript = (payload.get("transcript") or "").strip()
    if not transcript:
        raise ValueError("Sarvam STT returned empty transcript")
    return transcript

def stt_process(ogg_bytes: bytes) -> str:
    if not ogg_bytes:
        print("[ERROR] Input audio bytes are empty")
        return "I didn't receive any audio."

    errors = []

    try:
        return _sarvam_stt_process(ogg_bytes)
    except Exception as e:
        errors.append(f"Sarvam STT failed: {str(e)}")

    try:
        local_text = _local_stt_process(ogg_bytes)
        if not _is_low_quality_transcript(local_text):
            return local_text
        errors.append("Local STT output was low quality")
    except Exception as e:
        errors.append(f"Local STT fallback failed: {str(e)}")

    print("[ERROR] Speech-to-text pipeline failed:", " | ".join(errors))
    return "Sorry, I couldn't transcribe your audio right now."


def detect_language(text: str) -> str:
    """
    Detects if text is primarily Hindi or English.
    Checks for Devanagari script characters.
    """
    if not text:
        return "en-IN"

    # Count Devanagari characters
    devanagari_count = sum(
        1 for ch in text if '\u0900' <= ch <= '\u097F'
    )

    # Heuristic: If Devanagari and contains typical Marathi words, return mr-IN
    marathi_keywords = ["आहे", "नाही", "होय", "कृपया", "माझे", "तुमचे", "आपण"]
    if devanagari_count > 0:
        marathi_count = sum(1 for word in marathi_keywords if word in text)
        if marathi_count > 0:
            return "mr-IN"
        # If not Marathi, assume Hindi for Devanagari
        if (devanagari_count / len(text)) > 0.2:
            return "hi-IN"

    return "en-IN"


def strip_markdown(text: str) -> str:
    """
    Remove markdown formatting from text for natural speech synthesis.
    """
    if not text:
        return text
    
    # Remove headers (# ## ###)
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    
    # Remove bold (**text** or __text__)
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)
    
    # Remove italic (*text* or _text_)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'_(.+?)_', r'\1', text)
    
    # Remove strikethrough (~~text~~)
    text = re.sub(r'~~(.+?)~~', r'\1', text)
    
    # Remove inline code (`code`)
    text = re.sub(r'`(.+?)`', r'\1', text)
    
    # Remove code blocks (```code```)
    text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
    
    # Remove links [text](url) -> text
    text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)
    
    # Remove images ![alt](url)
    text = re.sub(r'!\[.*?\]\(.+?\)', '', text)
    
    # Remove horizontal rules (---, ***, ___)
    text = re.sub(r'^[-*_]{3,}\s*$', '', text, flags=re.MULTILINE)
    
    # Remove bullet points (- * +)
    text = re.sub(r'^[\s]*[-*+]\s+', '', text, flags=re.MULTILINE)
    
    # Remove numbered lists (1. 2. etc)
    text = re.sub(r'^[\s]*\d+\.\s+', '', text, flags=re.MULTILINE)
    
    # Remove blockquotes (>)
    text = re.sub(r'^>\s+', '', text, flags=re.MULTILINE)
    
    # Clean up multiple newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Clean up multiple spaces
    text = re.sub(r' {2,}', ' ', text)
    
    return text.strip()


def truncate_text_for_tts(text: str, max_bytes: int = 4500) -> str:
    """
    Truncate text to fit within byte limit while preserving complete sentences.
    Leaves some buffer (500 bytes) below the 5000 byte limit.
    """
    if not text:
        return text
    
    # Check if text is within limit
    text_bytes = text.encode('utf-8')
    if len(text_bytes) <= max_bytes:
        return text
    
    print(f"[WARN] Text too long ({len(text_bytes)} bytes), truncating to {max_bytes} bytes")
    
    # Try to truncate at sentence boundaries
    sentences = text.replace('।', '.').split('.') 
    
    truncated = ""
    for sentence in sentences:
        test_text = truncated + sentence + "."
        if len(test_text.encode('utf-8')) > max_bytes:
            break
        truncated = test_text
    
    # If no complete sentences fit, do character-wise truncation
    if not truncated:
        while len(text.encode('utf-8')) > max_bytes:
            text = text[:-1]
        truncated = text + "..."
    
    print(f"[DEBUG] Truncated to {len(truncated.encode('utf-8'))} bytes")
    return truncated.strip()


def tts_process(text: str) -> bytes:
    if not text or not text.strip():
        print("[ERROR] TTS input text is empty")
        text = "I have nothing to say."
    
    text = text.strip()
    print(f"[DEBUG] TTS input ({len(text)} chars, {len(text.encode('utf-8'))} bytes): {text[:100]}...")
    
    # Strip markdown formatting before processing
    text = strip_markdown(text)
    print(f"[DEBUG] After markdown strip: {text[:100]}...")
    
    # Truncate if necessary
    text = truncate_text_for_tts(text)
    
    lang = detect_language(text)
    print(f"[DEBUG] Detected language: {lang}")

    errors = []

    try:
        return _sarvam_tts_process(text, lang)
    except Exception as e:
        errors.append(f"Sarvam TTS failed: {str(e)}")

    try:
        return _local_tts_process(text, lang)
    except Exception as e:
        errors.append(f"Local TTS fallback failed: {str(e)}")

    raise RuntimeError("Text-to-speech pipeline failed: " + " | ".join(errors))


def _resolve_local_tts_model(lang_code: str) -> str:
    if lang_code == "hi-IN":
        return OPEN_SOURCE_TTS_MODEL_HI
    if lang_code == "mr-IN":
        return OPEN_SOURCE_TTS_MODEL_MR
    return OPEN_SOURCE_TTS_MODEL_EN


def _get_local_tts_bundle(model_id: str):
    if model_id in _LOCAL_TTS_MODELS:
        return _LOCAL_TTS_MODELS[model_id]

    from transformers import AutoTokenizer, VitsModel

    tokenizer = AutoTokenizer.from_pretrained(model_id)
    model = VitsModel.from_pretrained(model_id)
    _LOCAL_TTS_MODELS[model_id] = (tokenizer, model)
    return tokenizer, model


def _local_tts_process(text: str, lang_code: str) -> bytes:
    import numpy as np
    import torch
    from scipy.io.wavfile import write as write_wav

    model_id = _resolve_local_tts_model(lang_code)
    tokenizer, model = _get_local_tts_bundle(model_id)

    inputs = tokenizer(text, return_tensors="pt")
    with torch.no_grad():
        waveform = model(**inputs).waveform.squeeze().cpu().numpy()

    waveform = np.clip(waveform, -1.0, 1.0)
    pcm = (waveform * 32767).astype(np.int16)

    wav_bytes_io = io.BytesIO()
    write_wav(wav_bytes_io, int(getattr(model.config, "sampling_rate", 16000)), pcm)
    wav_bytes = wav_bytes_io.getvalue()
    if not wav_bytes:
        raise ValueError("Local TTS produced empty audio")
    print(f"[DEBUG] Generated {len(wav_bytes)} bytes using local open-source TTS ({model_id})")
    return wav_bytes


def _sarvam_tts_process(text: str, lang_code: str) -> bytes:
    if not SARVAM_API_KEY:
        raise ValueError("Missing SARVAM_API_KEY for TTS fallback")

    response = requests.post(
        SARVAM_TTS_API_URL,
        headers={
            "api-subscription-key": SARVAM_API_KEY,
            "Content-Type": "application/json",
        },
        json={
            "text": text,
            "target_language_code": lang_code,
            "model": SARVAM_TTS_MODEL,
            "speaker": SARVAM_TTS_SPEAKER,
        },
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()
    audio_items = payload.get("audios") or []
    if not audio_items:
        raise ValueError("Sarvam TTS response did not include audio data")
    audio_bytes = base64.b64decode(audio_items[0])
    print(f"[DEBUG] Generated {len(audio_bytes)} bytes of WAV audio from Sarvam")
    return audio_bytes