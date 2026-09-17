import unittest

from scout.analyst import build_viral_dna
from scout.models import ValidationError

VALID_DNA = dict(
    topic="MCP 서버 수익화",
    hook_principle="이미 잘 쓰는 도구인데 그걸로 돈 버는 방법만 안 알려진 정보 격차를 드러낸다",
    emotion="놓치고 있었다는 조바심",
    problem="설명 콘텐츠는 많은데 수익화 콘텐츠가 없다",
    desire="남들보다 먼저 부수입 경로를 확보하고 싶다",
    format="번호 단락 정보성 포스트",
    structure="통념 -> 반박근거 -> 실제기준 -> 적용대상 -> 예외",
    comment_trigger="스킬로 만들 만한 반복 업무를 묻는 질문",
    shopping_signal="없음 (정보성 콘텐츠, 직접 판매 없음)",
    replicability=75,
)


class ViralDnaTests(unittest.TestCase):
    def test_valid_input_builds_record(self):
        dna = build_viral_dna(VALID_DNA)
        self.assertEqual(dna["topic"], VALID_DNA["topic"])
        self.assertEqual(dna["replicability"], 75)

    def test_rejects_missing_field(self):
        bad = dict(VALID_DNA)
        del bad["emotion"]
        with self.assertRaises(ValidationError):
            build_viral_dna(bad)

    def test_rejects_out_of_range_replicability(self):
        bad = dict(VALID_DNA, replicability=150)
        with self.assertRaises(ValidationError):
            build_viral_dna(bad)

    def test_rejects_verbatim_copy_of_source_hook(self):
        bad = dict(VALID_DNA)
        bad["source_hook_example"] = bad["hook_principle"]
        with self.assertRaises(ValidationError):
            build_viral_dna(bad)

    def test_allows_source_hook_when_principle_is_distilled(self):
        good = dict(VALID_DNA)
        good["source_hook_example"] = "MCP 서버 하나 만들면 돈이 된다. 진짜로."
        dna = build_viral_dna(good)
        self.assertEqual(dna["hook_principle"], VALID_DNA["hook_principle"])


if __name__ == "__main__":
    unittest.main()
