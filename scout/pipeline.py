"""Ingest pipeline: validate -> dedup -> score -> persist.

This is the deterministic half of SCOUT / AGENT ECONOMY RADAR. The
non-deterministic half -- actually finding candidates on GitHub, Hacker
News, Reddit, Naver, etc. and judging Korean Gap / Money Gap -- is done by
the research agent (Hermes) using web search/fetch, which produces the raw
candidate JSON this module consumes. This module never invents data; it
only validates, scores and stores what the research step already found.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import replace

from scout.models import Candidate, ValidationError, validate_raw_candidate
from scout.scoring import score_and_tier, is_product_opportunity
from scout import dedup
from scout.analyst import build_viral_dna
from scout.money import build_money_analysis


def _slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text or "item"


def make_id(track: str, name: str) -> str:
    return f"{track.lower().replace('_', '-')}-{_slugify(name)}"


def build_candidate(raw: dict, today: str) -> Candidate:
    errors = validate_raw_candidate(raw)
    if errors:
        raise ValidationError("; ".join(errors))

    score_total, score_tier = score_and_tier(raw["track"], raw["subscores"])
    problem_strength = raw.get("problem_strength", "UNKNOWN")
    product_opp = is_product_opportunity(
        raw["track"], score_total, problem_strength,
        raw.get("hermes_compatible", "TEST"),
        raw.get("korean_gap", "UNKNOWN"), raw.get("money_gap", "UNKNOWN"),
    )

    return Candidate(
        id=make_id(raw["track"], raw["name"]),
        track=raw["track"],
        name=raw["name"],
        category=raw.get("category", raw["track"]),
        url=raw["url"],
        sources=list(dict.fromkeys(raw.get("sources", []))),
        stage=raw.get("stage", "NEW"),
        first_detected=today,
        last_checked=today,
        what_changed=raw.get("what_changed", ""),
        why_now=raw.get("why_now", ""),
        agent_use=raw.get("agent_use", ""),
        hook=raw.get("hook", ""),
        recommended_platform=raw.get("recommended_platform", ""),
        next_action=raw.get("next_action", ""),
        korean_gap=raw.get("korean_gap", "UNKNOWN"),
        korean_gap_evidence=raw.get("korean_gap_evidence", ""),
        money_gap=raw.get("money_gap", "UNKNOWN"),
        money_gap_evidence=raw.get("money_gap_evidence", ""),
        hermes_compatible=raw.get("hermes_compatible", "TEST"),
        license=raw.get("license", "UNKNOWN"),
        security_notes=raw.get("security_notes", ""),
        problem_strength=problem_strength,
        business_models=raw.get("business_models", []),
        combo_candidates=raw.get("combo_candidates", []),
        subscores=raw["subscores"],
        score_total=score_total,
        score_tier=score_tier,
        product_opportunity=product_opp,
    )


def ingest_batch(db: dict, raw_items: list[dict], today: str) -> dict:
    """Ingest a batch, returns summary counts. Mutates db in place."""
    from scout.storage import upsert, get_all

    created, updated, errors = [], [], []
    for raw in raw_items:
        try:
            candidate = build_candidate(raw, today)
        except ValidationError as e:
            errors.append({"name": raw.get("name", "UNKNOWN"), "error": str(e)})
            continue

        existing = dedup.find_duplicate(get_all(db), candidate)
        if existing:
            merged_sources = dedup.merge_sources(existing, candidate)
            updated_candidate = replace(
                existing,
                sources=merged_sources,
                last_checked=today,
                stage=candidate.stage,
                subscores=candidate.subscores,
                score_total=candidate.score_total,
                score_tier=candidate.score_tier,
                product_opportunity=candidate.product_opportunity,
                what_changed=candidate.what_changed or existing.what_changed,
                korean_gap=candidate.korean_gap,
                korean_gap_evidence=candidate.korean_gap_evidence or existing.korean_gap_evidence,
                money_gap=candidate.money_gap,
                money_gap_evidence=candidate.money_gap_evidence or existing.money_gap_evidence,
            )
            upsert(db, updated_candidate)
            updated.append(updated_candidate)
        else:
            upsert(db, candidate)
            created.append(candidate)

    return {"created": created, "updated": updated, "errors": errors}


def analyze_batch(db: dict, analysis_items: list[dict], today: str) -> dict:
    """PHASE 2: apply ANALYST (VIRAL DNA) + MONEY AGENT to candidates that
    already exist in the database (from a prior ingest). Never creates new
    candidates -- ANALYST/MONEY only deepen what SCOUT already found.
    """
    from scout.storage import get, upsert

    analyzed, errors = [], []
    for item in analysis_items:
        candidate_id = item.get("candidate_id")
        candidate = get(db, candidate_id) if candidate_id else None
        if candidate is None:
            errors.append({"candidate_id": candidate_id, "error": "candidate not found in database"})
            continue

        try:
            viral_dna = build_viral_dna(item["viral_dna"]) if "viral_dna" in item else candidate.viral_dna
            money_analysis = (
                build_money_analysis(item["money_paths"]) if "money_paths" in item else candidate.money_analysis
            )
        except (ValidationError, KeyError) as e:
            errors.append({"candidate_id": candidate_id, "error": str(e)})
            continue

        updated_candidate = replace(
            candidate, viral_dna=viral_dna, money_analysis=money_analysis, last_checked=today,
        )
        upsert(db, updated_candidate)
        analyzed.append(updated_candidate)

    return {"analyzed": analyzed, "errors": errors}
