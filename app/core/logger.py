import logging
import logging.handlers
import os
import json
from datetime import datetime

# Ensure logs directory exists
os.makedirs("logs", exist_ok=True)

class JsonFormatter(logging.Formatter):
    """Formats log records as detailed JSON for deep technical inspection."""
    def format(self, record):
        log_record = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "file": record.pathname,
            "line": record.lineno
        }
        
        # If extra data is passed (like LLM responses), add it to the JSON
        if hasattr(record, "extra_data"):
            log_record["extra_data"] = record.extra_data
            
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
            
        return json.dumps(log_record)

def setup_logger(name: str):
    logger = logging.getLogger(name)
    
    # If the logger already has handlers, return it to avoid duplicate logs
    if logger.hasHandlers():
        return logger
        
    logger.setLevel(logging.DEBUG) # Base level captures everything

    # 1. Console Handler (Simple and clean for the terminal)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO) # Only show INFO and above on console
    console_format = logging.Formatter('👉 %(message)s')
    console_handler.setFormatter(console_format)

    # 2. File Handler (Detailed, Technical, JSON format)
    file_handler = logging.handlers.RotatingFileHandler(
        "logs/fedlens_detailed.log", 
        maxBytes=5*1024*1024, # 5MB limit per file
        backupCount=3 # Keep 3 backups
    )
    file_handler.setLevel(logging.DEBUG) # Save EVERYTHING to the file
    file_handler.setFormatter(JsonFormatter())

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    return logger
