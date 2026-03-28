"""SQLite adapter — lightweight local storage with transaction-level atomicity."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

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


@register_adapter("sqlite")
class SqliteAdapter(StorageAdapter):
    def __init__(self, config: NexMemConfig) -> None:
        path = Path(config.sqlite_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db_path = str(path)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS entities (
                    namespace TEXT NOT NULL,
                    name TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    observations TEXT NOT NULL DEFAULT '[]',
                    PRIMARY KEY (namespace, name)
                );
                CREATE TABLE IF NOT EXISTS relations (
                    namespace TEXT NOT NULL,
                    from_entity TEXT NOT NULL,
                    to_entity TEXT NOT NULL,
                    relation_type TEXT NOT NULL,
                    PRIMARY KEY (namespace, from_entity, to_entity, relation_type)
                );
                CREATE INDEX IF NOT EXISTS idx_entities_ns ON entities(namespace);
                CREATE INDEX IF NOT EXISTS idx_relations_ns ON relations(namespace);
                """
            )

    async def create_entities(
        self, namespace: str, entities: list[Entity]
    ) -> list[Entity]:
        created: list[Entity] = []
        with self._connect() as conn:
            for e in entities:
                try:
                    conn.execute(
                        "INSERT INTO entities (namespace, name, entity_type, observations) "
                        "VALUES (?, ?, ?, ?)",
                        (namespace, e.name, e.entityType, json.dumps(e.observations)),
                    )
                    created.append(e)
                except sqlite3.IntegrityError:
                    pass
        return created

    async def create_relations(
        self, namespace: str, relations: list[Relation]
    ) -> list[Relation]:
        created: list[Relation] = []
        with self._connect() as conn:
            for r in relations:
                try:
                    conn.execute(
                        "INSERT INTO relations (namespace, from_entity, to_entity, relation_type) "
                        "VALUES (?, ?, ?, ?)",
                        (namespace, r.from_entity, r.to_entity, r.relationType),
                    )
                    created.append(r)
                except sqlite3.IntegrityError:
                    pass
        return created

    async def add_observations(
        self, namespace: str, observations: list[ObservationUpdate]
    ) -> list[ObservationResult]:
        results: list[ObservationResult] = []
        with self._connect() as conn:
            for obs in observations:
                row = conn.execute(
                    "SELECT observations FROM entities WHERE namespace=? AND name=?",
                    (namespace, obs.entityName),
                ).fetchone()
                if row is None:
                    raise ValueError(f"Entity with name {obs.entityName} not found")
                existing: list[str] = json.loads(row["observations"])
                existing_set = set(existing)
                added = [c for c in obs.contents if c not in existing_set]
                existing.extend(added)
                conn.execute(
                    "UPDATE entities SET observations=? WHERE namespace=? AND name=?",
                    (json.dumps(existing), namespace, obs.entityName),
                )
                results.append(
                    ObservationResult(entityName=obs.entityName, addedObservations=added)
                )
        return results

    async def delete_entities(self, namespace: str, entity_names: list[str]) -> None:
        with self._connect() as conn:
            placeholders = ",".join("?" for _ in entity_names)
            params = [namespace] + entity_names
            conn.execute(
                f"DELETE FROM entities WHERE namespace=? AND name IN ({placeholders})",
                params,
            )
            conn.execute(
                f"DELETE FROM relations WHERE namespace=? AND "
                f"(from_entity IN ({placeholders}) OR to_entity IN ({placeholders}))",
                params + entity_names,
            )

    async def delete_observations(
        self, namespace: str, deletions: list[ObservationDeletion]
    ) -> None:
        with self._connect() as conn:
            for d in deletions:
                row = conn.execute(
                    "SELECT observations FROM entities WHERE namespace=? AND name=?",
                    (namespace, d.entityName),
                ).fetchone()
                if row is None:
                    continue
                existing: list[str] = json.loads(row["observations"])
                to_remove = set(d.observations)
                filtered = [o for o in existing if o not in to_remove]
                conn.execute(
                    "UPDATE entities SET observations=? WHERE namespace=? AND name=?",
                    (json.dumps(filtered), namespace, d.entityName),
                )

    async def delete_relations(
        self, namespace: str, relations: list[Relation]
    ) -> None:
        with self._connect() as conn:
            for r in relations:
                conn.execute(
                    "DELETE FROM relations WHERE namespace=? AND from_entity=? "
                    "AND to_entity=? AND relation_type=?",
                    (namespace, r.from_entity, r.to_entity, r.relationType),
                )

    async def read_graph(self, namespace: str) -> KnowledgeGraph:
        with self._connect() as conn:
            return self._load_graph(conn, namespace)

    async def search_nodes(self, namespace: str, query: str) -> KnowledgeGraph:
        with self._connect() as conn:
            pattern = f"%{query}%"
            rows = conn.execute(
                "SELECT name, entity_type, observations FROM entities "
                "WHERE namespace=? AND (name LIKE ? OR entity_type LIKE ? OR observations LIKE ?)",
                (namespace, pattern, pattern, pattern),
            ).fetchall()
            entities = [
                Entity(
                    name=r["name"],
                    entityType=r["entity_type"],
                    observations=json.loads(r["observations"]),
                )
                for r in rows
            ]
            matched_names = {e.name for e in entities}
            rel_rows = conn.execute(
                "SELECT from_entity, to_entity, relation_type FROM relations WHERE namespace=?",
                (namespace,),
            ).fetchall()
            relations = [
                Relation(
                    from_entity=r["from_entity"],
                    to_entity=r["to_entity"],
                    relationType=r["relation_type"],
                )
                for r in rel_rows
                if r["from_entity"] in matched_names or r["to_entity"] in matched_names
            ]
            return KnowledgeGraph(entities=entities, relations=relations)

    async def open_nodes(self, namespace: str, names: list[str]) -> KnowledgeGraph:
        with self._connect() as conn:
            placeholders = ",".join("?" for _ in names)
            rows = conn.execute(
                f"SELECT name, entity_type, observations FROM entities "
                f"WHERE namespace=? AND name IN ({placeholders})",
                [namespace] + names,
            ).fetchall()
            entities = [
                Entity(
                    name=r["name"],
                    entityType=r["entity_type"],
                    observations=json.loads(r["observations"]),
                )
                for r in rows
            ]
            matched_names = {e.name for e in entities}
            rel_rows = conn.execute(
                "SELECT from_entity, to_entity, relation_type FROM relations WHERE namespace=?",
                (namespace,),
            ).fetchall()
            relations = [
                Relation(
                    from_entity=r["from_entity"],
                    to_entity=r["to_entity"],
                    relationType=r["relation_type"],
                )
                for r in rel_rows
                if r["from_entity"] in matched_names or r["to_entity"] in matched_names
            ]
            return KnowledgeGraph(entities=entities, relations=relations)

    async def health_check(self) -> bool:
        try:
            with self._connect() as conn:
                conn.execute("SELECT 1")
            return True
        except Exception:
            return False

    def _load_graph(self, conn: sqlite3.Connection, namespace: str) -> KnowledgeGraph:
        e_rows = conn.execute(
            "SELECT name, entity_type, observations FROM entities WHERE namespace=?",
            (namespace,),
        ).fetchall()
        r_rows = conn.execute(
            "SELECT from_entity, to_entity, relation_type FROM relations WHERE namespace=?",
            (namespace,),
        ).fetchall()
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
