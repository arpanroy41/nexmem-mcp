"""Tests for the JSONL file adapter."""

import pytest

from nexmem_mcp.adapters.jsonl import JsonlAdapter
from nexmem_mcp.types import Entity, ObservationDeletion, ObservationUpdate, Relation

NS = "self:testuser"


@pytest.mark.asyncio
async def test_create_and_read_entities(jsonl_adapter: JsonlAdapter, sample_entities):
    created = await jsonl_adapter.create_entities(NS, sample_entities)
    assert len(created) == 3

    graph = await jsonl_adapter.read_graph(NS)
    assert len(graph.entities) == 3
    names = {e.name for e in graph.entities}
    assert "AuthService" in names


@pytest.mark.asyncio
async def test_create_entities_idempotent(jsonl_adapter: JsonlAdapter, sample_entities):
    await jsonl_adapter.create_entities(NS, sample_entities)
    dupes = await jsonl_adapter.create_entities(NS, sample_entities)
    assert len(dupes) == 0

    graph = await jsonl_adapter.read_graph(NS)
    assert len(graph.entities) == 3


@pytest.mark.asyncio
async def test_create_and_read_relations(
    jsonl_adapter: JsonlAdapter, sample_entities, sample_relations
):
    await jsonl_adapter.create_entities(NS, sample_entities)
    created = await jsonl_adapter.create_relations(NS, sample_relations)
    assert len(created) == 2

    graph = await jsonl_adapter.read_graph(NS)
    assert len(graph.relations) == 2


@pytest.mark.asyncio
async def test_add_observations(jsonl_adapter: JsonlAdapter, sample_entities):
    await jsonl_adapter.create_entities(NS, sample_entities)
    results = await jsonl_adapter.add_observations(
        NS,
        [ObservationUpdate(entityName="AuthService", contents=["Deployed on K8s", "Uses OAuth2"])],
    )
    assert len(results) == 1
    assert results[0].addedObservations == ["Deployed on K8s"]

    graph = await jsonl_adapter.read_graph(NS)
    auth = next(e for e in graph.entities if e.name == "AuthService")
    assert "Deployed on K8s" in auth.observations
    assert auth.observations.count("Uses OAuth2") == 1


@pytest.mark.asyncio
async def test_add_observations_missing_entity(jsonl_adapter: JsonlAdapter):
    with pytest.raises(ValueError, match="not found"):
        await jsonl_adapter.add_observations(
            NS,
            [ObservationUpdate(entityName="Ghost", contents=["nope"])],
        )


@pytest.mark.asyncio
async def test_delete_entities(jsonl_adapter: JsonlAdapter, sample_entities, sample_relations):
    await jsonl_adapter.create_entities(NS, sample_entities)
    await jsonl_adapter.create_relations(NS, sample_relations)

    await jsonl_adapter.delete_entities(NS, ["AuthService"])

    graph = await jsonl_adapter.read_graph(NS)
    names = {e.name for e in graph.entities}
    assert "AuthService" not in names
    # Relations referencing AuthService should also be gone
    for r in graph.relations:
        assert r.from_entity != "AuthService"
        assert r.to_entity != "AuthService"


@pytest.mark.asyncio
async def test_delete_observations(jsonl_adapter: JsonlAdapter, sample_entities):
    await jsonl_adapter.create_entities(NS, sample_entities)
    await jsonl_adapter.delete_observations(
        NS,
        [ObservationDeletion(entityName="AuthService", observations=["Uses OAuth2"])],
    )

    graph = await jsonl_adapter.read_graph(NS)
    auth = next(e for e in graph.entities if e.name == "AuthService")
    assert "Uses OAuth2" not in auth.observations
    assert "Written in Go" in auth.observations


@pytest.mark.asyncio
async def test_delete_relations(jsonl_adapter: JsonlAdapter, sample_entities, sample_relations):
    await jsonl_adapter.create_entities(NS, sample_entities)
    await jsonl_adapter.create_relations(NS, sample_relations)

    await jsonl_adapter.delete_relations(
        NS,
        [Relation(from_entity="AuthService", to_entity="UserDB", relationType="reads_from")],
    )

    graph = await jsonl_adapter.read_graph(NS)
    assert len(graph.relations) == 1
    assert graph.relations[0].from_entity == "PaymentAPI"


@pytest.mark.asyncio
async def test_search_nodes(jsonl_adapter: JsonlAdapter, sample_entities, sample_relations):
    await jsonl_adapter.create_entities(NS, sample_entities)
    await jsonl_adapter.create_relations(NS, sample_relations)

    result = await jsonl_adapter.search_nodes(NS, "auth")
    assert len(result.entities) == 1
    assert result.entities[0].name == "AuthService"
    assert len(result.relations) >= 1


@pytest.mark.asyncio
async def test_search_nodes_by_observation(jsonl_adapter: JsonlAdapter, sample_entities):
    await jsonl_adapter.create_entities(NS, sample_entities)
    result = await jsonl_adapter.search_nodes(NS, "gRPC")
    assert len(result.entities) == 1
    assert result.entities[0].name == "PaymentAPI"


@pytest.mark.asyncio
async def test_open_nodes(jsonl_adapter: JsonlAdapter, sample_entities, sample_relations):
    await jsonl_adapter.create_entities(NS, sample_entities)
    await jsonl_adapter.create_relations(NS, sample_relations)

    result = await jsonl_adapter.open_nodes(NS, ["UserDB"])
    assert len(result.entities) == 1
    assert result.entities[0].name == "UserDB"
    assert any(r.to_entity == "UserDB" for r in result.relations)


@pytest.mark.asyncio
async def test_namespace_isolation(jsonl_adapter: JsonlAdapter, sample_entities):
    await jsonl_adapter.create_entities("team:alpha", sample_entities)
    await jsonl_adapter.create_entities("team:beta", [Entity(name="BetaOnly", entityType="x", observations=[])])

    alpha = await jsonl_adapter.read_graph("team:alpha")
    beta = await jsonl_adapter.read_graph("team:beta")
    assert len(alpha.entities) == 3
    assert len(beta.entities) == 1


@pytest.mark.asyncio
async def test_health_check(jsonl_adapter: JsonlAdapter):
    assert await jsonl_adapter.health_check() is True
