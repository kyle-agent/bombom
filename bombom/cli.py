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

from datetime import date
from pathlib import Path

from . import confirm as confirm_mod
from . import release as release_mod
from . import scaffold as scaffold_mod
from .bom import compute_bom
from .catalog import Catalog, CatalogError, reindex, sync
from .confirm import ConfirmError, ConfirmScope, GateBlocked
from .export import build_data, write_export
from .overlay import CategoryBook, TypeMetaBook
from .workspace import Workspace


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


def _won(n: int) -> str:
    return "₩" + format(int(n), ",d")


def _cmd_bom(args) -> int:
    as_of = date.fromisoformat(args.as_of) if args.as_of else None
    ws = Workspace.open(".")
    result = compute_bom(
        args.path,
        catalog=ws.catalog,
        pricebook=ws.pricebook,
        release=args.release,
        valuation_date=as_of,
        categories=ws.categories,
        fields=ws.fields,
        type_meta=ws.type_meta,
    )
    print(f"BOM — {args.path}  (as of {result.valuation_date})")
    print(f"  총 CAPEX : {_won(result.total_capex)}")
    if args.release:
        print(f"  릴리즈 {args.release} 추가분 : {_won(result.release_delta)}")
    print(f"  전력 합계 : {result.power_w:,} W")
    if result.by_category:
        print("  카테고리별: " + ", ".join(f"{k}={_won(v)}" for k, v in sorted(result.by_category.items())))
    if result.by_release:
        print("  릴리즈별  : " + ", ".join(f"{k}={_won(v)}" for k, v in sorted(result.by_release.items())))
    if result.unpriced:
        print(f"  ⚠️ 미가격 {len(result.unpriced)}건: "
              + ", ".join(f"{li.name}×{li.qty}" for li in result.unpriced[:8]))
    errors = [i for i in result.issues if i.level == "error"]
    if errors:
        print(f"  ⚠️ 오류 {len(errors)}건 (집계 제외):")
        for i in errors[: args.show_issues]:
            print(f"      - {i.path}: {i.message}")
    # Non-zero exit when anything was excluded, so CI/callers can distinguish a clean run.
    return 1 if errors else 0


def _cmd_scaffold(args) -> int:
    root = "."
    if args.kind == "offering":
        p = scaffold_mod.scaffold_offering(root, args.names[0])
    elif args.kind == "region":
        p = scaffold_mod.scaffold_region(root, *args.names[:2])
    elif args.kind == "zone":
        p = scaffold_mod.scaffold_zone(root, *args.names[:3])
    elif args.kind == "rack-type":
        p = scaffold_mod.scaffold_rack_type(root, *args.names[:4])
    elif args.kind == "rack":
        p = scaffold_mod.scaffold_rack(root, *args.names[:5], rack_model_slug=args.rack_model)
    else:  # clone
        p = scaffold_mod.clone_subtree(args.names[0], args.names[1])
    print(f"created: {p}")
    return 0


def _cmd_category(args) -> int:
    book = CategoryBook.load(Path("categories") / "overlay.yaml")
    book.set(args.slug, args.category)
    print(f"category set: {args.slug} → {args.category}")
    return 0


def _cmd_meta(args) -> int:
    if args.meta_cmd == "fields":
        for f in Workspace.open(".").fields:
            req = "필수" if f.required else "선택"
            print(f"  {f.key} ({f.label or f.key}) {f.type} · {req} · {f.applies_to} · {f.scope}")
        return 0
    # set-type slug key=value
    book = TypeMetaBook.load(Path("meta") / "devicetypes")
    key, _, value = args.assignment.partition("=")
    book.set(args.slug, key.strip(), value.strip(), vendor=args.vendor)
    print(f"type meta set: {args.slug}.{key.strip()} = {value.strip()}")
    return 0


def _cmd_release(args) -> int:
    if args.release_cmd == "list":
        tags = release_mod.list_tags(Path("."))
        print("\n".join(tags) if tags else "(no release tags)")
    else:
        print("tagged:", release_mod.tag_release(args.name, cwd=Path(".")))
    return 0


def _print_gate(gate) -> None:
    if gate.affected_racks:
        print(f"  영향 랙 {len(gate.affected_racks)}개 · 변경셋 CAPEX {_won(gate.capex)}")
    for i in gate.errors:
        print(f"  ✗ {i.path}: {i.message}")
    for i in gate.warnings:
        print(f"  ⚠ {i.path}: {i.message}")


