"""KnowledgeGraphManager — thin delegation layer from tools to adapter."""

from __future__ import annotations

from nexmem_mcp.adapters.base import StorageAdapter
from nexmem_mcp.types import (
    Entity,
    KnowledgeGraph,
    ObservationDeletion,
    ObservationResult,
    ObservationUpdate,
    Relation,
)


class KnowledgeGraphManager:
    """Delegates every operation to the configured StorageAdapter within a namespace."""

    def __init__(self, adapter: StorageAdapter, namespace: str) -> None:
        self._adapter = adapter
        self._namespace = namespace

    @property
    def namespace(self) -> str:
        return self._namespace

    async def create_entities(self, entities: list[Entity]) -> list[Entity]:
        return await self._adapter.create_entities(self._namespace, entities)

    async def create_relations(self, relations: list[Relation]) -> list[Relation]:
        return await self._adapter.create_relations(self._namespace, relations)

    async def add_observations(
        self, observations: list[ObservationUpdate]
    ) -> list[ObservationResult]:
        return await self._adapter.add_observations(self._namespace, observations)

    async def delete_entities(self, entity_names: list[str]) -> None:
        await self._adapter.delete_entities(self._namespace, entity_names)

    async def delete_observations(
        self, deletions: list[ObservationDeletion]
    ) -> None:
        await self._adapter.delete_observations(self._namespace, deletions)

    async def delete_relations(self, relations: list[Relation]) -> None:
        await self._adapter.delete_relations(self._namespace, relations)

    async def read_graph(self) -> KnowledgeGraph:
        return await self._adapter.read_graph(self._namespace)

    async def search_nodes(self, query: str) -> KnowledgeGraph:
        return await self._adapter.search_nodes(self._namespace, query)

    async def open_nodes(self, names: list[str]) -> KnowledgeGraph:
        return await self._adapter.open_nodes(self._namespace, names)

    async def health_check(self) -> bool:
        return await self._adapter.health_check()
