# 🌾 AgriSaathi (Krishivya Bot)

<div align="center">
  <img src="assets/icon.png" alt="AgriSaathi Icon" width="120" />
  <p><strong>Multimodal AI Agriculture Telegram Bot — Powered by Google Cloud</strong></p>
</div>

---

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-blue.svg" alt="Python Version" />
  <img src="https://img.shields.io/badge/Google%20Cloud-Vertex%20AI-4285F4.svg" alt="Google Cloud" />
  <img src="https://img.shields.io/badge/Telegram-Bot%20API-2CA5E0.svg" alt="Telegram API" />
  <img src="https://img.shields.io/badge/Framework-Flask-black.svg" alt="Flask" />
</p>

## 📖 Overview

**AgriSaathi** (also known as the Krishivya Bot) is an intelligent, accessible, and empathetic AI Agriculture Officer available directly on Telegram. Designed to assist Indian farmers, it provides context-aware agronomic advice, diagnoses crop diseases from images, and interacts seamlessly across text and voice in multiple regional languages. 

## ✨ Key Features

- **📸 Multimodal Crop Diagnosis**: Farmers can send pictures of affected crops. The bot utilizes Gemini 2.5 Pro Vision to diagnose the pest/disease, estimate damage severity, and provide actionable organic and chemical remedies.
- **🗣️ Voice & Multilingual Interaction**: Breaking the literacy and language barriers, the bot supports full two-way voice communication in regional Indian languages (Hindi, Marathi, Bengali, Punjabi, etc.) using GCP Speech-to-Text v2 and Text-to-Speech.
- **🌾 RAG-Powered Knowledge Base**: Answers questions strictly related to farming, soil, weather, fertilizers, and government subsidies with deep accuracy and step-by-step guidance.
- **⏰ Smart Agricultural Reminders**: Farmers can schedule reminders for critical tasks (e.g., "Remind me to spray pesticide tomorrow morning"). 
- **🚨 Expert Escalation Protocol**: Complex queries or high-risk pesticide recommendations are automatically logged to Firestore and flagged for human review by the nearest Agriculture Officer.

## 🏗️ Architecture & Technologies

The system recently underwent a full migration to the **Google Cloud Platform (GCP)** ecosystem to ensure enterprise-grade stability and unified credential management.

* **Core AI Inference**: [Google Vertex AI (Gemini 2.5 Pro)](https://cloud.google.com/vertex-ai) for text generation and multimodal vision reasoning.
* **Voice Services**: Native GCP Cloud Speech-to-Text v2 and Cloud Text-to-Speech.
* **Database / State**: [Firestore](https://firebase.google.com/docs/firestore) for persistent session tracking and escalation logging.
* **Backend Engine**: [Flask](https://flask.palletsprojects.com/) + Gunicorn for robust webhook handling.
* **Task Scheduling**: `Flask-APScheduler` for managing reminder workflows.
* **Local Tunneling**: `pyngrok` for seamless local development webhook integration with Telegram.

## 🚀 Setup & Installation

### 1. Prerequisites
- **Python 3.11+** installed.
- **Google Cloud Platform (GCP) Project** with Vertex AI, Speech-to-Text, Text-to-Speech, and Firestore APIs enabled.
- A **Telegram Bot Token** generated via [@BotFather](https://t.me/botfather).

### 2. Clone & Install Dependencies
This project uses [uv](https://github.com/astral-sh/uv) (or pip) for fast dependency management.
```bash
git clone <your-repo-url>
cd AgriSaathi
# Using uv (recommended)
uv venv
uv pip install -r pyproject.toml

# Or using pip
pip install .
```

### 3. Environment Variables
Create a `.env` file in the root directory:
```env
TELEGRAM_TOKEN=your_telegram_bot_token_here
GCP_PROJECT_ID=sam-sang-493608
GCP_REGION=us-central1
USE_NGROK=True
PORT=5000
```

### 4. GCP Authentication
Ensure you have a valid Service Account key with the requisite permissions for Vertex AI, Speech, and Firestore.
Save it as `credentials.json` in the root directory.

### 5. Run the Bot
```bash
uv run app.py
```
*On startup, the app will automatically spawn an Ngrok tunnel and register the webhook with Telegram.*

## 📜 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

---
<div align="center">
  <i>Empowering agriculture through conversational AI.</i>
</div>