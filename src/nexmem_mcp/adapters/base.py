"""Abstract base class for storage adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod

from nexmem_mcp.types import (
    Entity,
    KnowledgeGraph,
    ObservationDeletion,
    ObservationResult,
    ObservationUpdate,
    Relation,
)


class StorageAdapter(ABC):
    """Abstract interface for knowledge graph storage backends.

    Every method operates within a namespace for multi-tenant isolation.
    Write operations are designed to be atomic at the DB level — no
    read-modify-write cycles that could cause race conditions.
    """

    @abstractmethod
    async def create_entities(
        self, namespace: str, entities: list[Entity]
    ) -> list[Entity]:
        """Insert entities, skipping any whose name already exists (idempotent)."""
        ...

    @abstractmethod
    async def create_relations(
        self, namespace: str, relations: list[Relation]
    ) -> list[Relation]:
        """Insert relations, skipping exact duplicates (idempotent)."""
        ...

    @abstractmethod
    async def add_observations(
        self, namespace: str, observations: list[ObservationUpdate]
    ) -> list[ObservationResult]:
        """Atomically append observations to existing entities."""
        ...

    @abstractmethod
    async def delete_entities(self, namespace: str, entity_names: list[str]) -> None:
        """Delete entities by name and remove any relations that reference them."""
        ...

    @abstractmethod
    async def delete_observations(
        self, namespace: str, deletions: list[ObservationDeletion]
    ) -> None:
        """Remove specific observations from entities."""
        ...

    @abstractmethod
    async def delete_relations(
        self, namespace: str, relations: list[Relation]
    ) -> None:
        """Remove exact-match relations."""
        ...

    @abstractmethod
    async def read_graph(self, namespace: str) -> KnowledgeGraph:
        """Return the full knowledge graph for a namespace."""
        ...

    @abstractmethod
    async def search_nodes(self, namespace: str, query: str) -> KnowledgeGraph:
        """Search entities by name, type, or observation content (case-insensitive).

        Returns matching entities plus any relations where at least one
        endpoint is in the result set.
        """
        ...

    @abstractmethod
    async def open_nodes(self, namespace: str, names: list[str]) -> KnowledgeGraph:
        """Retrieve specific entities by name.

        Returns the requested entities plus any relations where at least
        one endpoint is in the requested set.
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Return True if the backend is reachable and operational."""
        ...
