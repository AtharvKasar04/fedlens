import os
import json
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from openai import OpenAI
from dotenv import load_dotenv
from sqlalchemy.orm import Session
import instructor

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


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_available_meetings",
            "description": "Lists all available FOMC meeting dates in the database.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_fomc_documents",
            "description": "Searches FOMC statements and minutes for relevant textual excerpts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query"},
                    "meeting_date_filter": {"type": "string", "description": "Optional specific meeting date (YYYY-MM-DD)"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_market_reaction",
            "description": "Fetches the stock (SPY) and bond (TLT) market percentage change and explanation for a given FOMC meeting.",
            "parameters": {
                "type": "object",
                "properties": {
                    "meeting_date": {"type": "string", "description": "The FOMC meeting date (YYYY-MM-DD)"}
                },
                "required": ["meeting_date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_economic_series",
            "description": "Searches the database for available economic series to get their FRED IDs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search term (e.g., 'unemployment', 'inflation')"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_economic_data",
            "description": "Fetches macroeconomic data for a specific time period. You MUST have the exact FRED ID first.",
            "parameters": {
                "type": "object",
                "properties": {
                    "fred_id": {"type": "string", "description": "The FRED series ID (e.g., UNRATE)"},
                    "start_date": {"type": "string", "description": "Optional start date (YYYY-MM-DD)"},
                    "end_date": {"type": "string", "description": "Optional end date (YYYY-MM-DD)"}
                },
                "required": ["fred_id"]
            }
        }
    }
]

def handle_list_available_meetings(args, db: Session):
    from app.db.models import FOMCMeeting
    meetings = db.query(FOMCMeeting).order_by(FOMCMeeting.meeting_date.desc()).all()
    if not meetings:
        return "No meetings available."
    dates = [str(m.meeting_date) for m in meetings]
    return f"Available meeting dates: {', '.join(dates)}"

def handle_get_market_reaction(args, db: Session):
    from app.db.models import FOMCMeeting, MarketReaction
    date_str = args.get("meeting_date")
    meeting = db.query(FOMCMeeting).filter(FOMCMeeting.meeting_date == date_str).first()
    if not meeting:
        return f"No meeting found for {date_str}"
    reaction = db.query(MarketReaction).filter(MarketReaction.meeting_id == meeting.id).first()
    if not reaction:
        return f"No market reaction data for {date_str}"
    
    return f"[MARKET DATA] Meeting Date: {date_str}\nSPY (S&P 500) changed by {reaction.spy_change_pct}%.\nTLT (20+ Yr Treasuries) changed by {reaction.tlt_change_pct}%.\nAI Explanation: {reaction.ai_explanation}"

def handle_search_economic_series(args, db: Session):
    from app.db.models import EconomicSeries
    query = args.get("query", "").lower()
    series = db.query(EconomicSeries).all()
    results = []
    for s in series:
        s_name = s.name.lower() if s.name else ""
        s_desc = s.description.lower() if s.description else ""
        if query in s_name or query in s_desc:
            results.append(f"{s.name} (FRED ID: {s.fred_id})")
    if not results:
        return f"No economic series found matching '{query}'"
    return "Available series:\n" + "\n".join(results)

