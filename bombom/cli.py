"""bombom command-line interface.

    bombom catalog sync     [--vendors dell,arista]
    bombom catalog reindex  [--vendors ...] [--kinds device,module,rack]
    bombom catalog get-device <slug> [--manufacturer NAME]
    bombom catalog get-rack <slug>
    bombom catalog list-vendor <manufacturer> [--kind device]
    bombom catalog counts
"""

from __future__ import annotations

import argparse
import json
import sys

from .catalog import Catalog, CatalogError, reindex, sync


def _split(value: str | None) -> list[str] | None:
    if not value:
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


def _cmd_sync(args) -> int:
    result = sync(vendors=_split(args.vendors))
    print(f"pinned commit: {result.pinned_sha}")
    print(
        "discovered: "
        + ", ".join(f"{kind}={n}" for kind, n in result.counts.items())
    )
    return 0


def _cmd_reindex(args) -> int:
    summary = reindex(vendors=_split(args.vendors), kinds=tuple(_split(args.kinds) or
                      ("device", "module", "rack")))
    print(f"index: {summary.db_path}")
    print("indexed: " + ", ".join(f"{kind}={n}" for kind, n in summary.counts.items()))
    if summary.quarantine:
        print(f"\nquarantined ({len(summary.quarantine)}) — excluded from index:")
        for item in summary.quarantine[: args.show_quarantine]:
            print(f"  [{item.kind}] {item.source_path}")
            for err in item.errors[:3]:
                print(f"      - {err}")
        remaining = len(summary.quarantine) - args.show_quarantine
        if remaining > 0:
            print(f"  … and {remaining} more")
    return 0


def _print_spec(spec) -> int:
    if spec is None:
        print("not found", file=sys.stderr)
        return 1
    print(json.dumps(spec.model_dump(by_alias=True, exclude_none=True), indent=2, ensure_ascii=False))
    return 0


def _cmd_get_device(args) -> int:
    return _print_spec(Catalog().get_device_type(args.slug, manufacturer=args.manufacturer))


def _cmd_get_rack(args) -> int:
    return _print_spec(Catalog().get_rack_type(args.slug))


def _cmd_list_vendor(args) -> int:
    rows = Catalog().list_by_vendor(args.manufacturer, kind=args.kind)
    for row in rows:
        ident = row["slug"] or row["part_number"] or row["model"]
        print(f"{row['kind']:7} {ident}\t{row['model']}")
    print(f"\n{len(rows)} entries", file=sys.stderr)
    return 0


def _cmd_counts(args) -> int:
    print(json.dumps(Catalog().counts(), indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bombom")
    sub = parser.add_subparsers(dest="group", required=True)

    catalog = sub.add_parser("catalog", help="hardware catalog operations").add_subparsers(
        dest="command", required=True
    )

    p_sync = catalog.add_parser("sync", help="update the submodule to its pinned commit")
    p_sync.add_argument("--vendors", help="comma-separated manufacturer filter")
    p_sync.set_defaults(func=_cmd_sync)

    p_reindex = catalog.add_parser("reindex", help="(re)build the SQLite index")
    p_reindex.add_argument("--vendors", help="comma-separated manufacturer filter")
    p_reindex.add_argument("--kinds", help="comma-separated: device,module,rack")
    p_reindex.add_argument("--show-quarantine", type=int, default=10,
                           help="how many quarantined files to list (default 10)")
    p_reindex.set_defaults(func=_cmd_reindex)

    p_gd = catalog.add_parser("get-device", help="print a device type by slug")
    p_gd.add_argument("slug")
    p_gd.add_argument("--manufacturer")
    p_gd.set_defaults(func=_cmd_get_device)

    p_gr = catalog.add_parser("get-rack", help="print a rack type by slug")
    p_gr.add_argument("slug")
    p_gr.set_defaults(func=_cmd_get_rack)

    p_lv = catalog.add_parser("list-vendor", help="list specs for a manufacturer")
    p_lv.add_argument("manufacturer")
    p_lv.add_argument("--kind", choices=("device", "module", "rack"))
    p_lv.set_defaults(func=_cmd_list_vendor)

    p_counts = catalog.add_parser("counts", help="row counts per kind")
    p_counts.set_defaults(func=_cmd_counts)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except CatalogError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
