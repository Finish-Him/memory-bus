"""Quality Gate — validates chunks before ingest."""

import re
from .database import AGENT_SCHEMAS
from ..models import ChunkIngest


class QualityGate:
    """Validates chunks against quality rules before ingest."""

    PII_PATTERNS = [
        (re.compile(r"\d{3}\.\d{3}\.\d{3}-\d{2}"), "CPF"),
        (re.compile(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}"), "CNPJ"),
        (re.compile(r"\(\d{2}\)\s*\d{4,5}-\d{4}"), "Telefone"),
        (re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"), "Email"),
    ]

    SECRET_PATTERNS = [
        (re.compile(r"sk-[a-zA-Z0-9]{32,}"), "OpenAI API Key"),
        (re.compile(r"ghp_[a-zA-Z0-9]{36}"), "GitHub Token"),
        (re.compile(r"eyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+"), "JWT Token"),
    ]

    def validate_chunk(
        self, schema: str, chunk: ChunkIngest
    ) -> list[dict]:
        """Validate a single chunk. Returns list of failures."""
        failures = []

        # Cross-agent check
        owner = chunk.metadata.owner_agent
        if owner != schema:
            failures.append({
                "chunk_index": chunk.chunk_index,
                "reason": f"Cross-agent: owner={owner}, schema={schema}",
                "severity": "high",
            })

        # PII scan
        for pattern, label in self.PII_PATTERNS:
            if pattern.search(chunk.content):
                if chunk.sensitivity == "public":
                    failures.append({
                        "chunk_index": chunk.chunk_index,
                        "reason": f"PII detected: {label} in public chunk",
                        "severity": "high",
                    })
                elif chunk.metadata.pii_class == "none":
                    failures.append({
                        "chunk_index": chunk.chunk_index,
                        "reason": f"PII detected: {label} but pii_class=none",
                        "severity": "medium",
                    })

        # Secret scan
        for pattern, label in self.SECRET_PATTERNS:
            if pattern.search(chunk.content):
                failures.append({
                    "chunk_index": chunk.chunk_index,
                    "reason": f"Secret detected: {label}",
                    "severity": "high",
                })

        # Blocked + external embedding
        if chunk.sensitivity == "blocked" and chunk.can_embed_externally:
            failures.append({
                "chunk_index": chunk.chunk_index,
                "reason": "Blocked chunk with can_embed_externally=true",
                "severity": "high",
            })

        # Empty content
        if not chunk.content.strip():
            failures.append({
                "chunk_index": chunk.chunk_index,
                "reason": "Empty content",
                "severity": "medium",
            })

        return failures
