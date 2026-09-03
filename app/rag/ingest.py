"""
RAG Database Initialization and Corpus Ingestion Pipeline

This executable script prepares the database infrastructure for vector search and backfills the corpus. It must be run to initialize the RAG capabilities or when historical data needs to be fully reprocessed.

Key Operations:
1. Extension Provisioning: Ensures the `pgvector` extension is enabled in PostgreSQL.
2. Schema Generation: Creates the `document_chunks` table to house textual snippets and their corresponding embeddings.
3. Text Processing: Iterates through all parsed FOMC documents, segments them via `chunker.py`, and dispatches them to the `Embedder`.
4. Indexing: Builds both GIN indexes for BM25 keyword search and IVFFlat indexes for approximate nearest neighbor (ANN) vector search.

Configuration Parameters:
- Database Schema: The `document_chunks` table definition and index strategies (e.g., IVFFlat vs HNSW) are defined within `setup_pgvector_and_table`.
"""
import sys
from sqlalchemy import text

from app.db.session import SessionLocal
from app.db.models import FOMCDocument
from app.rag.chunker import chunk_document
from app.rag.embedder import Embedder
from app.core.logger import setup_logger

logger = setup_logger(__name__)


def setup_pgvector_and_table(db):
    """
    Enables pgvector extension and creates the document_chunks table
    with the vector column. Safe to run multiple times (uses IF NOT EXISTS).
    """
    logger.info("Enabling pgvector extension...")
    db.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    db.commit()

    logger.info("Creating document_chunks table...")
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS document_chunks (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            document_id     UUID REFERENCES fomc_documents(id) ON DELETE CASCADE,
            meeting_id      UUID REFERENCES fomc_meetings(id),
            chunk_index     INT NOT NULL,
            text            TEXT NOT NULL,
            doc_type        VARCHAR(20),
            meeting_date    DATE,
            word_count      INT,
            embedding       VECTOR(1536),
            CONSTRAINT unique_chunk UNIQUE (document_id, chunk_index)
        )
    """))
    db.commit()

    # Create the BM25 full-text search index (ts_vector as expression index, not generated)
    logger.info("Creating full-text search index...")
    db.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_chunks_fts
        ON document_chunks
        USING GIN (to_tsvector('english', text))
    """))

    # Create the pgvector cosine similarity index
    logger.info("Creating pgvector index...")
    db.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_chunks_vector
        ON document_chunks
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 10)
    """))
    db.commit()
    logger.info("✅ pgvector and document_chunks table ready.")


def run_ingestion(dry_run: bool = False):
    db = SessionLocal()
    embedder = Embedder()

    try:
        # 1. Setup infrastructure
        setup_pgvector_and_table(db)

        # 2. Load all existing FOMC documents from DB
        documents = db.query(FOMCDocument).all()
        logger.info(f"Found {len(documents)} FOMC documents to process")

        if not documents:
            logger.warning("No documents in DB. Run the scraper first.")
            return

        total_chunks = 0
        total_stored = 0

        for doc in documents:
            # 3. Chunk each document
            chunks = chunk_document(
                document_id=str(doc.id),
                meeting_id=str(doc.meeting_id),
                doc_type=doc.doc_type,
                raw_text=doc.raw_text,
                meeting_date=str(doc.meeting.meeting_date) if doc.meeting else "unknown",
                source_url=doc.source_url,
            )
            total_chunks += len(chunks)

            if dry_run:
                logger.info(f"[DRY RUN] Would embed {len(chunks)} chunks for doc {doc.id}")
                continue

            # 4. Embed and store (this calls OpenAI API)
            stored = embedder.embed_and_store(chunks, db)
            total_stored += stored

        logger.info(f"✅ RAG Ingestion complete: {total_chunks} chunks, {total_stored} stored with embeddings")

    except Exception as e:
        logger.error(f"RAG ingestion failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    if dry_run:
        logger.info("Running in DRY RUN mode — no OpenAI API calls will be made.")
    run_ingestion(dry_run=dry_run)
