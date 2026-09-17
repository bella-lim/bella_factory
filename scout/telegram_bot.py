"""Telegram Approval (spec section 21).

Publish approval is always a human action taken on a real Telegram message
-- nothing in this module can mark a candidate APPROVED on its own. The
message/keyboard builders and the decision-applying logic are pure
functions with no network dependency, so they're fully unit-testable; only
`call_telegram_api` and the functions built on it actually reach the
network (blocked from this sandbox's egress policy -- see README -- so
sending has to be exercised from an environment where api.telegram.org is
reachable).

Required environment variables (never hardcode these, never commit a real
value -- see .env.example):
    TELEGRAM_BOT_TOKEN     bot token from @BotFather
    TELEGRAM_CHAT_ID       the chat/user id approval requests are sent to
    TELEGRAM_WEBHOOK_SECRET  shared secret Telegram echoes back in the
                             X-Telegram-Bot-Api-Secret-Token header, used
                             by webhook_server.py to reject spoofed calls
"""
from __future__ import annotations

import datetime
import json
import os
import urllib.error
import urllib.request

from scout.models import ACTION_TO_STATUS, APPROVAL_ACTIONS, ValidationError

TELEGRAM_API_ROOT = "https://api.telegram.org"

BUTTON_LABELS = {
    "preview": "👀 미리보기",
    "revise": "✏️ 수정",
    "approve": "✅ 게시 승인",
    "discard": "🗑️ 폐기",
}


def _escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def format_approval_message(candidate) -> str:
    """Section 21 preview message: enough to decide, not the full drafts."""
    lines = [
        f"<b>{_escape_html(candidate.name)}</b>",
        f"트랙: {candidate.track} / {candidate.category}",
        f"점수: {candidate.score_total} ({candidate.score_tier})",
    ]

    if candidate.money_analysis:
        m = candidate.money_analysis
        lines.append(f"MONEY AGENT: {m['classification']} (LEVEL {m.get('product_ladder_level') or '-'})")

    if candidate.editor_review:
        r = candidate.editor_review
        lines.append(f"FINAL EDITOR: {r['status']} (이슈 {r['issue_count']}건)")

    threads = (candidate.content or {}).get("threads")
    if threads and "info" in threads:
        excerpt = threads["info"][:300]
        lines.append("")
        lines.append("--- Threads (정보형) 미리보기 ---")
        lines.append(_escape_html(excerpt))

    lines.append("")
    lines.append(f"Sources: {' | '.join(candidate.sources[:3])}")
    lines.append("")
    lines.append("이 요청은 게시 승인이 아니라 검토 요청입니다. 버튼으로 결정해 주세요.")

    return "\n".join(lines)


def build_inline_keyboard(candidate_id: str) -> dict:
    def button(action):
        return {"text": BUTTON_LABELS[action], "callback_data": f"{action}:{candidate_id}"}

    return {
        "inline_keyboard": [
            [button("preview"), button("revise")],
            [button("approve"), button("discard")],
        ]
    }


def build_send_payload(candidate, chat_id: str) -> dict:
    return {
        "chat_id": chat_id,
        "text": format_approval_message(candidate),
        "parse_mode": "HTML",
        "reply_markup": build_inline_keyboard(candidate.id),
    }


def parse_callback_data(data: str) -> tuple[str, str]:
    if ":" not in data:
        raise ValidationError(f"malformed callback_data (expected 'action:candidate_id'): {data!r}")
    action, candidate_id = data.split(":", 1)
    if action not in APPROVAL_ACTIONS:
        raise ValidationError(f"unknown approval action {action!r} (must be one of {sorted(APPROVAL_ACTIONS)})")
    if not candidate_id:
        raise ValidationError("callback_data has an empty candidate_id")
    return action, candidate_id


def record_approval_requested(db: dict, candidate_id: str, message_id=None) -> "Candidate":
    from dataclasses import replace
    from scout.storage import get, upsert

    candidate = get(db, candidate_id)
    if candidate is None:
        raise ValidationError(f"candidate {candidate_id!r} not found in database")
    if candidate.content_status != "PREVIEW_READY":
        raise ValidationError(
            f"candidate {candidate_id!r} has content_status={candidate.content_status!r}, "
            "must be PREVIEW_READY (passed FINAL EDITOR) before requesting approval"
        )

    updated = replace(candidate, approval={
        "status": "PENDING",
        "requested_at": _now(),
        "message_id": message_id,
        "decided_at": None,
        "decided_by": None,
        "notes": "",
    })
    upsert(db, updated)
    return updated


def apply_decision(db: dict, candidate_id: str, action: str, decided_by: str, notes: str = "") -> "Candidate":
    """The only function that may move a candidate to APPROVED, and only in
    response to a real decision (an action string), never invented here."""
    from dataclasses import replace
    from scout.storage import get, upsert

    if action not in APPROVAL_ACTIONS:
        raise ValidationError(f"unknown approval action {action!r} (must be one of {sorted(APPROVAL_ACTIONS)})")

    candidate = get(db, candidate_id)
    if candidate is None:
        raise ValidationError(f"candidate {candidate_id!r} not found in database")
    if not candidate.approval or candidate.approval.get("status") is None:
        raise ValidationError(
            f"candidate {candidate_id!r} has no pending approval request -- "
            "call record_approval_requested / `scout.cli request-approval` first"
        )

    if action == "preview":
        # 미리보기 is a no-op decision -- still PENDING, just acknowledges.
        return candidate

    new_status = ACTION_TO_STATUS[action]
    updated_approval = dict(candidate.approval)
    updated_approval.update({
        "status": new_status,
        "decided_at": _now(),
        "decided_by": decided_by,
        "notes": notes,
    })
    updated = replace(
        candidate,
        approval=updated_approval,
        content_status=new_status if new_status != "APPROVED" else candidate.content_status,
    )
    upsert(db, updated)
    return updated


def call_telegram_api(method: str, payload: dict, bot_token: str) -> dict:
    """Thin network wrapper. Blocked from this sandbox's egress policy --
    run from an environment where api.telegram.org is reachable."""
    url = f"{TELEGRAM_API_ROOT}/bot{bot_token}/{method}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Telegram API {method} failed: HTTP {e.code}: {body}") from e


def send_approval_request(candidate, db: dict, bot_token: str, chat_id: str) -> "Candidate":
    payload = build_send_payload(candidate, chat_id)
    response = call_telegram_api("sendMessage", payload, bot_token)
    message_id = response.get("result", {}).get("message_id")
    return record_approval_requested(db, candidate.id, message_id=message_id)


def answer_callback_query(callback_query_id: str, bot_token: str, text: str = "") -> dict:
    return call_telegram_api("answerCallbackQuery", {"callback_query_id": callback_query_id, "text": text}, bot_token)


def edit_message_after_decision(chat_id: str, message_id: int, candidate, bot_token: str) -> dict:
    status_text = {
        "APPROVED": "✅ 게시 승인됨 (실제 게시는 별도 PUBLISH 단계에서 처리 -- 이 시스템은 자동 게시하지 않음)",
        "NEEDS_REVISION": "✏️ 수정 요청됨",
        "REJECTED": "🗑️ 폐기됨",
        "PENDING": "⏳ 검토 대기 중",
    }.get(candidate.approval.get("status"), "")
    text = format_approval_message(candidate) + f"\n\n<b>{status_text}</b>"
    return call_telegram_api(
        "editMessageText",
        {"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "HTML"},
        bot_token,
    )


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is not set -- see .env.example for required Telegram credentials")
    return value
