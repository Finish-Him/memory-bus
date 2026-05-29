"""Ingest Zeus style SFT data into Memory Bus (schema: zeus)."""
import os, json, sys, requests, hashlib

API_BASE = os.environ.get("MEMORY_BUS_URL", "https://msc-academy.com.br/memory-bus")
BUS_KEY = os.environ.get("MEMORY_BUS_API_KEY", os.environ.get("API_KEY", ""))
DATASET = os.path.expanduser(
    "~/workspace/Msc-company/Ai-training/datasets/Finish-him__zeus-style-sft-v1/data/train.jsonl"
)

if not BUS_KEY:
    print("ERROR: API_KEY or MEMORY_BUS_API_KEY not set")
    sys.exit(1)

BATCH_SIZE = 10


def ingest_zeus():
    conversations = []
    with open(DATASET, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            conversations.append(json.loads(line))

    print(f"Loaded {len(conversations)} Zeus conversations")

    for i in range(0, len(conversations), BATCH_SIZE):
        batch = conversations[i : i + BATCH_SIZE]
        documents = []

        for conv in batch:
            conv_id = conv.get("id", "unknown")
            content_parts = []
            for msg in conv.get("messages", []):
                role = msg.get("role", "unknown")
                text = msg.get("content", "")
                if role == "system":
                    continue
                content_parts.append(f"[{role}]: {text}")

            full_content = "\n".join(content_parts)
            checksum = hashlib.sha256(full_content.encode()).hexdigest()

            chunks = []
            turns = conv.get("messages", [])
            current_turn = []
            chunk_idx = 0

            for msg in turns:
                if msg["role"] == "system":
                    continue
                current_turn.append(f"[{msg['role']}]: {msg['content']}")
                if msg["role"] == "assistant":
                    chunks.append({
                        "content": "\n".join(current_turn),
                        "chunk_index": chunk_idx,
                        "sensitivity": "blocked",
                        "can_embed_externally": False,
                        "metadata": {
                            "owner_agent": "zeus",
                            "purpose": "style_sft",
                            "source_scope": "private",
                            "pii_class": "medium",
                            "review_status": "needs_review",
                            "conv_id": conv_id,
                        },
                    })
                    current_turn = []
                    chunk_idx += 1

            if chunks:
                documents.append({
                    "title": f"zeus-conv-{conv_id}",
                    "source_path": f"zeus-style-sft/{conv_id}",
                    "source_kind": "whatsapp",
                    "checksum": checksum,
                    "chunks": chunks,
                })

        if not documents:
            continue

        payload = {"agent": "zeus", "documents": documents}
        try:
            resp = requests.post(
                f"{API_BASE}/api/v1/ingest",
                json=payload,
                headers={"X-API-Key": BUS_KEY, "Content-Type": "application/json"},
                timeout=120,
            )
            resp.raise_for_status()
            result = resp.json()
            print(
                f"  Batch {i // BATCH_SIZE + 1}: "
                f"{result['documents_count']} docs, "
                f"{result['chunks_count']} ch, "
                f"{result['embedded_count']} emb, "
                f"{result['blocked_count']} blocked"
            )
        except Exception as e:
            print(f"  Batch {i // BATCH_SIZE + 1}: FAIL — {e}")

    print("Zeus ingest done!")


if __name__ == "__main__":
    ingest_zeus()
