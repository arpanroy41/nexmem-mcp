"""Shared fixtures for hivemind-mcp tests."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from hivemind_mcp.adapters.jsonl import JsonlAdapter
from hivemind_mcp.adapters.sqlite import SqliteAdapter
from hivemind_mcp.config import BackendType, HiveMindConfig, MemoryMode
from hivemind_mcp.types import Entity, Relation


@pytest.fixture
def sample_entities() -> list[Entity]:
    return [
        Entity(name="AuthService", entityType="service", observations=["Uses OAuth2", "Written in Go"]),
        Entity(name="PaymentAPI", entityType="service", observations=["Uses gRPC", "Handles billing"]),
        Entity(name="UserDB", entityType="database", observations=["PostgreSQL 16", "Contains user data"]),
    ]


@pytest.fixture
def sample_relations() -> list[Relation]:
    return [
        Relation(from_entity="AuthService", to_entity="UserDB", relationType="reads_from"),
        Relation(from_entity="PaymentAPI", to_entity="AuthService", relationType="depends_on"),
    ]


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def jsonl_config(tmp_dir: Path) -> HiveMindConfig:
    return HiveMindConfig(
        mode=MemoryMode.SELF,
        user_name="testuser",
        backend=BackendType.JSONL,
        jsonl_path=str(tmp_dir / "memory.jsonl"),
    )


@pytest.fixture
def jsonl_adapter(jsonl_config: HiveMindConfig) -> JsonlAdapter:
    return JsonlAdapter(jsonl_config)


@pytest.fixture
def sqlite_config(tmp_dir: Path) -> HiveMindConfig:
    return HiveMindConfig(
        mode=MemoryMode.SELF,
        user_name="testuser",
        backend=BackendType.SQLITE,
        sqlite_path=str(tmp_dir / "memory.db"),
    )


@pytest.fixture
def sqlite_adapter(sqlite_config: HiveMindConfig) -> SqliteAdapter:
    return SqliteAdapter(sqlite_config)
