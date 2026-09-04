"""
Core Analysis Orchestrator

This module coordinates the complete lifecycle of FOMC document processing. It sequentially executes data retrieval, machine learning extraction, and divergence detection to form a comprehensive policy analysis.

Execution Flow:
1. Ingestion: Invokes `FedScraper` to acquire the raw text of FOMC press releases.
2. Persistence: Commits the raw document metadata to the PostgreSQL database.
3. LLM Extraction: Prompts the LLM (via `FedLensLLM`) to perform a structured grading of the economy (improving, deteriorating, stable) based purely on the text.
4. Temporal Comparison: Computes text diffs against the prior meeting and generates an interpretation of the hawkish or dovish shifts.
5. Auditing: Triggers the `DivergenceDetector` to compare the Fed's claims against real-world economic data.

Configuration Parameters:
- Execution Order: Controlled by the `process_meeting` method.
- Prompt Engineering: The instructions provided to the LLM for structured extraction are defined within the `prompt` variables throughout the pipeline.
"""
import logging
import json
from datetime import datetime
from pydantic import BaseModel, Field

from app.ingestion.fed_scraper import FedScraper
from app.analysis.llm_client import FedLensLLM
from app.analysis.differ import compute_text_diff
from app.analysis.divergence import DivergenceDetector
from app.analysis.market import MarketReactionEngine
from app.db.session import SessionLocal
from app.db.models import FOMCMeeting, FOMCDocument, PolicyAssessment, MeetingComparison
from app.core.logger import setup_logger

logger = setup_logger(__name__)

# Define the full Pydantic schema for the LLM to extract
class AssessmentDimension(BaseModel):
    grade: str = Field(description="Must be 'improving', 'deteriorating', or 'stable'")
    evidence: str = Field(description="The exact quote from the text that justifies this grade")

class FullPolicyAssessment(BaseModel):
    inflation: AssessmentDimension
    labor_market: AssessmentDimension
    economic_growth: AssessmentDimension
    financial_conditions: AssessmentDimension
    forward_guidance: AssessmentDimension
    overall_stance: AssessmentDimension

class ChangeInterpretation(BaseModel):
    summary_of_changes: str = Field(description="A 1-2 sentence summary of what changed.")
    hawkish_or_dovish: str = Field(description="Did the changes make the statement more 'hawkish', 'dovish', or 'neutral'?")
    key_takeaway: str = Field(description="Why these specific word changes matter to the market.")

