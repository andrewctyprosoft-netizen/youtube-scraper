"""Turn pasted text into YouTube targets. Pure logic, no network.

Accepts messy input: one link per line, links inside sentences, bare video
IDs, ``youtu.be`` / ``shorts`` / ``embed`` / ``live`` links, playlists,
channels (``@handle``, ``/channel/UC…``) and plain words (searched).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

_URL = re.compile(r"(?:https?://)?(?:[\w-]+\.)*(?:youtube\.com|youtu\.be|youtube-nocookie\.com)/[^\s<>\"']*", re.I)
_VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
_PLAYLIST_ID = re.compile(r"^(?:PL|UU|LL|FL|OL|RD)[A-Za-z0-9_-]{10,}$")


@dataclass(frozen=True)
class Target:
    """Something to fetch: ``kind`` is video, playlist, channel or search."""

    kind: str
    url: str
    label: str

    @property
    def is_video(self) -> bool:
        """True for a single video."""
        return self.kind == "video"


def looks_like_id(token: str) -> bool:
    """True for an 11-char video ID that is unlikely to be an ordinary word."""
    if not _VIDEO_ID.match(token):
        return False
    has_mark = any(ch.isdigit() or ch in "-_" for ch in token)
    mixed = any(ch.isupper() for ch in token) and any(ch.islower() for ch in token)
    return has_mark or mixed


def video_url(video_id: str) -> str:
    """Canonical watch URL for a video ID."""
    return f"https://www.youtube.com/watch?v={video_id}"


def classify_url(raw: str) -> Target | None:
    """Classify one YouTube URL; ``None`` when it is not a usable YouTube link."""
    url = raw.strip().rstrip(".,;)]}>")
    if not url.lower().startswith("http"):
        url = "https://" + url
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path
    query = parse_qs(parsed.query)
    segments = [s for s in path.split("/") if s]

    if host.endswith("youtu.be") and segments and _VIDEO_ID.match(segments[0]):
        return Target("video", video_url(segments[0]), segments[0])

    if "youtube" not in host:
        return None

    vid = (query.get("v") or [""])[0]
    if path.startswith("/watch") and _VIDEO_ID.match(vid):
        # A watch link inside a playlist is still treated as the one video;
        # paste the playlist link itself to get every video.
        return Target("video", video_url(vid), vid)
    if segments and segments[0] in {"shorts", "embed", "live", "v", "e"} and len(segments) > 1:
        if _VIDEO_ID.match(segments[1]):
            return Target("video", video_url(segments[1]), segments[1])

    plist = (query.get("list") or [""])[0]
    if plist and (path.startswith("/playlist") or not vid):
        return Target("playlist", f"https://www.youtube.com/playlist?list={plist}", plist)

    if segments:
        first = segments[0]
        if first.startswith("@") or first in {"channel", "c", "user"}:
            base_len = 1 if first.startswith("@") else 2
            if len(segments) < base_len:
                return None
            base = "/".join(segments[:base_len])
            tab = segments[base_len] if len(segments) > base_len else "videos"
            if tab not in {"videos", "shorts", "streams", "playlists", "podcasts"}:
                tab = "videos"
            return Target("channel", f"https://www.youtube.com/{base}/{tab}", base)
    return None


def parse_input(text: str) -> tuple[list[Target], list[str]]:
    """Split pasted text into targets.

    Returns ``(targets, searches)``: every YouTube link or bare ID found, in
    order and without duplicates, and the lines that hold no link (to be
    searched on YouTube). Lines starting with ``#`` are comments.
    """
    targets: list[Target] = []
    searches: list[str] = []
    seen: set[str] = set()

    def add(target: Target | None) -> None:
        if target and target.url not in seen:
            seen.add(target.url)
            targets.append(target)

    for line in text.splitlines():
        line = line.strip().lstrip("﻿")
        if not line or line.startswith("#"):
            continue
        found = _URL.findall(line)
        if found:
            for url in found:
                add(classify_url(url))
            continue
        tokens = line.split()
        if all(looks_like_id(t) or _PLAYLIST_ID.match(t) for t in tokens):
            for tok in tokens:
                if _PLAYLIST_ID.match(tok) and not looks_like_id(tok):
                    add(Target("playlist", f"https://www.youtube.com/playlist?list={tok}", tok))
                else:
                    add(Target("video", video_url(tok), tok))
            continue
        searches.append(line)
    return targets, searches


def search_url(query: str, count: int) -> str:
    """yt-dlp search pseudo-URL."""
    return f"ytsearch{max(1, min(count, 200))}:{query}"
