"""Ingest router — accepts documents with chunks."""

from fastapi import APIRouter, Depends
from uuid import UUID

from ..models import IngestRequest, IngestResponse
from ..services.database import DatabasePool, AGENT_SCHEMAS
from ..services.embedder import Embedder
from ..services.gate import QualityGate
from ..dependencies import get_db, get_embedder, get_gate

router = APIRouter()


@router.post("/ingest", response_model=IngestResponse)
async def ingest_documents(
    body: IngestRequest,
    db: DatabasePool = Depends(get_db),
    emb: Embedder = Depends(get_embedder),
    gate: QualityGate = Depends(get_gate),
):
    schema = body.agent

    # Ensure schema exists
    await db.run_migration(schema)

    # Start ingest run
    run_id = await db.insert_ingest_run(schema)

    docs_count = 0
    chunks_count = 0
    embedded_count = 0
    blocked_count = 0
    failures = []

    for doc in body.documents:
        # Gate validation for all chunks
        doc_failures = []
        for chunk in doc.chunks:
            doc_failures.extend(gate.validate_chunk(schema, chunk))

        if doc_failures:
            failures.extend(doc_failures)
            continue

        doc_id = await db.insert_document(schema, doc, run_id)
        docs_count += 1

        # Process chunks in batches of 20 for embedding
        embeddable = [
            c for c in doc.chunks
            if c.sensitivity != "blocked" and c.can_embed_externally
        ]
        blocked = [c for c in doc.chunks if c.sensitivity == "blocked"]

        # Embed embeddable chunks
        if embeddable:
            batch_texts = [c.content for c in embeddable]
            embeddings = await emb.embed(batch_texts)
            for i, chunk in enumerate(embeddable):
                cid = await db.insert_chunk(
                    schema, doc_id, chunk, embeddings[i]
                )
                if cid:
                    embedded_count += 1
                    chunks_count += 1

        # Insert blocked chunks without embedding
        for chunk in blocked:
            cid = await db.insert_chunk(schema, doc_id, chunk, None)
            if cid:
                blocked_count += 1
                chunks_count += 1

    # Update ingest run
    async with db.pool.acquire() as conn:
        await conn.execute(
            f"""
            UPDATE {schema}.ingest_runs
            SET status = 'completed',
                documents_count = $1,
                chunks_count = $2,
                embedded_count = $3,
                blocked_count = $4,
                finished_at = now()
            WHERE id = $5
            """,
            docs_count, chunks_count, embedded_count,
            blocked_count, run_id,
        )

    return IngestResponse(
        ingest_run_id=run_id,
        documents_count=docs_count,
        chunks_count=chunks_count,
        embedded_count=embedded_count,
        blocked_count=blocked_count,
        failed_count=len(failures),
        failures=failures,
    )
