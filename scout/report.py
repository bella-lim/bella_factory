"""Daily report generation (spec sections 17 and 26)."""
from __future__ import annotations

from scout.models import Candidate

MEDALS = ["🥇", "🥈", "🥉"]

STRONG_SIGNAL_THRESHOLD = 85


def _fmt_gap(value) -> str:
    if value is True:
        return "YES"
    if value is False:
        return "NO"
    return "UNKNOWN"


def render_top3(candidates: list[Candidate]) -> str:
    """Section 17: TOP 3 REPORT, drawn from non-agent-economy tracks."""
    pool = [c for c in candidates if c.track != "AGENT_ECONOMY" and c.score_tier != "ARCHIVE"]
    pool.sort(key=lambda c: c.score_total, reverse=True)
    top = pool[:3]

    if not top:
        return "## TOP 3 REPORT\n\n오늘 ARCHIVE 등급을 넘는 TOP 후보 없음. 억지로 후보를 만들지 않음.\n"

    lines = ["## TOP 3 REPORT\n"]
    for medal, c in zip(MEDALS, top):
        lines.append(f"### {medal} {c.name}\n")
        lines.append(f"- Trend: {c.what_changed or 'UNKNOWN'}")
        lines.append(f"- Korean Gap: {_fmt_gap(c.korean_gap)} ({c.korean_gap_evidence or 'UNKNOWN'})")
        lines.append(f"- Money Gap: {_fmt_gap(c.money_gap)} ({c.money_gap_evidence or 'UNKNOWN'})")
        lines.append(f"- Scout Score: {c.score_total} ({c.score_tier})")
        lines.append(f"- 왜 지금인가: {c.why_now or 'UNKNOWN'}")
        lines.append(f"- 수익방법: {', '.join(c.business_models) if c.business_models else 'TRAFFIC CONTENT'}")
        lines.append(f"- 추천 플랫폼: {c.recommended_platform or 'UNKNOWN'}")
        lines.append(f"- Hook: {c.hook or 'UNKNOWN'}")
        lines.append(f"- Hermes 적용: {c.hermes_compatible}")
        lines.append(f"- Combo Opportunity: {', '.join(c.combo_candidates) if c.combo_candidates else 'NONE'}")
        lines.append(f"- Sources: {' | '.join(c.sources)}")
        lines.append("- 버튼: 🔥 제작 / 👀 관찰 / ❌ 제외\n")
    return "\n".join(lines)


def render_agent_money_signal(candidates: list[Candidate]) -> str:
    """Section 26: AGENT MONEY SIGNAL block."""
    pool = [c for c in candidates if c.track == "AGENT_ECONOMY"]
    strong = [c for c in pool if c.score_total >= STRONG_SIGNAL_THRESHOLD]
    strong.sort(key=lambda c: c.score_total, reverse=True)

    lines = ["## 🤖 AGENT MONEY SIGNAL\n"]
    if not strong:
        lines.append("오늘은 강한 MONEY SIGNAL 없음.\n")
        if pool:
            lines.append("### 참고: WATCH 단계 후보 (점수 미달, 강제 승격하지 않음)\n")
            watch = sorted(pool, key=lambda c: c.score_total, reverse=True)[:3]
            for c in watch:
                lines.append(f"- {c.name} ({c.category}) — Agent Money Score {c.score_total} ({c.score_tier}) — {c.sources[0] if c.sources else 'UNKNOWN'}")
        return "\n".join(lines)

    for c in strong:
        lines.append(f"### {c.name}\n")
        lines.append(f"- Category: {c.category}")
        lines.append(f"- Stage: {c.stage}")
        lines.append(f"- What Changed: {c.what_changed or 'UNKNOWN'}")
        lines.append(f"- Agent Use: {c.agent_use or 'UNKNOWN'}")
        lines.append(f"- Hermes: {c.hermes_compatible}")
        lines.append(f"- 🇰🇷 Korean Gap: {_fmt_gap(c.korean_gap)} ({c.korean_gap_evidence or 'UNKNOWN'})")
        lines.append(f"- 💰 Money Gap: {_fmt_gap(c.money_gap)} ({c.money_gap_evidence or 'UNKNOWN'})")
        lines.append(f"- 🧩 Combo Opportunity: {', '.join(c.combo_candidates) if c.combo_candidates else 'NONE'}")
        lines.append(f"- Money Model: {', '.join(c.business_models) if c.business_models else 'TRAFFIC CONTENT'}")
        lines.append(f"- AGENT MONEY SCORE: {c.score_total} ({c.score_tier})")
        if c.product_opportunity:
            lines.append("- 💎 PRODUCT OPPORTUNITY 승격 조건 충족")
        lines.append(f"- 🎯 NEXT ACTION: {c.next_action or 'UNKNOWN'}")
        lines.append(f"- Sources: {' | '.join(c.sources)}\n")
    return "\n".join(lines)


def render_daily_report(date_str: str, candidates: list[Candidate]) -> str:
    header = f"# AI SNS MONEY FACTORY — Daily Report ({date_str})\n"
    return "\n".join([header, render_top3(candidates), render_agent_money_signal(candidates)])
