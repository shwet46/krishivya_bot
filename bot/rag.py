import os
import vertexai
from vertexai.generative_models import GenerativeModel, Part
from dotenv import load_dotenv

load_dotenv()

GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")
GCP_REGION = os.getenv("GCP_REGION", "asia-south1")

vertexai.init(project=GCP_PROJECT_ID, location=GCP_REGION)

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

model = GenerativeModel(
    "gemini-2.5-flash",
    system_instruction=SYSTEM_PROMPT,
)

def generate_response(user_input, image_bytes=None):
    """
    Generate a response using the Gemini model.
    Supports both text and multimodal (image) input.
    """
    if image_bytes:
        image_part = Part.from_data(data=image_bytes, mime_type="image/jpeg")
        response = model.generate_content([user_input, image_part])
    else:
        response = model.generate_content(user_input)
    
    return response.text
