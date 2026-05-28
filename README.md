# Memory Bus

Shared semantic memory layer for AI agents — Atlas, Zeus, Alexandria, Arquimedes.

## Architecture

FastAPI + Postgres/pgvector + hybrid search (vector + BM25).

Each agent has an isolated schema with identical structure:
- `atlas` — patrimonio DIRTIC/DETRAN-RJ
- `zeus` — agente pessoal Moises
- `alexandria` — vault/conhecimento
- `arquimedes` — auditoria + tutor MSC Academy

## Endpoints

- `GET /health` — liveness
- `GET /health/ready` — readiness (checks DB)
- `POST /api/v1/ingest` — upload documents with chunks
- `POST /api/v1/search` — hybrid semantic + lexical search
- `GET /api/v1/agents/{name}/stats` — per-agent metrics

## Quick Start

```bash
cp .env.example .env
# Edit .env with your keys

docker compose -f infra/docker-compose.yml up -d
```

## Authentication

API key in `X-API-Key` header. Set `API_KEY` in `.env`.
