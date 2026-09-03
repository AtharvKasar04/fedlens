"""
Retrieval-Augmented Generation (RAG) Query Engine

This module orchestrates the question-answering capabilities of the system. It bridges user queries with historical FOMC context to generate highly accurate, citation-backed responses.

Execution Flow:
1. Retrieval: Accepts a natural language query and utilizes the `Retriever` module to fetch the most semantically relevant paragraphs from the historical database.
2. Context Assembly: Packages the retrieved chunks into a strict context window.
3. Generation: Instructs the LLM to synthesize an answer. Crucially, the system prompt restricts the LLM to exclusively use the provided context, heavily mitigating the risk of hallucinations.

Configuration Parameters:
- System Prompts: The constraints and tone instructions provided to the LLM are defined in the `qa_prompt`.
- Retrieval Limits: The number of chunks retrieved (`top_k`) is configurable at the endpoint level.
"""
import os
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from openai import OpenAI
from dotenv import load_dotenv
from sqlalchemy.orm import Session

from app.rag.retriever import HybridRetriever
from app.core.logger import setup_logger

load_dotenv()
logger = setup_logger(__name__)


class Citation(BaseModel):
    chunk_index: int = Field(description="Index of the evidence chunk this citation refers to")
    meeting_date: str = Field(description="The FOMC meeting date this passage is from")
    doc_type: str = Field(description="Document type: statement, minutes, etc.")
    verbatim_passage: str = Field(description="The exact text passage used as evidence")


class AnswerWithEvidence(BaseModel):
    answer: str = Field(description="Direct, concise answer to the question")
    reasoning: str = Field(description="Step-by-step reasoning process before the final answer")
    citations: List[Citation] = Field(description="List of source passages that support the answer")
    confidence: str = Field(description="high, medium, or low — how confident is the answer based on the retrieved evidence?")


class QAEngine:
    def __init__(self):
        self.retriever = HybridRetriever()
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = "gpt-4o-mini"

    def ask(
        self,
        question: str,
        db: Session,
        top_k: int = 5,
        meeting_date_filter: Optional[str] = None,
        doc_type_filter: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Full RAG Q&A pipeline:
        1. Retrieve top-K passages from FOMC corpus (hybrid BM25 + vector + rerank)
        2. Format passages as numbered context for the LLM
        3. Ask LLM to answer with citations
        4. Return structured response with evidence
        """
        # Step 1: Retrieve relevant passages
        passages = self.retriever.retrieve(
            query=question,
            db=db,
            top_k=top_k,
            meeting_date_filter=meeting_date_filter,
            doc_type_filter=doc_type_filter,
        )

        if not passages:
            return {
                "answer": "No relevant FOMC documents found in the database for this question.",
                "reasoning": "The document_chunks table is empty or no chunks matched the query.",
                "citations": [],
                "confidence": "low",
                "passages_retrieved": 0,
            }

        # Step 2: Format context block for LLM
        context_blocks = []
        for i, p in enumerate(passages):
            context_blocks.append(
                f"[PASSAGE {i+1}] (Meeting: {p['meeting_date']}, Type: {p['doc_type']})\n{p['text']}"
            )
        context = "\n\n---\n\n".join(context_blocks)

        # Step 3: Build prompt with anti-hallucination guardrails
        prompt = f"""You are an expert analyst of Federal Reserve monetary policy.
Answer the question below using ONLY the provided FOMC passages. 
Do NOT introduce information not present in the passages.
Do NOT compute or estimate numerical values — only quote what is explicitly stated.

CRITICAL INSTRUCTION ON DATES & META-QUESTIONS:
1. If the user's question asks about a specific meeting date or time period (e.g., "Jan 2023", "2022") AND the provided passages do NOT match that date, you MUST refuse to answer and state that data for that date is unavailable. Do NOT hallucinate.
2. If the user asks a general question or a meta-question (e.g., "how many years of data do you have?") and the answer is NOT in the provided passages, simply state that the provided excerpts do not contain this information. Do not use the date rejection message for this.

QUESTION: {question}

RETRIEVED PASSAGES:
{context}

Instructions:
1. First, write your step-by-step reasoning in the 'reasoning' field. Explicitly check if the passage dates match requested dates (if any).
2. Then provide a direct, concise answer in the 'answer' field.
3. For each piece of evidence used, add a citation with the exact passage number, meeting date, doc type, and verbatim quote.
4. Rate your confidence as 'high' (strong direct evidence), 'medium' (indirect evidence), or 'low' (weak, tangential, or missing evidence).
"""
        import instructor
        client = instructor.from_openai(self.client)

        logger.info(f"Sending Q&A request to {self.model} for: '{question[:60]}...'")
        response = client.chat.completions.create(
            model=self.model,
            response_model=AnswerWithEvidence,
            messages=[{"role": "user", "content": prompt}],
        )
        logger.debug(
            "Q&A response received",
            extra={"extra_data": {"response": response.model_dump()}}
        )

        return {
            "answer": response.answer,
            "reasoning": response.reasoning,
            "citations": [c.model_dump() for c in response.citations],
            "confidence": response.confidence,
            "passages_retrieved": len(passages),
            "passages": [
                {
                    "meeting_date": p["meeting_date"],
                    "doc_type": p["doc_type"],
                    "text": p["text"][:300] + "..." if len(p["text"]) > 300 else p["text"],
                    "rerank_score": p.get("rerank_score"),
                }
                for p in passages
            ],
        }
