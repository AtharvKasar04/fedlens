import logging
import json
from datetime import datetime
from pydantic import BaseModel, Field

from app.ingestion.fed_scraper import FedScraper
from app.analysis.llm_client import FedLensLLM
from app.db.session import SessionLocal
from app.db.models import FOMCMeeting, FOMCDocument, PolicyAssessment

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Define the full Pydantic schema for the LLM to extract
class AssessmentDimension(BaseModel):
    grade: str = Field(description="Must be 'improving', 'deteriorating', or 'stable'")
    evidence: str = Field(description="The exact quote from the text that justifies this grade")

class FullPolicyAssessment(BaseModel):
    inflation: AssessmentDimension
    labor_market: AssessmentDimension
    economic_growth: AssessmentDimension
    overall_stance: AssessmentDimension

class AnalysisPipeline:
    def __init__(self):
        self.scraper = FedScraper()
        self.llm = FedLensLLM()
        
    def process_meeting(self, date_str: str):
        """Processes a single meeting: Scrape -> DB -> LLM Extract -> DB"""
        db = SessionLocal()
        
        try:
            # 1. Scrape the statement
            logger.info(f"Processing meeting: {date_str}")
            statement_text = self.scraper.get_statement(date_str)
            
            if not statement_text:
                logger.error(f"Could not find statement for {date_str}")
                return
                
            meeting_date = datetime.strptime(date_str, "%Y%m%d").date()
            
            # 2. Save or get the Meeting in the Database
            meeting = db.query(FOMCMeeting).filter(FOMCMeeting.meeting_date == meeting_date).first()
            if not meeting:
                meeting = FOMCMeeting(meeting_date=meeting_date, statement_date=meeting_date)
                db.add(meeting)
                db.commit()
                db.refresh(meeting)
                
            # 3. Save the Document in the Database
            doc = db.query(FOMCDocument).filter(
                FOMCDocument.meeting_id == meeting.id,
                FOMCDocument.doc_type == "statement"
            ).first()
            
            if not doc:
                url = f"https://www.federalreserve.gov/newsevents/pressreleases/monetary{date_str}a.htm"
                doc = FOMCDocument(
                    meeting_id=meeting.id,
                    doc_type="statement",
                    source_url=url,
                    raw_text=statement_text,
                    word_count=len(statement_text.split())
                )
                db.add(doc)
                db.commit()
                db.refresh(doc)
                
            logger.info(f"Successfully saved statement to DB. Word count: {doc.word_count}")
            
            # 4. Have the LLM extract the policy assessment
            # Check if we already did it to avoid double-charging the API
            existing_assessment = db.query(PolicyAssessment).filter(PolicyAssessment.meeting_id == meeting.id).first()
            if existing_assessment:
                logger.info("Assessment already exists in DB. Skipping LLM call.")
                return
                
            logger.info("Sending statement to LLM for grading...")
            prompt = f"""
            You are an expert Federal Reserve policy analyst.
            Read the following FOMC statement and extract the policy assessments.
            
            STATEMENT TEXT:
            {statement_text}
            """
            
            response = self.llm.client.chat.completions.create(
                model=self.llm.model,
                response_model=FullPolicyAssessment,
                messages=[{"role": "user", "content": prompt}]
            )
            
            # 5. Save the Assessment to the Database
            assessment = PolicyAssessment(
                meeting_id=meeting.id,
                document_id=doc.id,
                inflation_assessment=response.inflation.model_dump(),
                labor_assessment=response.labor_market.model_dump(),
                growth_assessment=response.economic_growth.model_dump(),
                overall_stance=response.overall_stance.model_dump(),
                raw_llm_output=response.model_dump(),
                extraction_model=self.llm.model
            )
            
            db.add(assessment)
            db.commit()
            logger.info("Successfully saved LLM assessment to DB!")
            
        except Exception as e:
            logger.error(f"Error processing meeting {date_str}: {e}")
            db.rollback()
        finally:
            db.close()

if __name__ == "__main__":
    pipeline = AnalysisPipeline()
    # Let's test it on the most recent meeting: September 18, 2024
    print("\n--- RUNNING PIPELINE ON SEPT 2024 MEETING ---\n")
    pipeline.process_meeting("20240918")
    print("\nPipeline finished.")
