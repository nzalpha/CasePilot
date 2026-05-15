from __future__ import annotations

import logging
from typing import Any

from neo4j.exceptions import Neo4jError, ServiceUnavailable

from backend.ingestion.embedder import OpenAIEmbedder
from backend.models.schemas import ChunkResult


logger = logging.getLogger(__name__)


def record_to_chunk_result(record: Any, score: float | None = None) -> ChunkResult:
    return ChunkResult(
        chunk_id=record["chunk_id"],
        text=record["text"],
        score=float(record["score"] if score is None else score),
        doc_link=record["doc_link"],
        page_number=int(record["page_number"] or 0),
        document_id=record["document_id"],
    )


class VectorSearcher:
    def __init__(
        self,
        driver: Any,
        embedder: OpenAIEmbedder | None = None,
    ) -> None:
        self.driver = driver
        self.embedder = embedder or OpenAIEmbedder()

    async def search(self, question: str, top_k: int = 5) -> list[ChunkResult]:
        embedding = await self.embedder.embed_text(question)
        query = """
        CALL db.index.vector.queryNodes(
          'chunk_embedding', $top_k, $embedding
        )
        YIELD node AS chunk, score
        MATCH (d:Document)-[:HAS_CHUNK]->(chunk)
        RETURN chunk.id AS chunk_id,
               chunk.text AS text,
               chunk.doc_link AS doc_link,
               chunk.page_number AS page_number,
               d.id AS document_id,
               score
        """
        try:
            with self.driver.session() as session:
                records = session.run(query, top_k=top_k, embedding=embedding)
                return [record_to_chunk_result(record) for record in records]
        except (Neo4jError, ServiceUnavailable) as exc:
            logger.exception("Vector search failed: %s", exc)
            raise
