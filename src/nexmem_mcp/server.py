"""FastMCP server exposing knowledge graph tools."""

from __future__ import annotations

import json
import sys

from fastmcp import FastMCP

from nexmem_mcp.adapters import create_adapter
from nexmem_mcp.config import NexMemConfig
from nexmem_mcp.manager import KnowledgeGraphManager
from nexmem_mcp.namespace import resolve_namespace
from nexmem_mcp.types import (
    Entity,
    KnowledgeGraph,
    ObservationDeletion,
    ObservationUpdate,
    Relation,
)

config = NexMemConfig()
adapter = create_adapter(config)
namespace = resolve_namespace(config)
manager = KnowledgeGraphManager(adapter, namespace)

mcp = FastMCP(
    name="nexmem-mcp",
    instructions=config.get_instructions(),
)


# ── Read tools ────────────────────────────────────────────────────────────


@mcp.tool
async def read_graph() -> dict:
    """Read the entire knowledge graph."""
    graph = await manager.read_graph()
    return graph.to_dict()


@mcp.tool
async def search_nodes(query: str) -> dict:
    """Search for nodes in the knowledge graph based on a query.

    Matches against entity names, types, and observation content (case-insensitive).
    """
    graph = await manager.search_nodes(query)
    return graph.to_dict()


@mcp.tool
async def open_nodes(names: list[str]) -> dict:
    """Open specific nodes in the knowledge graph by their names."""
    graph = await manager.open_nodes(names)
    return graph.to_dict()


# ── Write tools (hidden when read-only) ──────────────────────────────────

_write_tags = set() if not config.read_only else {"_disabled"}


@mcp.tool(tags=_write_tags)
async def create_entities(
    entities: list[dict],
) -> str:
    """Create multiple new entities in the knowledge graph.

    Each entity dict must have: name (str), entityType (str), observations (list[str]).
    """
    parsed = [
        Entity(
            name=e["name"],
            entityType=e["entityType"],
            observations=e.get("observations", []),
        )
        for e in entities
    ]
    result = await manager.create_entities(parsed)
    return json.dumps([{"name": e.name, "entityType": e.entityType, "observations": e.observations} for e in result], indent=2)


@mcp.tool(tags=_write_tags)
async def create_relations(
    relations: list[dict],
) -> str:
    """Create multiple new relations between entities in the knowledge graph.

    Each relation dict must have: from (str), to (str), relationType (str).
    Relations should be in active voice.
    """
    parsed = [
        Relation(
            from_entity=r["from"],
            to_entity=r["to"],
            relationType=r["relationType"],
        )
        for r in relations
    ]
    result = await manager.create_relations(parsed)
    return json.dumps([r.to_jsonl() for r in result], indent=2)


@mcp.tool(tags=_write_tags)
async def add_observations(
    observations: list[dict],
) -> str:
    """Add new observations to existing entities in the knowledge graph.

    Each dict must have: entityName (str), contents (list[str]).
    """
    parsed = [
        ObservationUpdate(entityName=o["entityName"], contents=o["contents"])
        for o in observations
    ]
    result = await manager.add_observations(parsed)
    return json.dumps(
        [{"entityName": r.entityName, "addedObservations": r.addedObservations} for r in result],
        indent=2,
    )


@mcp.tool(tags=_write_tags)
async def delete_entities(entityNames: list[str]) -> str:
    """Delete multiple entities and their associated relations from the knowledge graph."""
    await manager.delete_entities(entityNames)
    return "Entities deleted successfully"


@mcp.tool(tags=_write_tags)
async def delete_observations(
    deletions: list[dict],
) -> str:
    """Delete specific observations from entities in the knowledge graph.

    Each dict must have: entityName (str), observations (list[str]).
    """
    parsed = [
        ObservationDeletion(entityName=d["entityName"], observations=d["observations"])
        for d in deletions
    ]
    await manager.delete_observations(parsed)
    return "Observations deleted successfully"


@mcp.tool(tags=_write_tags)
async def delete_relations(
    relations: list[dict],
) -> str:
    """Delete multiple relations from the knowledge graph.

    Each relation dict must have: from (str), to (str), relationType (str).
    """
    parsed = [
        Relation(
            from_entity=r["from"],
            to_entity=r["to"],
            relationType=r["relationType"],
        )
        for r in relations
    ]
    await manager.delete_relations(parsed)
    return "Relations deleted successfully"


# ── Extra tools ───────────────────────────────────────────────────────────


@mcp.tool
async def get_memory_status() -> dict:
    """Show the current memory configuration: mode, backend, namespace, health."""
    healthy = await manager.health_check()
    return {
        "mode": config.mode.value,
        "backend": config.backend.value,
        "namespace": namespace,
        "user_name": config.user_name,
        "team_name": config.team_name or None,
        "read_only": config.read_only,
        "healthy": healthy,
    }


@mcp.tool(tags=_write_tags)
async def import_jsonl(jsonl_content: str) -> str:
    """Import entities and relations from JSONL-formatted text.

    Compatible with @modelcontextprotocol/server-memory and other MCP memory exports.
    Each line should be a JSON object with a 'type' field of 'entity' or 'relation'.
    """
    entities: list[Entity] = []
    relations: list[Relation] = []
    for line in jsonl_content.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        item = json.loads(line)
        if item.get("type") == "entity":
            entities.append(Entity.from_jsonl(item))
        elif item.get("type") == "relation":
            relations.append(Relation.from_jsonl(item))

    created_entities = await manager.create_entities(entities)
    created_relations = await manager.create_relations(relations)
    return json.dumps(
        {
            "imported_entities": len(created_entities),
            "imported_relations": len(created_relations),
            "skipped_entities": len(entities) - len(created_entities),
            "skipped_relations": len(relations) - len(created_relations),
        },
        indent=2,
    )


# ── Hide disabled write tools ────────────────────────────────────────────

if config.read_only:
    mcp.disable(tags={"_disabled"})


# ── Entry point ───────────────────────────────────────────────────────────


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
