"""Reports derived from the BOM engine — the *outputs* a designer/finance consumer needs.

- Investment-target list (BOM view "a"): the line items added in a given release, with their
  hierarchy/location, ready to export as CSV (opens in Excel).
- Release summary: per-release incremental + cumulative CAPEX (views "a" + running "c").

All numbers come from `compute_bom`; this module only filters/shapes/serialises. Prices stay
in KRW; unpriced items are kept visible (`priced=False`), never silently costed as ₩0.
"""

from __future__ import annotations

import csv
import io
from datetime import date
from pathlib import Path
from typing import Optional

from ..bom import compute_bom
from ..design import parse_hierarchy


def _hier(rack_path: str) -> dict[str, str]:
    return parse_hierarchy(Path(rack_path)) if rack_path else {}


def placed_rows(ws, root, *, release: Optional[str] = None,
                valuation_date: Optional[date] = None) -> list[dict]:
    """Every placed line item in scope (optionally just one release), tagged with location."""
    result = compute_bom(
        Path(root), catalog=ws.catalog, pricebook=ws.pricebook, release=release,
        valuation_date=valuation_date, categories=ws.categories, fields=ws.fields,
        type_meta=ws.type_meta,
    )
    rows = []
    for li in result.line_items:
        if release is not None and li.release != release:
            continue
        h = _hier(li.rack_path)
        rows.append({
            "offering": h.get("offering", ""),
            "region": h.get("region", ""),
            "zone": h.get("zone", ""),
            "rack_type": h.get("rack_type", ""),
            "rack": li.rack_id,
            "name": li.name,
            "category": li.category,
            "release": li.release or "",
            "qty": li.qty,
            "unit_cost": li.unit_cost,            # None = unpriced
            "subtotal": li.subtotal,
            "priced": li.unit_cost is not None,
        })
    rows.sort(key=lambda r: (r["region"], r["zone"], r["rack_type"], r["rack"], r["name"]))
    return rows


def investment_rows(ws, root, release: str, *, valuation_date: Optional[date] = None) -> list[dict]:
    """The investment-target list for one release (= placed_rows filtered to that release)."""
    return placed_rows(ws, root, release=release, valuation_date=valuation_date)


_CSV_HEADERS = [
    ("offering", "오퍼링"), ("region", "리전"), ("zone", "존"), ("rack_type", "랙타입"),
    ("rack", "랙"), ("name", "장비"), ("category", "카테고리"), ("release", "릴리즈"),
    ("qty", "수량"), ("unit_cost", "단가(KRW)"), ("subtotal", "소계(KRW)"),
]


def _safe_cell(value):
    """Neutralise CSV/Excel formula injection: a leading = + - @ (or control char) is escaped
    so a spreadsheet treats the cell as text, not a formula."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


def investment_csv(rows: list[dict], *, release: str = "") -> str:
    """Serialise investment rows to CSV (UTF-8 BOM for Excel). Ends with a TOTAL row."""
    buf = io.StringIO()
    buf.write("﻿")               # BOM so Excel reads UTF-8 (Korean headers) correctly
    w = csv.writer(buf)
    w.writerow([label for _, label in _CSV_HEADERS])
    total = 0
    for r in rows:
        w.writerow([_safe_cell(c) for c in (
            r["offering"], r["region"], r["zone"], r["rack_type"], r["rack"], r["name"],
            r["category"], r["release"], r["qty"],
            "" if r["unit_cost"] is None else r["unit_cost"],
            r["subtotal"],
        )])
        total += r["subtotal"]
    w.writerow(["", "", "", "", "", f"합계 ({release})" if release else "합계", "", "",
                sum(r["qty"] for r in rows), "", total])
    return buf.getvalue()


def summarize_releases(result) -> list[dict]:
    """Per-release incremental CAPEX + running cumulative from an existing BomResult.
    `qty` counts every device installed in the release (priced or not); `increment_capex`
    reflects only priced items (unpriced never enter `by_release`)."""
    counts: dict[str, int] = {}
    for li in result.line_items:
        if li.release:
            counts[li.release] = counts.get(li.release, 0) + li.qty
    out = []
    cumulative = 0
    for rel in sorted(result.by_release):
        increment = result.by_release[rel]
        cumulative += increment
        out.append({
            "release": rel,
            "qty": counts.get(rel, 0),
            "increment_capex": increment,
            "cumulative_capex": cumulative,
        })
    return out


def release_summary(ws, root, *, valuation_date: Optional[date] = None) -> list[dict]:
    """Per-release incremental CAPEX + running cumulative, sorted by release name."""
    return summarize_releases(compute_bom(
        Path(root), catalog=ws.catalog, pricebook=ws.pricebook, valuation_date=valuation_date,
        categories=ws.categories, fields=ws.fields, type_meta=ws.type_meta,
    ))
