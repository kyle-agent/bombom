"""Device category overlay (ours) — slug → category, kept out of the catalog.

Categories: server / network / storage / other. A YAML overlay (`categories/overlay.yaml`)
holds explicit assignments; anything unset falls back to a name heuristic. Same separation
principle as pricing/meta (ADR spec-cost-separation).
"""

from __future__ import annotations

from pathlib import Path

import yaml

CATEGORIES = ("server", "network", "storage", "other")


def heuristic_category(model: str, manufacturer: str = "") -> str:
    n = f"{model} {manufacturer}".lower()
    if any(k in n for k in ("switch", "nexus", "dcs-", "catalyst", "router", "arista")):
        return "network"
    if any(k in n for k in ("storage", "powerstore", "aff", "netapp", "isilon", "vsp")):
        return "storage"
    if any(k in n for k in ("poweredge", "proliant", "server", "blade", "ucs")):
        return "server"
    return "other"


class CategoryBook:
    def __init__(self, overlay: dict[str, str] | None = None, path: Path | None = None):
        self._map = dict(overlay or {})
        self._path = path

    @classmethod
    def load(cls, overlay_path: Path) -> "CategoryBook":
        overlay_path = Path(overlay_path)
        data: dict[str, str] = {}
        if overlay_path.exists():
            doc = yaml.safe_load(overlay_path.read_text()) or {}
            data = dict(doc.get("categories", {}))
        return cls(data, overlay_path)

    def get(self, slug: str, *, model: str = "", manufacturer: str = "") -> str:
        if slug in self._map:
            return self._map[slug]
        return heuristic_category(model or slug, manufacturer)

    def is_explicit(self, slug: str) -> bool:
        return slug in self._map

    def set(self, slug: str, category: str) -> None:
        if category not in CATEGORIES:
            raise ValueError(f"category must be one of {CATEGORIES}")
        self._map[slug] = category
        if self._path is not None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                yaml.safe_dump({"categories": dict(sorted(self._map.items()))}, allow_unicode=True)
            )
