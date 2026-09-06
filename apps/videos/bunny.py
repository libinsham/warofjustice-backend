"""
Bunny Stream integration. The API key NEVER goes to the frontend — every
call to Bunny's API happens server-side from Django. The browser only ever
talks to Bunny directly for the actual video byte upload, using a short-
lived, single-use upload URL/signature we generate here.
"""
import hashlib
import time

import requests
from django.conf import settings

BUNNY_API_BASE = "https://video.bunnycdn.com/library"


def _headers():
    return {"AccessKey": settings.BUNNY_STREAM_API_KEY, "Content-Type": "application/json"}


def create_video(title: str) -> dict:
    """Step 1: ask Bunny to create a video slot; returns its guid.
    The browser then uploads the actual file bytes directly to Bunny
    using that guid — large video files never pass through Django."""
    url = f"{BUNNY_API_BASE}/{settings.BUNNY_STREAM_LIBRARY_ID}/videos"
    resp = requests.post(url, json={"title": title}, headers=_headers(), timeout=15)
    resp.raise_for_status()
    return resp.json()  # {"guid": "...", ...}


def generate_upload_signature(video_guid: str, expires_in: int = 3600) -> dict:
    """
    Bunny's TUS-resumable-upload signature scheme:
    sha256(library_id + api_key + expiration + video_guid)
    The frontend uses this directly with tus-js-client against
    https://video.bunnycdn.com/tusupload — Django never touches the bytes.
    """
    expiration = int(time.time()) + expires_in
    raw = f"{settings.BUNNY_STREAM_LIBRARY_ID}{settings.BUNNY_STREAM_API_KEY}{expiration}{video_guid}"
    signature = hashlib.sha256(raw.encode()).hexdigest()

    return {
        "endpoint": "https://video.bunnycdn.com/tusupload",
        "library_id": settings.BUNNY_STREAM_LIBRARY_ID,
        "video_guid": video_guid,
        "expiration": expiration,
        "signature": signature,
    }


def get_video_status(video_guid: str) -> dict:
    url = f"{BUNNY_API_BASE}/{settings.BUNNY_STREAM_LIBRARY_ID}/videos/{video_guid}"
    resp = requests.get(url, headers=_headers(), timeout=15)
    resp.raise_for_status()
    return resp.json()


def delete_video(video_guid: str) -> None:
    url = f"{BUNNY_API_BASE}/{settings.BUNNY_STREAM_LIBRARY_ID}/videos/{video_guid}"
    resp = requests.delete(url, headers=_headers(), timeout=15)
    resp.raise_for_status()


def build_playback_url(video_guid: str) -> str:
    return f"https://{settings.BUNNY_STREAM_CDN_HOSTNAME}/{video_guid}/playlist.m3u8"


def build_thumbnail_url(video_guid: str) -> str:
    return f"https://{settings.BUNNY_STREAM_CDN_HOSTNAME}/{video_guid}/thumbnail.jpg"
