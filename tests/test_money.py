import unittest

from scout.money import build_money_analysis
from scout.models import ValidationError


def paths(**overrides):
    base = {
        "content_revenue": {"viable": True, "why": "스킬 수익화 정보성 콘텐츠 자체가 조회수를 만든다"},
        "affiliate": {"viable": True, "why": "관련 툴/강의 제휴 링크 삽입 가능"},
        "consulting": {"viable": True, "why": "기업 대상 맞춤 스킬 제작대행 수요 존재"},
        "micro_saas": {"viable": False, "why": "아직 반복 수요 검증 안 됨"},
        "skill": {"viable": "UNKNOWN", "why": ""},
    }
    base.update(overrides)
    return base


class MoneyAgentTests(unittest.TestCase):
    def test_three_viable_paths_is_monetizable(self):
        result = build_money_analysis(paths())
        self.assertEqual(result["classification"], "MONETIZABLE")
        self.assertEqual(result["viable_count"], 3)

    def test_fewer_than_three_is_traffic_content(self):
        weak = paths(consulting={"viable": False, "why": "수요 근거 부족"})
        result = build_money_analysis(weak)
        self.assertEqual(result["classification"], "TRAFFIC CONTENT")
        self.assertIsNone(result["product_ladder_level"])

    def test_viable_path_without_reason_is_rejected(self):
        bad = paths(affiliate={"viable": True, "why": ""})
        with self.assertRaises(ValidationError):
            build_money_analysis(bad)

    def test_unknown_path_key_is_rejected(self):
        bad = paths(**{"nft_drop": {"viable": True, "why": "억지 수익모델"}})
        with self.assertRaises(ValidationError):
            build_money_analysis(bad)

    def test_ladder_level_reflects_highest_unlocked_rung(self):
        result = build_money_analysis(paths())
        # content_revenue + affiliate (L2) + consulting (L3) viable -> L3
        self.assertEqual(result["product_ladder_level"], 3)
        self.assertIn("LEVEL 1", result["next_action"])

    def test_micro_saas_alone_still_recommends_starting_at_level_1(self):
        only_saas = {
            "micro_saas": {"viable": True, "why": "반복 수요 확인됨"},
            "content_revenue": {"viable": True, "why": "콘텐츠 자체 수요 있음"},
            "affiliate": {"viable": True, "why": "제휴 가능"},
        }
        result = build_money_analysis(only_saas)
        self.assertEqual(result["product_ladder_level"], 4)
        self.assertIn("LEVEL 1", result["next_action"])
        self.assertIn("처음부터 SaaS로 가지 않고", result["next_action"])


if __name__ == "__main__":
    unittest.main()
