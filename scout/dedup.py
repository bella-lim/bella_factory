"""Trend-cluster deduplication (spec section 10 note: 'dedup Trend Cluster').

Two candidates are treated as the same underlying opportunity -- not two
separate rows -- when they share a track/category and either the same URL
(same domain + path) or a name similar enough that they are clearly the same
tool/topic (e.g. "MCPJungle" vs "mcpjungle - MCP server registry").
"""
from __future__ import annotations

import difflib
import re
from urllib.parse import urlparse

from scout.models import Candidate

NAME_SIMILARITY_THRESHOLD = 0.82


def _normalize_name(name: str) -> str:
    name = name.lower()
    name = re.sub(r"[^a-z0-9가-힣\s]", " ", name)
    return re.sub(r"\s+", " ", name).strip()


def _normalize_url(url: str) -> str:
    p = urlparse(url.lower())
    path = p.path.rstrip("/")
    return f"{p.netloc}{path}"


def find_duplicate(existing: list[Candidate], candidate: Candidate) -> Candidate | None:
    cand_url = _normalize_url(candidate.url)
    cand_name = _normalize_name(candidate.name)

    same_scope = [c for c in existing if c.track == candidate.track and c.category == candidate.category]

    for c in same_scope:
        if _normalize_url(c.url) == cand_url:
            return c

    for c in same_scope:
        ratio = difflib.SequenceMatcher(None, _normalize_name(c.name), cand_name).ratio()
        if ratio >= NAME_SIMILARITY_THRESHOLD:
            return c

    return None


def merge_sources(existing: Candidate, incoming: Candidate) -> list[str]:
    merged = list(dict.fromkeys(existing.sources + incoming.sources))
    return merged
