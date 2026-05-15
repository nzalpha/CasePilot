from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError, ServiceUnavailable

from backend.config import settings
from backend.ingestion.entity_extractor import ExtractedEntities


logger = logging.getLogger(__name__)


ENTITY_LABELS = {
    "products": "Product",
    "versions": "Version",
    "symptoms": "Symptom",
    "root_causes": "RootCause",
    "resolutions": "Resolution",
    "errors": "Error",
    "features": "Feature",
}


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "unknown"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class GraphWriter:
    def __init__(
        self,
        uri: str | None = None,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        self.uri = uri if uri is not None else settings.neo4j_uri
        self.username = username if username is not None else settings.neo4j_username
        self.password = password if password is not None else settings.neo4j_password
        self.driver = None

        if not self.uri or not self.username or not self.password:
            logger.warning("Neo4j settings are incomplete; graph writes are disabled")
            return

        try:
            self.driver = GraphDatabase.driver(
                self.uri,
                auth=(self.username, self.password),
            )
        except Exception as exc:
            logger.exception("Failed to initialize Neo4j driver: %s", exc)
            self.driver = None

    def close(self) -> None:
        if self.driver is not None:
            self.driver.close()

    def create_vector_index(self) -> None:
        if self.driver is None:
            return

        query = """
        CREATE VECTOR INDEX chunk_embedding IF NOT EXISTS
        FOR (c:Chunk) ON (c.embedding)
        OPTIONS { indexConfig: {
          `vector.dimensions`: 1536,
          `vector.similarity_function`: 'cosine'
        }}
        """
        try:
            with self.driver.session() as session:
                session.run(query)
        except (Neo4jError, ServiceUnavailable) as exc:
            logger.exception("Failed to create Neo4j vector index: %s", exc)

    def create_fulltext_index(self) -> None:
        if self.driver is None:
            return

        query = """
        CREATE FULLTEXT INDEX chunk_text IF NOT EXISTS
        FOR (n:Chunk) ON EACH [n.text]
        """
        try:
            with self.driver.session() as session:
                session.run(query)
        except (Neo4jError, ServiceUnavailable) as exc:
            logger.exception("Failed to create Neo4j fulltext index: %s", exc)

    def get_document_by_title(self, title: str) -> dict[str, Any] | None:
        return self._get_document("title", title)

    def get_document_by_source(self, source: str) -> dict[str, Any] | None:
        return self._get_document("source", source)

    def _get_document(self, field: str, value: str) -> dict[str, Any] | None:
        if self.driver is None:
            return None
        if field not in {"title", "source"}:
            raise ValueError("Unsupported document lookup field")

        query = f"""
        MATCH (d:Document {{{field}: $value}})
        RETURN d.id AS document_id,
               d.title AS title,
               d.source AS source,
               d.source_type AS source_type,
               d.status AS status,
               d.uploaded_at AS uploaded_at
        LIMIT 1
        """
        try:
            with self.driver.session() as session:
                record = session.run(query, value=value).single()
                return dict(record) if record else None
        except (Neo4jError, ServiceUnavailable) as exc:
            logger.exception("Failed to look up document by %s: %s", field, exc)
            return None

    def merge_document(
        self,
        document_id: str,
        title: str,
        source: str,
        source_type: str,
        status: str = "processing",
        uploaded_at: str | None = None,
    ) -> None:
        if self.driver is None:
            return

        query = """
        MERGE (d:Document {id: $id})
        SET d.title = $title,
            d.source = $source,
            d.source_type = $source_type,
            d.uploaded_at = coalesce(d.uploaded_at, $uploaded_at),
            d.status = $status
        """
        try:
            with self.driver.session() as session:
                session.run(
                    query,
                    id=document_id,
                    title=title,
                    source=source,
                    source_type=source_type,
                    status=status,
                    uploaded_at=uploaded_at or utc_now_iso(),
                )
        except (Neo4jError, ServiceUnavailable) as exc:
            logger.exception("Failed to merge document %s: %s", document_id, exc)

    def update_document_status(self, document_id: str, status: str) -> None:
        if self.driver is None:
            return

        query = """
        MERGE (d:Document {id: $document_id})
        SET d.status = $status
        """
        try:
            with self.driver.session() as session:
                session.run(query, document_id=document_id, status=status)
        except (Neo4jError, ServiceUnavailable) as exc:
            logger.exception(
                "Failed to update document %s status to %s: %s",
                document_id,
                status,
                exc,
            )

    def write_document_graph(
        self,
        document: dict[str, Any],
        chunks: list[dict[str, Any]],
        entities_by_chunk: dict[str, ExtractedEntities],
    ) -> None:
        if self.driver is None:
            logger.error("Cannot write document graph because Neo4j is not configured")
            raise RuntimeError("Neo4j is not configured")

        try:
            with self.driver.session() as session:
                session.execute_write(
                    self._write_document_graph_tx,
                    document,
                    chunks,
                    entities_by_chunk,
                )
                session.execute_write(self._create_related_chunks_tx, document["id"])
        except (Neo4jError, ServiceUnavailable) as exc:
            logger.exception("Failed to write graph for document %s: %s", document["id"], exc)
            raise

    @staticmethod
    def _write_document_graph_tx(
        tx: Any,
        document: dict[str, Any],
        chunks: list[dict[str, Any]],
        entities_by_chunk: dict[str, ExtractedEntities],
    ) -> None:
        tx.run(
            """
            MERGE (d:Document {id: $id})
            SET d.title = $title,
                d.source = $source,
                d.source_type = $source_type,
                d.uploaded_at = coalesce(d.uploaded_at, $uploaded_at),
                d.status = $status
            """,
            **document,
        )

        for chunk in chunks:
            tx.run(
                """
                MATCH (d:Document {id: $document_id})
                MERGE (c:Chunk {id: $chunk_id})
                SET c.text = $text,
                    c.embedding = $embedding,
                    c.page_number = $page_number,
                    c.position = $position,
                    c.doc_link = $doc_link
                MERGE (d)-[:HAS_CHUNK]->(c)
                """,
                document_id=document["id"],
                chunk_id=chunk["chunk_id"],
                text=chunk["text"],
                embedding=chunk["embedding"],
                page_number=chunk["page_number"],
                position=chunk["position"],
                doc_link=document["source"],
            )

            entities = entities_by_chunk.get(chunk["chunk_id"], {})
            for category, label in ENTITY_LABELS.items():
                names = entities.get(category, []) if isinstance(entities, dict) else []
                for name in names:
                    entity_id = slugify(name)
                    tx.run(
                        f"""
                        MATCH (c:Chunk {{id: $chunk_id}})
                        MERGE (e:Entity:{label} {{id: $entity_id}})
                        SET e.name = $name
                        MERGE (c)-[:MENTIONS]->(e)
                        """,
                        chunk_id=chunk["chunk_id"],
                        entity_id=entity_id,
                        name=name,
                    )

    @staticmethod
    def _create_related_chunks_tx(tx: Any, document_id: str) -> None:
        tx.run(
            """
            MATCH (d:Document {id: $document_id})-[:HAS_CHUNK]->(c1:Chunk)-[:MENTIONS]->(e:Entity)<-[:MENTIONS]-(c2:Chunk)<-[:HAS_CHUNK]-(d)
            WHERE c1.id < c2.id
            WITH c1, c2, count(DISTINCT e) AS shared_entities
            WHERE shared_entities >= 2
            MERGE (c1)-[:RELATED_TO]->(c2)
            """,
            document_id=document_id,
        )

    def list_documents(self) -> list[dict[str, Any]]:
        if self.driver is None:
            return []

        query = """
        MATCH (d:Document)
        OPTIONAL MATCH (d)-[:HAS_CHUNK]->(c:Chunk)
        RETURN d.id AS document_id,
               d.title AS title,
               d.source AS source,
               d.source_type AS source_type,
               d.status AS status,
               d.uploaded_at AS uploaded_at,
               count(c) AS chunk_count
        ORDER BY d.uploaded_at DESC
        """
        try:
            with self.driver.session() as session:
                return [dict(record) for record in session.run(query)]
        except (Neo4jError, ServiceUnavailable) as exc:
            logger.exception("Failed to list documents: %s", exc)
            return []

    def delete_document(self, document_id: str) -> dict[str, int] | None:
        if self.driver is None:
            return None

        try:
            with self.driver.session() as session:
                return session.execute_write(self._delete_document_tx, document_id)
        except (Neo4jError, ServiceUnavailable) as exc:
            logger.exception("Failed to delete document %s: %s", document_id, exc)
            raise

    @staticmethod
    def _delete_document_tx(tx: Any, document_id: str) -> dict[str, int] | None:
        document_record = tx.run(
            """
            MATCH (d:Document {id: $document_id})
            RETURN d.id AS id
            LIMIT 1
            """,
            document_id=document_id,
        ).single()
        if not document_record:
            return None

        chunk_record = tx.run(
            """
            MATCH (:Document {id: $document_id})-[:HAS_CHUNK]->(c:Chunk)
            RETURN count(DISTINCT c) AS deleted_chunks
            """,
            document_id=document_id,
        ).single()
        deleted_chunks = chunk_record["deleted_chunks"] if chunk_record else 0

        entity_record = tx.run(
            """
            MATCH (:Document {id: $document_id})-[:HAS_CHUNK]->(:Chunk)-[:MENTIONS]->(e:Entity)
            RETURN collect(DISTINCT e.id) AS entity_ids
            """,
            document_id=document_id,
        ).single()
        entity_ids = entity_record["entity_ids"] if entity_record else []

        tx.run(
            """
            MATCH (d:Document {id: $document_id})-[has_chunk:HAS_CHUNK]->(c:Chunk)
            OPTIONAL MATCH (c)-[mentions:MENTIONS]->(:Entity)
            OPTIONAL MATCH (c)-[related:RELATED_TO]-(:Chunk)
            WITH collect(DISTINCT has_chunk) +
                 collect(DISTINCT mentions) +
                 collect(DISTINCT related) AS relationships,
                 collect(DISTINCT c) AS chunks
            FOREACH (relationship IN relationships | DELETE relationship)
            FOREACH (chunk IN chunks | DELETE chunk)
            """,
            document_id=document_id,
        )

        deleted_entity_record = tx.run(
            """
            MATCH (e:Entity)
            WHERE e.id IN $entity_ids
              AND NOT (:Chunk)-[:MENTIONS]->(e)
            WITH collect(e) AS orphan_entities
            WITH orphan_entities, size(orphan_entities) AS deleted_entities
            FOREACH (entity IN orphan_entities | DETACH DELETE entity)
            RETURN deleted_entities
            """,
            entity_ids=entity_ids,
        ).single()
        deleted_entities = (
            deleted_entity_record["deleted_entities"] if deleted_entity_record else 0
        )

        tx.run(
            """
            MATCH (d:Document {id: $document_id})
            OPTIONAL MATCH (d)-[relationship]-()
            WITH d, collect(relationship) AS relationships
            FOREACH (relationship IN relationships | DELETE relationship)
            DELETE d
            """,
            document_id=document_id,
        )

        return {
            "deleted_chunks": deleted_chunks,
            "deleted_entities": deleted_entities,
        }
