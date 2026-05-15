from __future__ import annotations

import logging
from typing import Any

from neo4j.exceptions import Neo4jError, ServiceUnavailable

from backend.models.schemas import ChunkResult
from backend.retrieval.vector_searcher import record_to_chunk_result


logger = logging.getLogger(__name__)


class GraphExpander:
    def __init__(self, driver: Any) -> None:
        self.driver = driver

    async def expand(
        self,
        chunks: list[ChunkResult],
        max_additional_chunks: int = 10,
    ) -> list[ChunkResult]:
        if not chunks:
            return []

        query = """
        MATCH (start:Chunk {id: $chunk_id})
        CALL {
          WITH start
          MATCH (start)-[:RELATED_TO]-(related:Chunk)
          RETURN related
          UNION
          WITH start
          MATCH (start)-[:MENTIONS]->(:Entity)<-[:MENTIONS]-(related:Chunk)
          WHERE related.id <> start.id
          RETURN related
        }
        MATCH (d:Document)-[:HAS_CHUNK]->(related)
        RETURN DISTINCT related.id AS chunk_id,
                        related.text AS text,
                        related.doc_link AS doc_link,
                        related.page_number AS page_number,
                        d.id AS document_id
        """
        seen_chunk_ids = {chunk.chunk_id for chunk in chunks}
        expanded_chunks: list[ChunkResult] = []

        try:
            with self.driver.session() as session:
                for chunk in chunks:
                    records = session.run(query, chunk_id=chunk.chunk_id)
                    for record in records:
                        chunk_id = record["chunk_id"]
                        if chunk_id in seen_chunk_ids:
                            continue

                        seen_chunk_ids.add(chunk_id)
                        expanded_chunks.append(record_to_chunk_result(record, score=0.0))
                        if len(expanded_chunks) >= max_additional_chunks:
                            return expanded_chunks
            return expanded_chunks
        except (Neo4jError, ServiceUnavailable) as exc:
            logger.exception("Graph expansion failed: %s", exc)
            raise
