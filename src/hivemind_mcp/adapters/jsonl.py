"""JSONL file-based adapter — zero-dependency default.

Uses file locking for mutual exclusion. Suitable for self mode;
team mode should use a real database backend.
"""

from __future__ import annotations

import fcntl
import json
from pathlib import Path

from hivemind_mcp.adapters import register_adapter
from hivemind_mcp.adapters.base import StorageAdapter
from hivemind_mcp.config import HiveMindConfig
from hivemind_mcp.types import (
    Entity,
    KnowledgeGraph,
    ObservationDeletion,
    ObservationResult,
    ObservationUpdate,
    Relation,
)


@register_adapter("jsonl")
class JsonlAdapter(StorageAdapter):
    def __init__(self, config: HiveMindConfig) -> None:
        self._base_path = Path(config.jsonl_path).parent

    def _path_for(self, namespace: str) -> Path:
        safe_name = namespace.replace(":", "_").replace("/", "_")
        path = self._base_path / f"{safe_name}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def _load(self, namespace: str) -> KnowledgeGraph:
        path = self._path_for(namespace)
        if not path.exists():
            return KnowledgeGraph()
        entities: list[Entity] = []
        relations: list[Relation] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            if item.get("type") == "entity":
                entities.append(Entity.from_jsonl(item))
            elif item.get("type") == "relation":
                relations.append(Relation.from_jsonl(item))
        return KnowledgeGraph(entities=entities, relations=relations)

    def _save(self, namespace: str, graph: KnowledgeGraph) -> None:
        path = self._path_for(namespace)
        lines = [json.dumps(e.to_jsonl()) for e in graph.entities]
        lines += [json.dumps(r.to_jsonl()) for r in graph.relations]
        path.write_text("\n".join(lines) + "\n" if lines else "", encoding="utf-8")

    def _with_lock(self, namespace: str):
        """Context manager for file-level locking."""
        import contextlib

        @contextlib.contextmanager
        def _lock():
            path = self._path_for(namespace)
            path.touch(exist_ok=True)
            with open(path, "r+") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)

        return _lock()

    async def create_entities(
        self, namespace: str, entities: list[Entity]
    ) -> list[Entity]:
        with self._with_lock(namespace):
            graph = self._load(namespace)
            existing_names = {e.name for e in graph.entities}
            new = [e for e in entities if e.name not in existing_names]
            graph.entities.extend(new)
            self._save(namespace, graph)
            return new

    async def create_relations(
        self, namespace: str, relations: list[Relation]
    ) -> list[Relation]:
        with self._with_lock(namespace):
            graph = self._load(namespace)
            existing = {
                (r.from_entity, r.to_entity, r.relationType) for r in graph.relations
            }
            new = [
                r
                for r in relations
                if (r.from_entity, r.to_entity, r.relationType) not in existing
            ]
            graph.relations.extend(new)
            self._save(namespace, graph)
            return new

    async def add_observations(
        self, namespace: str, observations: list[ObservationUpdate]
    ) -> list[ObservationResult]:
        with self._with_lock(namespace):
            graph = self._load(namespace)
            entity_map = {e.name: e for e in graph.entities}
            results: list[ObservationResult] = []
            for obs in observations:
                entity = entity_map.get(obs.entityName)
                if entity is None:
                    raise ValueError(f"Entity with name {obs.entityName} not found")
                added = [c for c in obs.contents if c not in entity.observations]
                entity.observations.extend(added)
                results.append(
                    ObservationResult(entityName=obs.entityName, addedObservations=added)
                )
            self._save(namespace, graph)
            return results

    async def delete_entities(self, namespace: str, entity_names: list[str]) -> None:
        with self._with_lock(namespace):
            graph = self._load(namespace)
            names = set(entity_names)
            graph.entities = [e for e in graph.entities if e.name not in names]
            graph.relations = [
                r
                for r in graph.relations
                if r.from_entity not in names and r.to_entity not in names
            ]
            self._save(namespace, graph)

    async def delete_observations(
        self, namespace: str, deletions: list[ObservationDeletion]
    ) -> None:
        with self._with_lock(namespace):
            graph = self._load(namespace)
            entity_map = {e.name: e for e in graph.entities}
            for d in deletions:
                entity = entity_map.get(d.entityName)
                if entity:
                    to_remove = set(d.observations)
                    entity.observations = [
                        o for o in entity.observations if o not in to_remove
                    ]
            self._save(namespace, graph)

    async def delete_relations(
        self, namespace: str, relations: list[Relation]
    ) -> None:
        with self._with_lock(namespace):
            graph = self._load(namespace)
            to_remove = {
                (r.from_entity, r.to_entity, r.relationType) for r in relations
            }
            graph.relations = [
                r
                for r in graph.relations
                if (r.from_entity, r.to_entity, r.relationType) not in to_remove
            ]
            self._save(namespace, graph)

    async def read_graph(self, namespace: str) -> KnowledgeGraph:
        return self._load(namespace)

    async def search_nodes(self, namespace: str, query: str) -> KnowledgeGraph:
        graph = self._load(namespace)
        q = query.lower()
        matched = [
            e
            for e in graph.entities
            if q in e.name.lower()
            or q in e.entityType.lower()
            or any(q in o.lower() for o in e.observations)
        ]
        matched_names = {e.name for e in matched}
        matched_relations = [
            r
            for r in graph.relations
            if r.from_entity in matched_names or r.to_entity in matched_names
        ]
        return KnowledgeGraph(entities=matched, relations=matched_relations)

    async def open_nodes(self, namespace: str, names: list[str]) -> KnowledgeGraph:
        graph = self._load(namespace)
        name_set = set(names)
        matched = [e for e in graph.entities if e.name in name_set]
        matched_names = {e.name for e in matched}
        matched_relations = [
            r
            for r in graph.relations
            if r.from_entity in matched_names or r.to_entity in matched_names
        ]
        return KnowledgeGraph(entities=matched, relations=matched_relations)

    async def health_check(self) -> bool:
        return True
