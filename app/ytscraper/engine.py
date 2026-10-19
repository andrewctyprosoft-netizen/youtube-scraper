"""Find and run the external engines (yt-dlp, deno, ffmpeg).

yt-dlp runs as a separate ``yt-dlp.exe`` in ``tools/`` so it can update itself
(``yt-dlp -U``) without rebuilding this app: YouTube changes often and a stale
yt-dlp is the usual reason downloads stop working.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Callable, Iterable

from .links import video_url

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


class Cancelled(Exception):
    """Raised when the user pressed Stop."""


class EngineError(Exception):
    """yt-dlp failed; ``str(exc)`` is a short, user-facing reason."""


def app_dir() -> Path:
    """Folder holding the app (the .exe when frozen, the project root in dev)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


@dataclass
class Tools:
    """Resolved engine locations."""

    ytdlp: list[str]
    deno: Path | None
    node: str | None
    ffmpeg_dir: Path | None
    frozen_ytdlp: bool  # True when yt-dlp.exe can self-update

    @classmethod
    def discover(cls, base: Path | None = None) -> "Tools":
        """Look in ``<app>/tools`` first, then PATH, then the dev venv."""
        tools = (base or app_dir()) / "tools"
        exe = tools / "yt-dlp.exe"
        if exe.exists():
            ytdlp, frozen = [str(exe)], True
        elif shutil.which("yt-dlp"):
            ytdlp, frozen = [shutil.which("yt-dlp")], True  # type: ignore[list-item]
        else:
            ytdlp, frozen = [sys.executable, "-m", "yt_dlp"], False
        deno = tools / "deno.exe"
        deno_path = deno if deno.exists() else (Path(p) if (p := shutil.which("deno")) else None)
        ffmpeg = tools / "ffmpeg.exe"
        if ffmpeg.exists():
            ffmpeg_dir: Path | None = tools
        elif p := shutil.which("ffmpeg"):
            ffmpeg_dir = Path(p).parent
        else:
            ffmpeg_dir = None
        return cls(ytdlp, deno_path, shutil.which("node"), ffmpeg_dir, frozen)

    def base_args(self) -> list[str]:
        """Arguments every yt-dlp call gets."""
        args = ["--ignore-config", "--no-color", "--newline", "--encoding", "utf-8", "--no-update"]
        if self.deno:
            args += ["--js-runtimes", f"deno:{self.deno}"]
        elif self.node:
            args += ["--js-runtimes", f"node:{self.node}"]
        if self.ffmpeg_dir:
            args += ["--ffmpeg-location", str(self.ffmpeg_dir)]
        return args


@dataclass
class Auth:
    """Optional login cookies for age-restricted or members-only videos."""

    browser: str = ""  # firefox, edge, chrome, brave …
    cookies_file: str = ""

    def args(self) -> list[str]:
        """yt-dlp cookie arguments."""
        if self.cookies_file:
            return ["--cookies", self.cookies_file]
        if self.browser:
            return ["--cookies-from-browser", self.browser]
        return []


@dataclass
class Entry:
    """One video in the list."""

    id: str
    title: str
    url: str
    duration: float | None = None
    channel: str = ""
    source: str = ""  # playlist / channel / search it came from
    extra: dict = field(default_factory=dict)


Runner = Callable[[list[str], Callable[[str], None] | None, threading.Event | None], tuple[int, str]]


def run_process(
    cmd: list[str],
    on_line: Callable[[str], None] | None = None,
    cancel: threading.Event | None = None,
) -> tuple[int, str]:
    """Run ``cmd`` hidden; stream lines to ``on_line``; return (code, output)."""
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        creationflags=CREATE_NO_WINDOW,
        env=env,
    )
    lines: list[str] = []
    stop_watch = threading.Event()

    def watch() -> None:
        while not stop_watch.wait(0.2):
            if cancel is not None and cancel.is_set() and proc.poll() is None:
                proc.kill()
                return

    watcher = threading.Thread(target=watch, daemon=True)
    watcher.start()
    assert proc.stdout is not None
    for raw in proc.stdout:
        line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
        # Video-info JSON lines can be 10 MB each: pass them on, never keep them.
        lines.append(line if len(line) < 4000 else "<json>")
        if on_line:
            on_line(line)
    code = proc.wait()
    stop_watch.set()
    if cancel is not None and cancel.is_set():
        raise Cancelled()
    return code, "\n".join(lines)


