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


# ANALYST AGENT (section 16): the fixed set of angles every VIRAL DNA record
# must cover before it counts as an analysis rather than a note.
VIRAL_DNA_FIELDS = {
    "topic", "hook_principle", "emotion", "problem", "desire",
    "format", "structure", "comment_trigger", "shopping_signal",
    "replicability",
}

# MONEY AGENT (section 12): the fixed menu of revenue paths to evaluate.
# Never invent a path outside this list, and never fabricate viability --
# each "viable" path must carry a reason.
REVENUE_PATH_KEYS = {
    "affiliate", "recurring_affiliate", "content_revenue", "skill",
    "template", "digital_product", "smartstore", "guide_ebook",
    "consulting", "agent_setup_service", "lead_generation",
    "micro_saas", "data_business",
}

MONETIZABLE_MIN_VIABLE_PATHS = 3  # section 12: "최소 3개의 현실적인 수익화 경로"

# CREATOR AGENT (section 18): required fields per platform output.
THREADS_VERSIONS = {"info", "experience", "shopping"}  # 정보형 / 경험·공감형 / 쇼핑·문제해결형
THREADS_MAX_CHARS = 500

NAVER_BLOG_FIELDS = {
    "titles", "main_keyword", "sub_keywords", "hook", "problem", "situation",
    "cause", "solution", "selection_criteria", "product_service", "faq", "closing",
}

YOUTUBE_SHORTS_FIELDS = {
    "hook", "problem", "discovery_solution", "core", "cta",
    "titles", "thumbnail_texts", "broll", "subtitles", "video_prompt",
    "description", "tags",
}

# Telegram Approval (section 21): the only 4 buttons that exist, and the
# only 4 decision outcomes this pipeline understands. "APPROVED" is the
# single publish-approval state -- nothing downstream may set it except a
# real decision recorded through this action set.
APPROVAL_ACTIONS = {"preview", "revise", "approve", "discard"}
ACTION_TO_STATUS = {
    "preview": "PENDING",
    "revise": "NEEDS_REVISION",
    "approve": "APPROVED",
    "discard": "REJECTED",
}

# PUBLISH (section 22 onward). Only platforms with a content draft (§18)
# can be published; capability is honest per-platform, not assumed:
#   threads         real API (Meta Graph, graph.threads.net), implemented
#   youtube_shorts  real API (YouTube Data API v3), implemented, but needs
#                   an actual rendered video file this pipeline never
#                   produces -- CREATOR only writes a video_prompt, not a
#                   video. Publish requires the file path to be supplied.
#   naver_blog      No current, reliable, officially-supported public API
#                   for a third party to create a post on an arbitrary
#                   personal Naver Blog (the only documented mechanism is
#                   a MetaWeblog/XML-RPC integration from ~2010 with no
#                   confirmed 2026 support). Never fabricated as "working."
PUBLISH_PLATFORMS = {"threads", "naver_blog", "youtube_shorts"}
PUBLISH_NOT_SUPPORTED_PLATFORMS = {"naver_blog"}

# GROWTH + FEEDBACK (sections 22-25).
GROWTH_WINDOWS = ("1H", "6H", "24H", "72H", "7D")
GROWTH_METRIC_FIELDS = {
    "views", "likes", "comments", "shares", "saves",
    "clicks", "product_clicks", "conversions", "revenue",
}
# Every metric is a non-negative number or the literal string "UNKNOWN" --
# never silently defaulted to 0, which would misrepresent "not tracked" as
# "tracked and zero."
PERFORMANCE_RATIO_BANDS = (
    (0.7, "UNDERPERFORM"),
    (1.5, "NORMAL"),
    (3.0, "WINNER"),
    (5.0, "HOT"),
    (float("inf"), "BREAKOUT"),
)
MIN_BASELINE_SAMPLE_SIZE = 3  # never compute a "median" off fewer posts than this


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

    # PHASE 2: ANALYST (VIRAL DNA, section 16) and MONEY AGENT (revenue
    # paths + product ladder, sections 12/15). Empty until analyze is run.
    viral_dna: dict = field(default_factory=dict)
    money_analysis: dict = field(default_factory=dict)

    # PHASE 3: CREATOR (Threads/Naver/Shorts drafts, section 18) and FINAL
    # EDITOR (section 19). Empty until create/review is run. content_status
    # (above) tracks lifecycle; these hold the actual drafts and the review.
    content: dict = field(default_factory=dict)
    editor_review: dict = field(default_factory=dict)

    # PHASE 4: Telegram Approval (section 21). Publish approval is always a
    # human action taken on a real Telegram message -- nothing in this
    # codebase can set status to APPROVED on its own.
    approval: dict = field(default_factory=dict)

    # PHASE 5: PUBLISH. Keyed by platform ("threads" / "naver_blog" /
    # "youtube_shorts"), each entry {status, post_id, url, error, published_at}.
    # publish.guard_approved() is the single gate every publisher goes
    # through -- see scout/publish.py.
    publish_status: dict = field(default_factory=dict)

    # PHASE 5: GROWTH + FEEDBACK (sections 22-25). Keyed by measurement
    # window (1H/6H/24H/72H/7D), each entry {metrics, performance,
    # money_performance, feedback}. growth.guard_published() is the gate --
    # you can't measure growth on something never actually posted.
    growth: dict = field(default_factory=dict)

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