def _cmd_confirm(args) -> int:
    ws = Workspace.open(".")
    if args.confirm_cmd == "list":
        rows = confirm_mod.list_confirmations(ws.root)
        if not rows:
            print("(no confirmations)")
        for c in rows:
            tag = f" tag={c.tag}" if c.tag else ""
            print(f"  {c.id}  [{c.kind}]  {c.status}{tag}")
        return 0
    if args.confirm_cmd == "show":
        got = confirm_mod.detail(ws, args.id)
        if got is None:
            print(f"error: confirmation not found: {args.id}", file=sys.stderr)
            return 2
        conf, gate = got
        print(f"{conf.id} [{conf.kind}] {conf.status}"
              + (f" tag={conf.tag}" if conf.tag else ""))
        _print_gate(gate)
        return 0
    try:
        if args.confirm_cmd == "request":
            scope = ConfirmScope(release=args.release) if args.kind == "release" \
                else ConfirmScope(paths=args.paths or [])
            conf, gate, _ = confirm_mod.request(ws, conf_id=args.id, kind=args.kind,
                                                scope=scope, requester=args.requester)
            print(f"requested: {conf.id} → {conf.status}")
            _print_gate(gate)
            return 0
        # approve
        conf, gate, _, tag = confirm_mod.approve(ws, conf_id=args.id, approver=args.approver)
        print(f"confirmed: {conf.id} → {conf.status}  (tag {tag})")
        _print_gate(gate)
        return 0
    except GateBlocked as gb:
        print("확정 게이트 실패 (error를 고친 뒤 다시 시도):", file=sys.stderr)
        _print_gate(gb.gate)
        return 1
    except ConfirmError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def _cmd_export(args) -> int:
    ws = Workspace.open(".")
    payload = build_data(ws, args.path, release=args.release, is_mock=False)
    out = write_export(payload, args.out, template=Path("web") / "viewer.html")
    print(f"exported: {out}  (총 CAPEX {_won(payload['bom']['total_capex'])})")
    return 0


def _cmd_serve(args) -> int:
    import uvicorn

    from .api import create_app

    uvicorn.run(create_app("."), host=args.host, port=args.port)
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

    p_bom = sub.add_parser("bom", help="compute the BOM/CAPEX for a design subtree")
    p_bom.add_argument("path", help="hierarchy path, e.g. offerings/cloud-a or a zone dir")
    p_bom.add_argument("--release", help="highlight this release's added CAPEX")
    p_bom.add_argument("--as-of", help="valuation date YYYY-MM-DD (default today)")
    p_bom.add_argument("--pricing", default="pricing", help="pricing overlay dir (default: pricing/)")
    p_bom.add_argument("--show-issues", type=int, default=10)
    p_bom.set_defaults(func=_cmd_bom)

    p_sc = sub.add_parser("scaffold", help="create base data (hierarchy) / clone a subtree")
    p_sc.add_argument("kind", choices=("offering", "region", "zone", "rack-type", "rack", "clone"))
    p_sc.add_argument("names", nargs="+",
                      help="positional names; rack-type: o r z type · rack: o r z type rack")
    p_sc.add_argument("--rack-model", help="catalog rack model slug, e.g. vertiv-vr3300 (for 'rack')")
    p_sc.set_defaults(func=_cmd_scaffold)

    p_cat = sub.add_parser("category", help="device category overlay").add_subparsers(
        dest="cat_cmd", required=True)
    p_cat_set = p_cat.add_parser("set")
    p_cat_set.add_argument("slug")
    p_cat_set.add_argument("category", choices=("server", "network", "storage", "other"))
    p_cat_set.set_defaults(func=_cmd_category)

    p_meta = sub.add_parser("meta", help="device meta / custom fields").add_subparsers(
        dest="meta_cmd", required=True)
    p_meta.add_parser("fields").set_defaults(func=_cmd_meta)
    p_meta_set = p_meta.add_parser("set-type", help="set a type-level meta value")
    p_meta_set.add_argument("slug")
    p_meta_set.add_argument("assignment", help="key=value")
    p_meta_set.add_argument("--vendor", default="misc")
    p_meta_set.set_defaults(func=_cmd_meta)

    p_rel = sub.add_parser("release", help="release ↔ git tags").add_subparsers(
        dest="release_cmd", required=True)
    p_rel.add_parser("list").set_defaults(func=_cmd_release)
    p_rel_tag = p_rel.add_parser("tag")
    p_rel_tag.add_argument("name")
    p_rel_tag.set_defaults(func=_cmd_release)

    p_conf = sub.add_parser("confirm", help="confirm workflow (gate → in-review → tag)"
                            ).add_subparsers(dest="confirm_cmd", required=True)
    p_conf.add_parser("list").set_defaults(func=_cmd_confirm)
    p_conf_show = p_conf.add_parser("show")
    p_conf_show.add_argument("id")
    p_conf_show.set_defaults(func=_cmd_confirm)
    p_conf_req = p_conf.add_parser("request", help="run the gate and open an in-review confirmation")
    p_conf_req.add_argument("id")
    p_conf_req.add_argument("--kind", choices=("release", "build"), default="release")
    p_conf_req.add_argument("--release", help="scope.release (kind=release)")
    p_conf_req.add_argument("--paths", nargs="*", help="scope.paths (kind=build)")
    p_conf_req.add_argument("--requester")
    p_conf_req.set_defaults(func=_cmd_confirm)
    p_conf_app = p_conf.add_parser("approve", help="confirm an in-review item and tag it")
    p_conf_app.add_argument("id")
    p_conf_app.add_argument("--approver")
    p_conf_app.set_defaults(func=_cmd_confirm)

    p_exp = sub.add_parser("export", help="bake a static viewer HTML with real data")
    p_exp.add_argument("out", help="output .html path")
    p_exp.add_argument("--path", default="offerings", help="hierarchy subtree to export")
    p_exp.add_argument("--release")
    p_exp.set_defaults(func=_cmd_export)

    p_srv = sub.add_parser("serve", help="run the read-only web app (uvicorn)")
    p_srv.add_argument("--host", default="127.0.0.1")
    p_srv.add_argument("--port", type=int, default=8000)
    p_srv.set_defaults(func=_cmd_serve)

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
