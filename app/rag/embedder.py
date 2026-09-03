"""
Document Embedding Module

This module handles the vectorization phase of the Retrieval-Augmented Generation (RAG) pipeline. It converts textual chunks from FOMC statements into high-dimensional numerical vectors using OpenAI's embedding models. 

By translating text into a 1536-dimensional vector space, the system can perform mathematically precise similarity searches to retrieve the most relevant historical context for user queries. The resulting vectors are inserted directly into PostgreSQL utilizing the `pgvector` extension.

Configuration Parameters:
- `EMBEDDING_MODEL`: The OpenAI model used for vectorization (default: `text-embedding-3-small`).
- `EMBEDDING_DIMS`: The dimensionality of the resulting vectors (default: 1536).
"""
import os
import time
from typing import List, Dict, Any

from openai import OpenAI
from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.logger import setup_logger

load_dotenv()
logger = setup_logger(__name__)

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMS = 1536

class Embedder:
    """
    Connects to OpenAI's embeddings API, batches our text chunks together to save time/money,
    and then writes the resulting vectors directly into our PostgreSQL database using `pgvector` SQL syntax.
    """
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), timeout=60.0)

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Calls OpenAI embeddings API in a single batch request.
        OpenAI supports up to 2048 inputs per request.
        Returns a list of 1536-dim float vectors.
        """
        total_chars = sum(len(t) for t in texts)
        logger.info(f"Requesting embeddings for {len(texts)} texts ({total_chars} chars) via {EMBEDDING_MODEL}")
        # Truncate to 30000 chars max to stay within token limits
        texts = [t[:30000] for t in texts]
        response = self.client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=texts,
        )
        vectors = [item.embedding for item in response.data]
        logger.debug(
            f"Embeddings received",
            extra={"extra_data": {"count": len(vectors), "dims": len(vectors[0]) if vectors else 0}}
        )
        return vectors

    def embed_and_store(self, chunks: List[Dict[str, Any]], db: Session) -> int:
        """
        Given a list of chunk dicts (from chunker.py), embeds their text and
        inserts rows into the document_chunks table using raw SQL with pgvector syntax.

        Returns the number of chunks successfully stored.
        """
        if not chunks:
            logger.warning("No chunks provided to embed_and_store")
            return 0

        texts = [c["text"] for c in chunks]
        vectors = self.embed_texts(texts)

        stored = 0
        for chunk, vector in zip(chunks, vectors):
            # Convert vector list to pgvector string format: '[0.1, 0.2, ...]'
            vector_str = "[" + ",".join(str(v) for v in vector) + "]"

            # pgvector requires the ::vector cast which conflicts with SQLAlchemy's
            # parameter binding. We safely embed the vector string directly in SQL
            # (it's a float array we generated, not user input — no injection risk).
            sql = text(f"""
                INSERT INTO document_chunks
                    (id, document_id, meeting_id, chunk_index, text, doc_type,
                     meeting_date, word_count, embedding)
                VALUES
                    (:id, :document_id, :meeting_id, :chunk_index, :text, :doc_type,
                     :meeting_date, :word_count, '{vector_str}'::vector)
                ON CONFLICT (document_id, chunk_index) DO NOTHING
            """)
            db.execute(sql, {k: v for k, v in chunk.items() if k != "embedding"})
            stored += 1

        db.commit()
        logger.info(f"Stored {stored} embedded chunks in document_chunks")
        return stored
