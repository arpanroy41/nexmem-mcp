"""Tests for KnowledgeGraphManager delegation."""

import pytest

from nexmem_mcp.adapters.jsonl import JsonlAdapter
from nexmem_mcp.manager import KnowledgeGraphManager
from nexmem_mcp.types import Entity, ObservationUpdate, Relation


@pytest.fixture
def mgr(jsonl_adapter: JsonlAdapter) -> KnowledgeGraphManager:
    return KnowledgeGraphManager(jsonl_adapter, "self:testuser")


@pytest.mark.asyncio
async def test_full_lifecycle(mgr: KnowledgeGraphManager):
    # Create
    entities = [
        Entity(name="SvcA", entityType="service", observations=["uses REST"]),
        Entity(name="SvcB", entityType="service", observations=["uses gRPC"]),
    ]
    created = await mgr.create_entities(entities)
    assert len(created) == 2

    relations = [Relation(from_entity="SvcA", to_entity="SvcB", relationType="calls")]
    await mgr.create_relations(relations)

    # Read
    graph = await mgr.read_graph()
    assert len(graph.entities) == 2
    assert len(graph.relations) == 1

    # Search
    result = await mgr.search_nodes("REST")
    assert len(result.entities) == 1
    assert result.entities[0].name == "SvcA"

    # Add observations
    obs_result = await mgr.add_observations(
        [ObservationUpdate(entityName="SvcA", contents=["deployed on AWS"])]
    )
    assert obs_result[0].addedObservations == ["deployed on AWS"]

    # Open
    opened = await mgr.open_nodes(["SvcB"])
    assert len(opened.entities) == 1

    # Delete
    await mgr.delete_entities(["SvcA"])
    graph = await mgr.read_graph()
    assert len(graph.entities) == 1
    assert len(graph.relations) == 0

    # Health
    assert await mgr.health_check() is True
