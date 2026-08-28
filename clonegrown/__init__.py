"""Clonegrown: per-task Git working-directory lifecycle management.

Each agent task can use a linked-worktree or local-clone worker. Collection
preserves a clean committed tip under a canonical Git ref; integration remains
explicit. The alpha's current custody limits are documented in the README.

Public Python API::

    from clonegrown import init_workspace, spawn, collect, release, claim, discard, recover, status, ClonegrownError
"""
from __future__ import annotations

from .core import ClonegrownError, CWSError
from .lifecycle import claim, collect, discard, init_workspace, release, spawn
from .recovery import recover, status

__version__ = "0.1.0a1"
__all__ = ["ClonegrownError", "CWSError", "init_workspace", "spawn", "collect", "release", "claim", "discard",
           "recover", "status", "__version__"]
