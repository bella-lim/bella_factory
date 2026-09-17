"""PUBLISH (spec section 22 onward), gated by section 21 approval.

The one hard rule every publisher goes through first: nothing here ever
posts anything for a candidate whose approval.status != "APPROVED".
guard_approved() enforces that before any network call.

Platform capability is reported honestly, not assumed:
  - threads: real (Meta Graph API, graph.threads.net), two-step
    container -> publish flow. Requires Tech Provider Verification and a
    threads_content_publish-scoped access token from Meta.
  - youtube_shorts: real (YouTube Data API v3, resumable upload), but
    needs an actual rendered video file -- this pipeline's CREATOR only
    produces a video_prompt/script (content.youtube_shorts.video_prompt),
    never a video, so the caller must render one and supply its path.
  - naver_blog: NOT_SUPPORTED. There is no current, reliably-documented
    public API for a third party to create a post on an arbitrary
    personal Naver Blog (the only documented mechanism found is a
    MetaWeblog/XML-RPC integration described in a 2010 blog post, with no
    confirmed current support). Publishing here always returns a clear
    NOT_SUPPORTED result rather than pretending to work -- see README.

None of the network-touching functions here have been exercised against
the real APIs from this development sandbox (same constraint as PHASE 4's
Telegram integration: outbound HTTPS to arbitrary hosts is blocked by this
session's egress policy). Payload/metadata builders are pure and unit
tested; the HTTP calls built on top need to be smoke-tested from an
environment with real network access and real credentials first.
"""
from __future__ import annotations

import datetime
import json
import mimetypes
import os
import urllib.error
import urllib.parse
import urllib.request

from scout.models import ValidationError

THREADS_API_ROOT = "https://graph.threads.net/v1.0"
YOUTUBE_UPLOAD_ROOT = "https://www.googleapis.com/upload/youtube/v3/videos"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def guard_approved(candidate) -> None:
    """The single publish gate. Every publisher calls this first."""
    if candidate.approval.get("status") != "APPROVED":
        raise ValidationError(
            f"candidate {candidate.id!r} is not APPROVED (approval.status="
            f"{candidate.approval.get('status')!r}) -- publish is refused without an "
            "explicit human approval (section 21)"
        )


def _http_post_form(url: str, data: dict) -> dict:
    encoded = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(url, data=encoded, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"POST {url} failed: HTTP {e.code}: {body}") from e


# ---------- Threads ----------

def build_threads_container_payload(candidate, version: str) -> dict:
    threads_content = (candidate.content or {}).get("threads")
    if not threads_content or version not in threads_content:
        raise ValidationError(f"candidate {candidate.id!r} has no threads.{version} draft to publish")
    return {"media_type": "TEXT", "text": threads_content[version]}


def publish_threads(candidate, version: str, threads_user_id: str, access_token: str) -> dict:
    guard_approved(candidate)
    payload = build_threads_container_payload(candidate, version)
    payload["access_token"] = access_token

    container = _http_post_form(f"{THREADS_API_ROOT}/{threads_user_id}/threads", payload)
    creation_id = container.get("id")
    if not creation_id:
        return {"status": "FAILED", "error": f"container creation returned no id: {container}",
                "post_id": None, "url": None, "published_at": _now()}

    result = _http_post_form(
        f"{THREADS_API_ROOT}/{threads_user_id}/threads_publish",
        {"creation_id": creation_id, "access_token": access_token},
    )
    post_id = result.get("id")
    if not post_id:
        return {"status": "FAILED", "error": f"publish step returned no id: {result}",
                "post_id": None, "url": None, "published_at": _now()}

    return {
        "status": "PUBLISHED", "post_id": post_id, "error": None,
        "url": f"https://www.threads.net/@{threads_user_id}/post/{post_id}",
        "published_at": _now(),
    }


# ---------- Naver Blog ----------

