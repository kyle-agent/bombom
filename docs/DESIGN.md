# bombom — Design Overview

> Status: **locked (high-level)** as of 2026-06-19. Feature-level scope is locked per
> feature via `/brief`. Decisions here are recorded individually in `docs/decisions/`.

## What bombom is

A tool for cloud-service infrastructure designers to **select hardware, lay it out in
racks, and derive the capital investment (BOM/CAPEX)**. Hardware specs come from the
NetBox community catalog; bombom adds the cost layer and the org-specific placement model
that NetBox does not provide.

## The two layers (never mixed)

```
[technical spec]  community devicetype-library   ──(key: manufacturer+slug | part_number)──┐
   read-only, synced via git submodule (pinned commit)                                      │ JOIN
                                                                                            │
[cost overlay]    bombom price book (pricing/<vendor>.yaml)  ───────────────────────────────┘
   ours, time-versioned: unit_cost, currency, source, valid_from/valid_to
```

Price is **never** written into the device YAML — that would conflict on every community
update. The two are joined by a stable key at BOM time.

## Data model

**A. Catalog (synced, read-only)** — mirrors devicetype-library schema:
`DeviceTypeSpec` (manufacturer, model, slug, part_number, u_height, is_full_depth,
weight, airflow, is_powered, power_ports[], interfaces[], module_bays[], device_bays[]),
`ModuleTypeSpec` (profile CPU/GPU/PSU/Fan…, attribute_data), `RackTypeSpec`
(u_height, width, weight).

**B. Cost overlay (ours)** — `PriceEntry`: key → unit_cost, currency, source,
valid_from/valid_to, note.

**C. Org hierarchy + placement (ours)** — Offering → Region → Zone → RackGroup → Rack →
Device. The **directory tree IS the hierarchy** (see git layout). A rack file references a
`RackTypeSpec` and lists mounted devices/modules at positions, plus `custom_line_items`
for non-catalog parts (cables, optics, PDUs, labor, spares).

**D. BOM engine** — walk a design subtree → flatten to (part key, qty) → join PriceEntry
at a valuation date → CAPEX rollup (by manufacturer/category/rack/zone/offering). Power
rollup (Σ maximum/allocated draw, watts) for capacity only; cost conversion deferred
(CAPEX-first).

## Org hierarchy ↔ NetBox mapping

| bombom | NetBox | note |
|---|---|---|
| Offering | (none — new top tier) | service/product unit |
| Region | Region | |
| Zone | Site | availability zone / physical site |
| Rack Group | Location (formerly RackGroup) | |
| Rack | Rack | references RackTypeSpec |
| Device | Device | references DeviceTypeSpec, U position + face |

Catalog (DeviceType/ModuleType/RackType) is reused as-is from NetBox/community; only the
placement hierarchy is bombom-specific.

## Git layout (directory = hierarchy)

```
vendor/devicetype-library/                       # git submodule (community, pinned)
pricing/<vendor>.yaml                            # price overlay
offerings/<offering>/offering.yaml
  regions/<region>/region.yaml
    zones/<zone>/zone.yaml
      rack-groups/<rack-group>/rack-group.yaml
        racks/<rack>.yaml                        # designer's output
.index/                                          # rebuildable SQLite cache (gitignored)
```

Example `racks/<rack>.yaml`:
```yaml
rack_type: { manufacturer: vertiv, slug: vertiv-vr3300 }   # u_height=42, etc. from catalog
mounted:
  - device_type: { manufacturer: dell, slug: poweredge-r760 }
    position: 40
    face: front
    qty: 1
  - device_type: { manufacturer: arista, slug: dcs-7050sx3-48yc8 }
    position: 1
    face: front
    qty: 2
custom_line_items:
  - { name: "DAC 100G 3m", qty: 24, unit_cost: 90, currency: USD }
```

## Application architecture

- **Backend (Python / FastAPI):** git is the datastore (read via working copy + commit on
  write using a git lib); catalog sync; rebuildable SQLite index for queries; BOM engine;
  **server-side rack elevation SVG rendering** (NetBox-style: computed from rack u_height +
  each device's position/u_height/face); REST API.
- **Frontend (JS — React/Svelte SPA):** hierarchy tree nav; rack elevation view (consumes
  the SVG/geometry); HW candidate picker (search catalog) with **form-based** placement
  (qty, U position, face); live BOM/CAPEX panel.
- **Edit loop:** designer edits via form → `POST` to API → backend writes the rack YAML →
  git commit. Screen and git are two faces of the same data. Collaboration via branch/PR;
  branch = cost scenario, ref-to-ref diff = investment delta.

## Community reflection

devicetype-library as a **git submodule** pinned to a commit. A `sync` command does
`git pull` → validate (reuse upstream schema) → rebuild index, vendor-selectable. New HW =
upstream PR merges → bump pin → appears automatically. We never author device specs; if a
HW is missing we contribute a PR upstream (temporary local `overrides/` in identical
schema if urgent).

## Scope OUT (deferred)

- Running NetBox as an app / its database.
- OPEX / power-cost / full TCO (power capacity computed, but not costed).
- Interactive drag-and-drop rack editing (form-based for MVP).
- Multi-currency normalization, depreciation schedules.
