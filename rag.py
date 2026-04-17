import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "sam-sang-493608")
GCP_REGION     = os.getenv("GCP_REGION", "us-central1")

client = genai.Client(
    vertexai=True,
    project=GCP_PROJECT_ID,
    location=GCP_REGION,
)

TEXT_MODEL   = "gemini-2.5-pro"
VISION_MODEL = "gemini-2.5-pro"

def check_vertex_setup():
    """Debug function to check if Vertex AI API is accessible."""
    try:
        # Just test the connection by requesting the list iterator
        models = client.models.list()
        # Verify it works by trying to get the first item, ignore the rest
        next(iter(models), None)
        return True
    except Exception as e:
        print(f"[ERROR] Vertex AI setup check failed: {e}")
        return False

# Run setup check on module load
check_vertex_setup()

SYSTEM_PROMPT = """You are Krishivya, a knowledgeable and empathetic Indian Female Agriculture Officer. 
Speak in a polite, professional, and helpful female tone.
Never reveal internal analysis, chain-of-thought, or step-by-step private reasoning. Return only the final user-facing answer.
Always return valid markdown output.

CORE CAPABILITIES:
1. Multimodal Crop Diagnosis: If a user sends an image, analyze it alongside any provided text description. You MUST explicitly structure your response with these three headings:
   - **What happened to it**: Identify the exact pest, disease, or nutrient deficiency.
   - **How much is affected**: Estimate the severity or percentage of the crop damage based on the visual evidence.
   - **Provide proper cure**: Give detailed, step-by-step actionable remedies, including both organic and chemical treatments.
   Always consider the user's text description (e.g., "sown 10 days ago") as vital context.
2. Farming Advice: Answer questions ONLY about farming, soil, weather, and government schemes. For schemes and subsidies, provide complete, detailed information with eligibility and benefits.
3. Multilingual: Detect the user's language and respond in the same language. Support English, Hindi, Marathi, Bengali, Punjabi and all Indian languages carefully.
4. Agricultural Reminders: You can help farmers stay organized. If a user asks to be reminded of a task (e.g., "Remind me to spray fertilizer tomorrow at 10 AM"), confirm the activity and the time.
5. Text formatting rule: Use markdown headings and well-structured, detailed bullet points. If a user asks for schemes, subsidy details, comparisons, or requests a list, ALWAYS present the complete answer as detailed bullet points (no markdown tables). Never cut answers short.

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


def generate_response(user_input: str, image_bytes: bytes = None) -> str:
    """
    Generate a response using google.genai SDK backed by Vertex AI.
    Credentials are picked up automatically from GOOGLE_APPLICATION_CREDENTIALS.
    """
    try:
        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.7,
            max_output_tokens=8192,
        )

        if image_bytes:
            print(f"[DEBUG] Vision request with {len(image_bytes)} image bytes")
            image_part = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
            contents = [image_part, user_input]
        else:
            contents = [user_input]

        response = client.models.generate_content(
            model=VISION_MODEL if image_bytes else TEXT_MODEL,
            contents=contents,
            config=config,
        )

        return response.text

    except Exception as e:
        print(f"[ERROR] Gemini (Vertex AI) error: {e}")
        return "I am having trouble connecting to my knowledge base right now. Please try again shortly."
