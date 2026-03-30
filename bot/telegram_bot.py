import requests
from datetime import datetime, timedelta
from flask import Blueprint, request
from audio_utils.audio_utils import mp3_to_ogg

telegram_bp = Blueprint("telegram_bot", __name__)
VOICE_PROCESSING_PAUSED = True


def send_scheduled_reminder(chat_id, message_text):
    """Callback for APScheduler to send a message after a delay."""
    from app import TELEGRAM_TOKEN
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        data={
            "chat_id": chat_id,
            "text": f"🔔 *Krishivya Reminder:*\n\n{message_text}",
            "parse_mode": "Markdown",
        },
    )


def parse_and_schedule_reminder(chat_id, user_text):
    """Use Sarvam text API to extract task and time, then schedule if found."""
    from app import scheduler
    from llm_processing.llm_service import parse_reminder_request

    try:
        data = parse_reminder_request(
            user_text=user_text,
            now_text=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        )

        task = data.get("task")
        delay = int(data.get("delay_seconds") or 0)

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
    from llm_processing.llm_service import WELCOME_MESSAGE, generate_response
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
            reply = generate_response(user_query, image_bytes=img_bytes)
        except Exception as e:
            print(f"Vision error: {e}")
            reply = "I'm sorry, I couldn't process the photo. Please ensure it's a clear shot of the crop."

        send_telegram_message(TELEGRAM_TOKEN, chat_id, reply)

    # VOICE/AUDIO HANDLER
    elif "voice" in message or "audio" in message:
        if VOICE_PROCESSING_PAUSED:
            send_telegram_message(
                TELEGRAM_TOKEN,
                chat_id,
                "Krishivya is resting now, please text only.",
            )
        else:
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendChatAction",
                          data={"chat_id": chat_id, "action": "record_voice"})

            if "voice" in message:
                file_id = message["voice"]["file_id"]
            else:
                file_id = message["audio"]["file_id"]

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
                if "redirecting this query to the nearest Agriculture Officer" in ai_reply:
                    handle_human_escalation(chat_id, user_text)

            except Exception as e:
                print("Voice error:", e)
                fallback_reply = ai_reply or "I heard you, but I could not generate a voice response right now."
                send_telegram_message(TELEGRAM_TOKEN, chat_id, "I heard you, but my voice system is resting. Here's my reply: " + fallback_reply)

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
    requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
    )

def handle_human_escalation(chat_id, context):
    """
    Logic to notify a real human officer. 
    In a real app, this would write to Firestore or send a Slack/Email alert.
    """
    print(f"ALERT: User {chat_id} needs human help with context: {context}")