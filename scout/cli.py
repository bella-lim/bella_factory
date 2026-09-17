"""CLI entry point.

    python3 -m scout.cli ingest  <candidates.json> [--date YYYY-MM-DD]
    python3 -m scout.cli analyze <analysis.json>    [--date YYYY-MM-DD]
    python3 -m scout.cli create  <content.json>     [--date YYYY-MM-DD]
    python3 -m scout.cli report  [--date YYYY-MM-DD] [--out path]
    python3 -m scout.cli list    [--track TRACK]
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys

from scout import storage, report
from scout.pipeline import ingest_batch, analyze_batch, create_batch


def _today() -> str:
    return datetime.date.today().isoformat()


def cmd_ingest(args: argparse.Namespace) -> int:
    with open(args.file, "r", encoding="utf-8") as f:
        raw_items = json.load(f)

    db = storage.load_db(args.db)
    result = ingest_batch(db, raw_items, args.date or _today())
    storage.save_db(db, args.db)

    print(f"Created: {len(result['created'])}")
    for c in result["created"]:
        print(f"  + [{c.track}] {c.name} -> {c.score_total} ({c.score_tier})")
    print(f"Updated (deduped): {len(result['updated'])}")
    for c in result["updated"]:
        print(f"  ~ [{c.track}] {c.name} -> {c.score_total} ({c.score_tier})")
    if result["errors"]:
        print(f"Errors: {len(result['errors'])}", file=sys.stderr)
        for e in result["errors"]:
            print(f"  ! {e['name']}: {e['error']}", file=sys.stderr)
        return 1
    return 0


def cmd_analyze(args: argparse.Namespace) -> int:
    with open(args.file, "r", encoding="utf-8") as f:
        analysis_items = json.load(f)

    db = storage.load_db(args.db)
    result = analyze_batch(db, analysis_items, args.date or _today())
    storage.save_db(db, args.db)

    print(f"Analyzed: {len(result['analyzed'])}")
    for c in result["analyzed"]:
        money = c.money_analysis.get("classification", "N/A")
        print(f"  * [{c.track}] {c.name} -> money={money}, ladder={c.money_analysis.get('product_ladder_level')}")
    if result["errors"]:
        print(f"Errors: {len(result['errors'])}", file=sys.stderr)
        for e in result["errors"]:
            print(f"  ! {e['candidate_id']}: {e['error']}", file=sys.stderr)
        return 1
    return 0


def cmd_create(args: argparse.Namespace) -> int:
    with open(args.file, "r", encoding="utf-8") as f:
        content_items = json.load(f)

    db = storage.load_db(args.db)
    result = create_batch(db, content_items, args.date or _today())
    storage.save_db(db, args.db)

    print(f"Created content: {len(result['created'])}")
    for c in result["created"]:
        print(f"  * [{c.track}] {c.name} -> editor={c.content_status} (issues={c.editor_review['issue_count']})")
    if result["errors"]:
        print(f"Errors: {len(result['errors'])}", file=sys.stderr)
        for e in result["errors"]:
            print(f"  ! {e['candidate_id']}: {e['error']}", file=sys.stderr)
        return 1
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    date_str = args.date or _today()
    db = storage.load_db(args.db)
    candidates = storage.seen_on(db, date_str)
    text = report.render_daily_report(date_str, candidates)

    out_path = args.out or os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "reports", f"{date_str}.md"
    )
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text)

    print(text)
    print(f"\n[saved to {out_path}]", file=sys.stderr)
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    db = storage.load_db(args.db)
    candidates = storage.get_all(db)
    if args.track:
        candidates = [c for c in candidates if c.track == args.track]
    candidates.sort(key=lambda c: c.score_total, reverse=True)
    for c in candidates:
        print(f"{c.id:45s} {c.track:14s} {c.score_total:3d} {c.score_tier:16s} {c.stage:10s} {c.url}")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="scout")
    parser.add_argument("--db", default=storage.DEFAULT_DB_PATH)
    sub = parser.add_subparsers(dest="command", required=True)

    p_ingest = sub.add_parser("ingest")
    p_ingest.add_argument("file")
    p_ingest.add_argument("--date")
    p_ingest.set_defaults(func=cmd_ingest)

    p_analyze = sub.add_parser("analyze")
    p_analyze.add_argument("file")
    p_analyze.add_argument("--date")
    p_analyze.set_defaults(func=cmd_analyze)

    p_create = sub.add_parser("create")
    p_create.add_argument("file")
    p_create.add_argument("--date")
    p_create.set_defaults(func=cmd_create)

    p_report = sub.add_parser("report")
    p_report.add_argument("--date")
    p_report.add_argument("--out")
    p_report.set_defaults(func=cmd_report)

    p_list = sub.add_parser("list")
    p_list.add_argument("--track")
    p_list.set_defaults(func=cmd_list)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
