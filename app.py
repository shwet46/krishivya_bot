import os
import requests
from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv
from flask_apscheduler import APScheduler
from google.cloud import firestore
from pyngrok import ngrok

load_dotenv()

from bot.telegram_bot import telegram_bp

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "credentials.json"

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")


db = firestore.Client()

app = Flask(__name__)
CORS(app) 

# Initialize Scheduler
scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()

app.register_blueprint(telegram_bp)

@app.route("/")
def home():
    return "AgriSaathi Telegram Bot is running!"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)