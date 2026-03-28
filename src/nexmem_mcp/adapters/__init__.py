"""Adapter registry and factory."""

from __future__ import annotations

from typing import Callable, Type

from nexmem_mcp.adapters.base import StorageAdapter
from nexmem_mcp.config import BackendType, NexMemConfig

_REGISTRY: dict[str, Type[StorageAdapter]] = {}


def register_adapter(name: str) -> Callable[[Type[StorageAdapter]], Type[StorageAdapter]]:
    """Decorator to register a storage adapter under a given name.

    Usage:
        @register_adapter("mongodb")
        class MongoDBAdapter(StorageAdapter): ...
    """

    def wrapper(cls: Type[StorageAdapter]) -> Type[StorageAdapter]:
        _REGISTRY[name] = cls
        return cls

    return wrapper


def create_adapter(config: NexMemConfig) -> StorageAdapter:
    """Instantiate the appropriate adapter based on configuration."""
    _ensure_builtins_loaded()

    name = config.backend.value
    if name not in _REGISTRY:
        available = ", ".join(sorted(_REGISTRY.keys()))
        raise ValueError(
            f"Unknown backend '{name}'. Available: {available}. "
            f"You may need to install an extra: pip install 'mcp-nexmem[{name}]'"
        )

    adapter_cls = _REGISTRY[name]
    return adapter_cls(config)


def _ensure_builtins_loaded() -> None:
    """Import built-in adapters so their @register_adapter decorators run."""
    import nexmem_mcp.adapters.jsonl  # noqa: F401
    import nexmem_mcp.adapters.sqlite  # noqa: F401

    try:
        import nexmem_mcp.adapters.mongodb  # noqa: F401
    except ImportError:
        pass
    try:
        import nexmem_mcp.adapters.postgres  # noqa: F401
    except ImportError:
        pass
    try:
        import nexmem_mcp.adapters.redis  # noqa: F401
    except ImportError:
        pass
