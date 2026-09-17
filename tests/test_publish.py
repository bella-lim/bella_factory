import unittest
from dataclasses import replace

from scout.models import ValidationError
from scout.pipeline import build_candidate, create_batch
from scout.publish import (
    apply_publish_result, build_threads_container_payload,
    build_youtube_metadata, guard_approved, publish_naver_blog,
    publish_youtube_shorts,
)
from scout.telegram_bot import apply_decision, record_approval_requested
from tests.test_pipeline_and_storage import agent_raw
from tests.test_creator import valid_threads, valid_youtube_shorts


def make_approved_candidate():
    candidate = build_candidate(agent_raw(), "2026-09-13")
    db = {candidate.id: candidate.to_dict()}
    result = create_batch(db, [{
        "candidate_id": candidate.id,
        "content": {"threads": valid_threads(), "youtube_shorts": valid_youtube_shorts()},
    }], "2026-09-13")
    assert not result["errors"], result["errors"]
    record_approval_requested(db, candidate.id, message_id=1)
    updated = apply_decision(db, candidate.id, "approve", decided_by="bella")
    return db, updated


class GuardApprovedTests(unittest.TestCase):
    def test_refuses_unapproved_candidate(self):
        candidate = build_candidate(agent_raw(), "2026-09-13")
        with self.assertRaises(ValidationError):
            guard_approved(candidate)

    def test_refuses_pending_approval(self):
        candidate = build_candidate(agent_raw(), "2026-09-13")
        candidate = replace(candidate, approval={"status": "PENDING"})
        with self.assertRaises(ValidationError):
            guard_approved(candidate)

    def test_allows_approved_candidate(self):
        _, candidate = make_approved_candidate()
        guard_approved(candidate)  # should not raise


class ThreadsPayloadTests(unittest.TestCase):
    def test_builds_text_container_payload(self):
        _, candidate = make_approved_candidate()
        payload = build_threads_container_payload(candidate, "info")
        self.assertEqual(payload["media_type"], "TEXT")
        self.assertEqual(payload["text"], candidate.content["threads"]["info"])

    def test_rejects_missing_version(self):
        _, candidate = make_approved_candidate()
        with self.assertRaises(ValidationError):
            build_threads_container_payload(candidate, "nonexistent")


class NaverBlogTests(unittest.TestCase):
    def test_always_not_supported(self):
        _, candidate = make_approved_candidate()
        result = publish_naver_blog(candidate)
        self.assertEqual(result["status"], "NOT_SUPPORTED")
        self.assertIsNone(result["post_id"])
        self.assertIn("No current", result["error"])

    def test_still_refuses_unapproved(self):
        candidate = build_candidate(agent_raw(), "2026-09-13")
        with self.assertRaises(ValidationError):
            publish_naver_blog(candidate)


class YoutubeMetadataTests(unittest.TestCase):
    def test_builds_metadata_from_shorts_content(self):
        _, candidate = make_approved_candidate()
        metadata = build_youtube_metadata(candidate)
        self.assertEqual(metadata["snippet"]["title"], candidate.content["youtube_shorts"]["titles"][0])
        self.assertEqual(metadata["status"]["privacyStatus"], "private")

    def test_missing_video_file_fails_without_network_call(self):
        _, candidate = make_approved_candidate()
        result = publish_youtube_shorts(candidate, "/tmp/does-not-exist.mp4", "cid", "csecret", "rtoken")
        self.assertEqual(result["status"], "FAILED")
        self.assertIn("no video file", result["error"])

    def test_refuses_unapproved_before_checking_video_file(self):
        candidate = build_candidate(agent_raw(), "2026-09-13")
        with self.assertRaises(ValidationError):
            publish_youtube_shorts(candidate, "/tmp/whatever.mp4", "cid", "csecret", "rtoken")


class ApplyPublishResultTests(unittest.TestCase):
    def test_attaches_result_to_candidate(self):
        db, candidate = make_approved_candidate()
        result = {"status": "PUBLISHED", "post_id": "123", "url": "https://example.com/123",
                   "error": None, "published_at": "2026-09-13T00:00:00Z"}
        updated = apply_publish_result(db, candidate.id, "threads", result)
        self.assertEqual(updated.publish_status["threads"]["post_id"], "123")

    def test_missing_candidate_raises(self):
        with self.assertRaises(ValidationError):
            apply_publish_result({}, "nope", "threads", {"status": "PUBLISHED"})


if __name__ == "__main__":
    unittest.main()
