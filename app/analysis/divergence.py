"""
Economic Divergence Detection Engine

This module serves as the auditing layer of the application. It cross-references the qualitative assessments extracted from FOMC statements against the quantitative macroeconomic data retrieved from FRED. 

Key Operations:
- Temporal Integrity: The engine strictly filters FRED data using `release_date <= meeting.meeting_date`. This guarantees that the system evaluates the Federal Reserve based exclusively on data that was publicly available at the time of their statements, completely eliminating look-ahead bias.
- Contradiction Analysis: If the mathematical trend of an economic indicator (e.g., Unemployment Rate) contradicts the qualitative grade assigned by the Fed (e.g., "deteriorating"), the system flags a divergence.
- AI Explanation: An LLM is prompted to provide a step-by-step interpretation of why the divergence occurred and its potential severity.

Configuration Parameters:
- Indicator Mapping: The logic bridging specific LLM extraction fields (like `labor_assessment`) to specific FRED series (like `UNRATE`) is defined within `check_meeting_divergence`.
"""
import logging
from pydantic import BaseModel, Field

from app.analysis.llm_client import FedLensLLM
from app.db.session import SessionLocal
from app.db.models import FOMCMeeting, PolicyAssessment, EconomicSeries, EconomicObservation, Divergence
from app.core.logger import setup_logger

logger = setup_logger(__name__)

class DivergenceReport(BaseModel):
    explanation: str = Field(description="Step-by-step reasoning of whether the Fed's claim matches the actual data.")
    is_divergent: bool = Field(description="True ONLY IF the Fed's claim contradicts the actual economic data trend. False if they match.")
    severity: str = Field(description="Low, Medium, or High severity of the divergence.")

class DivergenceDetector:
    def __init__(self):
        self.llm = FedLensLLM()
        
    def check_meeting_divergence(self, date_str: str):
        db = SessionLocal()
        try:
            # Get the meeting and assessment
            meeting = db.query(FOMCMeeting).filter(FOMCMeeting.meeting_date == f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}").first()
            if not meeting:
                logger.error("Meeting not found.")
                return
                
            assessment = db.query(PolicyAssessment).filter(PolicyAssessment.meeting_id == meeting.id).first()
            if not assessment:
                logger.error("No policy assessment found for this meeting.")
                return
                
            # Let's check Labor Market Divergence (UNRATE)
            unrate_series = db.query(EconomicSeries).filter(EconomicSeries.fred_id == "UNRATE").first()
            
            # Get the most recent observation that was AVAILABLE (release_date <= meeting_date) BEFORE the meeting date
            latest_unrate = db.query(EconomicObservation).filter(
                EconomicObservation.series_id == unrate_series.id,
                EconomicObservation.release_date <= meeting.meeting_date
            ).order_by(EconomicObservation.observation_date.desc()).first()
            
            if not latest_unrate:
                logger.warning(f"No UNRATE data available prior to {meeting.meeting_date}")
                return
                
            # Get the previous observation to see the trend
            prev_unrate = db.query(EconomicObservation).filter(
                EconomicObservation.series_id == unrate_series.id,
                EconomicObservation.observation_date < latest_unrate.observation_date,
                EconomicObservation.release_date <= meeting.meeting_date
            ).order_by(EconomicObservation.observation_date.desc()).first()
            
            if not prev_unrate:
                return

            # Check if divergence already exists
            existing_divergence = db.query(Divergence).filter(
                Divergence.meeting_id == meeting.id,
                Divergence.series_id == unrate_series.id
            ).first()
            if existing_divergence:
                logger.info("Divergence for this meeting and series already checked. Skipping.")
                return
            
            labor_grade = assessment.labor_assessment['grade']
            labor_evidence = assessment.labor_assessment['evidence']
            
            logger.info("Asking LLM to detect divergence in Labor Market...")
            
            prompt = f"""
            You are an expert Federal Reserve auditor. Your job is to catch the Fed if their words contradict the actual economic data.
            
            DEFINITION OF DIVERGENCE:
            A divergence occurs when the Fed claims a metric is moving in one direction, but the actual data shows it moving in the opposite direction.
            
            FED'S CLAIM (from their statement):
            Grade: {labor_grade}
            Evidence: "{labor_evidence}"
            
            ACTUAL ECONOMIC DATA (Unemployment Rate available at the time of the meeting):
            Previous Month: {prev_unrate.value}%
            Current Month: {latest_unrate.value}%
            Trend: {'Up (Worse)' if latest_unrate.value > prev_unrate.value else 'Down (Better)' if latest_unrate.value < prev_unrate.value else 'Flat'}
            
            First, write a step-by-step explanation comparing the Fed's claim to the actual data trend.
            Then, determine if there is a divergence.
            """
            
            response = self.llm.client.chat.completions.create(
                model=self.llm.model,
                response_model=DivergenceReport,
                messages=[{"role": "user", "content": prompt}]
            )
            
            logger.debug("Received divergence report from LLM.", extra={"extra_data": {"divergence_response": response.model_dump()}})
            
            divergence = Divergence(
                meeting_id=meeting.id,
                series_id=unrate_series.id,
                fed_claim_text=labor_evidence,
                fed_claim_direction=labor_grade,
                data_direction='deteriorating' if latest_unrate.value > prev_unrate.value else 'improving' if latest_unrate.value < prev_unrate.value else 'stable',
                data_summary={
                    "previous_value": float(prev_unrate.value),
                    "current_value": float(latest_unrate.value),
                    "previous_date": prev_unrate.observation_date.isoformat(),
                    "current_date": latest_unrate.observation_date.isoformat()
                },
                explanation=response.explanation,
                severity=response.severity,
                is_divergent=response.is_divergent,
                divergence_score=1.0 if response.is_divergent else 0.0 # simple score for now
            )
            
            db.add(divergence)
            db.commit()
            
            print(f"Saved divergence check for meeting {meeting.meeting_date} (Is Divergent: {response.is_divergent})")
            
        except Exception as e:
            logger.error(f"Error detecting divergence: {e}")
            db.rollback()
        finally:
            db.close()

if __name__ == "__main__":
    detector = DivergenceDetector()
    detector.check_meeting_divergence("20240918")
