"""Telegram webhook receiver for Approval decisions (spec section 21).

A long-running process (unlike the rest of this CLI, which is one-shot
batch commands) -- run it with `python3 -m scout.cli serve-webhook` on a
host that has a public HTTPS endpoint Telegram can reach (this sandbox
cannot reach api.telegram.org at all, let alone be reached by it, so this
has to run somewhere else; put a reverse proxy with TLS in front of it,
this server itself speaks plain HTTP).

Every request is checked against TELEGRAM_WEBHOOK_SECRET before anything
in the payload is trusted -- Telegram echoes the secret_token configured
via `scout.cli set-webhook` back in the X-Telegram-Bot-Api-Secret-Token
header on every call.
"""
from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from scout import storage
from scout.models import ValidationError
from scout.telegram_bot import (
    answer_callback_query, apply_decision, edit_message_after_decision,
    parse_callback_data, require_env,
)

WEBHOOK_PATH = "/telegram-webhook"


class TelegramWebhookHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        sys.stderr.write(f"[webhook] {self.address_string()} - {fmt % args}\n")

    def _reject(self, code: int, reason: str) -> None:
        self.send_response(code)
        self.end_headers()
        sys.stderr.write(f"[webhook] rejected: {reason}\n")

    def do_POST(self) -> None:  # noqa: N802 (BaseHTTPRequestHandler naming)
        if self.path != WEBHOOK_PATH:
            self._reject(404, f"unknown path {self.path!r}")
            return

        expected_secret = os.environ.get("TELEGRAM_WEBHOOK_SECRET")
        received_secret = self.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if not expected_secret or received_secret != expected_secret:
            self._reject(401, "missing/invalid X-Telegram-Bot-Api-Secret-Token")
            return

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b""

        # Always ack 200 immediately once auth passes -- Telegram retries
        # aggressively on non-2xx and we don't want a retry storm from a
        # slow downstream (Telegram API / disk) turning into duplicate work.
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b"{}")

        try:
            self._handle_update(json.loads(body.decode("utf-8")))
        except Exception as e:  # noqa: BLE001 -- log and move on, already acked
            sys.stderr.write(f"[webhook] error handling update: {e}\n")

    def _handle_update(self, update: dict) -> None:
        callback_query = update.get("callback_query")
        if not callback_query:
            return  # not an approval button press -- ignore silently

        data = callback_query.get("data", "")
        try:
            action, candidate_id = parse_callback_data(data)
        except ValidationError as e:
            sys.stderr.write(f"[webhook] {e}\n")
            return

        decided_by = (callback_query.get("from") or {}).get("username") or str(
            (callback_query.get("from") or {}).get("id", "unknown")
        )

        db = storage.load_db()
        try:
            candidate = apply_decision(db, candidate_id, action, decided_by)
        except ValidationError as e:
            sys.stderr.write(f"[webhook] {e}\n")
            return
        storage.save_db(db)

        bot_token = require_env("TELEGRAM_BOT_TOKEN")
        chat_id = callback_query["message"]["chat"]["id"]
        message_id = callback_query["message"]["message_id"]
        answer_callback_query(callback_query["id"], bot_token, text=f"{action} 반영됨")
        edit_message_after_decision(chat_id, message_id, candidate, bot_token)


def run_server(port: int = 8443) -> None:
    require_env("TELEGRAM_WEBHOOK_SECRET")
    require_env("TELEGRAM_BOT_TOKEN")
    server = ThreadingHTTPServer(("0.0.0.0", port), TelegramWebhookHandler)
    sys.stderr.write(f"[webhook] listening on :{port}{WEBHOOK_PATH}\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
