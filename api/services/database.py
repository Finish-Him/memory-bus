"""Database pool and query helpers."""

import os
import asyncpg
from typing import Optional
from uuid import UUID


AGENT_SCHEMAS = ["atlas", "zeus", "alexandria", "arquimedes"]


class DatabasePool:
    """Async connection pool to Postgres + pgvector."""

    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self):
        url = os.getenv("DATABASE_URL", "")
        # Convert postgresql+asyncpg:// to postgres:// for asyncpg
        url = url.replace("postgresql+asyncpg://", "postgres://")
        self.pool = await asyncpg.create_pool(
            url,
            min_size=2,
            max_size=10,
            command_timeout=30,
        )

    async def disconnect(self):
        if self.pool:
            await self.pool.close()

    async def health_check(self) -> bool:
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("SELECT 1")
            return True
        except Exception:
            return False

    async def rate_limit_check(self, key: str, limit: int) -> int:
        """Simple in-memory-like counter using Postgres advisory lock."""
        async with self.pool.acquire() as conn:
            # Use a simple table for rate limiting
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS _rate_limits (
                    key text PRIMARY KEY,
                    count integer DEFAULT 1,
                    expires_at timestamptz DEFAULT now() + interval '1 minute'
                )
            """)
            result = await conn.fetchrow(
                """
                INSERT INTO _rate_limits (key, count, expires_at)
                VALUES ($1, 1, now() + interval '1 minute')
                ON CONFLICT (key) DO UPDATE
                SET count = _rate_limits.count + 1
                WHERE _rate_limits.expires_at > now()
                RETURNING count
                """,
                key,
            )
            if result:
                return result["count"]
            # Key expired — reset
            await conn.execute("DELETE FROM _rate_limits WHERE key = $1", key)
            return 1

    async def run_migration(self, schema: str):
        """Ensure schema and tables exist."""
        async with self.pool.acquire() as conn:
            await conn.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            await conn.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

            await conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {schema}.documents (
                    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                    title text NOT NULL,
                    source_path text NOT NULL,
                    source_kind text NOT NULL,
                    checksum text NOT NULL,
                    ingest_run_id uuid,
                    created_at timestamptz DEFAULT now(),
                    updated_at timestamptz DEFAULT now(),
                    UNIQUE (source_path, checksum)
                )
            """)

            await conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {schema}.chunks (
                    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                    document_id uuid REFERENCES {schema}.documents(id) ON DELETE CASCADE,
                    chunk_index integer NOT NULL,
                    content text NOT NULL,
                    content_hash text NOT NULL UNIQUE,
                    sensitivity text NOT NULL
                        CHECK (sensitivity IN ('public','restricted','blocked')),
                    can_embed_externally boolean DEFAULT false,
                    metadata jsonb DEFAULT '{{}}'::jsonb,
                    embedding vector(1536),
                    tsv tsvector GENERATED ALWAYS AS
                        (to_tsvector('portuguese', content)) STORED,
                    created_at timestamptz DEFAULT now(),
                    updated_at timestamptz DEFAULT now()
                )
            """)

            # Indices
            await conn.execute(f"""
                CREATE INDEX IF NOT EXISTS {schema}_chunks_embedding_idx
                ON {schema}.chunks USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 100)
            """)
            await conn.execute(f"""
                CREATE INDEX IF NOT EXISTS {schema}_chunks_tsv_idx
                ON {schema}.chunks USING gin (tsv)
            """)
            await conn.execute(f"""
                CREATE INDEX IF NOT EXISTS {schema}_chunks_meta_idx
                ON {schema}.chunks USING gin (metadata)
            """)
            await conn.execute(f"""
                CREATE INDEX IF NOT EXISTS {schema}_chunks_sens_idx
                ON {schema}.chunks (sensitivity)
            """)

    async def insert_ingest_run(
        self, schema: str, status: str = "running"
    ) -> UUID:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                f"INSERT INTO {schema}.ingest_runs (status) VALUES ($1) RETURNING id",
                status,
            )
            return row["id"]

    async def insert_document(
        self, schema: str, doc, ingest_run_id: UUID
    ) -> UUID:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                f"""
                INSERT INTO {schema}.documents
                    (title, source_path, source_kind, checksum, ingest_run_id)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (source_path, checksum) DO UPDATE
                    SET updated_at = now()
                RETURNING id
                """,
                doc.title, doc.source_path, doc.source_kind,
                doc.checksum, ingest_run_id,
            )
            return row["id"]

    async def insert_chunk(
        self, schema: str, document_id: UUID, chunk, embedding: Optional[list[float]]
    ) -> UUID:
        import hashlib
        content_hash = hashlib.sha256(chunk.content.encode()).hexdigest()

        async with self.pool.acquire() as conn:
            emb_str = None
            if embedding:
                emb_str = f"[{','.join(str(v) for v in embedding)}]"

            row = await conn.fetchrow(
                f"""
                INSERT INTO {schema}.chunks
                    (document_id, chunk_index, content, content_hash,
                     sensitivity, can_embed_externally, metadata, embedding)
                VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb,
                        $8::vector)
                ON CONFLICT (content_hash) DO NOTHING
                RETURNING id
                """,
                document_id, chunk.chunk_index, chunk.content, content_hash,
                chunk.sensitivity, chunk.can_embed_externally,
                chunk.metadata.model_dump_json(), emb_str,
            )
            return row["id"] if row else None

    async def hybrid_search(
        self, schema: str, query_embedding: list[float],
        query_text: str, top_k: int = 10,
        sensitivity_filter: list[str] = None,
        min_score: float = 0.0,
    ) -> list[dict]:
        sens_list = "', '".join(sensitivity_filter or ["public", "restricted"])
        emb_str = f"[{','.join(str(v) for v in query_embedding)}]"

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT
                    c.id as chunk_id,
                    c.document_id,
                    d.title as document_title,
                    c.content,
                    1 - (c.embedding <=> $1::vector) as score,
                    ts_rank_cd(c.tsv, plainto_tsquery('portuguese', $2)) as lexical_score,
                    c.metadata,
                    c.sensitivity
                FROM {schema}.chunks c
                JOIN {schema}.documents d ON d.id = c.document_id
                WHERE c.sensitivity IN ('{sens_list}')
                  AND c.embedding IS NOT NULL
                ORDER BY c.embedding <=> $1::vector
                LIMIT $3
                """,
                emb_str, query_text, top_k,
            )
            return [dict(r) for r in rows if r["score"] >= min_score]

    async def get_stats(self, schema: str) -> dict:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                f"""
                SELECT
                    COUNT(DISTINCT d.id)::int as total_documents,
                    COUNT(c.id)::int as total_chunks,
                    COUNT(c.id) FILTER (WHERE c.embedding IS NOT NULL)::int as embedded_chunks,
                    COUNT(c.id) FILTER (WHERE c.sensitivity = 'blocked')::int as blocked_chunks,
                    MAX(d.created_at) as last_ingest
                FROM {schema}.documents d
                LEFT JOIN {schema}.chunks c ON c.document_id = d.id
                """
            )
            if not row:
                return {}
            return dict(row)
