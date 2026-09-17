"""CREATOR AGENT (spec section 18): Threads / Naver Blog / YouTube Shorts drafts.

This module only validates structure -- required fields present, Threads
length limits respected, at least one draft platform supplied. It never
generates or judges content quality; that's done by the research/writing
step (Hermes using the threads-viral-writer skill etc.) that produces the
raw JSON this module consumes, mirroring how PHASE 1/2 split research from
the deterministic pipeline.
"""
from __future__ import annotations

from scout.models import (
    NAVER_BLOG_FIELDS, THREADS_MAX_CHARS, THREADS_VERSIONS,
    YOUTUBE_SHORTS_FIELDS, ValidationError,
)


def validate_threads(raw: dict) -> list[str]:
    errors = []
    missing = THREADS_VERSIONS - set(raw)
    if missing:
        errors.append(f"threads content missing versions: {sorted(missing)}")

    for version, text in raw.items():
        if version not in THREADS_VERSIONS:
            errors.append(f"unknown threads version {version!r} (must be one of {sorted(THREADS_VERSIONS)})")
            continue
        if not str(text).strip():
            errors.append(f"threads.{version} must not be empty")
        elif len(text) > THREADS_MAX_CHARS:
            errors.append(
                f"threads.{version} is {len(text)} chars, over the {THREADS_MAX_CHARS}-char single-post "
                "limit -- split into a chain instead of submitting an oversized single post"
            )
    return errors


def validate_naver_blog(raw: dict) -> list[str]:
    errors = []
    missing = NAVER_BLOG_FIELDS - set(raw)
    if missing:
        errors.append(f"naver_blog missing fields: {sorted(missing)}")

    titles = raw.get("titles")
    if titles is not None and (not isinstance(titles, list) or len(titles) != 3):
        errors.append(f"naver_blog.titles must be a list of exactly 3 SEO title options, got {titles!r}")

    sub_keywords = raw.get("sub_keywords")
    if sub_keywords is not None and not isinstance(sub_keywords, list):
        errors.append("naver_blog.sub_keywords must be a list")

    faq = raw.get("faq")
    if faq is not None and (not isinstance(faq, list) or not faq):
        errors.append("naver_blog.faq must be a non-empty list of {question, answer} entries")

    for field_name in ("main_keyword", "hook", "problem", "situation", "cause",
                        "solution", "selection_criteria", "product_service", "closing"):
        if field_name in raw and not str(raw[field_name]).strip():
            errors.append(f"naver_blog.{field_name} must not be empty")
    return errors


def validate_youtube_shorts(raw: dict) -> list[str]:
    errors = []
    missing = YOUTUBE_SHORTS_FIELDS - set(raw)
    if missing:
        errors.append(f"youtube_shorts missing fields: {sorted(missing)}")

    titles = raw.get("titles")
    if titles is not None and (not isinstance(titles, list) or len(titles) != 5):
        errors.append(f"youtube_shorts.titles must be a list of exactly 5 title options, got {titles!r}")

    thumbs = raw.get("thumbnail_texts")
    if thumbs is not None and (not isinstance(thumbs, list) or len(thumbs) != 3):
        errors.append(f"youtube_shorts.thumbnail_texts must be a list of exactly 3 options, got {thumbs!r}")

    tags = raw.get("tags")
    if tags is not None and not isinstance(tags, list):
        errors.append("youtube_shorts.tags must be a list")

    for field_name in ("hook", "problem", "discovery_solution", "core", "cta",
                        "broll", "subtitles", "video_prompt", "description"):
        if field_name in raw and not str(raw[field_name]).strip():
            errors.append(f"youtube_shorts.{field_name} must not be empty")
    return errors


def build_content(raw: dict) -> dict:
    """raw may contain any subset of 'threads' / 'naver_blog' / 'youtube_shorts'
    -- CREATOR does not require every platform, only that whatever is
    supplied is structurally complete."""
    if not raw:
        raise ValidationError("content must include at least one of threads/naver_blog/youtube_shorts")

    errors = []
    if "threads" in raw:
        errors += validate_threads(raw["threads"])
    if "naver_blog" in raw:
        errors += validate_naver_blog(raw["naver_blog"])
    if "youtube_shorts" in raw:
        errors += validate_youtube_shorts(raw["youtube_shorts"])

    unknown = set(raw) - {"threads", "naver_blog", "youtube_shorts"}
    if unknown:
        errors.append(f"unknown content platforms: {sorted(unknown)}")

    if errors:
        raise ValidationError("; ".join(errors))

    return raw
