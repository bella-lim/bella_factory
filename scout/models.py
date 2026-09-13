"""Data model for SCOUT / AGENT ECONOMY RADAR candidates.

A single schema covers both general trend candidates (AI / SHOPPING / VIRAL
tracks, scored with SCOUT SCORE) and Agent Economy candidates (Tool / Skill /
MCP / API / ... scored with AGENT MONEY SCORE), because they share the same
lifecycle: discover -> verify -> score -> store -> report.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

TRACKS = {"AI_TREND", "SHOPPING", "VIRAL", "AGENT_ECONOMY"}

AGENT_ECONOMY_CATEGORIES = {
    "TOOL", "SKILL", "MCP", "API", "RUNTIME", "MEMORY", "IDENTITY",
    "PAYMENT", "SECURITY", "OBSERVABILITY", "BROWSER", "DATA",
    "AUTOMATION", "MARKETPLACE", "INFRA",
}

STAGES = {"NEW", "WATCH", "EMERGING", "BREAKOUT", "COMMERCIAL", "COOLING"}

# UNKNOWN is always a valid value for any tri-state gap/flag field per spec
# section 7 ("Never fabricate metrics; use UNKNOWN when data cannot be
# verified").
TRI_STATE = {True, False, "UNKNOWN"}

SCOUT_SCORE_WEIGHTS = {
    "rising_signal": 25,
    "source_diversity": 20,
    "platform_spread": 15,
    "novelty": 15,
    "korean_gap": 15,
    "monetization": 10,
}

AGENT_MONEY_SCORE_WEIGHTS = {
    "problem_solving": 15,
    "agent_utility": 10,
    "hermes_compatibility": 10,
    "early_market_signal": 10,
    "korean_gap": 10,
    "affiliate_potential": 10,
    "service_potential": 15,
    "skill_template_potential": 10,
    "content_potential": 10,
}


class ValidationError(ValueError):
    pass


@dataclass
class Candidate:
    id: str
    track: str
    name: str
    category: str
    url: str
    sources: list[str] = field(default_factory=list)
    stage: str = "NEW"
    first_detected: str = ""
    last_checked: str = ""

    # narrative fields (kept short, sourced from real research notes)
    what_changed: str = ""
    why_now: str = ""
    agent_use: str = ""
    hook: str = ""
    recommended_platform: str = ""
    next_action: str = ""

    # gap / compatibility flags -- True / False / "UNKNOWN" only
    korean_gap: Any = "UNKNOWN"
    korean_gap_evidence: str = ""
    money_gap: Any = "UNKNOWN"
    money_gap_evidence: str = ""
    hermes_compatible: str = "TEST"  # YES / TEST / NO

    # safety / provenance
    license: str = "UNKNOWN"
    security_notes: str = ""
    problem_strength: str = "UNKNOWN"  # HIGH / MEDIUM / LOW / UNKNOWN

    # monetization
    business_models: list[str] = field(default_factory=list)
    combo_candidates: list[str] = field(default_factory=list)

    # scoring
    subscores: dict = field(default_factory=dict)
    score_total: int = 0
    score_tier: str = ""
    product_opportunity: bool = False

    # lifecycle tracking (sections 21-27; left UNKNOWN/empty until later phases)
    test_status: str = "NOT_TESTED"
    content_status: str = "NONE"
    performance: str = "UNKNOWN"
    revenue: str = "UNKNOWN"

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "Candidate":
        known = {f for f in Candidate.__dataclass_fields__}
        return Candidate(**{k: v for k, v in d.items() if k in known})


def validate_raw_candidate(raw: dict) -> list[str]:
    """Return a list of validation error strings (empty == valid)."""
    errors = []

    track = raw.get("track")
    if track not in TRACKS:
        errors.append(f"track must be one of {sorted(TRACKS)}, got {track!r}")

    if not raw.get("name"):
        errors.append("name is required")

    if not raw.get("url", "").startswith("http"):
        errors.append("url must be a real http(s) URL (no fabricated URLs)")

    sources = raw.get("sources") or []
    if not sources:
        errors.append("at least one source URL is required")

    if track == "AGENT_ECONOMY":
        cat = raw.get("category")
        if cat not in AGENT_ECONOMY_CATEGORIES:
            errors.append(
                f"category must be one of {sorted(AGENT_ECONOMY_CATEGORIES)} for AGENT_ECONOMY, got {cat!r}"
            )
        weights = AGENT_MONEY_SCORE_WEIGHTS
    else:
        weights = SCOUT_SCORE_WEIGHTS

    stage = raw.get("stage", "NEW")
    if stage not in STAGES:
        errors.append(f"stage must be one of {sorted(STAGES)}, got {stage!r}")

    for flag in ("korean_gap", "money_gap"):
        val = raw.get(flag, "UNKNOWN")
        if val not in TRI_STATE:
            errors.append(f"{flag} must be True/False/'UNKNOWN', got {val!r}")

    hermes = raw.get("hermes_compatible", "TEST")
    if hermes not in {"YES", "TEST", "NO"}:
        errors.append(f"hermes_compatible must be YES/TEST/NO, got {hermes!r}")

    subscores = raw.get("subscores") or {}
    missing = set(weights) - set(subscores)
    if missing:
        errors.append(f"subscores missing keys: {sorted(missing)}")
    for k, v in subscores.items():
        if k not in weights:
            errors.append(f"unknown subscore key {k!r}")
            continue
        if not isinstance(v, (int, float)) or v < 0 or v > weights[k]:
            errors.append(f"subscore {k} must be a number in [0, {weights[k]}], got {v!r}")

    return errors
