import os
import json
import datetime
from pathlib import Path
from app.core.logger import setup_logger

logger = setup_logger(__name__)

def log_token_usage(operation: str, usage, model: str = "gpt-4o-mini"):
    """
    Logs OpenAI token usage to a local JSONL file.
    
    Args:
        operation (str): A description of the operation (e.g., 'QAEngine.ask', 'PolicyAssessment').
        usage: The usage object returned by the OpenAI API.
        model (str): The model used.
    """
    if not usage:
        return
        
    try:
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / "token_usage.jsonl"
        
        # Extract token counts safely
        prompt_tokens = getattr(usage, "prompt_tokens", 0)
        completion_tokens = getattr(usage, "completion_tokens", 0)
        total_tokens = getattr(usage, "total_tokens", 0)
        
        log_entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "operation": operation,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens
        }
        
        with open(log_file, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
            
        logger.debug(f"Logged {total_tokens} tokens for operation: {operation}")
    except Exception as e:
        logger.error(f"Failed to log token usage: {e}")
