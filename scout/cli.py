"""CLI entry point.

    python3 -m scout.cli ingest           <candidates.json> [--date YYYY-MM-DD]
    python3 -m scout.cli analyze          <analysis.json>    [--date YYYY-MM-DD]
    python3 -m scout.cli create           <content.json>     [--date YYYY-MM-DD]
    python3 -m scout.cli request-approval <candidate_id>
    python3 -m scout.cli record-decision  <candidate_id> <preview|revise|approve|discard> [--by NAME] [--notes TEXT]
    python3 -m scout.cli set-webhook      <public_https_url>
    python3 -m scout.cli serve-webhook    [--port 8443]
    python3 -m scout.cli report           [--date YYYY-MM-DD] [--out path]
    python3 -m scout.cli list             [--track TRACK]

request-approval / set-webhook / serve-webhook need TELEGRAM_BOT_TOKEN (and
TELEGRAM_CHAT_ID / TELEGRAM_WEBHOOK_SECRET respectively) set in the
environment -- see .env.example. They reach api.telegram.org, which this
sandbox's egress policy blocks; run them from an environment with network
access to Telegram.
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


def cmd_request_approval(args: argparse.Namespace) -> int:
    from scout.telegram_bot import require_env, send_approval_request

    db = storage.load_db(args.db)
    candidate = storage.get(db, args.candidate_id)
    if candidate is None:
        print(f"! candidate {args.candidate_id!r} not found", file=sys.stderr)
        return 1

    try:
        bot_token = require_env("TELEGRAM_BOT_TOKEN")
        chat_id = require_env("TELEGRAM_CHAT_ID")
        updated = send_approval_request(candidate, db, bot_token, chat_id)
    except Exception as e:  # noqa: BLE001 -- surface any failure (validation, network, HTTP) to the operator
        print(f"! request-approval failed: {e}", file=sys.stderr)
        return 1

    storage.save_db(db, args.db)
    print(f"Approval requested: {updated.name} -> message_id={updated.approval.get('message_id')}")
    return 0


def cmd_record_decision(args: argparse.Namespace) -> int:
    from scout.telegram_bot import apply_decision
    from scout.models import ValidationError

    db = storage.load_db(args.db)
    try:
        updated = apply_decision(db, args.candidate_id, args.action, args.by, args.notes or "")
    except ValidationError as e:
        print(f"! {e}", file=sys.stderr)
        return 1

    storage.save_db(db, args.db)
    print(f"Decision recorded: {updated.name} -> {updated.approval.get('status')} (by {args.by})")
    return 0


def cmd_set_webhook(args: argparse.Namespace) -> int:
    from scout.telegram_bot import call_telegram_api, require_env

    bot_token = require_env("TELEGRAM_BOT_TOKEN")
    secret = require_env("TELEGRAM_WEBHOOK_SECRET")
    from scout.webhook_server import WEBHOOK_PATH

    url = args.public_url.rstrip("/") + WEBHOOK_PATH
    response = call_telegram_api("setWebhook", {"url": url, "secret_token": secret}, bot_token)
    print(json.dumps(response, ensure_ascii=False, indent=2))
    return 0 if response.get("ok") else 1


def cmd_serve_webhook(args: argparse.Namespace) -> int:
    from scout.webhook_server import run_server

    run_server(args.port)
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

    p_request_approval = sub.add_parser("request-approval")
    p_request_approval.add_argument("candidate_id")
    p_request_approval.set_defaults(func=cmd_request_approval)

    p_record_decision = sub.add_parser("record-decision")
    p_record_decision.add_argument("candidate_id")
    p_record_decision.add_argument("action", choices=["preview", "revise", "approve", "discard"])
    p_record_decision.add_argument("--by", default="unknown")
    p_record_decision.add_argument("--notes")
    p_record_decision.set_defaults(func=cmd_record_decision)

    p_set_webhook = sub.add_parser("set-webhook")
    p_set_webhook.add_argument("public_url")
    p_set_webhook.set_defaults(func=cmd_set_webhook)

    p_serve_webhook = sub.add_parser("serve-webhook")
    p_serve_webhook.add_argument("--port", type=int, default=8443)
    p_serve_webhook.set_defaults(func=cmd_serve_webhook)

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
