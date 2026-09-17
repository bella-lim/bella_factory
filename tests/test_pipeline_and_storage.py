import tempfile
import os
import unittest

from scout import storage
from scout.models import ValidationError
from scout.pipeline import build_candidate, ingest_batch, analyze_batch


AGENT_SUBSCORES = {
    "problem_solving": 15, "agent_utility": 9, "hermes_compatibility": 8,
    "early_market_signal": 9, "korean_gap": 10, "affiliate_potential": 8,
    "service_potential": 13, "skill_template_potential": 9, "content_potential": 8,
}

SCOUT_SUBSCORES = {
    "rising_signal": 22, "source_diversity": 18, "platform_spread": 12,
    "novelty": 13, "korean_gap": 13, "monetization": 8,
}


def agent_raw(**overrides):
    raw = dict(
        track="AGENT_ECONOMY", name="Example MCP Server", category="MCP",
        url="https://github.com/example/example-mcp",
        sources=["https://github.com/example/example-mcp", "https://news.ycombinator.com/item?id=1"],
        stage="EMERGING", hermes_compatible="TEST", korean_gap=True, money_gap=True,
        problem_strength="HIGH", business_models=["Affiliate", "Skill", "Agent Setup Service"],
        subscores=AGENT_SUBSCORES,
    )
    raw.update(overrides)
    return raw


def scout_raw(**overrides):
    raw = dict(
        track="AI_TREND", name="Example AI Trend", category="AI_TREND",
        url="https://example.com/trend",
        sources=["https://example.com/trend", "https://reddit.com/r/x/y"],
        stage="EMERGING", hermes_compatible="TEST", korean_gap=False, money_gap="UNKNOWN",
        subscores=SCOUT_SUBSCORES,
    )
    raw.update(overrides)
    return raw


class BuildCandidateTests(unittest.TestCase):
    def test_valid_agent_candidate(self):
        c = build_candidate(agent_raw(), "2026-09-13")
        self.assertEqual(c.score_total, sum(AGENT_SUBSCORES.values()))
        self.assertEqual(c.id, "agent-economy-example-mcp-server")

    def test_rejects_fabricated_url(self):
        with self.assertRaises(ValidationError):
            build_candidate(agent_raw(url="not-a-url"), "2026-09-13")

    def test_rejects_missing_sources(self):
        with self.assertRaises(ValidationError):
            build_candidate(agent_raw(sources=[]), "2026-09-13")

    def test_rejects_bad_category(self):
        with self.assertRaises(ValidationError):
            build_candidate(agent_raw(category="NOT_A_CATEGORY"), "2026-09-13")

    def test_rejects_incomplete_subscores(self):
        bad = dict(AGENT_SUBSCORES)
        del bad["problem_solving"]
        with self.assertRaises(ValidationError):
            build_candidate(agent_raw(subscores=bad), "2026-09-13")


class IngestBatchTests(unittest.TestCase):
    def test_new_and_duplicate_handling(self):
        db = {}
        result = ingest_batch(db, [agent_raw(), scout_raw()], "2026-09-13")
        self.assertEqual(len(result["created"]), 2)
        self.assertEqual(len(result["updated"]), 0)

        # Re-ingest the same agent candidate a day later -> should update, not duplicate.
        result2 = ingest_batch(db, [agent_raw(stage="BREAKOUT")], "2026-09-14")
        self.assertEqual(len(result2["created"]), 0)
        self.assertEqual(len(result2["updated"]), 1)
        self.assertEqual(result2["updated"][0].stage, "BREAKOUT")
        self.assertEqual(len(db), 2)

    def test_errors_collected_not_raised(self):
        db = {}
        result = ingest_batch(db, [agent_raw(url="bad")], "2026-09-13")
        self.assertEqual(len(result["errors"]), 1)
        self.assertEqual(len(db), 0)


class AnalyzeBatchTests(unittest.TestCase):
    def test_analyze_attaches_viral_dna_and_money_to_existing_candidate(self):
        db = {}
        ingest_batch(db, [agent_raw()], "2026-09-13")
        candidate_id = "agent-economy-example-mcp-server"

        analysis = [{
            "candidate_id": candidate_id,
            "viral_dna": {
                "topic": "MCP 서버 수익화",
                "hook_principle": "정보 격차 자체가 후크",
                "emotion": "조바심", "problem": "가이드 없음", "desire": "선점하고 싶다",
                "format": "정보성", "structure": "통념->반박->기준->대상->예외",
                "comment_trigger": "경험 공유 유도", "shopping_signal": "없음",
                "replicability": 70,
            },
            "money_paths": {
                "content_revenue": {"viable": True, "why": "정보 격차 콘텐츠 자체 수요"},
                "affiliate": {"viable": True, "why": "관련 툴 제휴 가능"},
                "consulting": {"viable": True, "why": "기업 대상 대행 수요"},
            },
        }]
        result = analyze_batch(db, analysis, "2026-09-14")
        self.assertEqual(len(result["analyzed"]), 1)
        self.assertEqual(len(result["errors"]), 0)

        stored = storage.get(db, candidate_id)
        self.assertEqual(stored.viral_dna["topic"], "MCP 서버 수익화")
        self.assertEqual(stored.money_analysis["classification"], "MONETIZABLE")
        self.assertEqual(stored.last_checked, "2026-09-14")

    def test_analyze_missing_candidate_is_reported_as_error(self):
        db = {}
        result = analyze_batch(db, [{"candidate_id": "does-not-exist", "viral_dna": {}}], "2026-09-14")
        self.assertEqual(len(result["errors"]), 1)


class StorageTests(unittest.TestCase):
    def test_save_and_load_roundtrip(self):
        db = {}
        ingest_batch(db, [agent_raw()], "2026-09-13")
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "candidates.json")
            storage.save_db(db, path)
            loaded = storage.load_db(path)
            self.assertEqual(set(loaded.keys()), set(db.keys()))
            candidates = storage.get_all(loaded)
            self.assertEqual(candidates[0].name, "Example MCP Server")

    def test_seen_on_filters_by_date(self):
        db = {}
        ingest_batch(db, [agent_raw()], "2026-09-13")
        self.assertEqual(len(storage.seen_on(db, "2026-09-13")), 1)
        self.assertEqual(len(storage.seen_on(db, "2026-09-14")), 0)


if __name__ == "__main__":
    unittest.main()
