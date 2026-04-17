import io
from pydub import AudioSegment


def ogg_to_wav(ogg_bytes: bytes):
    """
    Convert OGG audio to raw PCM WAV data for Google Speech API.
    Returns raw audio bytes, sample rate, and channel count.
    """
    if not ogg_bytes:
        raise ValueError("Input OGG bytes are empty")
    
    try:
        # Load OGG audio
        audio = AudioSegment.from_file(io.BytesIO(ogg_bytes), format="ogg")
        
        if audio.channels > 1:
            audio = audio.set_channels(1)
      
        audio = audio.set_sample_width(2) 
        sample_rate = audio.frame_rate
        if sample_rate < 8000:
            audio = audio.set_frame_rate(16000)
            sample_rate = 16000
        
        # Export as raw PCM data
        raw_io = io.BytesIO()
        audio.export(raw_io, format="raw")
        raw_bytes = raw_io.getvalue()
        
        if not raw_bytes:
            raise ValueError("Audio conversion resulted in empty data")
        
        print(f"[DEBUG] Converted audio: {len(raw_bytes)} bytes, {sample_rate}Hz, {audio.channels} channels")
        
        return raw_bytes, sample_rate, audio.channels
        
    except Exception as e:
        raise ValueError(f"Failed to convert OGG to WAV: {str(e)}")


def mp3_to_ogg(mp3_bytes: bytes):
    """
    Convert MP3 audio to OGG format with Opus codec for Telegram.
    """
    if not mp3_bytes:
        raise ValueError("Input MP3 bytes are empty")
    
    try:
        # Load MP3 audio
        audio = AudioSegment.from_file(io.BytesIO(mp3_bytes), format="mp3")
        ogg_io = io.BytesIO()
        audio.export(
            ogg_io, 
            format="ogg", 
            codec="libopus",
            parameters=["-b:a", "64k"] 
        )
        ogg_bytes = ogg_io.getvalue()
        
        if not ogg_bytes:
            raise ValueError("MP3 to OGG conversion resulted in empty data")
        
        print(f"[DEBUG] Converted MP3 ({len(mp3_bytes)} bytes) to OGG ({len(ogg_bytes)} bytes)")
        
        return ogg_bytes
        
    except Exception as e:
        raise ValueError(f"Failed to convert MP3 to OGG: {str(e)}")
