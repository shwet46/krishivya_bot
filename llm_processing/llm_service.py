import base64
import json
import os

import requests
from dotenv import load_dotenv

load_dotenv()

FEATHERLESS_API_KEY = os.getenv("FEATHERLESS_API_KEY", "")
FEATHERLESS_API_URL = os.getenv("FEATHERLESS_API_URL", "https://api.featherless.ai/v1/chat/completions")
FEATHERLESS_MULTIMODAL_MODEL = os.getenv("FEATHERLESS_MULTIMODAL_MODEL", "meta-llama/Llama-3.2-11B-Vision-Instruct")

SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "")
SARVAM_CHAT_API_URL = os.getenv("SARVAM_CHAT_API_URL", "https://api.sarvam.ai/chat/completions")
SARVAM_CHAT_MODEL = os.getenv("SARVAM_CHAT_MODEL", "sarvam-30b")

SYSTEM_PROMPT = """You are Krishivya, a knowledgeable and empathetic Indian Female Agriculture Officer.
Speak in a polite, professional, and helpful female tone.

CORE CAPABILITIES:
1. Multimodal Crop Diagnosis: If a user sends an image, analyze it alongside any provided text description to identify pests, diseases, or nutrient deficiencies. Always consider the user's description (e.g., "sown 10 days ago") as vital context for your diagnosis. Provide organic and chemical remedies.
2. Farming Advice: Answer questions ONLY about farming, soil, weather, and government schemes.
3. Multilingual: Detect the user's language and respond in the same language.
4. Agricultural Reminders: You can help farmers stay organized. If a user asks to be reminded of a task (e.g., "Remind me to spray fertilizer tomorrow at 10 AM"), confirm the activity and the time.

ESCALATION RULE:
If a query is complex, involves high-risk pesticide chemicals, or if you are unsure of the diagnosis from an image, explicitly tell the user:
"I am redirecting this query to the nearest Agriculture Officer for expert verification. They will contact you shortly."
Trigger this whenever you cannot provide a 100% certain answer.
"""

WELCOME_MESSAGE = """🌾 Namaste!
I'm Krishivya, your AI Agriculture Officer.

Ask me about crops, soil, fertilizers, weather, or farming practices.
You can send text or voice messages in your language.
"""


def _extract_text_from_chat_response(payload: dict) -> str:
    choices = payload.get("choices") or []
    if choices:
        message = choices[0].get("message") or {}
        content = message.get("content")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict):
                    txt = item.get("text")
                    if txt:
                        parts.append(txt)
            if parts:
                return "\n".join(parts).strip()

    if "response" in payload and isinstance(payload["response"], str):
        return payload["response"].strip()

    if "output" in payload and isinstance(payload["output"], str):
        return payload["output"].strip()

    return ""


def _call_featherless(messages: list[dict], model: str) -> str:
    if not FEATHERLESS_API_KEY:
        raise ValueError("Missing FEATHERLESS_API_KEY in environment")

    response = requests.post(
        FEATHERLESS_API_URL,
        headers={
            "Authorization": f"Bearer {FEATHERLESS_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 900,
        },
        timeout=60,
    )
    response.raise_for_status()
    text = _extract_text_from_chat_response(response.json())
    if not text:
        raise ValueError("Featherless returned an empty response")
    return text


def _call_sarvam(messages: list[dict]) -> str:
    if not SARVAM_API_KEY:
        raise ValueError("Missing SARVAM_API_KEY in environment")

    response = requests.post(
        SARVAM_CHAT_API_URL,
        headers={
            "api-subscription-key": SARVAM_API_KEY,
            "Authorization": f"Bearer {SARVAM_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": SARVAM_CHAT_MODEL,
            "messages": messages,
            "temperature": 0.35,
            "max_tokens": 900,
        },
        timeout=60,
    )
    response.raise_for_status()
    text = _extract_text_from_chat_response(response.json())
    if not text:
        raise ValueError("Sarvam returned an empty response")
    return text


def _build_featherless_multimodal_messages(user_input: str, image_bytes: bytes) -> list[dict]:
    image_data = base64.b64encode(image_bytes).decode("utf-8")
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": user_input},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{image_data}"
                    },
                },
            ],
        },
    ]


def generate_response(user_input: str, image_bytes: bytes | None = None) -> str:
    """Generate multilingual farming responses via Sarvam and Featherless."""
    if image_bytes:
        draft = _call_featherless(
            _build_featherless_multimodal_messages(user_input, image_bytes),
            FEATHERLESS_MULTIMODAL_MODEL,
        )
        try:
            return _call_sarvam(
                [
                    {
                        "role": "system",
                        "content": "Rewrite the assistant draft in the same language as the user message. Keep agriculture facts unchanged, concise, and practical.",
                    },
                    {
                        "role": "user",
                        "content": f"User message:\n{user_input}\n\nAssistant draft:\n{draft}",
                    },
                ]
            )
        except Exception:
            return draft

    try:
        return _call_sarvam(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_input},
            ]
        )
    except Exception:
        return _call_featherless(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_input},
            ],
            os.getenv("FEATHERLESS_TEXT_MODEL", FEATHERLESS_MULTIMODAL_MODEL),
        )


def parse_reminder_request(user_text: str, now_text: str) -> dict:
    prompt = f"""
Extract the 'task' and 'delay_seconds' from this reminder request.
Current datetime: {now_text}

Rules:
1. If user says tomorrow at a time, compute delay from now.
2. If user says 'in 5 minutes', delay_seconds is 300.
3. Return ONLY JSON with keys: task, delay_seconds.
4. If no clear time: {{\"task\": null, \"delay_seconds\": 0}}

User request: {user_text}
""".strip()

    raw = _call_sarvam(
        [
            {
                "role": "system",
                "content": "You only return strict JSON and no markdown.",
            },
            {"role": "user", "content": prompt},
        ]
    )
    cleaned = raw.replace("```json", "").replace("```", "").strip()
    data = json.loads(cleaned)
    if not isinstance(data, dict):
        raise ValueError("Reminder parser did not return a JSON object")
    return data
