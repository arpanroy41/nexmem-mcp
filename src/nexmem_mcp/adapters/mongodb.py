"""MongoDB adapter — recommended for team mode.

Requires: pip install 'mcp-nexmem[mongodb]'
"""

from __future__ import annotations

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
    import motor.motor_asyncio as motor
except ImportError:
    raise ImportError(
        "MongoDB adapter requires 'motor'. Install with: pip install 'mcp-nexmem[mongodb]'"
    )


@register_adapter("mongodb")
class MongoDBAdapter(StorageAdapter):
    def __init__(self, config: NexMemConfig) -> None:
        self._client = motor.AsyncIOMotorClient(config.mongodb_uri)
        db_name = config.mongodb_uri.rsplit("/", 1)[-1].split("?")[0] or "nexmem"
        self._db = self._client[db_name]
        self._entities = self._db["entities"]
        self._relations = self._db["relations"]
        self._indexes_created = False

    async def _ensure_indexes(self) -> None:
        if self._indexes_created:
            return
        await self._entities.create_index(
            [("namespace", 1), ("name", 1)], unique=True
        )
        await self._relations.create_index(
            [("namespace", 1), ("from_entity", 1), ("to_entity", 1), ("relation_type", 1)],
            unique=True,
        )
        self._indexes_created = True

    async def create_entities(
        self, namespace: str, entities: list[Entity]
    ) -> list[Entity]:
        await self._ensure_indexes()
        if not entities:
            return []
        docs = [
            {
                "namespace": namespace,
                "name": e.name,
                "entity_type": e.entityType,
                "observations": e.observations,
            }
            for e in entities
        ]
        try:
            await self._entities.insert_many(docs, ordered=False)
        except Exception:
            pass
        created_names = set()
        for e in entities:
            existing = await self._entities.find_one(
                {"namespace": namespace, "name": e.name}
            )
            if existing and existing.get("observations") == e.observations:
                created_names.add(e.name)
        return [e for e in entities if e.name in created_names]

    async def create_relations(
        self, namespace: str, relations: list[Relation]
    ) -> list[Relation]:
        await self._ensure_indexes()
        if not relations:
            return []
        docs = [
            {
                "namespace": namespace,
                "from_entity": r.from_entity,
                "to_entity": r.to_entity,
                "relation_type": r.relationType,
            }
            for r in relations
        ]
        try:
            await self._relations.insert_many(docs, ordered=False)
            return relations
        except Exception:
            created: list[Relation] = []
            for r in relations:
                exists = await self._relations.find_one(
                    {
                        "namespace": namespace,
                        "from_entity": r.from_entity,
                        "to_entity": r.to_entity,
                        "relation_type": r.relationType,
                    }
                )
                if exists:
                    created.append(r)
            return created

    async def add_observations(
        self, namespace: str, observations: list[ObservationUpdate]
    ) -> list[ObservationResult]:
        await self._ensure_indexes()
        results: list[ObservationResult] = []
        for obs in observations:
            doc = await self._entities.find_one(
                {"namespace": namespace, "name": obs.entityName}
            )
            if doc is None:
                raise ValueError(f"Entity with name {obs.entityName} not found")
            existing_set = set(doc.get("observations", []))
            new_obs = [c for c in obs.contents if c not in existing_set]
            if new_obs:
                await self._entities.update_one(
                    {"namespace": namespace, "name": obs.entityName},
                    {"$push": {"observations": {"$each": new_obs}}},
                )
            results.append(
                ObservationResult(entityName=obs.entityName, addedObservations=new_obs)
            )
        return results

    async def delete_entities(self, namespace: str, entity_names: list[str]) -> None:
        await self._ensure_indexes()
        await self._entities.delete_many(
            {"namespace": namespace, "name": {"$in": entity_names}}
        )
        await self._relations.delete_many(
            {
                "namespace": namespace,
                "$or": [
                    {"from_entity": {"$in": entity_names}},
                    {"to_entity": {"$in": entity_names}},
                ],
            }
        )

    async def delete_observations(
        self, namespace: str, deletions: list[ObservationDeletion]
    ) -> None:
        await self._ensure_indexes()
        for d in deletions:
            await self._entities.update_one(
                {"namespace": namespace, "name": d.entityName},
                {"$pull": {"observations": {"$in": d.observations}}},
            )

    async def delete_relations(
        self, namespace: str, relations: list[Relation]
    ) -> None:
        await self._ensure_indexes()
        for r in relations:
            await self._relations.delete_one(
                {
                    "namespace": namespace,
                    "from_entity": r.from_entity,
                    "to_entity": r.to_entity,
                    "relation_type": r.relationType,
                }
            )

    async def read_graph(self, namespace: str) -> KnowledgeGraph:
        await self._ensure_indexes()
        e_cursor = self._entities.find({"namespace": namespace})
        r_cursor = self._relations.find({"namespace": namespace})
        entities = [
            Entity(
                name=doc["name"],
                entityType=doc["entity_type"],
                observations=doc.get("observations", []),
            )
            async for doc in e_cursor
        ]
        relations = [
            Relation(
                from_entity=doc["from_entity"],
                to_entity=doc["to_entity"],
                relationType=doc["relation_type"],
            )
            async for doc in r_cursor
        ]
        return KnowledgeGraph(entities=entities, relations=relations)

    async def search_nodes(self, namespace: str, query: str) -> KnowledgeGraph:
        await self._ensure_indexes()
        regex = {"$regex": query, "$options": "i"}
        e_cursor = self._entities.find(
            {
                "namespace": namespace,
                "$or": [
                    {"name": regex},
                    {"entity_type": regex},
                    {"observations": regex},
                ],
            }
        )
        entities = [
            Entity(
                name=doc["name"],
                entityType=doc["entity_type"],
                observations=doc.get("observations", []),
            )
            async for doc in e_cursor
        ]
        matched_names = {e.name for e in entities}
        r_cursor = self._relations.find(
            {
                "namespace": namespace,
                "$or": [
                    {"from_entity": {"$in": list(matched_names)}},
                    {"to_entity": {"$in": list(matched_names)}},
                ],
            }
        )
        relations = [
            Relation(
                from_entity=doc["from_entity"],
                to_entity=doc["to_entity"],
                relationType=doc["relation_type"],
            )
            async for doc in r_cursor
        ]
        return KnowledgeGraph(entities=entities, relations=relations)

    async def open_nodes(self, namespace: str, names: list[str]) -> KnowledgeGraph:
        await self._ensure_indexes()
        e_cursor = self._entities.find(
            {"namespace": namespace, "name": {"$in": names}}
        )
        entities = [
            Entity(
                name=doc["name"],
                entityType=doc["entity_type"],
                observations=doc.get("observations", []),
            )
            async for doc in e_cursor
        ]
        matched_names = {e.name for e in entities}
        r_cursor = self._relations.find(
            {
                "namespace": namespace,
                "$or": [
                    {"from_entity": {"$in": list(matched_names)}},
                    {"to_entity": {"$in": list(matched_names)}},
                ],
            }
        )
        relations = [
            Relation(
                from_entity=doc["from_entity"],
                to_entity=doc["to_entity"],
                relationType=doc["relation_type"],
            )
            async for doc in r_cursor
        ]
        return KnowledgeGraph(entities=entities, relations=relations)

    async def health_check(self) -> bool:
        try:
            await self._client.admin.command("ping")
            return True
        except Exception:
            return False
