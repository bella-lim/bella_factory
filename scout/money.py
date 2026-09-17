"""MONEY AGENT (spec sections 12-15): revenue-path evaluation + product ladder.

Evaluates a candidate against the fixed menu of revenue paths (section 12),
requires at least 3 realistic ("viable") paths with a stated reason before
calling it monetizable, and otherwise honestly classifies it as TRAFFIC
CONTENT rather than inventing a business model. Viable candidates are also
mapped onto the 4-level PRODUCT OPPORTUNITY ladder (section 15) -- but the
recommended next action always starts at LEVEL 1, never jumps straight to
a Micro SaaS, per "처음부터 SaaS를 만들지 않는다."
"""
from __future__ import annotations

from scout.models import MONETIZABLE_MIN_VIABLE_PATHS, REVENUE_PATH_KEYS, ValidationError

TRI_STATE = {True, False, "UNKNOWN"}

# Which revenue paths unlock which rung of the section 15 ladder.
LEVEL_2_PATHS = {"affiliate", "recurring_affiliate", "template", "skill", "digital_product",
                  "guide_ebook", "smartstore"}
LEVEL_3_PATHS = {"agent_setup_service", "consulting", "lead_generation", "data_business"}
LEVEL_4_PATHS = {"micro_saas"}

LEVEL_NAMES = {
    1: "LEVEL 1: CONTENT",
    2: "LEVEL 2: AFFILIATE / TEMPLATE / SKILL",
    3: "LEVEL 3: AGENT 구축 서비스",
    4: "LEVEL 4: MICRO SaaS",
}


def validate_revenue_paths(raw_paths: dict) -> list[str]:
    errors = []
    unknown_keys = set(raw_paths) - REVENUE_PATH_KEYS
    if unknown_keys:
        errors.append(f"unknown revenue path keys (not in section 12 menu): {sorted(unknown_keys)}")

    for key, entry in raw_paths.items():
        if key not in REVENUE_PATH_KEYS:
            continue
        if not isinstance(entry, dict) or "viable" not in entry:
            errors.append(f"revenue path {key!r} must be an object with a 'viable' key")
            continue
        viable = entry["viable"]
        if viable not in TRI_STATE:
            errors.append(f"revenue path {key!r}.viable must be True/False/'UNKNOWN', got {viable!r}")
        if viable is True and not str(entry.get("why", "")).strip():
            errors.append(
                f"revenue path {key!r} marked viable but has no reason -- "
                "MONEY AGENT never invents a forced business model (section 12)"
            )
    return errors


def _ladder_level(viable_keys: set) -> int | None:
    if not viable_keys:
        return None
    level = 1  # content is always the entry point once anything is viable
    if viable_keys & LEVEL_2_PATHS:
        level = 2
    if viable_keys & LEVEL_3_PATHS:
        level = 3
    if viable_keys & LEVEL_4_PATHS:
        level = 4
    return level


def build_money_analysis(raw_paths: dict) -> dict:
    errors = validate_revenue_paths(raw_paths)
    if errors:
        raise ValidationError("; ".join(errors))

    viable_keys = {k for k, v in raw_paths.items() if v.get("viable") is True}
    viable_count = len(viable_keys)
    classification = "MONETIZABLE" if viable_count >= MONETIZABLE_MIN_VIABLE_PATHS else "TRAFFIC CONTENT"
    ladder_level = _ladder_level(viable_keys) if classification == "MONETIZABLE" else None

    if ladder_level is None:
        next_action = "수익화 경로 3개 미만 -> TRAFFIC CONTENT로 분류, 억지로 사업화하지 않음"
    else:
        next_action = (
            f"{LEVEL_NAMES[1]}부터 시작 (도달 가능한 최고 단계는 {LEVEL_NAMES[ladder_level]}이지만, "
            "처음부터 SaaS로 가지 않고 콘텐츠/작은 테스트로 수요부터 검증)"
        )

    return {
        "revenue_paths": raw_paths,
        "viable_paths": sorted(viable_keys),
        "viable_count": viable_count,
        "classification": classification,
        "product_ladder_level": ladder_level,
        "next_action": next_action,
    }
