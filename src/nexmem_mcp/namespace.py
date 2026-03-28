"""Namespace resolution for self vs team memory isolation."""

from __future__ import annotations

from nexmem_mcp.config import NexMemConfig, MemoryMode


def resolve_namespace(config: NexMemConfig) -> str:
    """Build a namespace string from the current configuration.

    Returns:
        "self:<username>" in self mode, "team:<teamname>" in team mode.
    """
    if config.mode == MemoryMode.SELF:
        return f"self:{config.user_name}"
    config.validate_team_mode()
    return f"team:{config.team_name}"
