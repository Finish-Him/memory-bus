"""Dependency injection for Memory Bus API."""

from .services.database import DatabasePool
from .services.embedder import Embedder
from .services.gate import QualityGate


# Singleton instances created in api/__init__.py lifespan
_db: DatabasePool | None = None
_embedder: Embedder | None = None
_gate: QualityGate | None = None


def set_services(db: DatabasePool, embedder: Embedder, gate: QualityGate):
    global _db, _embedder, _gate
    _db = db
    _embedder = embedder
    _gate = gate


def get_db() -> DatabasePool:
    assert _db is not None, "Database not initialized"
    return _db


def get_embedder() -> Embedder:
    assert _embedder is not None, "Embedder not initialized"
    return _embedder


def get_gate() -> QualityGate:
    assert _gate is not None, "QualityGate not initialized"
    return _gate
