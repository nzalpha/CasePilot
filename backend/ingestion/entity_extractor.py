from __future__ import annotations

import json
import logging
from typing import Any, TypedDict

from openai import AsyncOpenAI

from backend.config import settings
from backend.ingestion.embedder import retry_async


logger = logging.getLogger(__name__)


class ExtractedEntities(TypedDict):
    products: list[str]
    versions: list[str]
    symptoms: list[str]
    root_causes: list[str]
    resolutions: list[str]
    errors: list[str]
    features: list[str]


ENTITY_KEYS = (
    "products",
    "versions",
    "symptoms",
    "root_causes",
    "resolutions",
    "errors",
    "features",
)


PROMPT_TEMPLATE = """You are a technical knowledge extraction assistant.
Read the following text and extract named entities.

Return ONLY valid JSON in this exact structure:
{
  "products": ["name1", "name2"],
  "versions": ["v1", "v2"],
  "symptoms": ["symptom1"],
  "root_causes": ["cause1"],
  "resolutions": ["resolution1"],
  "errors": ["error_code1"],
  "features": ["feature1"]
}

Rules:
- Only extract entities clearly present in the text
- Return empty arrays if none found for a category
- Return JSON only, no explanation, no markdown
  
Text:
{{chunk_text}}
"""


def empty_entities() -> ExtractedEntities:
    return {
        "products": [],
        "versions": [],
        "symptoms": [],
        "root_causes": [],
        "resolutions": [],
        "errors": [],
        "features": [],
    }


def normalize_entities(raw: dict[str, Any]) -> ExtractedEntities:
    normalized = empty_entities()
    for key in ENTITY_KEYS:
        values = raw.get(key, [])
        if not isinstance(values, list):
            continue

        seen: set[str] = set()
        cleaned: list[str] = []
        for value in values:
            if not isinstance(value, str):
                continue
            name = " ".join(value.split())
            if name and name.lower() not in seen:
                seen.add(name.lower())
                cleaned.append(name)
        normalized[key] = cleaned
    return normalized


def parse_entity_json(content: str) -> ExtractedEntities:
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        logger.warning("Entity extraction returned invalid JSON: %s", content[:200])
        return empty_entities()

    if not isinstance(parsed, dict):
        return empty_entities()
    return normalize_entities(parsed)


class OpenAIEntityExtractor:
    def __init__(self, client: AsyncOpenAI | None = None, model: str | None = None) -> None:
        self.client = client or AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = model or settings.openai_llm_model

    async def extract_entities(self, chunk_text: str) -> ExtractedEntities:
        prompt = PROMPT_TEMPLATE.replace("{{chunk_text}}", chunk_text)

        async def call_openai() -> ExtractedEntities:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content or "{}"
            return parse_entity_json(content)

        return await retry_async(call_openai, "OpenAI entity extraction")
