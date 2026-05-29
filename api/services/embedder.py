"""Embedding service — OpenAI / OpenRouter compatible."""

import os
from openai import AsyncOpenAI


class Embedder:
    """Generates embeddings via OpenAI-compatible API."""

    def __init__(self):
        self.client: AsyncOpenAI = None
        self.model: str = "text-embedding-3-small"
        self.dimensions: int = 1536

    async def configure(self, model: str, dimensions: int):
        self.model = model
        self.dimensions = dimensions

        base_url = os.getenv("EMBEDDING_BASE_URL", "https://api.openai.com/v1")
        api_key = os.getenv("EMBEDDING_API_KEY", os.getenv("OPENAI_API_KEY", ""))

        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
        )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts."""
        if not self.client:
            raise RuntimeError("Embedder not configured")
        response = await self.client.embeddings.create(
            model=self.model,
            input=texts,
            dimensions=self.dimensions,
        )
        return [d.embedding for d in response.data]

    async def embed_single(self, text: str) -> list[float]:
        results = await self.embed([text])
        return results[0]
