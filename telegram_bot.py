import requests
import io
import json
from datetime import datetime, timedelta
from flask import Blueprint, request
from audio_utils.audio_utils import mp3_to_ogg

telegram_bp = Blueprint("telegram_bot", __name__)


def send_scheduled_reminder(chat_id, message_text):
    """Callback for APScheduler to send a message after a delay."""
    from app import TELEGRAM_TOKEN
    send_telegram_message(TELEGRAM_TOKEN, chat_id, f"🔔 **Krishivya Reminder:**\n\n{message_text}")
    

def parse_and_schedule_reminder(chat_id, user_text):
    """Use Gemini to extract task and time, then schedule if found."""
    from app import scheduler
    from bot.rag import generate_response

    prompt = f"""
    Extact the 'task' and 'delay_seconds' from this agricultural reminder request.
    Today's date/time is: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    
    Rules:
    1. If user says 'tomorrow' at 10 AM, calculate seconds from now to tomorrow 10 AM.
    2. If user says 'in 5 minutes', delay_seconds is 300.
    3. Return ONLY a JSON object with 'task' and 'delay_seconds'.
    4. If no clear time is found, return {{"task": null, "delay_seconds": 0}}.
    
    User request: "{user_text}"
    """
    try:
        reply_text = generate_response(prompt)
        text = reply_text.replace("```json", "").replace("```", "").strip()
        data = json.loads(text)

        task = data.get("task")
        delay = data.get("delay_seconds")

        if task and delay > 0:
            job_id = f"reminder_{chat_id}_{datetime.now().timestamp()}"
            run_time = datetime.now() + timedelta(seconds=delay)
            scheduler.add_job(
                id=job_id,
                func=send_scheduled_reminder,
                args=[chat_id, task],
                trigger="date",
                run_date=run_time,
            )
            return f"Theek hai! I have scheduled a reminder for '{task}' at {run_time.strftime('%I:%M %p, %d %b')}."
    except Exception as e:
        print(f"Scheduling error: {e}")
    return None


@telegram_bp.route("/telegram", methods=["POST"])
def telegram_webhook():
    from app import (
        TELEGRAM_TOKEN,
    )
    from bot.rag import generate_response, WELCOME_MESSAGE
    from audio_utils.stt_tts import stt_process, tts_process

    data = request.json
    if not data or "message" not in data:
        return "OK", 200

    message = data["message"]
    chat_id = message["chat"]["id"]

    # IMAGE HANDLER 
    if "photo" in message:
        # Show 'uploading' action
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendChatAction",
                      data={"chat_id": chat_id, "action": "upload_photo"})
        
        # Get the highest resolution version
        file_id = message["photo"][-1]["file_id"]
        # Use caption as the query; default if empty
        user_query = message.get("caption", "Diagnose this crop for any diseases or pests.")

        # Download the image
        file_info = requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getFile",
                                 params={"file_id": file_id}).json()
        img_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_info['result']['file_path']}"
        img_bytes = requests.get(img_url).content

        try:
            from bot.rag import generate_response
            reply = generate_response(user_query, image_bytes=img_bytes)
        except Exception as e:
            print(f"Vision error: {e}")
            reply = "I'm sorry, I couldn't process the photo. Please ensure it's a clear shot of the crop."

        send_telegram_message(TELEGRAM_TOKEN, chat_id, reply)

    # VOICE HANDLER
    elif "voice" in message:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendChatAction",
                      data={"chat_id": chat_id, "action": "record_voice"})
        
        file_id = message["voice"]["file_id"]
        file_info = requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getFile",
                                 params={"file_id": file_id}).json()
        audio_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_info['result']['file_path']}"
        ogg_bytes = requests.get(audio_url).content

        try:
            user_text = stt_process(ogg_bytes)
            ai_reply = None
            if any(word in user_text.lower() for word in ["remind", "re-mind", "yaad dilao", "remember"]):
                ai_reply = parse_and_schedule_reminder(chat_id, user_text)
            
            if not ai_reply:
                ai_reply = generate_response(user_text)

            mp3_audio = tts_process(ai_reply)
            ogg_audio = mp3_to_ogg(mp3_audio)

            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVoice",
                data={"chat_id": chat_id},
                files={"voice": ("reply.ogg", ogg_audio)},
            )
            # Below the voice note, respond as text also
            send_telegram_message(TELEGRAM_TOKEN, chat_id, ai_reply)

            if "redirecting this query to the nearest Agriculture Officer" in ai_reply:
                handle_human_escalation(chat_id, user_text)

        except Exception as e:
            print("Voice error:", e)
            send_telegram_message(TELEGRAM_TOKEN, chat_id, "I heard you, but my voice system is resting. Here's my reply: " + ai_reply)

    # TEXT HANDLER 
    elif "text" in message:
        user_text = message["text"]
        if user_text == "/start":
            reply = WELCOME_MESSAGE
        else:
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendChatAction",
                          data={"chat_id": chat_id, "action": "typing"})

            reply = None
            if any(word in user_text.lower() for word in ["remind", "re-mind", "yaad dilao", "remember"]):
                reply = parse_and_schedule_reminder(chat_id, user_text)
            if not reply:
                reply = generate_response(user_text)
        
        send_telegram_message(TELEGRAM_TOKEN, chat_id, reply)

    return "OK", 200

def send_telegram_message(token, chat_id, text):
    import re
    # Convert standard Markdown to HTML for robust parsing
    # Escape HTML special characters
    clean_text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    
    # Process code blocks and inline code
    clean_text = re.sub(r'```\w*\n(.*?)\n?```', r'<pre>\1</pre>', clean_text, flags=re.DOTALL)
    clean_text = re.sub(r'```(.*?)```', r'<pre>\1</pre>', clean_text, flags=re.DOTALL)
    clean_text = re.sub(r'`(.*?)`', r'<code>\1</code>', clean_text)
    
    # Process bold
    clean_text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', clean_text, flags=re.DOTALL)
    
    # Process italic
    clean_text = re.sub(r'(?<!\*)\*([^\s*](?:.*?[^\s*])?)\*(?!\*)', r'<i>\1</i>', clean_text, flags=re.DOTALL)
    clean_text = re.sub(r'__(.*?)__', r'<i>\1</i>', clean_text, flags=re.DOTALL)
    
    # Process headers (convert to Bold)
    clean_text = re.sub(r'(?m)^#{1,6}\s*(.+)$', r'<b>\1</b>', clean_text)
    
    # Convert dashes or asterisks for list items into standard dot character
    clean_text = re.sub(r'(?m)^(\s*)[-*]\s+', r'\1• ', clean_text)

    response = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data={"chat_id": chat_id, "text": clean_text, "parse_mode": "HTML"},
    )
    if response.status_code != 200:
        print(f"[ERROR] Failed to send Telegram message with HTML: {response.text}")
        # Fallback without parse_mode if HTML formatting fails
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={"chat_id": chat_id, "text": text},
        )

def handle_human_escalation(chat_id, context):
    """
    Logic to notify a real human officer. 
    In a real app, this would write to Firestore or send a Slack/Email alert.
    """
    print(f"ALERT: User {chat_id} needs human help with context: {context}")