import unittest

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

    def test_no_strong_signal_message_when_all_below_threshold(self):
        weak_subs = dict(AGENT_SUBSCORES)
        for k in weak_subs:
            weak_subs[k] = 1
        c = build_candidate(agent_raw(subscores=weak_subs), "2026-09-13")
        text = render_daily_report("2026-09-13", [c])
        self.assertIn("오늘은 강한 MONEY SIGNAL 없음", text)


if __name__ == "__main__":
    unittest.main()
