"""Knowledge graph data types, wire-compatible with @modelcontextprotocol/server-memory."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Entity:
    name: str
    entityType: str
    observations: list[str] = field(default_factory=list)

    def to_jsonl(self) -> dict:
        return {
            "type": "entity",
            "name": self.name,
            "entityType": self.entityType,
            "observations": self.observations,
        }

    @classmethod
    def from_jsonl(cls, data: dict) -> Entity:
        return cls(
            name=data["name"],
            entityType=data["entityType"],
            observations=data.get("observations", []),
        )


@dataclass
class Relation:
    from_entity: str
    to_entity: str
    relationType: str

    def to_jsonl(self) -> dict:
        return {
            "type": "relation",
            "from": self.from_entity,
            "to": self.to_entity,
            "relationType": self.relationType,
        }

    @classmethod
    def from_jsonl(cls, data: dict) -> Relation:
        return cls(
            from_entity=data["from"],
            to_entity=data["to"],
            relationType=data["relationType"],
        )


@dataclass
class KnowledgeGraph:
    entities: list[Entity] = field(default_factory=list)
    relations: list[Relation] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "entities": [
                {"name": e.name, "entityType": e.entityType, "observations": e.observations}
                for e in self.entities
            ],
            "relations": [
                {"from": r.from_entity, "to": r.to_entity, "relationType": r.relationType}
                for r in self.relations
            ],
        }


@dataclass
class ObservationUpdate:
    entityName: str
    contents: list[str]


@dataclass
class ObservationResult:
    entityName: str
    addedObservations: list[str]


@dataclass
class ObservationDeletion:
    entityName: str
    observations: list[str]
