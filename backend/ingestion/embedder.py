from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from openai import AsyncOpenAI

from backend.config import settings


logger = logging.getLogger(__name__)


async def retry_async(
    operation: Callable[[], Awaitable[Any]],
    operation_name: str,
    attempts: int = 3,
    initial_delay: float = 1.0,
) -> Any:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return await operation()
        except Exception as exc:
            last_error = exc
            logger.warning(
                "%s failed on attempt %s/%s: %s",
                operation_name,
                attempt,
                attempts,
                exc,
            )
            if attempt < attempts:
                await asyncio.sleep(initial_delay * (2 ** (attempt - 1)))
    raise RuntimeError(f"{operation_name} failed after {attempts} attempts") from last_error


class OpenAIEmbedder:
    def __init__(
        self,
        client: AsyncOpenAI | None = None,
        model: str | None = None,
        dimensions: int | None = None,
    ) -> None:
        self.client = client or AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = model or settings.openai_embedding_model
        self.dimensions = dimensions or settings.embedding_dimensions

    async def embed_text(self, text: str) -> list[float]:
        async def call_openai() -> list[float]:
            response = await self.client.embeddings.create(
                model=self.model,
                input=text,
            )
            embedding = response.data[0].embedding
            if len(embedding) != self.dimensions:
                raise ValueError(
                    f"Expected embedding dimension {self.dimensions}, "
                    f"received {len(embedding)}"
                )
            return list(embedding)

        return await retry_async(call_openai, "OpenAI embedding")
