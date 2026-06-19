# 2026-06-19 — Reuse the community device-type library, do not run NetBox

## Context
We need a hardware catalog that stays current with new HW without us defining each model.
NetBox has a mature DCIM data model and a community `devicetype-library` (YAML, PR-driven)
that already does this. The forcing question: run NetBox itself, or just consume its data?

## Decision
Consume the `netbox-community/devicetype-library` YAML directly as our catalog source of
truth. Do **not** deploy the NetBox application. Reuse NetBox's schema/conventions for
DeviceType/ModuleType/RackType; build bombom's own lean placement + cost + BOM layers.

## Alternatives considered
- **Deploy NetBox as the DCIM backend** (import tool + REST API). Maximum reuse, but adds
  operational weight (Postgres/Redis/app) and makes bombom a thin plugin around a system
  whose core value (cost/BOM) it does not provide.
- **Vendor NetBox's Django models into our codebase.** Rejected — NetBox is a tightly
  coupled monolith; carving out DCIM is high-maintenance and drifts from upstream.

## Consequences
- New HW reflection = `git pull` of the submodule + reindex. We never hand-author specs.
- We must implement rack placement, elevation rendering, and power rollup ourselves
  (NetBox would have given these for free).
- The catalog is read-only to us; corrections go upstream as PRs.

## Override conditions
Revisit if we end up needing NetBox's full DCIM (cabling, IPAM, change-mgmt UI) — then
deploying NetBox as a backend may beat reimplementing it.
