#!/usr/bin/env python3
"""Script entry for the research harnesses: runs ``clonegrown.legacy_cli`` from this checkout."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from clonegrown.legacy_cli import main  # noqa: E402

raise SystemExit(main())
