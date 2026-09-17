"""Daily report generation (spec sections 17 and 26)."""
from __future__ import annotations

from scout.models import Candidate
from scout.money import LEVEL_NAMES

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
            lines.append("")
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


def render_viral_dna(candidates: list[Candidate]) -> str:
    """Section 16: ANALYST AGENT output -- principles only, never copied text."""
    analyzed = [c for c in candidates if c.viral_dna]
    if not analyzed:
        return ""

    lines = ["## 🧬 VIRAL DNA\n"]
    for c in analyzed:
        dna = c.viral_dna
        lines.append(f"### {c.name}\n")
        lines.append(f"- Topic: {dna['topic']}")
        lines.append(f"- Hook 원리: {dna['hook_principle']}")
        if dna.get("source_note"):
            lines.append(f"  (근거: {dna['source_note']})")
        lines.append(f"- Emotion: {dna['emotion']}")
        lines.append(f"- Problem: {dna['problem']}")
        lines.append(f"- Desire: {dna['desire']}")
        lines.append(f"- Format: {dna['format']}")
        lines.append(f"- Structure: {dna['structure']}")
        lines.append(f"- Comment Trigger: {dna['comment_trigger']}")
        lines.append(f"- Shopping Signal: {dna['shopping_signal']}")
        lines.append(f"- Replicability: {dna['replicability']}/100\n")
    return "\n".join(lines)


def render_money_agent(candidates: list[Candidate]) -> str:
    """Sections 12-15: MONEY AGENT revenue paths + product ladder."""
    analyzed = [c for c in candidates if c.money_analysis]
    if not analyzed:
        return ""

    lines = ["## 💵 MONEY AGENT REVENUE PATHS\n"]
    for c in analyzed:
        m = c.money_analysis
        lines.append(f"### {c.name}\n")
        lines.append(f"- 분류: {m['classification']} (검증된 경로 {m['viable_count']}개)")
        viable = m.get("viable_paths") or []
        lines.append(f"- 유효 경로: {', '.join(viable) if viable else '없음'}")
        for key, entry in m.get("revenue_paths", {}).items():
            if entry.get("viable") is True:
                lines.append(f"  - {key}: {entry.get('why', '')}")
        if m.get("product_ladder_level"):
            lines.append(f"- PRODUCT OPPORTUNITY 단계: {LEVEL_NAMES.get(m['product_ladder_level'], m['product_ladder_level'])}")
        lines.append(f"- 🎯 NEXT ACTION: {m['next_action']}\n")
    return "\n".join(lines)


def render_creator_output(candidates: list[Candidate]) -> str:
    """Section 18: CREATOR AGENT drafts -- summaries only (full drafts live
    in the content JSON / DB, not spammed into the daily report)."""
    created = [c for c in candidates if c.content]
    if not created:
        return ""

    lines = ["## ✍️ CREATOR OUTPUT\n"]
    for c in created:
        lines.append(f"### {c.name}\n")
        platforms = sorted(c.content)
        lines.append(f"- 초안 플랫폼: {', '.join(platforms)}")
        threads = c.content.get("threads")
        if threads:
            lines.append(f"- Threads 버전: {', '.join(sorted(threads))}")
        naver = c.content.get("naver_blog")
        if naver:
            lines.append(f"- Naver 블로그 제목안: {' / '.join(naver.get('titles', []))}")
        shorts = c.content.get("youtube_shorts")
        if shorts:
            lines.append(f"- Shorts 제목안: {' / '.join(shorts.get('titles', []))}")
        lines.append(f"- 상태: {c.content_status}\n")
    return "\n".join(lines)


def render_final_editor(candidates: list[Candidate]) -> str:
    """Section 19: FINAL EDITOR results. A PASS here is a precondition for
    human preview (section 21), never a publish approval."""
    reviewed = [c for c in candidates if c.editor_review]
    if not reviewed:
        return ""

    lines = ["## ✅ FINAL EDITOR CHECK\n"]
    for c in reviewed:
        review = c.editor_review
        lines.append(f"### {c.name}\n")
        lines.append(f"- 상태: {review['status']} (이슈 {review['issue_count']}건)")
        for category, issues in review["findings"].items():
            if issues:
                lines.append(f"  - {category}:")
                for issue in issues:
                    lines.append(f"    - {issue}")
        lines.append(f"- {review['note']}")
        lines.append("- 👀 미리보기 / ✏️ 수정 / ✅ 게시 승인 / 🗑️ 폐기 (명시적 게시 승인 없이는 게시하지 않음)\n")
    return "\n".join(lines)


def render_approval_status(candidates: list[Candidate]) -> str:
    """Section 21: Telegram Approval status. Never rendered as if this
    pipeline itself approved anything -- APPROVED only appears here because
    a real human decision was recorded via apply_decision()."""
    requested = [c for c in candidates if c.approval]
    if not requested:
        return ""

    lines = ["## 📲 TELEGRAM APPROVAL\n"]
    for c in requested:
        a = c.approval
        lines.append(f"### {c.name}\n")
        lines.append(f"- 상태: {a['status']}")
        lines.append(f"- 요청 시각: {a.get('requested_at', 'UNKNOWN')}")
        if a.get("decided_at"):
            lines.append(f"- 결정 시각: {a['decided_at']} (by {a.get('decided_by', 'UNKNOWN')})")
        if a.get("notes"):
            lines.append(f"- 메모: {a['notes']}")
        if a["status"] == "APPROVED":
            lines.append("- 게시 승인은 기록되었으나, 이 시스템은 실제 게시를 수행하지 않음 (PHASE 5 PUBLISH 미구현)")
        lines.append("")
    return "\n".join(lines)


def render_daily_report(date_str: str, candidates: list[Candidate]) -> str:
    header = f"# AI SNS MONEY FACTORY — Daily Report ({date_str})\n"
    sections = [
        header,
        render_top3(candidates),
        render_agent_money_signal(candidates),
        render_viral_dna(candidates),
        render_money_agent(candidates),
        render_creator_output(candidates),
        render_final_editor(candidates),
        render_approval_status(candidates),
    ]
    return "\n".join(s for s in sections if s)
