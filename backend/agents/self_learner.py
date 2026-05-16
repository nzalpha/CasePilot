from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from openai import AsyncOpenAI

from backend.config import settings
from backend.ingestion.chunker import chunk_pages
from backend.ingestion.embedder import OpenAIEmbedder, retry_async
from backend.ingestion.entity_extractor import OpenAIEntityExtractor
from backend.ingestion.graph_writer import GraphWriter


logger = logging.getLogger(__name__)

PII_PROMPT = (
    "Rewrite the following support Q&A with all personal information "
    "removed. Replace names, email addresses, phone numbers, and company names "
    "with generic placeholders like [Customer] or [Company]. Keep all technical "
    "details. Return only the rewritten Q&A, no explanation."
)


async def strip_pii_from_qa(
    question: str,
    answer: str,
    client: AsyncOpenAI | None = None,
) -> str:
    openai_client = client or AsyncOpenAI(api_key=settings.openai_api_key)
    qa_text = f"Question: {question}\n\nAnswer: {answer}"

    async def call_openai() -> str:
        response = await openai_client.chat.completions.create(
            model=settings.openai_llm_model,
            temperature=0,
            messages=[
                {"role": "system", "content": PII_PROMPT},
                {"role": "user", "content": qa_text},
            ],
        )
        return response.choices[0].message.content or qa_text

    return await retry_async(call_openai, "OpenAI PII removal")


async def ingest_resolved_qa(
    question: str,
    answer: str,
    case_number: str,
) -> bool:
    try:
        clean_qa = await strip_pii_from_qa(question, answer)
        document_id = f"resolved_case_{case_number}"
        pages = [{"page_number": 0, "text": clean_qa}]
        chunks = chunk_pages(pages, document_id=document_id)
        if not chunks:
            return False

        embedder = OpenAIEmbedder()
        entity_extractor = OpenAIEntityExtractor()

        async def enrich_chunk(chunk: dict[str, Any]) -> tuple[dict[str, Any], dict]:
            embedding_task = asyncio.create_task(embedder.embed_text(chunk["text"]))
            entities_task = asyncio.create_task(
                entity_extractor.extract_entities(chunk["text"])
            )
            embedding, entities = await asyncio.gather(embedding_task, entities_task)
            enriched_chunk = dict(chunk)
            enriched_chunk["embedding"] = embedding
            return enriched_chunk, entities

        enriched_results = await asyncio.gather(
            *(enrich_chunk(chunk) for chunk in chunks)
        )
        enriched_chunks = [chunk for chunk, _entities in enriched_results]
        entities_by_chunk = {
            chunk["chunk_id"]: entities for chunk, entities in enriched_results
        }

        document = {
            "id": document_id,
            "title": f"Resolved Case {case_number}",
            "source": f"salesforce_case_{case_number}",
            "source_type": "url",
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
            "status": "completed",
        }
        GraphWriter().write_document_graph(document, enriched_chunks, entities_by_chunk)
        return True
    except Exception as exc:
        logger.exception("Failed to ingest resolved Q&A for case %s: %s", case_number, exc)
        return False
