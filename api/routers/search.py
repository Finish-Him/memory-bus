"""Search router — hybrid semantic + lexical retrieval."""

import time
from fastapi import APIRouter, Depends

from ..models import SearchRequest, SearchResponse, SearchResult
from ..services.database import DatabasePool, AGENT_SCHEMAS
from ..services.embedder import Embedder
from ..dependencies import get_db, get_embedder

router = APIRouter()


@router.post("/search", response_model=SearchResponse)
async def search(
    body: SearchRequest,
    db: DatabasePool = Depends(get_db),
    emb: Embedder = Depends(get_embedder),
):
    start = time.time()

    # Generate query embedding
    query_emb = await emb.embed_single(body.query)

    # Hybrid search
    rows = await db.hybrid_search(
        schema=body.agent,
        query_embedding=query_emb,
        query_text=body.query,
        top_k=body.top_k,
        sensitivity_filter=[s for s in body.sensitivity_filter],
        min_score=body.min_score,
    )

    results = []
    for row in rows:
        meta = row.get("metadata", {})
        if isinstance(meta, str):
            import json
            meta = json.loads(meta)
        results.append(SearchResult(
            chunk_id=row["chunk_id"],
            document_id=row["document_id"],
            document_title=row.get("document_title", ""),
            content=row["content"],
            score=float(row["score"] or 0),
            lexical_score=float(row.get("lexical_score") or 0),
            rrf_score=None,  # RRF computed if hybrid; simplified for now
            metadata=meta or {},
            sensitivity=row.get("sensitivity", "restricted"),
        ))

    took_ms = (time.time() - start) * 1000

    return SearchResponse(
        results=results,
        took_ms=round(took_ms, 2),
        query_embedding_dim=len(query_emb),
    )
