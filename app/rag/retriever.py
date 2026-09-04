"""
RAG Step 3: Retriever
Hybrid BM25 + pgvector search with Reciprocal Rank Fusion (RRF), 
followed by cross-encoder reranking.

Per Implementation Plan (Section 9):
  Query
    ├── BM25 via PostgreSQL ts_vector (exact keyword match)
    └── pgvector cosine similarity (semantic match)
           ↓
    Reciprocal Rank Fusion (merge ranked lists)
           ↓
    Top 20 candidates
           ↓
    Cross-encoder reranking (ms-marco-MiniLM-L-6-v2, local, free)
           ↓
    Top 5 passages with metadata
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.logger import setup_logger

logger = setup_logger(__name__)

# RRF constant — standard value from the original RRF paper
RRF_K = 60


class HybridRetriever:
    _reranker = None  # Lazy-loaded — heavy model, load once

    def __init__(self):
        pass

    def _get_reranker(self):
        """Lazy-load the cross-encoder to avoid import cost at startup."""
        if HybridRetriever._reranker is None:
            logger.info("Loading cross-encoder reranker (ms-marco-MiniLM-L-6-v2)...")
            from sentence_transformers import CrossEncoder
            HybridRetriever._reranker = CrossEncoder(
                "cross-encoder/ms-marco-MiniLM-L-6-v2",
                max_length=512,
            )
            logger.info("Cross-encoder loaded successfully.")
        return HybridRetriever._reranker

    def _embed_query(self, query: str) -> List[float]:
        """Embed the query using OpenAI text-embedding-3-small."""
        import os
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=[query],
        )
        
        from app.core.token_logger import log_token_usage
        if hasattr(response, "usage"):
            log_token_usage("vector_search_embedder", response.usage, "text-embedding-3-small")
            
        return response.data[0].embedding

    def bm25_search(
        self, query: str, db: Session, top_k: int = 20,
        meeting_date_filter: Optional[str] = None,
        doc_type_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Full-text search using PostgreSQL ts_vector + ts_rank.
        The ts_vector is a generated column on document_chunks (set up in the migration).
        """
        sql = text(f"""
            SELECT
                id, document_id, meeting_id, chunk_index, text,
                doc_type, meeting_date,
                ts_rank(to_tsvector('english', text), plainto_tsquery('english', :query)) AS score
            FROM document_chunks
            WHERE to_tsvector('english', text) @@ plainto_tsquery('english', :query)
            {('AND meeting_date = :meeting_date' if meeting_date_filter else '')}
            {('AND doc_type = :doc_type' if doc_type_filter else '')}
            ORDER BY score DESC
            LIMIT :top_k
        """)
        params: Dict[str, Any] = {"query": query, "top_k": top_k}
        if meeting_date_filter:
            params["meeting_date"] = meeting_date_filter
        if doc_type_filter:
            params["doc_type"] = doc_type_filter
        rows = db.execute(sql, params).mappings().all()
        return [dict(r) for r in rows]

    def vector_search(
        self, query: str, db: Session, top_k: int = 20,
        meeting_date_filter: Optional[str] = None,
        doc_type_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Cosine similarity search using pgvector.
        <=> operator = cosine distance (lower = more similar).
        """
        query_vector = self._embed_query(query)
        vector_str = "[" + ",".join(str(v) for v in query_vector) + "]"

        filters = ""
        params: Dict[str, Any] = {"vector": vector_str, "top_k": top_k}

        if meeting_date_filter:
            filters += " AND meeting_date = :meeting_date"
            params["meeting_date"] = meeting_date_filter
        if doc_type_filter:
            filters += " AND doc_type = :doc_type"
            params["doc_type"] = doc_type_filter

        sql = text(f"""
            SELECT
                id, document_id, meeting_id, chunk_index, text,
                doc_type, meeting_date,
                1 - (embedding <=> '{vector_str}'::vector) AS score
            FROM document_chunks
            WHERE embedding IS NOT NULL
            {('AND meeting_date = :meeting_date' if meeting_date_filter else '')}
            {('AND doc_type = :doc_type' if doc_type_filter else '')}
            ORDER BY embedding <=> '{vector_str}'::vector
            LIMIT :top_k
        """)
        params: Dict[str, Any] = {"top_k": top_k}
        if meeting_date_filter:
            params["meeting_date"] = meeting_date_filter
        if doc_type_filter:
            params["doc_type"] = doc_type_filter
        rows = db.execute(sql, params).mappings().all()
        return [dict(r) for r in rows]

    def reciprocal_rank_fusion(
        self,
        bm25_results: List[Dict],
        vector_results: List[Dict],
        top_k: int = 20,
    ) -> List[Dict]:
        """
        Merge two ranked lists using Reciprocal Rank Fusion.
        RRF score = 1/(k + rank) summed across both lists.
        Produces a single unified ranked list.
        """
        scores: Dict[str, float] = {}
        chunks_by_id: Dict[str, Dict] = {}

        for rank, chunk in enumerate(bm25_results):
            chunk_id = str(chunk["id"])
            scores[chunk_id] = scores.get(chunk_id, 0) + 1 / (RRF_K + rank + 1)
            chunks_by_id[chunk_id] = chunk

        for rank, chunk in enumerate(vector_results):
            chunk_id = str(chunk["id"])
            scores[chunk_id] = scores.get(chunk_id, 0) + 1 / (RRF_K + rank + 1)
            chunks_by_id[chunk_id] = chunk

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        return [
            {**chunks_by_id[chunk_id], "rrf_score": rrf_score}
            for chunk_id, rrf_score in ranked
        ]

    def rerank(self, query: str, candidates: List[Dict], top_k: int = 5) -> List[Dict]:
        """
        Cross-encoder reranking using ms-marco-MiniLM-L-6-v2.
        Takes (query, passage) pairs and scores them with a fine-tuned BERT model.
        Much more accurate than bi-encoder similarity for final ranking.
        """
        if not candidates:
            return []

        reranker = self._get_reranker()
        pairs = [(query, c["text"]) for c in candidates]
        scores = reranker.predict(pairs)

        for chunk, score in zip(candidates, scores):
            chunk["rerank_score"] = float(score)

        reranked = sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)
        return reranked[:top_k]

    def retrieve(
        self,
        query: str,
        db: Session,
        top_k: int = 5,
        meeting_date_filter: Optional[str] = None,
        doc_type_filter: Optional[str] = None,
    ) -> List[Dict]:
        """
        Full hybrid retrieval pipeline:
        BM25 + pgvector → RRF → Cross-encoder reranking → Top-K passages
        """
        logger.info(f"Retrieving for query: '{query[:80]}...'")

        bm25 = self.bm25_search(query, db, top_k=20,
                                 meeting_date_filter=meeting_date_filter,
                                 doc_type_filter=doc_type_filter)
        vector = self.vector_search(query, db, top_k=20,
                                     meeting_date_filter=meeting_date_filter,
                                     doc_type_filter=doc_type_filter)

        logger.debug(f"BM25: {len(bm25)} results, Vector: {len(vector)} results")

        fused = self.reciprocal_rank_fusion(bm25, vector, top_k=20)
        reranked = self.rerank(query, fused, top_k=top_k)

        logger.info(f"Returning {len(reranked)} reranked passages")
        return reranked
