"""Tests for knowledge graph types and serialization."""

from hivemind_mcp.types import Entity, KnowledgeGraph, Relation


def test_entity_roundtrip():
    e = Entity(name="Foo", entityType="service", observations=["uses gRPC"])
    data = e.to_jsonl()
    assert data["type"] == "entity"
    assert data["name"] == "Foo"
    restored = Entity.from_jsonl(data)
    assert restored.name == e.name
    assert restored.entityType == e.entityType
    assert restored.observations == e.observations


def test_relation_roundtrip():
    r = Relation(from_entity="A", to_entity="B", relationType="depends_on")
    data = r.to_jsonl()
    assert data["type"] == "relation"
    assert data["from"] == "A"
    assert data["to"] == "B"
    restored = Relation.from_jsonl(data)
    assert restored.from_entity == r.from_entity
    assert restored.to_entity == r.to_entity
    assert restored.relationType == r.relationType


def test_knowledge_graph_to_dict():
    graph = KnowledgeGraph(
        entities=[Entity(name="X", entityType="t", observations=["o"])],
        relations=[Relation(from_entity="X", to_entity="Y", relationType="r")],
    )
    d = graph.to_dict()
    assert len(d["entities"]) == 1
    assert d["entities"][0]["name"] == "X"
    assert len(d["relations"]) == 1
    assert d["relations"][0]["from"] == "X"