_ERROR_HINTS = [
    (re.compile(r"HTTP Error 429|Too Many Requests", re.I), "rate_limited"),
    (re.compile(r"Sign in to confirm (you're|you are) not a bot", re.I), "bot_check"),
    (re.compile(r"Sign in to confirm your age|age-restricted|inappropriate for some users", re.I), "age"),
    (re.compile(r"members-only|join this channel", re.I), "members"),
    (re.compile(r"Private video", re.I), "private"),
    (re.compile(r"Video unavailable|This video is not available|has been removed", re.I), "unavailable"),
    (re.compile(r"Premieres in|live event will begin", re.I), "upcoming"),
    (re.compile(r"ffmpeg not found|ffprobe and ffmpeg not found", re.I), "no_ffmpeg"),
    (re.compile(r"Unable to download webpage|getaddrinfo failed|timed out|Connection", re.I), "network"),
    (re.compile(r"page needs to be reloaded|nsig extraction failed|Requested format is not available", re.I), "outdated"),
]


def classify_error(output: str) -> str:
    """Map yt-dlp output to a short error code (see i18n ``err_*``)."""
    for pattern, code in _ERROR_HINTS:
        if pattern.search(output):
            return code
    return "unknown"


def last_error_line(output: str) -> str:
    """The last ``ERROR:`` line of yt-dlp output, for the details log."""
    errors = [ln for ln in output.splitlines() if ln.startswith("ERROR")]
    return errors[-1] if errors else (output.strip().splitlines() or [""])[-1]


