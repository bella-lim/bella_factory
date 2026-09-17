import unittest
from dataclasses import replace

from scout.editor import run_final_editor
from scout.money import build_money_analysis
from scout.pipeline import build_candidate
from tests.test_pipeline_and_storage import agent_raw
from tests.test_creator import valid_threads


class FinalEditorTests(unittest.TestCase):
    def setUp(self):
        self.candidate = build_candidate(agent_raw(), "2026-09-13")

    def test_clean_content_passes(self):
        c = replace(self.candidate, content={"threads": valid_threads()})
        review = run_final_editor(c)
        self.assertEqual(review["status"], "PREVIEW_READY")
        self.assertEqual(review["issue_count"], 0)

    def test_no_sources_fails(self):
        c = replace(self.candidate, sources=[], content={"threads": valid_threads()})
        review = run_final_editor(c)
        self.assertEqual(review["status"], "NEEDS_REVISION")
        self.assertTrue(review["findings"]["sources"])

    def test_exaggeration_phrase_is_flagged(self):
        threads = valid_threads()
        threads["info"] = "이거 하면 무조건 인생이 바뀝니다"
        c = replace(self.candidate, content={"threads": threads})
        review = run_final_editor(c)
        self.assertTrue(review["findings"]["exaggeration"])

    def test_ai_style_phrase_is_flagged(self):
        threads = valid_threads()
        threads["info"] = "안녕하세요, 오늘은 스킬 수익화에 대해 알아보겠습니다"
        c = replace(self.candidate, content={"threads": threads})
        review = run_final_editor(c)
        self.assertTrue(review["findings"]["ai_style"])

    def test_near_duplicate_threads_versions_are_flagged(self):
        same_text = "1/ 완전히 똑같은 문장을 세 버전에 다 넣었다\n\n2/ 그래서 사실상 중복이다"
        threads = {"info": same_text, "experience": same_text, "shopping": same_text}
        c = replace(self.candidate, content={"threads": threads})
        review = run_final_editor(c)
        self.assertTrue(review["findings"]["duplication"])

    def test_missing_ad_disclosure_is_flagged_when_affiliate_viable(self):
        money = build_money_analysis({
            "content_revenue": {"viable": True, "why": "w1"},
            "affiliate": {"viable": True, "why": "w2"},
            "consulting": {"viable": True, "why": "w3"},
        })
        c = replace(self.candidate, money_analysis=money, content={"threads": valid_threads()})
        review = run_final_editor(c)
        self.assertTrue(review["findings"]["ad_disclosure"])

    def test_ad_disclosure_present_passes(self):
        money = build_money_analysis({
            "content_revenue": {"viable": True, "why": "w1"},
            "affiliate": {"viable": True, "why": "w2"},
            "consulting": {"viable": True, "why": "w3"},
        })
        threads = valid_threads()
        threads["info"] += " (이 글에는 제휴 링크가 포함될 수 있습니다)"
        c = replace(self.candidate, money_analysis=money, content={"threads": threads})
        review = run_final_editor(c)
        self.assertFalse(review["findings"]["ad_disclosure"])

    def test_agent_economy_missing_security_notes_is_flagged(self):
        c = replace(self.candidate, security_notes="", content={"threads": valid_threads()})
        review = run_final_editor(c)
        self.assertTrue(review["findings"]["agent_economy_security"])

    def test_never_sets_publish_approval(self):
        c = replace(self.candidate, content={"threads": valid_threads()})
        review = run_final_editor(c)
        self.assertNotIn("approved", review)
        self.assertIn("게시 승인", review["note"])


if __name__ == "__main__":
    unittest.main()
