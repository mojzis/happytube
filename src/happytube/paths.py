"""Filesystem locations shared across modules."""

from pathlib import Path

# src/happytube/paths.py -> src/happytube -> src -> project root
PROJECT_ROOT = Path(__file__).resolve().parents[2]
LEGACY_FETCHED_DIR = PROJECT_ROOT / "data" / "fetched"
