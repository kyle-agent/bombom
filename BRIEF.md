# Brief: Build catalog sync — vendor, parse, validate, and index the device-type library

**Goal**
Stand up bombom's hardware catalog subsystem: vendor `netbox-community/devicetype-library`
as a pinned git submodule, parse device/module/rack type YAML into typed models, validate
against the upstream schema, and build a rebuildable SQLite index exposed via a CLI and a
query API. This is the foundation the BOM engine, rack model, and UI all read from.

**Scope IN**
- Add `devicetype-library` as a git **submodule pinned to a specific commit** under
  `vendor/`; provide a documented way to bump the pin.
- `catalog sync` CLI: init/update the submodule to the pinned ref; **vendor-selectable**
  (`--vendors dell,arista`); prints pinned SHA + discovered counts.
- Parse **device-types, module-types, rack-types** YAML into typed (Pydantic) models
  including component templates (interfaces, power-ports, module/device-bays).
- **Strict validation** against the upstream schema; invalid specs are **quarantined**
  (reported with file paths, excluded from index), valid specs indexed.
- Build/rebuild a **SQLite index** that is fully reconstructible from files; idempotent
  (re-run → identical state, no dupes). Index dir gitignored.
- **Query API** module: `get_device_type(manufacturer, slug)`, `list_by_vendor(...)`,
  filter by type; CLI wrappers over the same functions. Join key = `manufacturer+slug`
  (fallback `part_number`).

**Scope OUT**
- Price/cost overlay and any BOM/CAPEX computation (separate feature).
- Org hierarchy, rack placement, and design files (Offering→…→Rack).
- Rack elevation rendering and any UI/frontend.
- Contributing specs upstream and local `overrides/` for not-yet-merged HW.
- Image assets (`elevation-images/`, `module-images/`).
- Scheduled/automatic submodule pin bumping (manual bump only).

**Constraints**
- File-level: `vendor/devicetype-library/` is **read-only** — never hand-edited
  (ADR library-only-catalog).
- Behavior-level: **git is source of truth; the index is never authoritative** — a full
  rebuild from files must reproduce state (ADR git-as-backend).
- Data: **no price/cost fields in the catalog** — spec stays separate from cost
  (ADR spec-cost-separation).
- Integration: honor the upstream devicetype-library YAML schema; do not fork its field names.

**Exit Criteria**
- [ ] `bombom catalog sync` initializes/updates the submodule to the pinned commit and
  prints the pinned SHA + counts (devices/modules/racks discovered).
- [ ] After reindex, `get_device_type("dell","poweredge-r760")` returns a parsed spec with
  `u_height` and component templates populated.
- [ ] Re-running reindex on unchanged files yields identical row counts (no duplicates) —
  idempotent.
- [ ] A deliberately malformed YAML is excluded from the index and listed in a quarantine
  summary (count + paths); valid specs still index.
- [ ] `catalog sync --vendors dell,arista` indexes only those manufacturers;
  `list_by_vendor("dell")` returns only Dell entries.
- [ ] Deleting the index dir and rebuilding reproduces identical query results.

**Risk Flags**
- Upstream schema may vary across vendors/types → strict validation could reject legitimate
  specs; quarantine must report clearly, never silently drop. If a type lacks a published
  schema, fall back to minimal field validation for that type.
- Submodule size (thousands of files) → rely on the pinned commit + vendor-selective parse
  to bound clone/parse time.
- `slug`/`part_number` collisions or missing keys → join-key resolution must flag, not crash.
