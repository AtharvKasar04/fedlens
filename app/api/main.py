import json
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional
import uvicorn

from app.db.session import SessionLocal
from app.db.models import FOMCMeeting, PolicyAssessment, MeetingComparison
from app.core.logger import setup_logger

logger = setup_logger(__name__)

app = FastAPI(
    title="FedLens API",
    description="Evidence-grounded FOMC monetary policy intelligence system.",
    version="1.0.0",
)

# Fix: Add CORS so the Next.js frontend (port 3000) can call this API (port 8000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/")
def read_root():
    return {"service": "FedLens API", "version": "1.0.0", "status": "ok"}


@app.get("/api/v1/meetings")
def get_meetings(db: Session = Depends(get_db)):
    """List all FOMC meetings in the database."""
    meetings = db.query(FOMCMeeting).order_by(FOMCMeeting.meeting_date.desc()).all()
    return [
        {
            "id": str(m.id),
            "date": str(m.meeting_date),
            "rate_decision": m.rate_decision,
        }
        for m in meetings
    ]


@app.get("/api/v1/meetings/{date_str}")
def get_meeting_detail(date_str: str, db: Session = Depends(get_db)):
    """
    Full intelligence report for a specific meeting.
    Returns assessment dimensions + change detection summary.
    Format: YYYY-MM-DD
    """
    meeting = db.query(FOMCMeeting).filter(
        FOMCMeeting.meeting_date == date_str
    ).first()
    if not meeting:
        raise HTTPException(status_code=404, detail=f"Meeting {date_str} not found")

    assessment = db.query(PolicyAssessment).filter(
        PolicyAssessment.meeting_id == meeting.id
    ).first()

    comparison = db.query(MeetingComparison).filter(
        MeetingComparison.comp_meeting_id == meeting.id
    ).first()

    response_data: dict = {"meeting_date": str(meeting.meeting_date)}

    if assessment and assessment.raw_llm_output:
        raw = assessment.raw_llm_output
        if isinstance(raw, str):
            raw = json.loads(raw)
        response_data["assessment"] = raw
    else:
        response_data["assessment"] = None

    if comparison and comparison.llm_interpretation:
        try:
            response_data["change_detection"] = json.loads(comparison.llm_interpretation)
        except (json.JSONDecodeError, TypeError):
            response_data["change_detection"] = {"summary_of_changes": comparison.llm_interpretation}
            
        if comparison.text_diff:
            response_data["change_detection"]["text_diff"] = comparison.text_diff
    else:
        response_data["change_detection"] = None

    return response_data


class AskRequest(BaseModel):
    question: str
    meeting_date: Optional[str] = None
    doc_type: Optional[str] = None
    top_k: int = 5


@app.post("/api/v1/ask")
def ask_question(request: AskRequest, db: Session = Depends(get_db)):
    """
    RAG Q&A endpoint. Accepts a natural language question about FOMC policy
    and returns a citation-backed answer using hybrid retrieval.

    Requires the document_chunks table to be populated via:
        uv run python -m app.rag.ingest
    """
    from app.rag.qa import QAEngine

    logger.info(f"Q&A request: '{request.question}'")

    try:
        engine = QAEngine()
        result = engine.ask(
            question=request.question,
            db=db,
            top_k=request.top_k,
            meeting_date_filter=request.meeting_date,
            doc_type_filter=request.doc_type,
        )
        return result
    except Exception as e:
        logger.error(f"Q&A failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/chunks/status")
def get_chunks_status(db: Session = Depends(get_db)):
    """How many embedded chunks exist in the RAG index."""
    from sqlalchemy import text
    try:
        result = db.execute(
            text("SELECT COUNT(*) FROM document_chunks WHERE embedding IS NOT NULL")
        ).scalar()
        return {"embedded_chunks": result, "rag_ready": result > 0}
    except Exception:
        return {"embedded_chunks": 0, "rag_ready": False, "note": "document_chunks table not yet created. Run: uv run python -m app.rag.ingest"}


@app.get("/api/v1/divergences")
def get_divergences(db: Session = Depends(get_db)):
    """List all detected divergences across meetings."""
    from app.db.models import Divergence, EconomicSeries
    divergences = db.query(Divergence).order_by(Divergence.meeting_id.desc()).all()
    result = []
    for d in divergences:
        meeting_date = d.meeting.meeting_date if d.meeting else None
        series_name = d.series.name if d.series else "Unknown Series"
        result.append({
            "id": str(d.id),
            "meeting_date": str(meeting_date),
            "series_name": series_name,
            "fed_claim_text": d.fed_claim_text,
            "fed_claim_direction": d.fed_claim_direction,
            "data_direction": d.data_direction,
            "is_divergent": d.is_divergent,
            "severity": d.severity,
            "explanation": d.explanation,
            "data_summary": d.data_summary
        })
    # Sort by meeting_date descending manually in case the DB sort by meeting_id doesn't match date perfectly
    result.sort(key=lambda x: x["meeting_date"], reverse=True)
    return result


@app.get("/api/v1/series/{series_name}/observations")
def get_series_observations(series_name: str, meeting_date: str, db: Session = Depends(get_db)):
    """Fetch historical observations for a series up to a meeting date."""
    from app.db.models import EconomicSeries, EconomicObservation
    import datetime
    
    series = db.query(EconomicSeries).filter(EconomicSeries.name == series_name).first()
    if not series:
        # Fallback to check by fred_id
        series = db.query(EconomicSeries).filter(EconomicSeries.fred_id == series_name).first()
        if not series:
            raise HTTPException(status_code=404, detail="Series not found")
            
    try:
        m_date = datetime.datetime.strptime(meeting_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        
    # Get up to 24 months prior to the meeting date
    start_date = m_date - datetime.timedelta(days=365 * 2)
    
    observations = db.query(EconomicObservation).filter(
        EconomicObservation.series_id == series.id,
        EconomicObservation.release_date <= m_date,
        EconomicObservation.observation_date >= start_date
    ).order_by(EconomicObservation.observation_date.asc()).all()
    
    return [
        {
            "date": str(obs.observation_date),
            "value": float(obs.value) if obs.value is not None else None
        }
        for obs in observations
    ]

if __name__ == "__main__":
    uvicorn.run("app.api.main:app", host="0.0.0.0", port=8000, reload=True)
