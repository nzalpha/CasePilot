from __future__ import annotations

from typing import Any

from openai import AsyncOpenAI

from backend.config import settings
from backend.ingestion.embedder import retry_async
from backend.models.schemas import ChunkResult


FALLBACK_ANSWER = (
    "I don't have enough information in the knowledge base "
    "to answer this question."
)

PROMPT_TEMPLATE = """You are a technical support assistant. Answer the question
using ONLY the context provided below.

Rules:
- Base your answer strictly on the provided context
- If the context does not contain enough information to
  answer, say: "I don't have enough information in the
  knowledge base to answer this question."
- Be concise and structured
- Include specific steps or commands where relevant
- Do not make up information not present in the context

Context:
{{context}}

Question: {{question}}

Answer:
"""


def unique_sources(chunks: list[ChunkResult]) -> list[str]:
    sources: list[str] = []
    seen_sources: set[str] = set()
    for chunk in chunks:
        if chunk.doc_link and chunk.doc_link not in seen_sources:
            seen_sources.add(chunk.doc_link)
            sources.append(chunk.doc_link)
    return sources


def build_context(chunks: list[ChunkResult]) -> str:
    context_parts = []
    for chunk in chunks:
        context_parts.append(
            "\n".join(
                [
                    f"Source: {chunk.doc_link}",
                    f"Document ID: {chunk.document_id}",
                    f"Page: {chunk.page_number}",
                    f"Chunk ID: {chunk.chunk_id}",
                    chunk.text,
                ]
            )
        )
    return "\n\n---\n\n".join(context_parts)


async def generate_answer(
    question: str,
    chunks: list[ChunkResult],
    model: str,
    confidence: float = 0.0,
    client: AsyncOpenAI | None = None,
) -> dict[str, Any]:
    if not chunks:
        return {
            "answer": FALLBACK_ANSWER,
            "confidence": 0.0,
            "sources": [],
        }

    openai_client = client or AsyncOpenAI(api_key=settings.openai_api_key)
    context = build_context(chunks)
    prompt = (
        PROMPT_TEMPLATE.replace("{{context}}", context)
        .replace("{{question}}", question)
    )

    async def call_openai() -> str:
        response = await openai_client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        return response.choices[0].message.content or FALLBACK_ANSWER

    answer = await retry_async(call_openai, "OpenAI answer generation")
    return {
        "answer": answer,
        "confidence": confidence,
        "sources": unique_sources(chunks),
    }