def publish_naver_blog(candidate, **_ignored) -> dict:
    guard_approved(candidate)
    return {
        "status": "NOT_SUPPORTED", "post_id": None, "url": None,
        "error": (
            "No current, reliably-documented public API exists for a third party to create a post "
            "on an arbitrary personal Naver Blog. Publish this draft manually through Naver's own "
            "blog editor using the naver_blog fields in data/content/*.json."
        ),
        "published_at": _now(),
    }


# ---------- YouTube Shorts ----------

def build_youtube_metadata(candidate) -> dict:
    shorts = (candidate.content or {}).get("youtube_shorts")
    if not shorts:
        raise ValidationError(f"candidate {candidate.id!r} has no youtube_shorts draft to publish")
    title = shorts["titles"][0] if shorts.get("titles") else candidate.name
    return {
        "snippet": {
            "title": title,
            "description": shorts.get("description", ""),
            "tags": shorts.get("tags", []),
            "categoryId": "22",  # People & Blogs
        },
        "status": {"privacyStatus": "private", "selfDeclaredMadeForKids": False},
    }


def _get_google_access_token(client_id: str, client_secret: str, refresh_token: str) -> str:
    data = urllib.parse.urlencode({
        "client_id": client_id, "client_secret": client_secret,
        "refresh_token": refresh_token, "grant_type": "refresh_token",
    }).encode("utf-8")
    req = urllib.request.Request(GOOGLE_TOKEN_URL, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))["access_token"]


def publish_youtube_shorts(candidate, video_file_path: str, client_id: str,
                            client_secret: str, refresh_token: str) -> dict:
    guard_approved(candidate)
    if not video_file_path or not os.path.exists(video_file_path):
        return {
            "status": "FAILED", "post_id": None, "url": None,
            "error": (
                f"no video file at {video_file_path!r} -- this pipeline's CREATOR only produces a "
                "video_prompt/script (content.youtube_shorts.video_prompt), never a rendered video; "
                "render one first and pass its path"
            ),
            "published_at": _now(),
        }

    metadata = build_youtube_metadata(candidate)
    access_token = _get_google_access_token(client_id, client_secret, refresh_token)

    init_req = urllib.request.Request(
        f"{YOUTUBE_UPLOAD_ROOT}?uploadType=resumable&part=snippet,status",
        data=json.dumps(metadata).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Type": mimetypes.guess_type(video_file_path)[0] or "video/mp4",
        },
        method="POST",
    )
    with urllib.request.urlopen(init_req, timeout=30) as resp:
        upload_url = resp.headers.get("Location")
    if not upload_url:
        return {"status": "FAILED", "post_id": None, "url": None,
                "error": "resumable upload session did not return a Location header", "published_at": _now()}

    with open(video_file_path, "rb") as f:
        video_bytes = f.read()
    upload_req = urllib.request.Request(
        upload_url, data=video_bytes,
        headers={"Content-Type": mimetypes.guess_type(video_file_path)[0] or "video/mp4"},
        method="PUT",
    )
    with urllib.request.urlopen(upload_req, timeout=600) as resp:
        result = json.loads(resp.read().decode("utf-8"))

    video_id = result.get("id")
    return {
        "status": "PUBLISHED" if video_id else "FAILED",
        "post_id": video_id,
        "url": f"https://youtube.com/shorts/{video_id}" if video_id else None,
        "error": None if video_id else f"upload response had no id: {result}",
        "published_at": _now(),
    }


def apply_publish_result(db: dict, candidate_id: str, platform: str, result: dict) -> "Candidate":
    from dataclasses import replace
    from scout.storage import get, upsert

    candidate = get(db, candidate_id)
    if candidate is None:
        raise ValidationError(f"candidate {candidate_id!r} not found in database")

    publish_status = dict(candidate.publish_status)
    publish_status[platform] = result
    updated = replace(candidate, publish_status=publish_status)
    upsert(db, updated)
    return updated
