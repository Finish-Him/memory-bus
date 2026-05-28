"""Memory Bus — Shared semantic memory layer for AI agents."""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
import time
import os

from .services.database import DatabasePool
from .services.embedder import Embedder
from .services.gate import QualityGate
from .dependencies import set_services

db_pool = DatabasePool()
embedder = Embedder()
quality_gate = QualityGate()

# Register singletons early
set_services(db_pool, embedder, quality_gate)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db_pool.connect()
    await embedder.configure(
        os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
        int(os.getenv("EMBEDDING_DIMENSIONS", "1536")),
    )
    yield
    await db_pool.disconnect()


app = FastAPI(
    title="Memory Bus",
    description="Shared semantic memory for AI agents — Atlas, Zeus, Alexandria, Arquimedes",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Auth dependency ---

async def verify_api_key(x_api_key: str = Header(...)):
    expected = os.getenv("API_KEY", "")
    if not expected:
        return
    if x_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key


# --- Rate limit middleware ---

@app.middleware("http")
async def rate_limit(request: Request, call_next):
    rpm = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
    key = f"rl:{request.client.host}:{int(time.time() / 60)}"
    current = await db_pool.rate_limit_check(key, rpm)
    if current > rpm:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    response = await call_next(request)
    return response


# --- Routers (import after app creation to avoid circular imports) ---

from .routers import health, ingest, search, agents

app.include_router(health.router, tags=["health"])
app.include_router(
    ingest.router,
    prefix="/api/v1",
    tags=["ingest"],
    dependencies=[Depends(verify_api_key)],
)
app.include_router(
    search.router,
    prefix="/api/v1",
    tags=["search"],
    dependencies=[Depends(verify_api_key)],
)
app.include_router(
    agents.router,
    prefix="/api/v1",
    tags=["agents"],
    dependencies=[Depends(verify_api_key)],
)
