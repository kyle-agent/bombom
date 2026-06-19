"""Read-only HTTP API (FastAPI) over the workspace: tree, catalog search, BOM, rack SVG."""

from .app import create_app

__all__ = ["create_app"]