class Engine:
    """High-level yt-dlp operations used by the jobs and the GUI."""

    def __init__(self, tools: Tools | None = None, runner: Runner | None = None, auth: Auth | None = None):
        self.tools = tools or Tools.discover()
        self.runner: Runner = runner or run_process
        self.auth = auth or Auth()

    def cmd(self, args: Iterable[str]) -> list[str]:
        """Full yt-dlp command line."""
        return [*self.tools.ytdlp, *self.tools.base_args(), *self.auth.args(), *args]

    def version(self) -> str:
        """Installed yt-dlp version, e.g. ``2026.08.19``."""
        code, out = self.runner([*self.tools.ytdlp, "--version"], None, None)
        lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
        return lines[-1] if code == 0 and lines else ""

    @staticmethod
    def version_age_days(version: str, today: date | None = None) -> int | None:
        """Days since the release in ``version`` (``YYYY.MM.DD``)."""
        match = re.match(r"(\d{4})\.(\d{1,2})\.(\d{1,2})", version)
        if not match:
            return None
        released = date(*(int(g) for g in match.groups()))
        return ((today or date.today()) - released).days

    def update(self, on_line: Callable[[str], None] | None = None) -> tuple[bool, str]:
        """Self-update yt-dlp.exe; returns (ok, output)."""
        if self.tools.frozen_ytdlp:
            code, out = self.runner([*self.tools.ytdlp, "-U"], on_line, None)
        else:
            code, out = self.runner(
                [sys.executable, "-m", "pip", "install", "-U", "yt-dlp[default]"], on_line, None
            )
        return code == 0, out

    def list_entries(
        self,
        url: str,
        source: str = "",
        cancel: threading.Event | None = None,
        limit: int = 0,
    ) -> list[Entry]:
        """Expand a playlist / channel / search URL into its videos (fast, flat)."""
        args = ["--flat-playlist", "-J", "--no-warnings"]
        if limit:
            args += ["--playlist-end", str(limit)]
        big: list[str] = []  # the -J line can be megabytes; run_process does not keep it
        code, out = self.runner(self.cmd([*args, url]), lambda ln: big.append(ln) if ln.startswith("{") else None,
                                cancel)
        data = _json_from_output(big[-1] if big else out)
        if data is None:
            raise EngineError(classify_error(out) if code else "unknown")
        name = source or data.get("title") or data.get("channel") or url
        entries: list[Entry] = []
        for item in data.get("entries") or [data]:
            if not item:
                continue
            if item.get("_type") == "playlist" or (
                item.get("ie_key") == "YoutubeTab" and "list=" in (item.get("url") or "")
            ):
                # A channel's playlists tab: expand each playlist one level.
                entries += self.list_entries(item["url"], item.get("title") or name, cancel, limit)
                continue
            vid = item.get("id") or ""
            if not vid or len(vid) != 11:
                continue
            entries.append(
                Entry(
                    id=vid,
                    title=item.get("title") or vid,
                    url=video_url(vid),
                    duration=item.get("duration"),
                    channel=item.get("channel") or item.get("uploader") or data.get("channel") or "",
                    source=name if (data.get("entries") is not None) else "",
                    extra={k: item[k] for k in ("upload_date", "timestamp") if item.get(k)},
                )
            )
        return entries

    # Only what a transcript needs: the watch page and one player API call. No
    # stream lists (hls/dash), no player JavaScript (no Deno run per video).
    LIGHT_EXTRACT = "youtube:skip=hls,dash,translated_subs;player_skip=js"

    def stream_infos(
        self,
        urls: list[str],
        batch_file: Path,
        on_info: Callable[[dict], None],
        on_line: Callable[[str], None] | None = None,
        cancel: threading.Event | None = None,
        sleep_requests: float = 0.0,
    ) -> tuple[int, str]:
        """Extract many videos in ONE yt-dlp process; ``on_info`` gets each video's info.

        One process avoids the engine start-up per video, and nothing is
        downloaded: captions are fetched separately by the caller.
        """
        batch_file.write_text("\n".join(urls) + "\n", encoding="utf-8")
        args = ["-j", "-i", "--ignore-no-formats-error", "--extractor-args", self.LIGHT_EXTRACT,
                "-a", str(batch_file)]
        if sleep_requests > 0:
            args += ["--sleep-requests", f"{sleep_requests:g}"]

        def route(line: str) -> None:
            if line.startswith("{"):
                try:
                    on_info(json.loads(line))
                    return
                except json.JSONDecodeError:
                    pass
            if on_line:
                on_line(line)

        return self.runner(self.cmd(args), route, cancel)

    def http_get(self, url: str, timeout: float = 30.0) -> bytes:
        """Plain GET (caption files, thumbnails). Raises ``urllib.error.HTTPError``."""
        return http_get(url, timeout)

    def run_download(
        self,
        args: list[str],
        url: str,
        on_line: Callable[[str], None] | None = None,
        cancel: threading.Event | None = None,
    ) -> tuple[int, str]:
        """Run one download command for ``url``."""
        tail = ["--", url] if url else []
        return self.runner(self.cmd([*args, *tail]), on_line, cancel)


def _json_from_output(out: str) -> dict | None:
    """Find the JSON document in yt-dlp ``-J`` output (warnings may surround it)."""
    start = out.find("{")
    end = out.rfind("}")
    if start < 0 or end < start:
        return None
    try:
        return json.loads(out[start : end + 1])
    except json.JSONDecodeError:
        for line in out.splitlines():
            if line.startswith("{"):
                try:
                    return json.loads(line)
                except json.JSONDecodeError:
                    continue
    return None


BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36")


def http_get(url: str, timeout: float = 30.0) -> bytes:
    """GET ``url`` with a browser User-Agent and return the body."""
    req = urllib.request.Request(url, headers={"User-Agent": BROWSER_UA, "Accept-Language": "en-US,en;q=0.9"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def oembed_title(video_id: str, timeout: float = 8.0) -> tuple[str, str] | None:
    """Quick (title, channel) lookup for one video without running yt-dlp."""
    url = "https://www.youtube.com/oembed?format=json&url=" + urllib.parse.quote(video_url(video_id), safe="")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data.get("title") or video_id, data.get("author_name") or ""
    except Exception:  # noqa: BLE001 - any failure just means "unknown title"
        return None
