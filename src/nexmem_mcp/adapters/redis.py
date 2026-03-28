"""Redis adapter using hash keys per entity and sorted sets for relations.

Requires: pip install 'mcp-nexmem[redis]'
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
    import redis.asyncio as aioredis
except ImportError:
    raise ImportError(
        "Redis adapter requires 'redis'. Install with: pip install 'mcp-nexmem[redis]'"
    )


@register_adapter("redis")
class RedisAdapter(StorageAdapter):
    """Stores entities as Redis hashes and relations as set members.

    Key scheme:
        {namespace}:entities        — Hash: name -> JSON(entity_type, observations)
        {namespace}:relations       — Set of JSON strings for each relation
    """

    def __init__(self, config: NexMemConfig) -> None:
        self._redis = aioredis.from_url(config.redis_url, decode_responses=True)

    def _ek(self, namespace: str) -> str:
        return f"{namespace}:entities"

    def _rk(self, namespace: str) -> str:
        return f"{namespace}:relations"

    async def create_entities(
        self, namespace: str, entities: list[Entity]
    ) -> list[Entity]:
        ek = self._ek(namespace)
        created: list[Entity] = []
        for e in entities:
            added = await self._redis.hsetnx(
                ek,
                e.name,
                json.dumps({"entity_type": e.entityType, "observations": e.observations}),
            )
            if added:
                created.append(e)
        return created

    async def create_relations(
        self, namespace: str, relations: list[Relation]
    ) -> list[Relation]:
        rk = self._rk(namespace)
        created: list[Relation] = []
        for r in relations:
            member = json.dumps(
                {
                    "from": r.from_entity,
                    "to": r.to_entity,
                    "relationType": r.relationType,
                },
                sort_keys=True,
            )
            added = await self._redis.sadd(rk, member)
            if added:
                created.append(r)
        return created

    async def add_observations(
        self, namespace: str, observations: list[ObservationUpdate]
    ) -> list[ObservationResult]:
        ek = self._ek(namespace)
        results: list[ObservationResult] = []
        for obs in observations:
            raw = await self._redis.hget(ek, obs.entityName)
            if raw is None:
                raise ValueError(f"Entity with name {obs.entityName} not found")
            data = json.loads(raw)
            existing_set = set(data.get("observations", []))
            added = [c for c in obs.contents if c not in existing_set]
            data["observations"] = data.get("observations", []) + added
            await self._redis.hset(ek, obs.entityName, json.dumps(data))
            results.append(
                ObservationResult(entityName=obs.entityName, addedObservations=added)
            )
        return results

    async def delete_entities(self, namespace: str, entity_names: list[str]) -> None:
        ek = self._ek(namespace)
        rk = self._rk(namespace)
        if entity_names:
            await self._redis.hdel(ek, *entity_names)
        names_set = set(entity_names)
        members = await self._redis.smembers(rk)
        for m in members:
            data = json.loads(m)
            if data["from"] in names_set or data["to"] in names_set:
                await self._redis.srem(rk, m)

    async def delete_observations(
        self, namespace: str, deletions: list[ObservationDeletion]
    ) -> None:
        ek = self._ek(namespace)
        for d in deletions:
            raw = await self._redis.hget(ek, d.entityName)
            if raw is None:
                continue
            data = json.loads(raw)
            to_remove = set(d.observations)
            data["observations"] = [
                o for o in data.get("observations", []) if o not in to_remove
            ]
            await self._redis.hset(ek, d.entityName, json.dumps(data))

    async def delete_relations(
        self, namespace: str, relations: list[Relation]
    ) -> None:
        rk = self._rk(namespace)
        for r in relations:
            member = json.dumps(
                {
                    "from": r.from_entity,
                    "to": r.to_entity,
                    "relationType": r.relationType,
                },
                sort_keys=True,
            )
            await self._redis.srem(rk, member)

    async def read_graph(self, namespace: str) -> KnowledgeGraph:
        ek = self._ek(namespace)
        rk = self._rk(namespace)
        all_entities = await self._redis.hgetall(ek)
        entities = []
        for name, raw in all_entities.items():
            data = json.loads(raw)
            entities.append(
                Entity(
                    name=name,
                    entityType=data["entity_type"],
                    observations=data.get("observations", []),
                )
            )
        members = await self._redis.smembers(rk)
        relations = []
        for m in members:
            data = json.loads(m)
            relations.append(
                Relation(
                    from_entity=data["from"],
                    to_entity=data["to"],
                    relationType=data["relationType"],
                )
            )
        return KnowledgeGraph(entities=entities, relations=relations)

    async def search_nodes(self, namespace: str, query: str) -> KnowledgeGraph:
        graph = await self.read_graph(namespace)
        q = query.lower()
        matched = [
            e
            for e in graph.entities
            if q in e.name.lower()
            or q in e.entityType.lower()
            or any(q in o.lower() for o in e.observations)
        ]
        matched_names = {e.name for e in matched}
        matched_rels = [
            r
            for r in graph.relations
            if r.from_entity in matched_names or r.to_entity in matched_names
        ]
        return KnowledgeGraph(entities=matched, relations=matched_rels)

    async def open_nodes(self, namespace: str, names: list[str]) -> KnowledgeGraph:
        ek = self._ek(namespace)
        rk = self._rk(namespace)
        entities: list[Entity] = []
        for name in names:
            raw = await self._redis.hget(ek, name)
            if raw is not None:
                data = json.loads(raw)
                entities.append(
                    Entity(
                        name=name,
                        entityType=data["entity_type"],
                        observations=data.get("observations", []),
                    )
                )
        matched_names = {e.name for e in entities}
        members = await self._redis.smembers(rk)
        relations = []
        for m in members:
            data = json.loads(m)
            if data["from"] in matched_names or data["to"] in matched_names:
                relations.append(
                    Relation(
                        from_entity=data["from"],
                        to_entity=data["to"],
                        relationType=data["relationType"],
                    )
                )
        return KnowledgeGraph(entities=entities, relations=relations)

    async def health_check(self) -> bool:
        try:
            return await self._redis.ping()
        except Exception:
            return False
