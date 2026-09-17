"""GROWTH + FEEDBACK (spec sections 22-25).

Measures published content at fixed windows (1H/6H/24H/72H/7D), computes a
PERFORMANCE RATIO against the account's own recent history (never a
guessed baseline), keeps content performance and money performance on
separate axes (section 24 -- a viral winner can be a money failure and
vice versa), and generates rule-based feedback for SCOUT/MONEY/CREATOR.

Nothing here can measure a candidate that was never actually published --
guard_published() is the gate. Nothing here fabricates a baseline from too
little history -- compute_baseline() refuses below
MIN_BASELINE_SAMPLE_SIZE comparable posts and returns None instead.
"""
from __future__ import annotations

import datetime
import statistics

from scout.models import (
    GROWTH_METRIC_FIELDS, GROWTH_WINDOWS, MIN_BASELINE_SAMPLE_SIZE,
    PERFORMANCE_RATIO_BANDS, ValidationError,
)


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def guard_published(candidate) -> None:
    published_platforms = [p for p, r in (candidate.publish_status or {}).items() if r.get("status") == "PUBLISHED"]
    if not published_platforms:
        raise ValidationError(
            f"candidate {candidate.id!r} has no PUBLISHED platform in publish_status -- "
            "growth can't be measured on something never actually posted"
        )


def validate_metrics(raw: dict) -> list[str]:
    errors = []
    unknown_keys = set(raw) - GROWTH_METRIC_FIELDS - {"platform", "measured_at"}
    if unknown_keys:
        errors.append(f"unknown metric fields: {sorted(unknown_keys)}")

    for key in GROWTH_METRIC_FIELDS:
        if key not in raw:
            continue
        value = raw[key]
        if value == "UNKNOWN":
            continue
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
            errors.append(f"metric {key!r} must be a non-negative number or 'UNKNOWN', got {value!r}")
    return errors


def build_metrics_record(raw: dict) -> dict:
    errors = validate_metrics(raw)
    if errors:
        raise ValidationError("; ".join(errors))
    record = {k: raw.get(k, "UNKNOWN") for k in GROWTH_METRIC_FIELDS}
    record["platform"] = raw.get("platform", "UNKNOWN")
    record["measured_at"] = raw.get("measured_at") or _now()
    return record


def band_for_ratio(ratio: float) -> str:
    for threshold, band in PERFORMANCE_RATIO_BANDS:
        if ratio < threshold:
            return band
    return PERFORMANCE_RATIO_BANDS[-1][1]  # unreachable (last threshold is inf), kept for clarity


def compute_baseline(db: dict, platform: str, window: str, metric_name: str, exclude_candidate_id: str) -> tuple:
    """Median of `metric_name` at `window` across the account's other posts
    on `platform`. Returns (baseline, sample_size); baseline is None below
    MIN_BASELINE_SAMPLE_SIZE comparable data points -- never a guess."""
    from scout.storage import get_all

    samples = []
    for candidate in get_all(db):
        if candidate.id == exclude_candidate_id:
            continue
        entry = (candidate.growth or {}).get(window, {}).get("metrics")
        if not entry or entry.get("platform") != platform:
            continue
        value = entry.get(metric_name)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            samples.append(value)

    if len(samples) < MIN_BASELINE_SAMPLE_SIZE:
        return None, len(samples)
    return statistics.median(samples), len(samples)


def compute_performance(db: dict, candidate, window: str, metrics: dict, metric_name: str = "views") -> dict:
    post_value = metrics.get(metric_name)
    baseline, sample_size = compute_baseline(db, metrics.get("platform", "UNKNOWN"), window, metric_name, candidate.id)

    if not isinstance(post_value, (int, float)) or isinstance(post_value, bool) or baseline is None:
        return {"ratio": None, "band": "UNKNOWN", "baseline": baseline, "baseline_sample_size": sample_size,
                "metric_used": metric_name}

    if baseline == 0:
        return {"ratio": None, "band": "UNKNOWN", "baseline": baseline, "baseline_sample_size": sample_size,
                "metric_used": metric_name}

    ratio = post_value / baseline
    return {"ratio": ratio, "band": band_for_ratio(ratio), "baseline": baseline,
            "baseline_sample_size": sample_size, "metric_used": metric_name}


