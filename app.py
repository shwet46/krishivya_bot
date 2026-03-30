import os
import sys
import requests
from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv
from flask_apscheduler import APScheduler
from pyngrok import ngrok

load_dotenv()

from bot.telegram_bot import telegram_bp

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# Ensure imports like "from app import scheduler" reuse this live module
# even when launched as "python app.py".
sys.modules.setdefault("app", sys.modules[__name__])

app = Flask(__name__)
CORS(app) 

# Initialize Scheduler
scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()

app.register_blueprint(telegram_bp)


def _start_ngrok_and_set_webhook(port: int) -> str | None:
    use_ngrok = os.getenv("USE_NGROK", "true").lower() == "true"
    if not use_ngrok:
        return None

    ngrok_auth_token = os.getenv("NGROK_AUTHTOKEN")
    if ngrok_auth_token:
        ngrok.set_auth_token(ngrok_auth_token)

    tunnel = ngrok.connect(addr=port, bind_tls=True)
    public_url = tunnel.public_url
    print(f"ngrok tunnel started: {public_url}")

    if TELEGRAM_TOKEN:
        webhook_url = f"{public_url}/telegram"
        response = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook",
            data={"url": webhook_url},
            timeout=30,
        )
        response.raise_for_status()
        print(f"Telegram webhook set to: {webhook_url}")
    else:
        print("TELEGRAM_TOKEN is missing; skipped webhook setup.")

    return public_url

@app.route("/")
def home():
    return "AgriSaathi Telegram Bot is running!"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    _start_ngrok_and_set_webhook(port)
    app.run(host='0.0.0.0', port=port)