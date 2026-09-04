"""
Large Language Model (LLM) Integration Client

This module provides the primary interface for communicating with OpenAI's API. It leverages the `instructor` library to enforce strict schema validation on the LLM's output, ensuring that the model responds with well-structured JSON data (defined by Pydantic models) rather than unstructured text. This structural guarantee is critical for downstream database insertion and algorithmic processing.

Configuration Parameters:
- Model Selection: Driven by the `LLM_MODEL` environment variable (default: `gpt-4o-mini`).
- Provider: Configured for OpenAI by default, but the `instructor` wrapper can be adapted for Anthropic or other SDKs if required.
"""
import os
import instructor
from openai import OpenAI
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from app.core.logger import setup_logger

load_dotenv()

logger = setup_logger(__name__)

class AssessmentGrade(BaseModel):
    """
    This class defines the exact shape of the data we want from the AI. 
    The AI will literally read the 'description' fields below to understand what it needs to extract.
    """
    grade: str = Field(description="Must be 'improving', 'deteriorating', or 'stable'")
    evidence: str = Field(description="Exact quote from the text justifying the grade")

class FedLensLLM:
    """
    The main AI wrapper. We use this throughout the app whenever we need to 'think' or extract data.
    """
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key or "paste_your" in api_key:
            raise ValueError("OPENAI_API_KEY is not set correctly in .env")
            
        self.model = os.getenv("LLM_MODEL", "gpt-4o-mini")
        
        # We wrap the standard OpenAI client with Instructor to force JSON outputs
        self.client = instructor.from_openai(OpenAI(api_key=api_key))
        
    def test_extraction(self) -> AssessmentGrade:
        """Simple test to verify the LLM can extract structured data."""
        logger.info(f"Testing LLM extraction using model: {self.model}")
        
        sample_text = "Recent indicators suggest that economic activity has continued to expand at a solid pace. Job gains have slowed, and the unemployment rate has moved up but remains low."
        
        prompt = f"""
        You are an expert Federal Reserve analyst. Read the following text and grade the labor market.
        
        TEXT:
        {sample_text}
        """
        
        response = self.client.chat.completions.create(
            model=self.model,
            response_model=AssessmentGrade,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        from app.core.token_logger import log_token_usage
        if hasattr(response, "_raw_response") and hasattr(response._raw_response, "usage"):
            log_token_usage("test_extraction", response._raw_response.usage, self.model)
        
        return response

if __name__ == "__main__":
    llm = FedLensLLM()
    print("Testing OpenAI API connection...")
    
    try:
        result = llm.test_extraction()
        print("\nSUCCESS! The AI successfully read the text and extracted:")
        print(f"Grade: {result.grade}")
        print(f"Evidence: \"{result.evidence}\"")
    except Exception as e:
        print(f"\nFAILED: {e}")
