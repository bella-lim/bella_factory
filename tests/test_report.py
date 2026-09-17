import unittest
from dataclasses import replace

from scout.analyst import build_viral_dna
from scout.money import build_money_analysis
from scout.pipeline import build_candidate
from scout.report import render_daily_report
from tests.test_pipeline_and_storage import agent_raw, scout_raw, AGENT_SUBSCORES


class ReportTests(unittest.TestCase):
    def test_report_includes_top3_and_agent_signal(self):
        c1 = build_candidate(scout_raw(), "2026-09-13")
        c2 = build_candidate(agent_raw(), "2026-09-13")
        text = render_daily_report("2026-09-13", [c1, c2])
        self.assertIn("TOP 3 REPORT", text)
        self.assertIn("AGENT MONEY SIGNAL", text)
        self.assertIn(c1.name, text)

    def test_report_omits_analyst_money_sections_when_unanalyzed(self):
        c1 = build_candidate(agent_raw(), "2026-09-13")
        text = render_daily_report("2026-09-13", [c1])
        self.assertNotIn("VIRAL DNA", text)
        self.assertNotIn("MONEY AGENT REVENUE PATHS", text)

    def test_report_includes_analyst_money_sections_when_analyzed(self):
        c1 = build_candidate(agent_raw(), "2026-09-13")
        dna = build_viral_dna({
            "topic": "t", "hook_principle": "principle", "emotion": "e", "problem": "p",
            "desire": "d", "format": "f", "structure": "s", "comment_trigger": "c",
            "shopping_signal": "sh", "replicability": 60,
        })
        money = build_money_analysis({
            "content_revenue": {"viable": True, "why": "w1"},
            "affiliate": {"viable": True, "why": "w2"},
            "consulting": {"viable": True, "why": "w3"},
        })
        c1 = replace(c1, viral_dna=dna, money_analysis=money)
        text = render_daily_report("2026-09-13", [c1])
        self.assertIn("VIRAL DNA", text)
        self.assertIn("MONEY AGENT REVENUE PATHS", text)
        self.assertIn("MONETIZABLE", text)

    def test_no_strong_signal_message_when_all_below_threshold(self):
        weak_subs = dict(AGENT_SUBSCORES)
        for k in weak_subs:
            weak_subs[k] = 1
        c = build_candidate(agent_raw(subscores=weak_subs), "2026-09-13")
        text = render_daily_report("2026-09-13", [c])
        self.assertIn("오늘은 강한 MONEY SIGNAL 없음", text)


if __name__ == "__main__":
    unittest.main()
