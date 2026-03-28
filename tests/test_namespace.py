"""Tests for namespace resolution."""

import pytest

from hivemind_mcp.config import HiveMindConfig, MemoryMode
from hivemind_mcp.namespace import resolve_namespace


def test_self_namespace():
    cfg = HiveMindConfig(mode=MemoryMode.SELF, user_name="alice")
    assert resolve_namespace(cfg) == "self:alice"


def test_team_namespace():
    cfg = HiveMindConfig(mode=MemoryMode.TEAM, user_name="alice", team_name="eng")
    assert resolve_namespace(cfg) == "team:eng"


def test_team_namespace_requires_team_name():
    cfg = HiveMindConfig(mode=MemoryMode.TEAM, user_name="alice", team_name="")
    with pytest.raises(ValueError, match="HIVEMIND_TEAM_NAME is required"):
        resolve_namespace(cfg)
