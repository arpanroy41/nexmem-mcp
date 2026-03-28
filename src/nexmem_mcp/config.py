"""Configuration via environment variables using pydantic-settings."""

from __future__ import annotations

import getpass
import os
from enum import Enum
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings


class MemoryMode(str, Enum):
    SELF = "self"
    TEAM = "team"


class BackendType(str, Enum):
    JSONL = "jsonl"
    SQLITE = "sqlite"
    MONGODB = "mongodb"
    POSTGRES = "postgres"
    REDIS = "redis"


class NexMemConfig(BaseSettings):
    model_config = {"env_prefix": "NEXMEM_"}

    mode: MemoryMode = MemoryMode.SELF
    user_name: str = ""
    team_name: str = ""
    backend: BackendType = BackendType.JSONL
    read_only: bool = False
    instructions: str = ""

    # Backend-specific
    jsonl_path: str = ""
    sqlite_path: str = ""
    mongodb_uri: str = "mongodb://localhost:27017/nexmem"
    postgres_uri: str = "postgresql://localhost:5432/nexmem"
    redis_url: str = "redis://localhost:6379/0"

    @field_validator("user_name", mode="before")
    @classmethod
    def default_user_name(cls, v: str) -> str:
        if not v:
            return getpass.getuser()
        return v

    @field_validator("jsonl_path", mode="before")
    @classmethod
    def default_jsonl_path(cls, v: str) -> str:
        if not v:
            return str(Path.home() / ".nexmem" / "memory.jsonl")
        return v

    @field_validator("sqlite_path", mode="before")
    @classmethod
    def default_sqlite_path(cls, v: str) -> str:
        if not v:
            return str(Path.home() / ".nexmem" / "memory.db")
        return v

    def validate_team_mode(self) -> None:
        if self.mode == MemoryMode.TEAM and not self.team_name:
            raise ValueError(
                "NEXMEM_TEAM_NAME is required when NEXMEM_MODE=team"
            )

    def get_instructions(self) -> str:
        """Resolve instructions from file path, inline text, or built-in default."""
        if self.instructions:
            path = Path(self.instructions)
            if path.is_file():
                return path.read_text(encoding="utf-8")
            return self.instructions
        return DEFAULT_INSTRUCTIONS


DEFAULT_INSTRUCTIONS = """\
You have access to a shared knowledge graph (NexMem) for persistent memory.

READING — Proactively search memory at the start of relevant tasks:
- Before working on a service, component, or system, call search_nodes to check \
for existing knowledge.
- Use open_nodes to get full details on specific entities you already know about.
- Use read_graph when you need a broad overview of what's been recorded.

WRITING — Save useful discoveries as you work (no need to be asked):
- New services, repositories, APIs, and their tech stacks
- Architecture patterns, design decisions, and conventions
- Dependencies and relationships between systems
- Non-obvious gotchas, configuration details, and debugging insights
- Team processes and workflows

DO NOT SAVE:
- Trivial or temporary information (one-off variable names, debug output)
- Information already present in the graph (search first to avoid duplicates)
- User-specific preferences or ephemeral session context
- Secrets, credentials, or sensitive data

Use create_entities for new things, add_observations to enrich existing entities, \
and create_relations to connect related entities.\
"""
