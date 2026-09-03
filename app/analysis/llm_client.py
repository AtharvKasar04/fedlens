import os
import logging
import instructor
from openai import OpenAI
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AssessmentGrade(BaseModel):
    grade: str = Field(description="Must be 'improving', 'deteriorating', or 'stable'")
    evidence: str = Field(description="Exact quote from the text justifying the grade")

class FedLensLLM:
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
