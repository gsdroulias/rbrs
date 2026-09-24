from google import genai

from rbrs.profile.models import SMEProfile


def extract_profile_from_text(text: str, api_key: str | None = None) -> SMEProfile:
    """
    Uses Gemini to extract an SME profile from unstructured text.
    Strictly uses Structured Outputs to guarantee Pydantic schema validation.
    """
    client = genai.Client(api_key=api_key)
    prompt = "Extract the SME profile attributes from the following text. Be strictly objective and abstain from hallucinating values."
    
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=f"{prompt}\n\n{text}",
        config={
            "response_mime_type": "application/json",
            "response_schema": SMEProfile,
            "temperature": 0.0
        }
    )
    
    if not response.text:
        raise ValueError("Failed to extract profile: Empty response from LLM.")
        
    return SMEProfile.model_validate_json(response.text)
