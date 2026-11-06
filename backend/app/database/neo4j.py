import asyncio
import logging
from uuid import UUID
from neo4j import AsyncGraphDatabase
from neo4j.exceptions import ServiceUnavailable, SessionExpired

from backend.app.settings import setting
from backend.app.schema.graph import GraphExtraction

logger = logging.getLogger(__name__)

class Neo4jClient:

    def __init__(self):
        # Configure driver for cloud-hosted Neo4j Aura with keep-alive, liveness checks,
        # and connection recycling to prevent TCP connection resets (WinError 10054 / SessionExpired)
        self.driver = AsyncGraphDatabase.driver(
            setting.neo4j_db_uri,
            auth=(
                setting.neo4j_username,
                setting.neo4j_password.get_secret_value(),
            ),
            max_connection_lifetime=180,
            liveness_check_timeout=30,
            connection_timeout=30,
            max_connection_pool_size=50,
            connection_acquisition_timeout=60.0,
        )

    async def init_schema(self):
        """
        Ensures essential constraints and composite indexes exist to prevent
        expensive full-graph scans on entity and document MERGE/MATCH operations.
        """
        async with self.driver.session() as session:
            try:
                await session.run(
                    """
                    CREATE CONSTRAINT entity_user_name_unique IF NOT EXISTS
                    FOR (e:Entity) REQUIRE (e.user_id, e.name) IS UNIQUE
                    """
                )
                logger.info("Neo4j uniqueness constraint verified: entity_user_name_unique")
            except Exception as e:
                logger.warning("Failed to create Entity uniqueness constraint (may already exist or unsupported): %s", e)

            try:
                await session.run(
                    """
                    CREATE INDEX doc_user_id_idx IF NOT EXISTS
                    FOR (d:Document) ON (d.user_id, d.id)
                    """
                )
                logger.info("Neo4j index verified: doc_user_id_idx")
            except Exception as e:
                logger.warning("Failed to create Document index (may already exist): %s", e)

    async def insert_graph(
        self,
        graph: GraphExtraction,
        file_name: str,
        user_id: UUID | str,
        doc_id: UUID | str,
    ):
        """
        Inserts document, entities, and relationships with strict tenant scoping (user_id on all nodes).
        Uses execute_write for automatic managed transaction retries on SessionExpired/ServiceUnavailable.
        """
        entities = [
            entity.model_dump()
            for entity in graph.entities
        ]
        relationships = [
            relationship.model_dump()
            for relationship in graph.relationships
        ]

        async def _write_tx(tx):
            # 1. Merge root Document node
            await tx.run(
                """
                MERGE (d:Document {id: $doc_id, user_id: $user_id})
                SET d.filename = $file_name
                """,
                user_id=str(user_id),
                doc_id=str(doc_id),
                file_name=file_name,
            )

            # 2. Merge entities and connect (:Document)-[:MENTIONS]->(:Entity)
            if entities:
                await tx.run(
                    """
                    MATCH (d:Document {id: $doc_id, user_id: $user_id})
                    UNWIND $entities AS entity
                    MERGE (e:Entity {name: entity.name, user_id: $user_id})
                    SET e.type = entity.type,
                        e.description = entity.description
                    MERGE (d)-[:MENTIONS]->(e)
                    """,
                    user_id=str(user_id),
                    doc_id=str(doc_id),
                    entities=entities,
                )

            # 3. Merge relationships between entities
            if relationships:
                await tx.run(
                    """
                    UNWIND $relationships AS relationship
                    MATCH (source:Entity {name: relationship.source, user_id: $user_id})
                    MATCH (target:Entity {name: relationship.target, user_id: $user_id})
                    MERGE (source)-[r:RELATED_TO {type: relationship.type}]->(target)
                    SET r.description = relationship.description
                    """,
                    user_id=str(user_id),
                    relationships=relationships,
                )

        async with self.driver.session() as session:
            await session.execute_write(_write_tx)

    async def close(self):
        await self.driver.close()

    async def delete_graph(self, doc_id: UUID | str, user_id: UUID | str):
        """
        Deleting graph when an error is encountered during upload, scoped strictly to user_id.
        """
        try:
            async with self.driver.session() as session:
                await session.run(
                    """
                    MATCH (d:Document {id: $doc_id, user_id: $user_id})
                    DETACH DELETE d
                    """,
                    doc_id=str(doc_id),
                    user_id=str(user_id)
                )
        except Exception as e:
            logger.warning("Failed to delete graph on rollback for doc_id=%s: %s", doc_id, e)

neo4j_client = Neo4jClient()
