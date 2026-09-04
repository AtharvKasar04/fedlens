import logging
import yfinance as yf
import pandas as pd
from datetime import timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.analysis.llm_client import FedLensLLM
from app.db.models import MarketReaction

logger = logging.getLogger(__name__)

class MarketExplanation(BaseModel):
    explanation: str

class MarketReactionEngine:
    def __init__(self, llm_client: FedLensLLM = None):
        self.llm = llm_client or FedLensLLM()
        
    def fetch_market_reaction(self, meeting_date):
        """
        Fetches SPY and TLT data for the meeting date and the previous trading day 
        to calculate the 1-day percentage change.
        """
        # Fetch a 5-day window ending on the day after the meeting to ensure we capture
        # the meeting day and the previous valid trading day.
        end_date = meeting_date + timedelta(days=1)
        start_date = meeting_date - timedelta(days=5)
        
        try:
            logger.info(f"Fetching market data for meeting on {meeting_date}")
            spy_data = yf.download("SPY", start=start_date.isoformat(), end=end_date.isoformat(), progress=False)
            tlt_data = yf.download("TLT", start=start_date.isoformat(), end=end_date.isoformat(), progress=False)
            
            if spy_data.empty or tlt_data.empty or len(spy_data) < 2:
                logger.warning(f"Insufficient market data for {meeting_date}")
                return None, None
                
            # Handle multi-level columns from yfinance >= 0.2.0
            if isinstance(spy_data.columns, pd.MultiIndex):
                spy_closes = spy_data['Close']['SPY']
                tlt_closes = tlt_data['Close']['TLT']
            else:
                spy_closes = spy_data['Close']
                tlt_closes = tlt_data['Close']
                
            spy_prev = spy_closes.iloc[-2].item()
            spy_curr = spy_closes.iloc[-1].item()
            spy_pct = ((spy_curr - spy_prev) / spy_prev) * 100
            
            tlt_prev = tlt_closes.iloc[-2].item()
            tlt_curr = tlt_closes.iloc[-1].item()
            tlt_pct = ((tlt_curr - tlt_prev) / tlt_prev) * 100
            
            return Decimal(str(round(spy_pct, 2))), Decimal(str(round(tlt_pct, 2)))
            
        except Exception as e:
            logger.error(f"Error fetching yfinance data: {e}")
            return None, None

    def interpret_reaction(self, spy_pct, tlt_pct, diff_summary):
        spy_pct_str = str(spy_pct)
        tlt_pct_str = str(tlt_pct)
        prompt = f"""
        The Federal Reserve just released their FOMC statement.
        Compared to the previous meeting, here is what changed:
        {diff_summary}
        
        The stock market (S&P 500) reacted by moving {spy_pct_str}%.
        The bond market (20+ Year Treasuries) reacted by moving {tlt_pct_str}%.
        
        CRITICAL INSTRUCTION FOR NUMBERS: 
        If you reference fractional interest rates (e.g., "4-1/4", "4-1/2", "4-3/4") from the Fed's statement, you MUST convert them to standard decimals (e.g., 4.25%, 4.50%, 4.75%) in your response.
        
        Explain WHY the market reacted this way based on the specific changes in the Fed's statement.
        Keep it to 2-3 concise paragraphs. Focus on the macroeconomic implications of the text changes.
        """
        
        response = self.llm.client.chat.completions.create(
            model=self.llm.model,
            response_model=MarketExplanation,
            messages=[
                {"role": "system", "content": "You are an expert macro-financial analyst."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_retries=3
        )
        
        from app.core.token_logger import log_token_usage
        if hasattr(response, "_raw_response") and hasattr(response._raw_response, "usage"):
            log_token_usage("market_reaction_interpretation", response._raw_response.usage, self.llm.model)
        
        return response.explanation
        
    def process_meeting(self, meeting_id, meeting_date, diff_summary, db: Session):
        existing = db.query(MarketReaction).filter(MarketReaction.meeting_id == meeting_id).first()
        if existing:
            logger.info(f"Market reaction already exists for {meeting_date}")
            return existing
            
        spy_pct, tlt_pct = self.fetch_market_reaction(meeting_date)
        if spy_pct is None:
            return None
            
        logger.info(f"Interpreting market reaction for {meeting_date}")
        explanation = self.interpret_reaction(spy_pct, tlt_pct, diff_summary)
        
        reaction = MarketReaction(
            meeting_id=meeting_id,
            spy_change_pct=spy_pct,
            tlt_change_pct=tlt_pct,
            ai_explanation=explanation
        )
        db.add(reaction)
        db.commit()
        db.refresh(reaction)
        return reaction
