"""Clonegrown: safe per-task Git working directories for coding agents.

Each agent task gets its own worker — a linked worktree or an independent
clone — and the lifecycle (spawn, collect, discard, recover) guarantees that
work is never duplicated, deleted before it is saved, or left half-done.

Public Python API::

    from clonegrown import init_workspace, spawn, collect, discard, recover, status, ClonegrownError
"""
from __future__ import annotations

from .core import ClonegrownError, CWSError
from .lifecycle import collect, discard, init_workspace, spawn
from .recovery import recover, status

__version__ = "0.1.0a1"
__all__ = ["ClonegrownError", "CWSError", "init_workspace", "spawn", "collect", "discard", "recover", "status", "__version__"]
