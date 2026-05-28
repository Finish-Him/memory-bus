"""Models for Memory Bus API."""

from pydantic import BaseModel, Field
from typing import Optional, Literal
from uuid import UUID


SENSITIVITY = Literal["public", "restricted", "blocked"]
PURPOSE = Literal["rag", "sft", "eval", "preference", "audit", "tutor", "style"]
AGENT_NAME = Literal["atlas", "zeus", "alexandria", "arquimedes"]


class ChunkMetadata(BaseModel):
    owner_agent: AGENT_NAME
    agent_role: Optional[str] = None
    purpose: PURPOSE
    version: str = "v1"
    source_scope: Literal["public", "internal", "private", "restricted"] = "internal"
    pii_class: Literal["none", "low", "medium", "high"] = "low"
    license_review: Literal["approved", "restricted", "pending"] = "approved"
    review_status: Literal["draft", "needs_review", "approved", "rejected"] = "approved"
    chunk_type: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    extra: dict = Field(default_factory=dict)


class ChunkIngest(BaseModel):
    content: str
    chunk_index: int
    sensitivity: SENSITIVITY = "restricted"
    can_embed_externally: bool = False
    metadata: ChunkMetadata


class DocumentIngest(BaseModel):
    title: str
    source_path: str
    source_kind: str  # pdf, xlsx, md, whatsapp, manual, web
    checksum: str
    chunks: list[ChunkIngest]


class IngestRequest(BaseModel):
    agent: AGENT_NAME
    documents: list[DocumentIngest]


class IngestResponse(BaseModel):
    ingest_run_id: UUID
    documents_count: int
    chunks_count: int
    embedded_count: int
    blocked_count: int
    failed_count: int = 0
    failures: list[dict] = Field(default_factory=list)


class SearchRequest(BaseModel):
    agent: AGENT_NAME
    query: str
    top_k: int = Field(default=10, ge=1, le=50)
    sensitivity_filter: list[SENSITIVITY] = Field(default=["public", "restricted"])
    hybrid: bool = True
    min_score: float = Field(default=0.0, ge=0.0, le=1.0)


class SearchResult(BaseModel):
    chunk_id: UUID
    document_id: UUID
    document_title: str
    content: str
    score: float
    lexical_score: Optional[float] = None
    rrf_score: Optional[float] = None
    metadata: dict
    sensitivity: str


class SearchResponse(BaseModel):
    results: list[SearchResult]
    took_ms: float
    query_embedding_dim: int


class AuditResult(BaseModel):
    passed: bool
    reason: Optional[str] = None
    severity: Literal["low", "medium", "high"] = "low"


class AgentStats(BaseModel):
    agent: str
    total_documents: int
    total_chunks: int
    embedded_chunks: int
    blocked_chunks: int
    by_sensitivity: dict[str, int]
    by_purpose: dict[str, int]
    last_ingest: Optional[str] = None
