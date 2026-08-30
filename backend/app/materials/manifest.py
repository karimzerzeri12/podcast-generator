import json
from dataclasses import dataclass

import fsspec

from app.config import get_settings
from app.materials.storage import join


@dataclass
class ManifestEntry:
    title: str
    description: str
    order_index: int
    filename: str


def resolve_manifest_path(root: str) -> str:
    settings = get_settings()
    return settings.source_manifest or join(root, "topics.json")


def load_manifest(fs: fsspec.AbstractFileSystem, manifest_path: str) -> list[ManifestEntry]:
    with fs.open(manifest_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return [
        ManifestEntry(
            title=entry["title"],
            description=entry.get("description", ""),
            order_index=entry.get("order_index", idx + 1),
            filename=entry["filename"],
        )
        for idx, entry in enumerate(raw)
    ]


def validate_manifest(fs: fsspec.AbstractFileSystem, root: str, entries: list[ManifestEntry]) -> None:
    """Every file a manifest entry references must exist and be openable. Fails
    loudly, naming every missing/unreadable file at once rather than stopping at
    the first one — so a misconfigured manifest can be fixed in one pass."""
    problems: list[str] = []
    for entry in entries:
        path = join(root, entry.filename)
        if not fs.exists(path):
            problems.append(f"{entry.title!r} -> {path} (does not exist)")
            continue
        try:
            with fs.open(path, "rb") as f:
                f.read(1)
        except Exception as exc:  # noqa: BLE001 — surfaced to the operator, not swallowed
            problems.append(f"{entry.title!r} -> {path} (not readable: {exc})")

    if problems:
        raise RuntimeError(
            "Manifest references files that are missing or unreadable:\n"
            + "\n".join(f"  - {p}" for p in problems)
        )
