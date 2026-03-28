"""PostgreSQL adapter with JSONB storage and single-statement atomicity.

Requires: pip install 'mcp-nexmem[postgres]'
"""

from __future__ import annotations

import json

from nexmem_mcp.adapters import register_adapter
from nexmem_mcp.adapters.base import StorageAdapter
from nexmem_mcp.config import NexMemConfig
from nexmem_mcp.types import (
    Entity,
    KnowledgeGraph,
    ObservationDeletion,
    ObservationResult,
    ObservationUpdate,
    Relation,
)

try:
    import asyncpg
except ImportError:
    raise ImportError(
        "PostgreSQL adapter requires 'asyncpg'. Install with: pip install 'mcp-nexmem[postgres]'"
    )


@register_adapter("postgres")
class PostgresAdapter(StorageAdapter):
    def __init__(self, config: NexMemConfig) -> None:
        self._dsn = config.postgres_uri
        self._pool: asyncpg.Pool | None = None

    async def _get_pool(self) -> asyncpg.Pool:
        if self._pool is None:
            self._pool = await asyncpg.create_pool(self._dsn, min_size=1, max_size=5)
            await self._init_schema()
        return self._pool

    async def _init_schema(self) -> None:
        pool = self._pool
        assert pool is not None
        async with pool.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS entities (
                    namespace TEXT NOT NULL,
                    name TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    observations JSONB NOT NULL DEFAULT '[]'::jsonb,
                    PRIMARY KEY (namespace, name)
                );
                CREATE TABLE IF NOT EXISTS relations (
                    namespace TEXT NOT NULL,
                    from_entity TEXT NOT NULL,
                    to_entity TEXT NOT NULL,
                    relation_type TEXT NOT NULL,
                    PRIMARY KEY (namespace, from_entity, to_entity, relation_type)
                );
                """
            )

    async def create_entities(
        self, namespace: str, entities: list[Entity]
    ) -> list[Entity]:
        pool = await self._get_pool()
        created: list[Entity] = []
        async with pool.acquire() as conn:
            for e in entities:
                result = await conn.execute(
                    "INSERT INTO entities (namespace, name, entity_type, observations) "
                    "VALUES ($1, $2, $3, $4) ON CONFLICT DO NOTHING",
                    namespace,
                    e.name,
                    e.entityType,
                    json.dumps(e.observations),
                )
                if result.endswith("1"):
                    created.append(e)
        return created

    async def create_relations(
        self, namespace: str, relations: list[Relation]
    ) -> list[Relation]:
        pool = await self._get_pool()
        created: list[Relation] = []
        async with pool.acquire() as conn:
            for r in relations:
                result = await conn.execute(
                    "INSERT INTO relations (namespace, from_entity, to_entity, relation_type) "
                    "VALUES ($1, $2, $3, $4) ON CONFLICT DO NOTHING",
                    namespace,
                    r.from_entity,
                    r.to_entity,
                    r.relationType,
                )
                if result.endswith("1"):
                    created.append(r)
        return created

    async def add_observations(
        self, namespace: str, observations: list[ObservationUpdate]
    ) -> list[ObservationResult]:
        pool = await self._get_pool()
        results: list[ObservationResult] = []
        async with pool.acquire() as conn:
            for obs in observations:
                row = await conn.fetchrow(
                    "SELECT observations FROM entities WHERE namespace=$1 AND name=$2",
                    namespace,
                    obs.entityName,
                )
                if row is None:
                    raise ValueError(f"Entity with name {obs.entityName} not found")
                existing: list[str] = json.loads(row["observations"])
                existing_set = set(existing)
                added = [c for c in obs.contents if c not in existing_set]
                if added:
                    new_obs = existing + added
                    await conn.execute(
                        "UPDATE entities SET observations=$1 WHERE namespace=$2 AND name=$3",
                        json.dumps(new_obs),
                        namespace,
                        obs.entityName,
                    )
                results.append(
                    ObservationResult(entityName=obs.entityName, addedObservations=added)
                )
        return results

    async def delete_entities(self, namespace: str, entity_names: list[str]) -> None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM entities WHERE namespace=$1 AND name = ANY($2)",
                namespace,
                entity_names,
            )
            await conn.execute(
                "DELETE FROM relations WHERE namespace=$1 AND "
                "(from_entity = ANY($2) OR to_entity = ANY($2))",
                namespace,
                entity_names,
            )

    async def delete_observations(
        self, namespace: str, deletions: list[ObservationDeletion]
    ) -> None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            for d in deletions:
                row = await conn.fetchrow(
                    "SELECT observations FROM entities WHERE namespace=$1 AND name=$2",
                    namespace,
                    d.entityName,
                )
                if row is None:
                    continue
                existing: list[str] = json.loads(row["observations"])
                to_remove = set(d.observations)
                filtered = [o for o in existing if o not in to_remove]
                await conn.execute(
                    "UPDATE entities SET observations=$1 WHERE namespace=$2 AND name=$3",
                    json.dumps(filtered),
                    namespace,
                    d.entityName,
                )

    async def delete_relations(
        self, namespace: str, relations: list[Relation]
    ) -> None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            for r in relations:
                await conn.execute(
                    "DELETE FROM relations WHERE namespace=$1 AND from_entity=$2 "
                    "AND to_entity=$3 AND relation_type=$4",
                    namespace,
                    r.from_entity,
                    r.to_entity,
                    r.relationType,
                )

    async def read_graph(self, namespace: str) -> KnowledgeGraph:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            e_rows = await conn.fetch(
                "SELECT name, entity_type, observations FROM entities WHERE namespace=$1",
                namespace,
            )
            r_rows = await conn.fetch(
                "SELECT from_entity, to_entity, relation_type FROM relations WHERE namespace=$1",
                namespace,
            )
        return KnowledgeGraph(
            entities=[
                Entity(
                    name=r["name"],
                    entityType=r["entity_type"],
                    observations=json.loads(r["observations"]),
                )
                for r in e_rows
            ],
            relations=[
                Relation(
                    from_entity=r["from_entity"],
                    to_entity=r["to_entity"],
                    relationType=r["relation_type"],
                )
                for r in r_rows
            ],
        )

    async def search_nodes(self, namespace: str, query: str) -> KnowledgeGraph:
        pool = await self._get_pool()
        pattern = f"%{query}%"
        async with pool.acquire() as conn:
            e_rows = await conn.fetch(
                "SELECT name, entity_type, observations FROM entities "
                "WHERE namespace=$1 AND (name ILIKE $2 OR entity_type ILIKE $2 "
                "OR observations::text ILIKE $2)",
                namespace,
                pattern,
            )
            entities = [
                Entity(
                    name=r["name"],
                    entityType=r["entity_type"],
                    observations=json.loads(r["observations"]),
                )
                for r in e_rows
            ]
            matched_names = [e.name for e in entities]
            if matched_names:
                r_rows = await conn.fetch(
                    "SELECT from_entity, to_entity, relation_type FROM relations "
                    "WHERE namespace=$1 AND (from_entity = ANY($2) OR to_entity = ANY($2))",
                    namespace,
                    matched_names,
                )
            else:
                r_rows = []
        return KnowledgeGraph(
            entities=entities,
            relations=[
                Relation(
                    from_entity=r["from_entity"],
                    to_entity=r["to_entity"],
                    relationType=r["relation_type"],
                )
                for r in r_rows
            ],
        )

    async def open_nodes(self, namespace: str, names: list[str]) -> KnowledgeGraph:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            e_rows = await conn.fetch(
                "SELECT name, entity_type, observations FROM entities "
                "WHERE namespace=$1 AND name = ANY($2)",
                namespace,
                names,
            )
            entities = [
                Entity(
                    name=r["name"],
                    entityType=r["entity_type"],
                    observations=json.loads(r["observations"]),
                )
                for r in e_rows
            ]
            matched_names = [e.name for e in entities]
            if matched_names:
                r_rows = await conn.fetch(
                    "SELECT from_entity, to_entity, relation_type FROM relations "
                    "WHERE namespace=$1 AND (from_entity = ANY($2) OR to_entity = ANY($2))",
                    namespace,
                    matched_names,
                )
            else:
                r_rows = []
        return KnowledgeGraph(
            entities=entities,
            relations=[
                Relation(
                    from_entity=r["from_entity"],
                    to_entity=r["to_entity"],
                    relationType=r["relation_type"],
                )
                for r in r_rows
            ],
        )

    async def health_check(self) -> bool:
        try:
            pool = await self._get_pool()
            async with pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return True
        except Exception:
            return False
