import os
import re
from google.cloud import speech_v2, texttospeech
from audio_utils.audio_utils import ogg_to_wav

GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")
REGION = "global"

if not GCP_PROJECT_ID:
    raise ValueError(
        "CRITICAL: GCP_PROJECT_ID environment variable is not set. "
        "Please export GCP_PROJECT_ID=your-google-cloud-id"
    )

def stt_process(ogg_bytes: bytes) -> str:
    if not ogg_bytes:
        print("[ERROR] Input audio bytes are empty")
        return "I didn't receive any audio."
    
    print(f"[DEBUG] Received {len(ogg_bytes)} bytes of OGG audio")
    
    try:
        wav_bytes, sample_rate, channels = ogg_to_wav(ogg_bytes)
    except Exception as e:
        print(f"[ERROR] Audio conversion failed: {str(e)}")
        return "Sorry, I couldn't process the audio file."
    
    if not wav_bytes or len(wav_bytes) < 100:
        print(f"[ERROR] Audio conversion resulted in empty or too small WAV bytes: {len(wav_bytes) if wav_bytes else 0}")
        return "The audio file seems to be empty or too short."
    
    print(f"[DEBUG] Converted to {len(wav_bytes)} bytes WAV, {sample_rate}Hz, {channels} channels")
    
    try:
        client = speech_v2.SpeechClient(
            client_options={
                "api_endpoint": "speech.googleapis.com",
                "quota_project_id": GCP_PROJECT_ID,
            }
        )
        
        recognizer = f"projects/{GCP_PROJECT_ID}/locations/global/recognizers/_"
        
        response = client.recognize(
            request={
                "recognizer": recognizer,
                "config": {
                    "explicit_decoding_config": {
                        "encoding": "LINEAR16",
                        "sample_rate_hertz": sample_rate,
                        "audio_channel_count": channels,
                    },
                    "language_codes": ["en-IN", "hi-IN", "mr-IN"],
                    "model": "long",
                },
                "content": wav_bytes,
            }
        )
        
        # Extract transcription
        transcripts = [
            r.alternatives[0].transcript
            for r in response.results
            if r.alternatives
        ]
        
        if not transcripts:
            print("[WARN] No speech detected in audio")
            return "I couldn't understand any speech in the audio. Please try speaking more clearly."
        
        result = " ".join(transcripts).strip()
        
        if not result:
            print("[WARN] Transcription resulted in empty string")
            return "I couldn't understand what was said. Please try again."
        
        print(f"[DEBUG] Transcription: {result}")
        return result
        
    except Exception as e:
        print(f"[ERROR] Speech-to-text failed: {str(e)}")
        return "Sorry, I encountered an error processing your speech."


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
    
    voice_map = {
        "hi-IN": "hi-IN-Wavenet-D",
        "en-IN": "en-IN-Wavenet-D",
    }
    
    try:
        client = texttospeech.TextToSpeechClient(
            client_options={
                "api_endpoint": "texttospeech.googleapis.com",
                "quota_project_id": GCP_PROJECT_ID,
            }
        )
        
        response = client.synthesize_speech(
            input=texttospeech.SynthesisInput(text=text),
            voice=texttospeech.VoiceSelectionParams(
                language_code=lang,
                name=voice_map[lang],
            ),
            audio_config=texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3,
                speaking_rate=1.0,
                pitch=0.0,
                effects_profile_id=["telephony-class-application"],
            ),
        )
        
        if not response.audio_content:
            raise ValueError("TTS returned empty audio content")
        
        print(f"[DEBUG] Generated {len(response.audio_content)} bytes of MP3 audio")
        return response.audio_content
        
    except Exception as e:
        print(f"[ERROR] Text-to-speech failed: {str(e)}")
        raise