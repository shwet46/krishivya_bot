import os
import requests
from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv
from flask_apscheduler import APScheduler
from google.cloud import firestore
from pyngrok import ngrok

load_dotenv()

# Point GCP client libraries to the service-account credentials file
os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", "credentials.json")

from bot.telegram_bot import telegram_bp

TELEGRAM_TOKEN  = os.getenv("TELEGRAM_TOKEN")
GCP_PROJECT_ID  = os.getenv("GCP_PROJECT_ID", "sam-sang-493608")

# Firestore client (used for escalation logging and session state)
db = firestore.Client(project=GCP_PROJECT_ID)

app = Flask(__name__)
CORS(app)

# Initialise background scheduler (for reminder jobs)
scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()

app.register_blueprint(telegram_bp)

# Auto-set Telegram Webhook using Ngrok (for local testing)
if os.environ.get("USE_NGROK", "True").lower() == "true":
    try:
        public_url = ngrok.connect(5000).public_url
        print(f" * Ngrok tunnel established at: {public_url}")
        webhook_url = f"{public_url}/telegram"
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook", 
                      data={"url": webhook_url})
        print(f" * Telegram webhook set to: {webhook_url}")
    except Exception as e:
        print(f" * Could not establish Ngrok tunnel: {e}")


@app.route("/")
def home():
    return "Krishivya — powered by Google Cloud — is running!"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)