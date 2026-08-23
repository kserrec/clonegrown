"""Clonegrown: isolated Git clone workspaces for coding agents.

Public Python API::

    from clonegrown import init_workspace, spawn, collect, discard, recover, status, CWSError
"""
from __future__ import annotations

from .core import CWSError
from .lifecycle import collect, discard, init_workspace, spawn
from .recovery import recover, status

__version__ = "0.1.0a1"
__all__ = ["CWSError", "init_workspace", "spawn", "collect", "discard", "recover", "status", "__version__"]
