"""ANALYST AGENT (spec section 16): distill VIRAL DNA from a candidate.

Input is a raw research note per candidate: the angles listed in section 16
(topic/hook/emotion/problem/desire/format/structure/comment trigger/
shopping signal/replicability) plus, when the analysis was grounded in a
real example post, the literal text of that example. The output stores only
the distilled *principle* -- never the literal example -- per section 16's
"복사 금지. 원리만 저장한다."
"""
from __future__ import annotations

from scout.models import VIRAL_DNA_FIELDS, ValidationError


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def validate_viral_dna(raw: dict) -> list[str]:
    errors = []

    missing = VIRAL_DNA_FIELDS - set(raw)
    if missing:
        errors.append(f"viral_dna missing fields: {sorted(missing)}")

    replicability = raw.get("replicability")
    if not isinstance(replicability, (int, float)) or not (0 <= replicability <= 100):
        errors.append(f"replicability must be a number in [0, 100], got {replicability!r}")

    hook_principle = raw.get("hook_principle", "")
    if not hook_principle or not hook_principle.strip():
        errors.append("hook_principle is required (the distilled principle, not the example text)")

    example = raw.get("source_hook_example", "")
    if example and hook_principle and _normalize(example) == _normalize(hook_principle):
        errors.append(
            "hook_principle must not be a verbatim copy of source_hook_example -- "
            "extract the underlying principle instead (section 16: 복사 금지)"
        )

    for field_name in ("topic", "emotion", "problem", "desire", "format", "structure",
                        "comment_trigger", "shopping_signal"):
        if not str(raw.get(field_name, "")).strip():
            errors.append(f"{field_name} must not be empty")

    return errors


def build_viral_dna(raw: dict) -> dict:
    errors = validate_viral_dna(raw)
    if errors:
        raise ValidationError("; ".join(errors))

    return {
        "topic": raw["topic"],
        "hook_principle": raw["hook_principle"],
        "source_note": raw.get("source_note", ""),
        "emotion": raw["emotion"],
        "problem": raw["problem"],
        "desire": raw["desire"],
        "format": raw["format"],
        "structure": raw["structure"],
        "comment_trigger": raw["comment_trigger"],
        "shopping_signal": raw["shopping_signal"],
        "replicability": raw["replicability"],
    }
