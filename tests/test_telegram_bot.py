import unittest
from dataclasses import replace

from scout.models import ValidationError
from scout.pipeline import build_candidate, create_batch
from scout.telegram_bot import (
    apply_decision, build_inline_keyboard, build_send_payload,
    format_approval_message, parse_callback_data, record_approval_requested,
)
from tests.test_pipeline_and_storage import agent_raw
from tests.test_creator import valid_threads


def make_preview_ready_candidate():
    candidate = build_candidate(agent_raw(), "2026-09-13")
    db = {candidate.id: candidate.to_dict()}
    result = create_batch(db, [{"candidate_id": candidate.id, "content": {"threads": valid_threads()}}], "2026-09-13")
    assert not result["errors"], result["errors"]
    return db, result["created"][0]


class MessageFormattingTests(unittest.TestCase):
    def test_format_includes_name_and_scores(self):
        _, candidate = make_preview_ready_candidate()
        text = format_approval_message(candidate)
        self.assertIn(candidate.name, text)
        self.assertIn(str(candidate.score_total), text)
        self.assertIn("게시 승인이 아니라 검토 요청", text)

    def test_format_escapes_html(self):
        _, candidate = make_preview_ready_candidate()
        candidate = replace(candidate, name="<script>alert(1)</script>")
        text = format_approval_message(candidate)
        self.assertNotIn("<script>", text)
        self.assertIn("&lt;script&gt;", text)


class KeyboardTests(unittest.TestCase):
    def test_keyboard_has_four_buttons_with_correct_callback_data(self):
        kb = build_inline_keyboard("agent-economy-example")
        buttons = [b for row in kb["inline_keyboard"] for b in row]
        self.assertEqual(len(buttons), 4)
        callback_data = {b["callback_data"] for b in buttons}
        self.assertEqual(callback_data, {
            "preview:agent-economy-example", "revise:agent-economy-example",
            "approve:agent-economy-example", "discard:agent-economy-example",
        })

    def test_build_send_payload_includes_chat_id_and_keyboard(self):
        _, candidate = make_preview_ready_candidate()
        payload = build_send_payload(candidate, "12345")
        self.assertEqual(payload["chat_id"], "12345")
        self.assertIn("reply_markup", payload)
        self.assertEqual(payload["parse_mode"], "HTML")


class CallbackParsingTests(unittest.TestCase):
    def test_parses_valid_callback(self):
        action, candidate_id = parse_callback_data("approve:agent-economy-example")
        self.assertEqual(action, "approve")
        self.assertEqual(candidate_id, "agent-economy-example")

    def test_candidate_id_with_colon_preserved(self):
        # candidate ids never contain ':' in this codebase, but the parser
        # should still split on the first ':' only, not silently truncate.
        action, candidate_id = parse_callback_data("approve:weird:id")
        self.assertEqual(action, "approve")
        self.assertEqual(candidate_id, "weird:id")

    def test_rejects_unknown_action(self):
        with self.assertRaises(ValidationError):
            parse_callback_data("publish:agent-economy-example")

    def test_rejects_malformed_data(self):
        with self.assertRaises(ValidationError):
            parse_callback_data("no-colon-here")


class ApprovalFlowTests(unittest.TestCase):
    def test_cannot_request_approval_before_preview_ready(self):
        candidate = build_candidate(agent_raw(), "2026-09-13")
        db = {candidate.id: candidate.to_dict()}
        with self.assertRaises(ValidationError):
            record_approval_requested(db, candidate.id)

    def test_request_then_approve(self):
        db, candidate = make_preview_ready_candidate()
        record_approval_requested(db, candidate.id, message_id=42)
        updated = apply_decision(db, candidate.id, "approve", decided_by="bella")
        self.assertEqual(updated.approval["status"], "APPROVED")
        self.assertEqual(updated.approval["decided_by"], "bella")
        self.assertIsNotNone(updated.approval["decided_at"])

    def test_cannot_decide_without_prior_request(self):
        db, candidate = make_preview_ready_candidate()
        with self.assertRaises(ValidationError):
            apply_decision(db, candidate.id, "approve", decided_by="bella")

    def test_preview_action_is_a_noop(self):
        db, candidate = make_preview_ready_candidate()
        record_approval_requested(db, candidate.id)
        updated = apply_decision(db, candidate.id, "preview", decided_by="bella")
        self.assertEqual(updated.approval["status"], "PENDING")

    def test_revise_sets_needs_revision_and_blocks_immediate_re_request(self):
        db, candidate = make_preview_ready_candidate()
        record_approval_requested(db, candidate.id)
        updated = apply_decision(db, candidate.id, "revise", decided_by="bella", notes="hook 약함")
        self.assertEqual(updated.approval["status"], "NEEDS_REVISION")
        self.assertEqual(updated.approval["notes"], "hook 약함")

        # content_status now NEEDS_REVISION -- re-requesting approval without
        # first re-running create/FINAL EDITOR should be refused.
        with self.assertRaises(ValidationError):
            record_approval_requested(db, candidate.id)

    def test_discard_sets_rejected(self):
        db, candidate = make_preview_ready_candidate()
        record_approval_requested(db, candidate.id)
        updated = apply_decision(db, candidate.id, "discard", decided_by="bella")
        self.assertEqual(updated.approval["status"], "REJECTED")

    def test_only_apply_decision_can_reach_approved(self):
        # No code path other than a real recorded decision can set APPROVED.
        db, candidate = make_preview_ready_candidate()
        self.assertNotEqual(candidate.approval.get("status"), "APPROVED")
        record_approval_requested(db, candidate.id)
        self.assertNotEqual(db[candidate.id]["approval"]["status"], "APPROVED")


if __name__ == "__main__":
    unittest.main()
