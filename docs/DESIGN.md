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

**C. Org hierarchy + placement (ours)** — Offering → Region → Zone → **Rack-Type** → Rack →
Device. **Rack-Type** is the purpose grouping (control/data/storage/network) and is the
directory level; the **directory tree IS the hierarchy** (see git layout). A rack file
references a **Rack Model** (`rack_model` → a catalog `RackTypeSpec`, the physical enclosure
that the designer *chooses*, e.g. vertiv-vr3300) and lists placements at positions, plus
`custom_line_items` for non-catalog parts. Terminology: **Rack-Type = purpose**,
**Rack Model = catalog physical rack** (ADR 2026-06-19-rack-type-vs-rack-model).

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
| Rack-Type (purpose) | Rack Role | control/data/storage/network — the dir level |
| Rack | Rack | references a Rack Model (`rack_model`) |
| Rack Model | RackType / Rack | catalog physical enclosure (RackTypeSpec) the designer picks |
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
      rack-types/<control|data|storage|network>/rack-type.yaml
        racks/<rack>.yaml                        # designer's output (references a rack_model)
.index/                                          # rebuildable SQLite cache (gitignored)
```

Example `racks/<rack>.yaml`:
```yaml
rack_model: { slug: vertiv-vr3300 }              # chosen physical rack (u_height etc. from catalog)
placements:
  - { device: dell-poweredge-r760, position: 40, release: R26.07, meta: { serial: SN1 } }
  - { device: arista-dcs-7050cx3-32s, position: 1, release: R26.07 }
custom_line_items:
  - { name: "DAC 100G 3m", qty: 24, unit_cost: 90000, release: R26.07 }
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

## Designer workflow (UI)

Two steps, with **quantity derived from placement** (ADR quantity-from-placement):

1. **Select (1차):** from categorized model candidates (server / network / storage / …),
   pick model types into a design shortlist. No quantity at this step — it is just a shortlist.
2. **Place (2차):** drag shortlisted models onto rack U positions. Bulk placement is
   supported (place N / fill contiguous U / repeat across racks). **Quantity = the count of
   placed instances — the single source of truth.**

After placement the screen shows the NetBox-style **rack elevation (SVG)** plus the placed
**device list**, which **exports to Excel (.xlsx)**. A separate **Report** function renders
the BOM to an externally-provided template via a field-mapping layer (deferred until the
template is supplied — no code change needed when it arrives, only a mapping).

**Preconditions / base data:**
- Offering / Region / Zone base data must exist before rack design (small YAML in the tree).
- Rack instances are created from a community **rack-type** (already in the catalog); the
  rack layout (what's mounted) is bombom's design output.
- **New region/zone bootstrap = clone an existing subtree** (copy the directory, rewrite
  identifiers) and modify — natural on the git backend.

**Device categorization:** the community catalog has no category/role field, so bombom
classifies device-types itself — heuristic auto-classification (interface mix, u_height,
module profiles, model-name cues) with **manual override**, stored in a category overlay
kept separate from the community spec, same as pricing (ADR device-categorization).

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