def handle_get_economic_data(args, db: Session):
    from app.db.models import EconomicSeries, EconomicObservation
    fred_id = args.get("fred_id")
    series = db.query(EconomicSeries).filter(EconomicSeries.fred_id == fred_id).first()
    if not series:
        return f"Economic series {fred_id} not found in database."
    
    q = db.query(EconomicObservation).filter(EconomicObservation.series_id == series.id)
    if args.get("start_date"):
        q = q.filter(EconomicObservation.observation_date >= args["start_date"])
    if args.get("end_date"):
        q = q.filter(EconomicObservation.observation_date <= args["end_date"])
        
    obs = q.order_by(EconomicObservation.observation_date.desc()).limit(12).all()
    if not obs:
        return f"No observations found for {fred_id}."
        
    res = [f"{o.observation_date}: {o.value} {series.units}" for o in obs]
    return f"[ECONOMIC DATA] Series: {series.name} ({fred_id})\nRecent observations:\n" + "\n".join(res)

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
        Agentic RAG Q&A pipeline:
        1. Give LLM access to search_documents, get_market, get_economic tools.
        2. Let LLM run tools to gather context.
        3. Force final answer through Instructor with citations.
        """
        logger.info(f"Agentic Q&A starting for: '{question[:60]}...'")
        
        messages = [
            {"role": "system", "content": "You are an autonomous research agent for Federal Reserve data. You have access to tools to fetch FOMC documents, market reactions, and economic data (like unemployment). \nCRITICAL RULES:\n1. ALWAYS use the `list_available_meetings` tool first if you only have a month and year (e.g., 'March 2025') so you can find the EXACT meeting date (YYYY-MM-DD).\n2. If the user asks ANY question about economic indicators, you MUST immediately call `search_economic_series` to find the exact FRED ID, and then call `get_economic_data`.\n3. Do NOT give up without trying your tools!"},
            {"role": "user", "content": question}
        ]
        
        all_passages_retrieved = []
        context_blocks = []
        
        # Agent Tool Loop
        for iteration in range(5):
            logger.info(f"Agent Loop Iteration {iteration+1}")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto"
            )
            msg = response.choices[0].message
            
            # Log usage for tool call loop
            from app.core.token_logger import log_token_usage
            if hasattr(response, "usage"):
                log_token_usage("qa_engine_loop", response.usage, self.model)

            messages.append(msg)
            
            if not msg.tool_calls:
                break
                
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except:
                    args = {}
                    
                logger.info(f"LLM called tool: {tc.function.name} with args {args}")
                
                if tc.function.name == "list_available_meetings":
                    res = handle_list_available_meetings(args, db)
                elif tc.function.name == "search_economic_series":
                    res = handle_search_economic_series(args, db)
                elif tc.function.name == "search_fomc_documents":
                    date_f = args.get("meeting_date_filter") or meeting_date_filter
                    passages = self.retriever.retrieve(
                        query=args.get("query", question), 
                        db=db, 
                        top_k=top_k, 
                        meeting_date_filter=date_f,
                        doc_type_filter=doc_type_filter
                    )
                    if passages:
                        blocks = []
                        for i, p in enumerate(passages):
                            all_passages_retrieved.append(p)
                            idx = len(all_passages_retrieved)
                            blocks.append(f"[PASSAGE {idx}] (Meeting: {p['meeting_date']}, Type: {p['doc_type']})\n{p['text']}")
                        res = "\n\n".join(blocks)
                    else:
                        res = f"No documents found matching query: {args.get('query')} and date: {date_f}"
                elif tc.function.name == "get_market_reaction":
                    res = handle_get_market_reaction(args, db)
                elif tc.function.name == "get_economic_data":
                    res = handle_get_economic_data(args, db)
                else:
                    res = "Unknown tool"
                    
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": res
                })
                context_blocks.append(res)
        
        if not context_blocks:
            context = "No relevant documents or data found in the database."
        else:
            context = "\n\n---\n\n".join(context_blocks)
            
        # Final Step: Format context block for LLM and enforce structured output
        prompt = f"""You are an expert analyst of Federal Reserve monetary policy.
Answer the question below using ONLY the provided context gathered from your tools.
Do NOT introduce information not present in the context.

CRITICAL INSTRUCTION FOR NUMBERS: 
If the context uses fractional interest rates (e.g., "4-1/4", "4-1/2", "4-3/4"), you MUST convert them to standard decimals (e.g., 4.25%, 4.50%, 4.75%) in your answer so it's easier to interpret.

QUESTION: {question}

GATHERED CONTEXT:
{context}

Instructions:
1. First, write your step-by-step reasoning in the 'reasoning' field.
2. Then provide a direct, concise answer in the 'answer' field (with converted decimals).
3. For each piece of evidence used, add a citation with the exact passage number, meeting date, doc type, and verbatim quote (you can leave fractions in the verbatim quote).
4. If you use Market Reaction or Economic Data, cite it as passage number 0, doc type 'data'.
5. Rate your confidence as 'high', 'medium', or 'low'.
"""
        instructor_client = instructor.from_openai(self.client)
        
        logger.info("Sending final synthesis request to LLM...")
        final_response = instructor_client.chat.completions.create(
            model=self.model,
            response_model=AnswerWithEvidence,
            messages=[{"role": "user", "content": prompt}],
        )

        from app.core.token_logger import log_token_usage
        if hasattr(final_response, "_raw_response") and hasattr(final_response._raw_response, "usage"):
            log_token_usage("qa_engine_synthesis", final_response._raw_response.usage, self.model)

        return {
            "answer": final_response.answer,
            "reasoning": final_response.reasoning,
            "citations": [c.model_dump() for c in final_response.citations],
            "confidence": final_response.confidence,
            "passages_retrieved": len(all_passages_retrieved),
            "passages": [
                {
                    "meeting_date": p["meeting_date"],
                    "doc_type": p["doc_type"],
                    "text": p["text"][:300] + "..." if len(p["text"]) > 300 else p["text"],
                    "rerank_score": p.get("rerank_score"),
                }
                for p in all_passages_retrieved
            ],
        }
