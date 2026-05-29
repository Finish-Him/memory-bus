"""Embedding service — multi-provider: OpenAI, OpenRouter, or local SentenceTransformers."""

import os
from openai import AsyncOpenAI


class Embedder:
    """Generates embeddings via OpenAI-compatible API or local model."""

    def __init__(self):
        self.client: AsyncOpenAI = None
        self.local_model = None
        self.model: str = "text-embedding-3-small"
        self.dimensions: int = 1536
        self.provider: str = "openai"

    async def configure(self, model: str, dimensions: int):
        self.model = model
        self.dimensions = dimensions
        self.provider = os.getenv("EMBEDDING_PROVIDER", "openai")

        if self.provider == "local":
            # Use sentence-transformers locally (CPU)
            from sentence_transformers import SentenceTransformer

            local_model_name = os.getenv("LOCAL_EMBEDDING_MODEL", model)
            self.local_model = SentenceTransformer(local_model_name)
            print(
                f"[Embedder] Loaded local model: {local_model_name} "
                f"(dim={self.local_model.get_sentence_embedding_dimension()})"
            )
        else:
            base_url = os.getenv("EMBEDDING_BASE_URL", "https://api.openai.com/v1")
            api_key = os.getenv("EMBEDDING_API_KEY", os.getenv("OPENAI_API_KEY", ""))
            self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    async def _local_embed(self, texts: list[str]) -> list[list[float]]:
        """Embed using local SentenceTransformer model (CPU)."""
        import asyncio

        loop = asyncio.get_running_loop()
        # Run in thread pool to avoid blocking
        embeddings = await loop.run_in_executor(
            None,
            lambda: self.local_model.encode(
                texts,
                normalize_embeddings=True,
                show_progress_bar=False,
            ).tolist(),
        )

        # Pad to target dimensions if model output is smaller
        result = []
        for vec in embeddings:
            if len(vec) < self.dimensions:
                vec = list(vec) + [0.0] * (self.dimensions - len(vec))
            result.append(vec[: self.dimensions])
        return result

    async def _openai_embed(self, texts: list[str]) -> list[list[float]]:
        """Embed via OpenAI-compatible API."""
        response = await self.client.embeddings.create(
            model=self.model,
            input=texts,
            dimensions=self.dimensions,
        )
        return [d.embedding for d in response.data]

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if self.provider == "local":
            return await self._local_embed(texts)
        else:
            return await self._openai_embed(texts)

    async def embed_single(self, text: str) -> list[float]:
        results = await self.embed([text])
        return results[0]
