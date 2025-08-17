"""Backend-specific installer modules for the Tomex project.

Submodules are imported lazily to avoid side effects when using
``python -m`` with a specific backend. This prevents modules from being
pre-loaded during package import, which previously triggered a runtime
warning.
"""

from importlib import import_module
from typing import Any

__all__ = ["windows", "wsl", "docker", "pip_installer"]


def __getattr__(name: str) -> Any:
    """Dynamically import installer submodules on first access."""
    if name in __all__:
        return import_module(f".{name}", __name__)
    raise AttributeError(f"module {__name__} has no attribute {name}")
