"""SCOUT SCORE (section 10) and AGENT MONEY SCORE (section 11)."""
from __future__ import annotations

from scout.models import AGENT_MONEY_SCORE_WEIGHTS, SCOUT_SCORE_WEIGHTS


def score_scout(subscores: dict) -> int:
    return round(sum(subscores.get(k, 0) for k in SCOUT_SCORE_WEIGHTS))


def scout_tier(total: int) -> str:
    if total >= 90:
        return "FIRST MOVER"
    if total >= 80:
        return "CREATE NOW"
    if total >= 70:
        return "WATCH"
    return "ARCHIVE"


def score_agent_money(subscores: dict) -> int:
    return round(sum(subscores.get(k, 0) for k in AGENT_MONEY_SCORE_WEIGHTS))


def agent_money_tier(total: int) -> str:
    if total >= 90:
        return "💎 BUILD BUSINESS"
    if total >= 80:
        return "💰 TEST NOW"
    if total >= 70:
        return "👀 WATCH"
    return "ARCHIVE"


def score_and_tier(track: str, subscores: dict) -> tuple[int, str]:
    if track == "AGENT_ECONOMY":
        total = score_agent_money(subscores)
        return total, agent_money_tier(total)
    total = score_scout(subscores)
    return total, scout_tier(total)


def is_product_opportunity(track: str, score_total: int, problem_strength: str,
                            hermes_compatible: str, korean_gap, money_gap) -> bool:
    """Section 14: promote to a business candidate, not just a content idea."""
    if track != "AGENT_ECONOMY":
        return False
    gap_present = (korean_gap is True) or (money_gap is True)
    return (
        score_total >= 90
        and problem_strength == "HIGH"
        and hermes_compatible in ("YES", "TEST")
        and gap_present
    )
