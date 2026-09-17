import unittest

from scout.creator import build_content
from scout.models import ValidationError, THREADS_MAX_CHARS


def valid_threads():
    return {
        "info": "1/ 스킬은 이미 190만 개 쌓였다\n\n2/ 근데 파는 법은 안 보였다",
        "experience": "1/ 3번 검색해도 답이 안 나왔다\n\n2/ 결국 직접 정리하기로 했다",
        "shopping": "1/ 스킬 제작에 필요한 도구부터 정리했다\n\n2/ 링크는 아래에 남긴다",
    }


def valid_naver_blog():
    return {
        "titles": ["제목1", "제목2", "제목3"],
        "main_keyword": "메인키워드",
        "sub_keywords": ["서브1", "서브2"],
        "hook": "훅", "problem": "문제", "situation": "상황", "cause": "원인",
        "solution": "해결", "selection_criteria": "선택기준", "product_service": "상품/서비스",
        "faq": [{"q": "질문1", "a": "답변1"}],
        "closing": "마무리",
    }


def valid_youtube_shorts():
    return {
        "hook": "0-3초 훅", "problem": "3-15초 문제", "discovery_solution": "15-40초 해결",
        "core": "40-52초 핵심", "cta": "52-60초 CTA",
        "titles": ["제목1", "제목2", "제목3", "제목4", "제목5"],
        "thumbnail_texts": ["썸네일1", "썸네일2", "썸네일3"],
        "broll": "B-roll 설명", "subtitles": "자막", "video_prompt": "영상 생성 프롬프트",
        "description": "설명란", "tags": ["태그1", "태그2"],
    }


class ThreadsValidationTests(unittest.TestCase):
    def test_valid_three_versions(self):
        content = build_content({"threads": valid_threads()})
        self.assertEqual(set(content["threads"]), {"info", "experience", "shopping"})

    def test_rejects_missing_version(self):
        bad = valid_threads()
        del bad["shopping"]
        with self.assertRaises(ValidationError):
            build_content({"threads": bad})

    def test_rejects_over_length_single_post(self):
        bad = valid_threads()
        bad["info"] = "가" * (THREADS_MAX_CHARS + 1)
        with self.assertRaises(ValidationError):
            build_content({"threads": bad})


class NaverBlogValidationTests(unittest.TestCase):
    def test_valid_naver_blog(self):
        content = build_content({"naver_blog": valid_naver_blog()})
        self.assertEqual(len(content["naver_blog"]["titles"]), 3)

    def test_rejects_wrong_title_count(self):
        bad = valid_naver_blog()
        bad["titles"] = ["제목1", "제목2"]
        with self.assertRaises(ValidationError):
            build_content({"naver_blog": bad})

    def test_rejects_empty_faq(self):
        bad = valid_naver_blog()
        bad["faq"] = []
        with self.assertRaises(ValidationError):
            build_content({"naver_blog": bad})


class YoutubeShortsValidationTests(unittest.TestCase):
    def test_valid_shorts(self):
        content = build_content({"youtube_shorts": valid_youtube_shorts()})
        self.assertEqual(len(content["youtube_shorts"]["titles"]), 5)

    def test_rejects_wrong_thumbnail_count(self):
        bad = valid_youtube_shorts()
        bad["thumbnail_texts"] = ["only one"]
        with self.assertRaises(ValidationError):
            build_content({"youtube_shorts": bad})

    def test_rejects_missing_field(self):
        bad = valid_youtube_shorts()
        del bad["cta"]
        with self.assertRaises(ValidationError):
            build_content({"youtube_shorts": bad})


class BuildContentTests(unittest.TestCase):
    def test_rejects_empty_content(self):
        with self.assertRaises(ValidationError):
            build_content({})

    def test_rejects_unknown_platform(self):
        with self.assertRaises(ValidationError):
            build_content({"tiktok": {}})

    def test_allows_partial_platforms(self):
        content = build_content({"threads": valid_threads()})
        self.assertNotIn("naver_blog", content)


if __name__ == "__main__":
    unittest.main()
