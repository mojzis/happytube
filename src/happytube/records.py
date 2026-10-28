"""Append-only record files shared by the channel registry and video reviews.

A record is one YAML file named after its own timestamp
(``<YYYYMMDDTHHMMSSZ>[-<who>][-N].yaml``). Every write creates a new file
exclusively — a name already taken gets ``-2``, ``-3`` … — so concurrent writers
never overwrite each other, and reading sorts by the record's timestamp, then by
that collision suffix, so ties are broken in write order.
"""

import re
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ValidationError

from happytube.utils import slugify

YAML_SUFFIX = ".yaml"
_COLLISION_SUFFIX = re.compile(r"^(?P<base>.+)-(?P<n>\d+)$")


class StoreError(Exception):
    """A file store problem (a broken file, a missing record or directory); the
    message is user-facing and names the file when there is one."""


def collision_index(name: str, names: set[str], suffix: str = YAML_SUFFIX) -> int:
    """Write order of a record file among same-stem files: base is 1, ``-N`` is N.

    A trailing ``-N`` only counts as a collision suffix when the base file exists,
    so a reviewer slug that ends in digits (``bot-2``) is not mistaken for one.
    """
    match = _COLLISION_SUFFIX.match(name.removesuffix(suffix))
    if match and f"{match['base']}{suffix}" in names:
        return int(match["n"])
    return 1


def dump_yaml(data: dict[str, Any]) -> str:
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)


def read_text(path: Path) -> str:
    """A record file's text; a file that cannot be read (not UTF-8, a directory,
    no permission) is a ``StoreError`` naming it."""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as e:
        msg = f"{path}: not UTF-8 text: {e}"
        raise StoreError(msg) from e
    except OSError as e:
        msg = f"{path}: cannot read it: {e.strerror or e}"
        raise StoreError(msg) from e


def load_yaml(path: Path) -> dict[str, Any]:
    text = read_text(path)
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        msg = f"{path}: invalid YAML: {e}"
        raise StoreError(msg) from e
    if not isinstance(data, dict):
        msg = f"{path}: expected a YAML mapping"
        raise StoreError(msg)
    return data


def validate[M: BaseModel](path: Path, data: dict[str, Any], model: type[M]) -> M:
    """Validate data read from ``path`` as ``model``; errors name the file."""
    try:
        return model.model_validate(data)
    except ValidationError as e:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in err['loc']) or '(file)'}: {err['msg']}"
            for err in e.errors()
        )
        msg = f"{path}: {problems}"
        raise StoreError(msg) from e


def load_model[M: BaseModel](path: Path, model: type[M]) -> M:
    """Validate a YAML file as ``model``; errors name the file."""
    return validate(path, load_yaml(path), model)


def load_records[M: BaseModel](
    directory: Path,
    model: type[M],
    timestamp: Callable[[M], datetime],
    suffix: str = YAML_SUFFIX,
    load: Callable[[Path, type[M]], M] = load_model,
) -> list[M]:
    """Every ``*<suffix>`` record file in ``directory``, read by ``load``, in write
    order: by ``timestamp``, then by the filename's collision suffix (base file
    first, then ``-2``, ``-3`` …)."""
    if not directory.is_dir():
        return []
    paths = list(directory.glob(f"*{suffix}"))
    names = {p.name for p in paths}
    loaded = [(load(p, model), p.name) for p in paths]
    loaded.sort(
        key=lambda pair: (
            timestamp(pair[0]),
            collision_index(pair[1], names, suffix),
            pair[1],
        )
    )
    return [record for record, _ in loaded]


def latest_by_name(directory: Path, suffix: str = YAML_SUFFIX) -> Path | None:
    """The newest record file by name alone: its timestamp stem, then the same
    collision-suffix rule as ``load_records``. Valid for files named by
    ``stamp`` of the record's own timestamp (evidence snapshots, vet reports),
    so only one file needs parsing."""
    if not directory.is_dir():
        return None
    paths = list(directory.glob(f"*{suffix}"))
    names = {p.name for p in paths}

    def key(path: Path) -> tuple[str, int, str]:
        index = collision_index(path.name, names, suffix)
        stem = path.stem
        if index > 1:
            stem = stem.rsplit("-", 1)[0]
        return (stem, index, path.name)

    return max(paths, key=key, default=None)


def write_new(
    directory: Path, stem: str, content: str, suffix: str = YAML_SUFFIX
) -> Path:
    """Create ``<stem><suffix>`` exclusively, or ``<stem>-2<suffix>``, ``-3`` …
    if taken. ``directory``'s parent must exist."""
    directory.mkdir(exist_ok=True)
    n = 1
    while True:
        name = f"{stem}{suffix}" if n == 1 else f"{stem}-{n}{suffix}"
        try:
            with (directory / name).open("x", encoding="utf-8") as f:
                f.write(content)
        except FileExistsError:
            n += 1
            continue
        return directory / name


def stamp(value: datetime) -> str:
    return value.strftime("%Y%m%dT%H%M%SZ")


def review_stem(created_at: datetime, reviewer: str) -> str:
    """File stem of a review: its timestamp and the reviewer's slug."""
    return f"{stamp(created_at)}-{slugify(reviewer) or 'reviewer'}"
