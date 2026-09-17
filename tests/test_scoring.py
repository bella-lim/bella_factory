import unittest

from scout.scoring import (
    score_scout, scout_tier, score_agent_money, agent_money_tier, is_product_opportunity,
)


class ScoutScoreTests(unittest.TestCase):
    def test_full_score(self):
        subs = {
            "rising_signal": 25, "source_diversity": 20, "platform_spread": 15,
            "novelty": 15, "korean_gap": 15, "monetization": 10,
        }
        self.assertEqual(score_scout(subs), 100)
        self.assertEqual(scout_tier(100), "FIRST MOVER")

    def test_tiers(self):
        self.assertEqual(scout_tier(95), "FIRST MOVER")
        self.assertEqual(scout_tier(85), "CREATE NOW")
        self.assertEqual(scout_tier(75), "WATCH")
        self.assertEqual(scout_tier(50), "ARCHIVE")

    def test_missing_keys_default_zero(self):
        self.assertEqual(score_scout({}), 0)


class AgentMoneyScoreTests(unittest.TestCase):
    def test_full_score(self):
        subs = {
            "problem_solving": 15, "agent_utility": 10, "hermes_compatibility": 10,
            "early_market_signal": 10, "korean_gap": 10, "affiliate_potential": 10,
            "service_potential": 15, "skill_template_potential": 10, "content_potential": 10,
        }
        self.assertEqual(score_agent_money(subs), 100)
        self.assertEqual(agent_money_tier(100), "💎 BUILD BUSINESS")

    def test_tiers(self):
        self.assertEqual(agent_money_tier(92), "💎 BUILD BUSINESS")
        self.assertEqual(agent_money_tier(82), "💰 TEST NOW")
        self.assertEqual(agent_money_tier(72), "👀 WATCH")
        self.assertEqual(agent_money_tier(40), "ARCHIVE")


class ProductOpportunityTests(unittest.TestCase):
    def test_promotes_when_all_conditions_met(self):
        self.assertTrue(is_product_opportunity(
            "AGENT_ECONOMY", 92, "HIGH", "YES", True, "UNKNOWN",
        ))

    def test_rejects_non_agent_economy(self):
        self.assertFalse(is_product_opportunity(
            "AI_TREND", 95, "HIGH", "YES", True, True,
        ))

    def test_rejects_without_gap(self):
        self.assertFalse(is_product_opportunity(
            "AGENT_ECONOMY", 95, "HIGH", "YES", False, "UNKNOWN",
        ))

    def test_rejects_low_score(self):
        self.assertFalse(is_product_opportunity(
            "AGENT_ECONOMY", 85, "HIGH", "YES", True, True,
        ))


if __name__ == "__main__":
    unittest.main()
