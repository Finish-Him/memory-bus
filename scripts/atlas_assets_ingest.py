"""Ingest Atlas individual asset data into Memory Bus (schema: atlas)."""
import os, json, sys, requests, hashlib

API_BASE = os.environ.get("MEMORY_BUS_URL", "https://msc-academy.com.br/memory-bus")
BUS_KEY = os.environ.get("MEMORY_BUS_API_KEY", os.environ.get("API_KEY", ""))
DATASET = os.path.expanduser(
    "~/workspace/Msc-company/Ai-training/agents/atlas-dirtic/bens.jsonl"
)

if not BUS_KEY:
    print("ERROR: API_KEY or MEMORY_BUS_API_KEY not set")
    sys.exit(1)

BATCH_SIZE = 50


def ingest_atlas_assets():
    assets = []
    with open(DATASET, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            assets.append(json.loads(line))

    print(f"Loaded {len(assets)} Atlas assets")

    for i in range(0, len(assets), BATCH_SIZE):
        batch = assets[i : i + BATCH_SIZE]
        documents = []

        for asset in batch:
            tag = asset.get("tag", "unknown")
            desc = asset.get("descricao", "Sem descricao")
            cat = asset.get("categoria", "")
            marca = asset.get("marca", "")
            loc = asset.get("localizacao", "")
            setor = asset.get("setor", "")
            status = asset.get("status", "")
            valor = asset.get("valor_aquisicao", 0)
            obs = asset.get("observacao", "")

            content = (
                f"Patrimonio: {tag} | Descricao: {desc} | Marca: {marca} | "
                f"Categoria: {cat} | Status: {status} | Localizacao: {loc} | "
                f"Setor: {setor} | Valor: R$ {valor:,.2f}"
            )
            if obs:
                content += f" | Obs: {obs}"

            checksum = hashlib.sha256(content.encode()).hexdigest()

            documents.append({
                "title": f"Bem {tag} — {desc}",
                "source_path": f"atlas-dirtic/bens.jsonl#{tag}",
                "source_kind": "manual",
                "checksum": checksum,
                "chunks": [{
                    "content": content,
                    "chunk_index": 0,
                    "sensitivity": "restricted",
                    "can_embed_externally": True,
                    "metadata": {
                        "owner_agent": "atlas",
                        "purpose": "rag",
                        "source_scope": "internal",
                        "pii_class": "low",
                        "review_status": "approved",
                        "chunk_type": "bem_individual",
                        "tag": tag,
                        "categoria": cat,
                        "setor": setor,
                        "flag_status": status,
                        "valor_aquisicao": valor,
                    },
                }],
            })

        payload = {"agent": "atlas", "documents": documents}
        try:
            resp = requests.post(
                f"{API_BASE}/api/v1/ingest",
                json=payload,
                headers={"X-API-Key": BUS_KEY, "Content-Type": "application/json"},
                timeout=120,
            )
            resp.raise_for_status()
            result = resp.json()
            total_batches = (len(assets) + BATCH_SIZE - 1) // BATCH_SIZE
            print(
                f"  Batch {i // BATCH_SIZE + 1}/{total_batches}: "
                f"{result['documents_count']} docs, "
                f"{result['chunks_count']} ch, "
                f"{result['embedded_count']} emb"
            )
        except Exception as e:
            print(f"  Batch {i // BATCH_SIZE + 1}: FAIL — {e}")

    print("Atlas assets ingest done!")


if __name__ == "__main__":
    ingest_atlas_assets()
