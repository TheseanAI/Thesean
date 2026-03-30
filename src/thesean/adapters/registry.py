"""Adapter discovery via stdlib entry points."""

from __future__ import annotations

from importlib.metadata import entry_points

from thesean.core.contracts import AdapterFactory

ADAPTER_GROUP = "thesean.adapters"


class AdapterLoadError(RuntimeError):
    pass


def discover_adapter_factories() -> dict[str, type]:
    """Return all registered adapter factory classes, keyed by name."""
    return {ep.name: ep.load() for ep in entry_points(group=ADAPTER_GROUP)}


def load_adapter_factory(name: str) -> AdapterFactory:
    """Instantiate the named adapter factory via entry points."""
    factories = discover_adapter_factories()
    if name not in factories:
        available = ", ".join(sorted(factories)) or "<none>"
        raise AdapterLoadError(
            f"Unknown adapter '{name}'. Available adapters: {available}"
        )
    factory = factories[name]()
    # Shallow structural check only — verifies method presence, not signatures
    if not isinstance(factory, AdapterFactory):
        raise AdapterLoadError(
            f"Adapter '{name}' is missing one or more required factory methods"
        )
    return factory