def compute_money_performance(metrics: dict, performance: dict) -> dict:
    """Section 24: content performance and money performance never mixed
    into one number. content_verdict mirrors the section-23 band computed
    from `performance`; money_verdict is judged solely on conversions."""
    content_verdict = f"VIRAL {performance['band']}" if performance["band"] != "UNKNOWN" else "VIRAL UNKNOWN"

    conversions = metrics.get("conversions")
    if conversions == "UNKNOWN" or conversions is None:
        money_verdict = "MONEY UNKNOWN"
    elif isinstance(conversions, (int, float)) and conversions > 0:
        money_verdict = "MONEY WINNER"
    else:
        money_verdict = "MONEY FAILURE"

    return {"content_verdict": content_verdict, "money_verdict": money_verdict}


_FEEDBACK_RULES = {
    ("HIGH", "MONEY WINNER"): {
        "scout_note": "강한 신호 확인됨 -- 유사 소재 우선순위 상향",
        "money_note": "현재 수익 경로가 실제로 작동함 -- 점수 유지/상향, 경로 확대 검토",
        "creator_note": "동일 구조(후크/CTA)로 후속 편 제작",
    },
    ("HIGH", "MONEY FAILURE"): {
        "scout_note": "소재 자체는 검증됨 -- 유사 주제 유지",
        "money_note": "클릭/노출은 있으나 전환 없음 -- 해당 수익 경로 점수 하향 검토",
        "creator_note": "CTA·제품 링크 배치를 더 명확하게 조정해 재시도",
    },
    ("HIGH", "MONEY UNKNOWN"): {
        "scout_note": "소재 반응은 좋음 -- 유지하되 전환 추적 안 됨에 유의",
        "money_note": "전환 추적이 안 되어 있음 -- 다음 편부터 추적 링크/픽셀 적용 필요",
        "creator_note": "다음 편에는 추적 가능한 CTA 링크 포함",
    },
    ("LOW", "MONEY WINNER"): {
        "scout_note": "바이럴은 약하지만 실수요가 확인된 틈새 소재 -- 유지",
        "money_note": "전환 자체는 확인됨 -- 점수 유지",
        "creator_note": "후크를 더 강하게 다시 시도해 노출을 늘려볼 것",
    },
    ("LOW", "MONEY FAILURE"): {
        "scout_note": "반응이 약함 -- 유사 소재 우선순위 하향 또는 ARCHIVE 검토",
        "money_note": "전환 경로 자체를 재검증 필요",
        "creator_note": "완전히 다른 각도로 재작성 검토",
    },
    ("LOW", "MONEY UNKNOWN"): {
        "scout_note": "반응도 약하고 전환도 추적 안 됨 -- 판단 보류, 데이터 더 필요",
        "money_note": "전환 추적 먼저 적용한 뒤 재평가",
        "creator_note": "판단 보류",
    },
    ("UNKNOWN", "MONEY WINNER"): {
        "scout_note": "바이럴 지표는 판단 불가(베이스라인 부족)하나 전환은 확인됨",
        "money_note": "전환 자체는 확인됨 -- 점수 유지",
        "creator_note": "판단 보류",
    },
    ("UNKNOWN", "MONEY FAILURE"): {
        "scout_note": "바이럴 지표 판단 불가, 전환도 없음 -- 판단 보류",
        "money_note": "전환 경로 재검증 필요",
        "creator_note": "판단 보류",
    },
    ("UNKNOWN", "MONEY UNKNOWN"): {
        "scout_note": "판단할 데이터가 부족함 -- 계정 히스토리가 쌓일 때까지 보류",
        "money_note": "판단 보류",
        "creator_note": "판단 보류",
    },
}

_HIGH_BANDS = {"WINNER", "HOT", "BREAKOUT"}
_LOW_BANDS = {"UNDERPERFORM", "NORMAL"}


def generate_feedback(performance: dict, money_performance: dict) -> dict:
    band = performance["band"]
    tier = "HIGH" if band in _HIGH_BANDS else ("LOW" if band in _LOW_BANDS else "UNKNOWN")
    rule = _FEEDBACK_RULES[(tier, money_performance["money_verdict"])]
    return {**rule, "generated_at": _now()}
