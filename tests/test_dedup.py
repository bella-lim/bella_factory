import unittest

from scout.dedup import find_duplicate, merge_sources
from scout.models import Candidate


def make(name, url, track="AGENT_ECONOMY", category="MCP", sources=None):
    return Candidate(
        id="x", track=track, name=name, category=category, url=url,
        sources=sources or [url],
    )


class DedupTests(unittest.TestCase):
    def test_same_url_is_duplicate(self):
        existing = [make("MCPJungle", "https://github.com/mcpjungle/mcpjungle")]
        cand = make("mcpjungle", "https://github.com/mcpjungle/mcpjungle/")
        self.assertIsNotNone(find_duplicate(existing, cand))

    def test_similar_name_same_category_is_duplicate(self):
        existing = [make("MCPJungle Registry", "https://example.com/a")]
        cand = make("MCPJungle registry", "https://example.com/b")
        self.assertIsNotNone(find_duplicate(existing, cand))

    def test_different_category_not_duplicate(self):
        existing = [make("Foo", "https://example.com/a", category="MCP")]
        cand = make("Foo", "https://example.com/a", category="TOOL")
        self.assertIsNone(find_duplicate(existing, cand))

    def test_unrelated_not_duplicate(self):
        existing = [make("Foo Tool", "https://example.com/a")]
        cand = make("Completely Different Thing", "https://example.com/z")
        self.assertIsNone(find_duplicate(existing, cand))

    def test_merge_sources_dedupes_and_preserves_order(self):
        a = make("Foo", "https://example.com/a", sources=["https://s1", "https://s2"])
        b = make("Foo", "https://example.com/a", sources=["https://s2", "https://s3"])
        merged = merge_sources(a, b)
        self.assertEqual(merged, ["https://s1", "https://s2", "https://s3"])


if __name__ == "__main__":
    unittest.main()
