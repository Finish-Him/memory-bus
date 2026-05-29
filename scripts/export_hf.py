"""Export Memory Bus data to HuggingFace dataset format (JSONL)."""

import os, json, sys, hashlib
from datetime import datetime

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def export_agent(
    agent: str,
    output_dir: str = "./hf_exports",
    purpose_filter: str = None,
    limit: int = None,
):
    """Export chunks from an agent schema to HuggingFace JSONL format."""
    import asyncpg

    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:password@localhost:5432/memory_bus",
    ).replace("postgresql+asyncpg://", "postgres://")

    os.makedirs(output_dir, exist_ok=True)

    async def _export():
        conn = await asyncpg.connect(DATABASE_URL)

        query = f"""
            SELECT
                c.id,
                d.title,
                c.content,
                c.sensitivity,
                c.metadata,
                c.created_at,
                d.source_path,
                d.source_kind
            FROM {agent}.chunks c
            JOIN {agent}.documents d ON d.id = c.document_id
        """
        params = []
        if purpose_filter:
            query += " WHERE c.metadata->>'purpose' = $1"
            params.append(purpose_filter)
        query += " ORDER BY c.created_at"
        if limit:
            query += f" LIMIT {limit}"

        rows = await conn.fetch(query, *params)
        await conn.close()

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Finish-Him__{agent}-curated-rag-v1_{timestamp}.jsonl"
        filepath = os.path.join(output_dir, filename)

        count = 0
        with open(filepath, "w", encoding="utf-8") as f:
            for row in rows:
                meta = row["metadata"]
                if isinstance(meta, str):
                    meta = json.loads(meta)

                record = {
                    "id": str(row["id"]),
                    "title": row["title"],
                    "content": row["content"],
                    "metadata": {
                        "owner_agent": agent,
                        "purpose": meta.get("purpose", "rag"),
                        "sensitivity": row["sensitivity"],
                        "source_path": row["source_path"],
                        "source_kind": row["source_kind"],
                        "exported_at": timestamp,
                        **(meta if isinstance(meta, dict) else {}),
                    },
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                count += 1

        print(f"Exported {count} records to {filepath}")

    import asyncio

    asyncio.run(_export())


def export_all(output_dir: str = "./hf_exports"):
    """Export all agent schemas."""
    for agent in ["atlas", "zeus", "alexandria", "arquimedes"]:
        try:
            export_agent(agent, output_dir)
        except Exception as e:
            print(f"  {agent}: FAIL — {e}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Export Memory Bus to HuggingFace format")
    parser.add_argument("--agent", choices=["atlas", "zeus", "alexandria", "arquimedes", "all"], default="all")
    parser.add_argument("--output", default="./hf_exports")
    parser.add_argument("--purpose", default=None)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    if args.agent == "all":
        export_all(args.output)
    else:
        export_agent(args.agent, args.output, args.purpose, args.limit)
