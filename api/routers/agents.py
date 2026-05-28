"""Agents router — per-agent statistics."""

from fastapi import APIRouter, Depends, HTTPException

from ..models import AgentStats
from ..services.database import DatabasePool, AGENT_SCHEMAS
from ..dependencies import get_db

router = APIRouter()


@router.get("/agents/{agent}/stats", response_model=AgentStats)
async def agent_stats(
    agent: str,
    db: DatabasePool = Depends(get_db),
):
    if agent not in AGENT_SCHEMAS:
        raise HTTPException(status_code=404, detail=f"Unknown agent: {agent}")

    stats = await db.get_stats(agent)

    # Parse JSONB fields from asyncpg
    by_sens = stats.get("by_sensitivity", {})
    by_purp = stats.get("by_purpose", {})
    if isinstance(by_sens, str):
        import json
        by_sens = json.loads(by_sens)
    if isinstance(by_purp, str):
        import json
        by_purp = json.loads(by_purp)

    return AgentStats(
        agent=agent,
        total_documents=stats.get("total_documents", 0),
        total_chunks=stats.get("total_chunks", 0),
        embedded_chunks=stats.get("embedded_chunks", 0),
        blocked_chunks=stats.get("blocked_chunks", 0),
        by_sensitivity=by_sens or {},
        by_purpose=by_purp or {},
        last_ingest=str(stats.get("last_ingest")) if stats.get("last_ingest") else None,
    )
