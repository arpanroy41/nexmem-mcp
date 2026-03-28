"""Tests for the SQLite adapter."""

import pytest

from hivemind_mcp.adapters.sqlite import SqliteAdapter
from hivemind_mcp.types import Entity, ObservationDeletion, ObservationUpdate, Relation

NS = "self:testuser"


@pytest.mark.asyncio
async def test_create_and_read_entities(sqlite_adapter: SqliteAdapter, sample_entities):
    created = await sqlite_adapter.create_entities(NS, sample_entities)
    assert len(created) == 3

    graph = await sqlite_adapter.read_graph(NS)
    assert len(graph.entities) == 3


@pytest.mark.asyncio
async def test_create_entities_idempotent(sqlite_adapter: SqliteAdapter, sample_entities):
    await sqlite_adapter.create_entities(NS, sample_entities)
    dupes = await sqlite_adapter.create_entities(NS, sample_entities)
    assert len(dupes) == 0


@pytest.mark.asyncio
async def test_create_and_read_relations(
    sqlite_adapter: SqliteAdapter, sample_entities, sample_relations
):
    await sqlite_adapter.create_entities(NS, sample_entities)
    created = await sqlite_adapter.create_relations(NS, sample_relations)
    assert len(created) == 2

    graph = await sqlite_adapter.read_graph(NS)
    assert len(graph.relations) == 2


@pytest.mark.asyncio
async def test_add_observations(sqlite_adapter: SqliteAdapter, sample_entities):
    await sqlite_adapter.create_entities(NS, sample_entities)
    results = await sqlite_adapter.add_observations(
        NS,
        [ObservationUpdate(entityName="AuthService", contents=["Deployed on K8s", "Uses OAuth2"])],
    )
    assert results[0].addedObservations == ["Deployed on K8s"]


@pytest.mark.asyncio
async def test_delete_entities_cascades_relations(
    sqlite_adapter: SqliteAdapter, sample_entities, sample_relations
):
    await sqlite_adapter.create_entities(NS, sample_entities)
    await sqlite_adapter.create_relations(NS, sample_relations)
    await sqlite_adapter.delete_entities(NS, ["AuthService"])

    graph = await sqlite_adapter.read_graph(NS)
    assert all(e.name != "AuthService" for e in graph.entities)
    assert all(
        r.from_entity != "AuthService" and r.to_entity != "AuthService"
        for r in graph.relations
    )


@pytest.mark.asyncio
async def test_delete_observations(sqlite_adapter: SqliteAdapter, sample_entities):
    await sqlite_adapter.create_entities(NS, sample_entities)
    await sqlite_adapter.delete_observations(
        NS, [ObservationDeletion(entityName="AuthService", observations=["Uses OAuth2"])]
    )
    graph = await sqlite_adapter.read_graph(NS)
    auth = next(e for e in graph.entities if e.name == "AuthService")
    assert "Uses OAuth2" not in auth.observations


@pytest.mark.asyncio
async def test_search_nodes(sqlite_adapter: SqliteAdapter, sample_entities):
    await sqlite_adapter.create_entities(NS, sample_entities)
    result = await sqlite_adapter.search_nodes(NS, "auth")
    assert len(result.entities) == 1
    assert result.entities[0].name == "AuthService"


@pytest.mark.asyncio
async def test_open_nodes(sqlite_adapter: SqliteAdapter, sample_entities, sample_relations):
    await sqlite_adapter.create_entities(NS, sample_entities)
    await sqlite_adapter.create_relations(NS, sample_relations)
    result = await sqlite_adapter.open_nodes(NS, ["UserDB"])
    assert len(result.entities) == 1
    assert any(r.to_entity == "UserDB" for r in result.relations)


@pytest.mark.asyncio
async def test_namespace_isolation(sqlite_adapter: SqliteAdapter, sample_entities):
    await sqlite_adapter.create_entities("team:alpha", sample_entities)
    await sqlite_adapter.create_entities(
        "team:beta", [Entity(name="BetaOnly", entityType="x", observations=[])]
    )
    alpha = await sqlite_adapter.read_graph("team:alpha")
    beta = await sqlite_adapter.read_graph("team:beta")
    assert len(alpha.entities) == 3
    assert len(beta.entities) == 1


@pytest.mark.asyncio
async def test_health_check(sqlite_adapter: SqliteAdapter):
    assert await sqlite_adapter.health_check() is True
