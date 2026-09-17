"""FINAL EDITOR (spec section 19): checks CREATOR output before it can even
reach preview/approval (section 21). This module can only catch what code
can catch -- banned phrase lists, structural duplication, missing required
disclosures. It is not a fact-checker: a PASS here is a precondition for
human preview, never a substitute for it, and never a publish approval.
"""
from __future__ import annotations

import difflib

# Section 19: 과장 -- absolute/overclaim language that has no place in a
# factual candidate write-up.
EXAGGERATION_PHRASES = [
    "무조건", "100%", "100퍼센트", "누구나 됩니다", "인생이 바뀝니다", "보장합니다",
]

# Section 19: AI 문체 -- the tell-tale generic-assistant phrasing to strip.
AI_STYLE_PHRASES = [
    "안녕하세요, 오늘은", "오늘은 ", "결론적으로", "여러분의 생각은 어떠신가요",
    "~에 대해 알아보겠습니다", "에 대해 알아보겠습니다",
]

DUPLICATE_SIMILARITY_THRESHOLD = 0.85


def _all_text_fields(content: dict) -> list[tuple[str, str]]:
    """Flatten every string field in a content dict to (path, text) pairs."""
    out = []

    def walk(prefix, value):
        if isinstance(value, str):
            if value.strip():
                out.append((prefix, value))
        elif isinstance(value, dict):
            for k, v in value.items():
                walk(f"{prefix}.{k}", v)
        elif isinstance(value, list):
            for i, v in enumerate(value):
                walk(f"{prefix}[{i}]", v)

    for platform, body in content.items():
        walk(platform, body)
    return out


def _check_banned_phrases(content: dict, phrases: list[str]) -> list[str]:
    hits = []
    for path, text in _all_text_fields(content):
        for phrase in phrases:
            if phrase in text:
                hits.append(f"{path} contains banned phrase {phrase!r}")
    return hits


def _check_threads_internal_duplication(content: dict) -> list[str]:
    threads = content.get("threads")
    if not threads:
        return []
    versions = list(threads.items())
    issues = []
    for i in range(len(versions)):
        for j in range(i + 1, len(versions)):
            (name_a, text_a), (name_b, text_b) = versions[i], versions[j]
            ratio = difflib.SequenceMatcher(None, text_a, text_b).ratio()
            if ratio >= DUPLICATE_SIMILARITY_THRESHOLD:
                issues.append(
                    f"threads.{name_a} and threads.{name_b} are {ratio:.0%} similar -- "
                    "the 3 required versions (정보형/경험담/쇼핑형) must be genuinely different angles"
                )
    return issues


def _check_ad_disclosure(candidate, content: dict) -> list[str]:
    money = candidate.money_analysis or {}
    affiliate_viable = any(
        money.get("revenue_paths", {}).get(k, {}).get("viable") is True
        for k in ("affiliate", "recurring_affiliate")
    )
    if not affiliate_viable:
        return []

    disclosure_markers = ["광고", "협찬", "제휴", "수수료"]
    all_text = " ".join(text for _, text in _all_text_fields(content))
    if not any(marker in all_text for marker in disclosure_markers):
        return [
            "affiliate revenue path is marked viable but no ad-disclosure marker "
            f"({'/'.join(disclosure_markers)}) found anywhere in the drafted content"
        ]
    return []


def _check_agent_economy_security_fields(candidate) -> list[str]:
    if candidate.track != "AGENT_ECONOMY":
        return []
    issues = []
    if not candidate.license or not candidate.license.strip():
        issues.append("AGENT_ECONOMY candidate has no license recorded (section 19 extra check)")
    if not candidate.security_notes or not candidate.security_notes.strip():
        issues.append("AGENT_ECONOMY candidate has no security_notes recorded (section 19 extra check)")
    return issues


def _check_sources(candidate) -> list[str]:
    if not candidate.sources:
        return ["candidate has no sources on record -- content cannot be fact-checked against anything"]
    return []


def run_final_editor(candidate) -> dict:
    """Runs every automatable check from section 19 against candidate.content.
    Returns a report; never sets an 'approved' flag -- that's a human-only
    action (section 21)."""
    content = candidate.content or {}

    findings = {
        "sources": _check_sources(candidate),
        "exaggeration": _check_banned_phrases(content, EXAGGERATION_PHRASES),
        "ai_style": _check_banned_phrases(content, AI_STYLE_PHRASES),
        "duplication": _check_threads_internal_duplication(content),
        "ad_disclosure": _check_ad_disclosure(candidate, content),
        "agent_economy_security": _check_agent_economy_security_fields(candidate),
    }

    all_issues = [issue for issues in findings.values() for issue in issues]
    status = "PREVIEW_READY" if not all_issues else "NEEDS_REVISION"

    return {
        "status": status,
        "findings": findings,
        "issue_count": len(all_issues),
        "note": "자동 검사 통과는 사람 미리보기의 전제조건일 뿐, 게시 승인이 아님 (section 21)",
    }
