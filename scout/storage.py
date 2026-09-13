"""Persistent candidate storage (MONEY SIGNAL DATABASE, spec section 27).

A plain JSON file is used instead of a binary database so that the
long-term asset described in section 27/28 stays human-readable and
diffable in git history -- every write is a full, inspectable snapshot.
"""
from __future__ import annotations

import json
import os
from typing import Iterable

from scout.models import Candidate

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "candidates.json")


def load_db(path: str = DEFAULT_DB_PATH) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return raw


def save_db(db: dict, path: str = DEFAULT_DB_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2, sort_keys=True)
    os.replace(tmp_path, path)


def get_all(db: dict) -> list[Candidate]:
    return [Candidate.from_dict(v) for v in db.values()]


def get(db: dict, candidate_id: str) -> Candidate | None:
    v = db.get(candidate_id)
    return Candidate.from_dict(v) if v else None


def upsert(db: dict, candidate: Candidate) -> None:
    db[candidate.id] = candidate.to_dict()


def by_track(db: dict, track: str) -> list[Candidate]:
    return [c for c in get_all(db) if c.track == track]


def seen_on(db: dict, date_str: str) -> list[Candidate]:
    """Candidates first detected or re-checked on the given date (YYYY-MM-DD)."""
    return [c for c in get_all(db) if c.first_detected == date_str or c.last_checked == date_str]
