"""Filesystem locations shared across modules.

``PROJECT_ROOT`` is derived from this file's location, so it only points at the
repo root in a source checkout or editable install (``uv sync``). Stage data
(``stages/``, ``templates/``, ``config/``) is still resolved relative to the
current working directory; a ``data_root`` setting should replace both later.
"""

from pathlib import Path

# src/happytube/paths.py -> src/happytube -> src -> project root
PROJECT_ROOT = Path(__file__).resolve().parents[2]
LEGACY_FETCHED_DIR = PROJECT_ROOT / "data" / "fetched"
