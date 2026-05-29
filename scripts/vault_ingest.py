"""Ingest Obsidian vault into Memory Bus (schema: alexandria)."""
import os, re, json, hashlib, requests, sys
from pathlib import Path

API_BASE = os.environ.get("MEMORY_BUS_URL", "https://msc-academy.com.br/memory-bus")
API_KEY = os.environ.get("MEMORY_BUS_API_KEY", os.environ.get("API_KEY", ""))
VAULT = os.path.expanduser(r"~/Documents/Obsidian Vaults/Alexandria")

if not API_KEY:
    print("ERROR: MEMORY_BUS_API_KEY not set")
    sys.exit(1)

SKIP_DIRS = {"Projetos", ".git", ".obsidian", "_templates", "node_modules"}
# Only ingest important docs (skip ephemeral changelogs/snapshots)
SKIP_PATTERNS = [
    "pi-stack/changelog",
    "pi-stack/snapshots",
    "pi-stack/dashboard",
    "_backup",
    "backup",
]
MIN_CHUNK_SIZE = 50  # chars
MAX_CHUNK_SIZE = 1500
BATCH_SIZE = 3  # documents per request (keep payloads under 1MB)


def split_by_headings(text: str) -> list[str]:
    """Split markdown text into chunks by ## headings."""
    sections = re.split(r"(?=^## )", text, flags=re.MULTILINE)
    chunks = []
    for sec in sections:
        sec = sec.strip()
        if len(sec) < MIN_CHUNK_SIZE:
            continue
        # If section is too big, chunk by paragraphs
        if len(sec) > MAX_CHUNK_SIZE:
            paras = sec.split("\n\n")
            current = ""
            for p in paras:
                if len(current) + len(p) < MAX_CHUNK_SIZE:
                    current += p + "\n\n"
                else:
                    if len(current) > MIN_CHUNK_SIZE:
                        chunks.append(current.strip())
                    current = p + "\n\n"
            if len(current) > MIN_CHUNK_SIZE:
                chunks.append(current.strip())
        else:
            chunks.append(sec)
    return chunks


def collect_documents(vault_path: str) -> list[dict]:
    """Walk vault and collect documents with chunks."""
    documents = []
    skipped = 0
    seen_checksums = set()

    for root, dirs, files in os.walk(vault_path):
        # Skip ignored dirs
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

        for fname in files:
            if not fname.endswith(".md"):
                continue
            fpath = os.path.join(root, fname)
            relpath = os.path.relpath(fpath, vault_path)

            # Skip ephemeral patterns
            if any(p in relpath for p in SKIP_PATTERNS):
                skipped += 1
                continue

            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception as e:
                skipped += 1
                continue

            if len(content) < MIN_CHUNK_SIZE:
                skipped += 1
                continue

            checksum = hashlib.sha256(content.encode()).hexdigest()
            if checksum in seen_checksums:
                skipped += 1
                continue
            seen_checksums.add(checksum)

            chunks = split_by_headings(content)
            if not chunks:
                # No headings — use whole file as one chunk
                if len(content) <= MAX_CHUNK_SIZE:
                    chunks = [content]
                else:
                    chunks = [content[:MAX_CHUNK_SIZE]]

            doc = {
                "title": relpath,
                "source_path": relpath,
                "source_kind": "md",
                "checksum": checksum,
                "chunks": [
                    {
                        "content": c,
                        "chunk_index": i,
                        "sensitivity": "restricted",
                        "can_embed_externally": True,
                        "metadata": {
                            "owner_agent": "alexandria",
                            "purpose": "rag",
                            "source_scope": "private",
                            "pii_class": "medium",
                            "review_status": "needs_review",
                            "tags": [relpath.split("/")[0]] if "/" in relpath else [],
                        },
                    }
                    for i, c in enumerate(chunks)
                ],
            }
            documents.append(doc)

    return documents, skipped


def ingest_batch(documents: list[dict]) -> dict:
    """Send a batch of documents to the Memory Bus API."""
    payload = {"agent": "alexandria", "documents": documents}
    resp = requests.post(
        f"{API_BASE}/api/v1/ingest",
        json=payload,
        headers={"X-API-Key": API_KEY, "Content-Type": "application/json"},
        timeout=300,
    )
    resp.raise_for_status()
    return resp.json()


def main():
    print(f"Scanning vault: {VAULT}")
    documents, skipped = collect_documents(VAULT)
    print(f"Found {len(documents)} unique documents ({skipped} skipped)")

    total_chunks = sum(len(d["chunks"]) for d in documents)
    print(f"Total chunks: {total_chunks}")

    # Ingest in batches
    for i in range(0, len(documents), BATCH_SIZE):
        batch = documents[i : i + BATCH_SIZE]
        batch_chunks = sum(len(d["chunks"]) for d in batch)
        print(
            f"  Batch {i // BATCH_SIZE + 1}/{(len(documents) + BATCH_SIZE - 1) // BATCH_SIZE}: "
            f"{len(batch)} docs, {batch_chunks} chunks... ",
            end="",
            flush=True,
        )
        try:
            result = ingest_batch(batch)
            print(
                f"OK — {result['chunks_count']} ch, {result['embedded_count']} emb, "
                f"{result['failed_count']} fails"
            )
        except Exception as e:
            print(f"FAIL: {e}")

    print("Done!")


if __name__ == "__main__":
    main()