class AnalysisPipeline:
    def __init__(self):
        self.scraper = FedScraper()
        self.llm = FedLensLLM()
        self.divergence_detector = DivergenceDetector()
        
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
            else:
                logger.info("Sending statement to LLM for grading...")
                prompt = f"""
                You are an expert Federal Reserve policy analyst.
                Read the following FOMC statement and extract the policy assessments.
                
                CRITICAL INSTRUCTION FOR NUMBERS: 
                If the statement uses fractional interest rates (e.g., "4-1/4", "4-1/2", "4-3/4"), you MUST convert them to standard decimals (e.g., 4.25%, 4.50%, 4.75%) in your response.
                
                STATEMENT TEXT:
                {statement_text}
                """
                
                response = self.llm.client.chat.completions.create(
                    model=self.llm.model,
                    response_model=FullPolicyAssessment,
                    messages=[{"role": "user", "content": prompt}]
                )
                
                from app.core.token_logger import log_token_usage
                if hasattr(response, "_raw_response") and hasattr(response._raw_response, "usage"):
                    log_token_usage("pipeline_policy_assessment", response._raw_response.usage, self.llm.model)
                
                logger.debug("Received response from LLM for policy assessment.", extra={"extra_data": {"response": response.model_dump()}})
                
                # 5. Save the Assessment to the Database
                assessment = PolicyAssessment(
                    meeting_id=meeting.id,
                    document_id=doc.id,
                    inflation_assessment=response.inflation.model_dump(),
                    labor_assessment=response.labor_market.model_dump(),
                    growth_assessment=response.economic_growth.model_dump(),
                    financial_conditions=response.financial_conditions.model_dump(),
                    forward_guidance=response.forward_guidance.model_dump(),
                    overall_stance=response.overall_stance.model_dump(),
                    raw_llm_output=response.model_dump(),
                    extraction_model=self.llm.model
                )
                
                db.add(assessment)
                db.commit()
                logger.info("Successfully saved LLM assessment to DB!")
            
            # 6. Change Detection (Diff against previous meeting)
            previous_meeting = db.query(FOMCMeeting).filter(
                FOMCMeeting.meeting_date < meeting.meeting_date
            ).order_by(FOMCMeeting.meeting_date.desc()).first()
            
            if previous_meeting:
                logger.info(f"Found previous meeting ({previous_meeting.meeting_date}). Computing diff...")
                prev_doc = db.query(FOMCDocument).filter(
                    FOMCDocument.meeting_id == previous_meeting.id,
                    FOMCDocument.doc_type == "statement"
                ).first()
                
                if prev_doc:
                    # Check if we already compared them
                    existing_comp = db.query(MeetingComparison).filter(
                        MeetingComparison.base_meeting_id == previous_meeting.id,
                        MeetingComparison.comp_meeting_id == meeting.id
                    ).first()
                    
                    if not existing_comp:
                        diff_text = compute_text_diff(prev_doc.raw_text, statement_text)
                        
                        logger.info("Asking LLM to interpret the changes...")
                        diff_prompt = f"""
                        You are an expert Federal Reserve policy analyst.
                        I am providing you with a redline diff between the previous FOMC statement and the new one.
                        [ADDED] means new words the Fed inserted.
                        [DELETED] means words the Fed removed.
                        
                        CRITICAL INSTRUCTION FOR NUMBERS: 
                        If the text uses fractional interest rates (e.g., "4-1/4", "4-1/2", "4-3/4"), you MUST convert them to standard decimals (e.g., 4.25%, 4.50%, 4.75%) in your response.
                        
                        DIFF TEXT:
                        {diff_text}
                        
                        Interpret what these specific changes mean for monetary policy.
                        """
                        
                        diff_response = self.llm.client.chat.completions.create(
                            model=self.llm.model,
                            response_model=ChangeInterpretation,
                            messages=[{"role": "user", "content": diff_prompt}]
                        )
                        
                        if hasattr(diff_response, "_raw_response") and hasattr(diff_response._raw_response, "usage"):
                            log_token_usage("pipeline_diff_interpretation", diff_response._raw_response.usage, self.llm.model)
                        
                        logger.debug("Received diff interpretation from LLM.", extra={"extra_data": {"diff_response": diff_response.model_dump()}})
                        
                        comparison = MeetingComparison(
                            base_meeting_id=previous_meeting.id,
                            comp_meeting_id=meeting.id,
                            text_diff={"raw_diff": diff_text},
                            llm_interpretation=diff_response.model_dump_json()
                        )
                        
                        db.add(comparison)
                        db.commit()
                        logger.info("Saved meeting comparison diff to DB.")
                        
                    else:
                        logger.info("Meeting comparison already exists. Skipping diff.")
                        
                    # Market Reaction Engine
                    market_engine = MarketReactionEngine(llm_client=self.llm)
                    logger.info("Triggering Market Reaction Engine...")
                    
                    # Ensure we have diff summary even if existing
                    diff_summary = ""
                    if not existing_comp:
                        diff_summary = diff_response.summary_of_changes
                    else:
                        import json
                        try:
                            interp = json.loads(existing_comp.llm_interpretation)
                            diff_summary = interp.get("summary_of_changes", "")
                        except:
                            diff_summary = existing_comp.llm_interpretation
                            
                    market_engine.process_meeting(meeting.id, meeting.meeting_date, diff_summary, db)
                    
                else:
                    logger.info("Previous document not found, skipping diff.")
            
        except Exception as e:
            logger.error(f"Error processing meeting {date_str}: {e}")
            db.rollback()
        finally:
            db.close()
            
        # 7. Divergence Detection (runs in its own session inside check_meeting_divergence)
        logger.info(f"Running Divergence Detection for {date_str}...")
        self.divergence_detector.check_meeting_divergence(date_str)

if __name__ == "__main__":
    pipeline = AnalysisPipeline()
    dates = pipeline.scraper.get_recent_meeting_dates()
    
    # Process from oldest to newest so diffs work correctly
    # The dates list from the scraper is newest first, so we reverse it.
    for date in reversed(dates):
        print(f"\n--- RUNNING PIPELINE ON MEETING ({date}) ---")
        pipeline.process_meeting(date)
    
    print("\nPipeline finished.")
