from __future__ import annotations

import logging
from typing import Any

from neo4j.exceptions import Neo4jError, ServiceUnavailable

from backend.models.schemas import ChunkResult
from backend.retrieval.vector_searcher import record_to_chunk_result


logger = logging.getLogger(__name__)


class FulltextSearcher:
    def __init__(self, driver: Any) -> None:
        self.driver = driver

    async def search(self, question: str, top_k: int = 5) -> list[ChunkResult]:
        cypher = """
        CALL db.index.fulltext.queryNodes(
          'chunk_text', $search_text
        )
        YIELD node AS chunk, score
        MATCH (d:Document)-[:HAS_CHUNK]->(chunk)
        RETURN chunk.id AS chunk_id,
               chunk.text AS text,
               chunk.doc_link AS doc_link,
               chunk.page_number AS page_number,
               d.id AS document_id,
               score
        LIMIT $top_k
        """
        try:
            with self.driver.session() as session:
                records = session.run(cypher, search_text=question, top_k=top_k)
                return [record_to_chunk_result(record) for record in records]
        except (Neo4jError, ServiceUnavailable) as exc:
            logger.exception("Fulltext search failed: %s", exc)
            raise
