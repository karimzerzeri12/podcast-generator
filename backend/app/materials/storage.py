"""Filesystem abstraction for course-material ingestion.

SOURCE_ROOT can be a local/network path (bare path or a file:// URI) or an
S3-compatible URI (s3://bucket/prefix). fsspec resolves the right backend from the
URL scheme, so the rest of the app just calls fs.exists()/fs.open() and never
branches on "is this local or S3".
"""

import fsspec

from app.config import get_settings


def get_filesystem() -> tuple[fsspec.AbstractFileSystem, str]:
    """Returns (filesystem, resolved_root) for settings.source_root."""
    settings = get_settings()
    if not settings.source_root:
        raise RuntimeError("SOURCE_ROOT is not configured")

    storage_options: dict = {}
    if settings.source_root.startswith("s3://") and settings.s3_endpoint_url:
        storage_options["client_kwargs"] = {"endpoint_url": settings.s3_endpoint_url}

    fs, _, paths = fsspec.get_fs_token_paths(settings.source_root, storage_options=storage_options)
    return fs, paths[0]


def join(root: str, filename: str) -> str:
    return f"{root.rstrip('/')}/{filename.lstrip('/')}"


def check_source_root() -> None:
    """Verifies SOURCE_ROOT is reachable, logging the resolved root either way.
    Raises if it's configured but unreachable — meant to be called at process
    startup (both the API server and the ingest CLI) so a misconfigured deploy
    fails at boot, not at a student's first request."""
    settings = get_settings()
    if not settings.source_root:
        return

    try:
        fs, root = get_filesystem()
        reachable = fs.exists(root)
    except Exception as exc:
        raise RuntimeError(f"SOURCE_ROOT '{settings.source_root}' is not reachable: {exc}") from exc

    if not reachable:
        raise RuntimeError(
            f"SOURCE_ROOT '{settings.source_root}' (resolved: '{root}') does not exist or "
            "is not reachable from this machine."
        )

    print(f"[materials] SOURCE_ROOT '{settings.source_root}' resolved to '{root}' — reachable.")
