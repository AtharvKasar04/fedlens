import uuid
from datetime import date, datetime
from typing import Optional, List, Any
from sqlalchemy import (
    Column, Integer, String, Date, DateTime, Numeric, Boolean, Text, ForeignKey, JSON
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func

Base = declarative_base()

class FOMCMeeting(Base):
    __tablename__ = 'fomc_meetings'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meeting_date = Column(Date, nullable=False, unique=True)
    statement_date = Column(Date)
    minutes_date = Column(Date)
    rate_decision = Column(String(20))
    target_rate_low = Column(Numeric(5,2))
    target_rate_high = Column(Numeric(5,2))
    has_sep = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    documents = relationship("FOMCDocument", back_populates="meeting")
    policy_assessment = relationship("PolicyAssessment", back_populates="meeting", uselist=False)

class FOMCDocument(Base):
    __tablename__ = 'fomc_documents'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meeting_id = Column(UUID(as_uuid=True), ForeignKey('fomc_meetings.id'))
    doc_type = Column(String(20), nullable=False) # 'statement', 'minutes', 'presser', 'sep'
    source_url = Column(Text, nullable=False)
    raw_text = Column(Text, nullable=False)
    word_count = Column(Integer)
    ingested_at = Column(DateTime(timezone=True), server_default=func.now())
    content_hash = Column(String(64))
    
    meeting = relationship("FOMCMeeting", back_populates="documents")

class PolicyAssessment(Base):
    __tablename__ = 'policy_assessments'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meeting_id = Column(UUID(as_uuid=True), ForeignKey('fomc_meetings.id'), unique=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey('fomc_documents.id'))
    
    inflation_assessment = Column(JSONB)
    labor_assessment = Column(JSONB)
    growth_assessment = Column(JSONB)
    financial_conditions = Column(JSONB)
    forward_guidance = Column(JSONB)
    overall_stance = Column(JSONB)
    
    raw_llm_output = Column(JSONB)
    extraction_model = Column(String(50))
    extraction_version = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    meeting = relationship("FOMCMeeting", back_populates="policy_assessment")

class EconomicSeries(Base):
    __tablename__ = 'economic_series'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fred_id = Column(String(20), nullable=False, unique=True)
    name = Column(Text, nullable=False)
    description = Column(Text)
    frequency = Column(String(10))
    units = Column(Text)
    policy_dimension = Column(String(30))
    # Note: For SQLite fallback during dev, we might use JSON instead of ARRAY
    claim_keywords = Column(JSONB) 

class EconomicObservation(Base):
    __tablename__ = 'economic_observations'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    series_id = Column(UUID(as_uuid=True), ForeignKey('economic_series.id'))
    observation_date = Column(Date, nullable=False)
    value = Column(Numeric)
    
    release_date = Column(Date, nullable=False)
    vintage_date = Column(Date)
    is_revised = Column(Boolean, default=False)

class MeetingComparison(Base):
    __tablename__ = 'meeting_comparisons'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    base_meeting_id = Column(UUID(as_uuid=True), ForeignKey('fomc_meetings.id'))
    comp_meeting_id = Column(UUID(as_uuid=True), ForeignKey('fomc_meetings.id'))
    
    text_diff = Column(JSONB)
    semantic_changes = Column(JSONB)
    llm_interpretation = Column(Text)
    stance_delta = Column(JSONB)
    evidence = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
