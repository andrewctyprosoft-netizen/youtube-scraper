"""Download jobs: run yt-dlp per video, clean captions, write the outputs.

Everything reports through ``emit(kind, **data)`` so the GUI (or a test)
can follow along. Kinds: ``log``, ``row`` (per-video status), ``progress``,
``done``.
"""
from __future__ import annotations

import csv
import json
import os
import queue
import re
import threading
import time
import unicodedata
import urllib.error
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

from . import captions as cap
from .docx_export import DocOptions, DocSection, build_docx
from .engine import Cancelled, Engine, Entry, classify_error, last_error_line

Emit = Callable[..., None]
SUB_EXTS = (".vtt", ".srt", ".srv3", ".ttml", ".json3")
_PERCENT = re.compile(r"\[download\]\s+(\d+(?:\.\d+)?)%")
_INVALID = re.compile(r'[<>"?*\x00-\x1f]')
_SWAP = str.maketrans({"/": "-", "\\": "-", "|": "-", ":": " -", "｜": "-", "／": "-"})
_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


@dataclass
class JobOptions:
    """What to download and how to write it."""

    out_dir: Path
    want_transcript: bool = True
    want_video: bool = False
    want_audio: bool = False
    want_thumbnail: bool = False
    language: str = "en"  # language code, or "orig" for the spoken language
    fallback_original: bool = True
    allow_auto: bool = True
    layout: str = "paragraphs"  # or "lines"
    timestamps: bool = False
    remove_rolling: bool = True
    remove_all_repeats: bool = False
    remove_tags: bool = True
    save_docx: bool = True
    save_txt: bool = False
    save_srt: bool = False
    save_combined_txt: bool = False
    save_csv: bool = True
    output_name: str = "Transcripts"
    docx: DocOptions = field(default_factory=DocOptions)
    video_quality: str = "720"  # best | 1080 | 720 | 480 | 360
    numbered: bool = False
    order: str = "list"  # list | az | za: file numbers and order in the Word/TXT/CSV files
    reuse_cache: bool = True
    delay: float = 1.0  # seconds between videos (yt-dlp gets half of it per request)
    workers: int = 2  # parallel yt-dlp processes for transcripts / metadata
    folders: dict[str, str] = field(
        default_factory=lambda: {
            "transcripts": "Transcripts",
            "subtitles": "Subtitles",
            "videos": "Videos",
            "audio": "Audio",
            "thumbnails": "Thumbnails",
        }
    )


@dataclass
class VideoResult:
    """Outcome for one video."""

    entry: Entry
    status: str = "pending"  # done | no_captions | error | skipped
    error: str = ""
    language: str = ""
    meta: dict = field(default_factory=dict)
    blocks: list[str] = field(default_factory=list)
    cues: list[cap.Cue] = field(default_factory=list)
    files: list[Path] = field(default_factory=list)
    available: list[str] = field(default_factory=list)
    from_cache: bool = False


# ---------------------------------------------------------------- helpers


def safe_filename(name: str, limit: int = 150) -> str:
    """Windows-safe file name (keeps Vietnamese and other letters)."""
    name = _INVALID.sub("", name.translate(_SWAP))
    name = re.sub(r"\s+", " ", name)
    name = re.sub(r"(\s*-\s*){2,}", " - ", name).strip(" -").rstrip(". ")
    if len(name) > limit:
        name = name[:limit].rstrip(". ")
    if not name or name.upper().split(".")[0] in _RESERVED:
        name = f"_{name}" if name else "untitled"
    return name


def unique_path(path: Path, used: set[str]) -> Path:
    """Add `` (2)``, `` (3)`` … until the path was not used in this run."""
    candidate, n = path, 2
    while str(candidate).lower() in used:
        candidate = path.with_name(f"{path.stem} ({n}){path.suffix}")
        n += 1
    used.add(str(candidate).lower())
    return candidate


def write_text_safely(path: Path, text: str, encoding: str = "utf-8") -> Path:
    """Write; if the file is open elsewhere (locked), write ``name (2).ext``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    for n in range(1, 50):
        target = path if n == 1 else path.with_name(f"{path.stem} ({n}){path.suffix}")
        try:
            target.write_text(text, encoding=encoding, newline="\n")
            return target
        except PermissionError:
            continue
    raise PermissionError(str(path))


def save_docx_safely(sections: list[DocSection], path: Path, options: DocOptions) -> Path:
    """Like :func:`write_text_safely` for Word files (Word locks open files)."""
    for n in range(1, 50):
        target = path if n == 1 else path.with_name(f"{path.stem} ({n}){path.suffix}")
        try:
            return build_docx(sections, target, options)
        except PermissionError:
            continue
    raise PermissionError(str(path))


def format_duration(seconds: float | None) -> str:
    """``1:02:03`` / ``4:05``; empty when unknown."""
    if not seconds:
        return ""
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def format_date(yyyymmdd: str | None) -> str:
    """``20261015`` -> ``2026-10-15``."""
    if yyyymmdd and len(yyyymmdd) == 8 and yyyymmdd.isdigit():
        return f"{yyyymmdd[:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:]}"
    return yyyymmdd or ""


def slim_meta(info: dict) -> dict:
    """The few metadata fields worth caching."""
    return {
        "id": info.get("id"),
        "title": info.get("title"),
        "channel": info.get("channel") or info.get("uploader") or "",
        "upload_date": info.get("upload_date") or "",
        "duration": info.get("duration"),
        "view_count": info.get("view_count"),
        "like_count": info.get("like_count"),
        "webpage_url": info.get("webpage_url"),
        "language": info.get("language") or "",
        "description": (info.get("description") or "")[:2000],
        "subtitles": sorted((info.get("subtitles") or {}).keys()),
        "automatic_captions": sorted(
            k for k in (info.get("automatic_captions") or {}) if k.endswith("-orig") or "-" not in k
        ),
    }


def pick_fallback_language(meta: dict) -> str | None:
    """Best language to use when the requested one is missing.

    Human-made subtitles in the spoken language, then the auto captions of
    the spoken language (``xx-orig``), then other subtitles (English first).
    YouTube also lists ``-orig`` tracks for AI-dubbed audio (a Vietnamese
    video can have ``en-orig``), so the spoken language decides first.
    """
    manual = [s for s in meta.get("subtitles", []) if s != "live_chat"]
    auto = meta.get("automatic_captions", [])
    orig = [a for a in auto if a.endswith("-orig")]
    spoken = (meta.get("language") or "").split("-")[0].lower()
    if spoken:
        for code in manual:
            if code.split("-")[0].lower() == spoken:
                return code
        for code in orig:
            if code.split("-")[0].lower() == spoken:
                return code
    if len(orig) == 1:
        return orig[0]

    def english_first(codes: list[str]) -> str | None:
        return next((c for c in codes if c.split("-")[0] == "en"), codes[0] if codes else None)

    return english_first(manual) or english_first(orig) or ("en" if "en" in auto else None)


def find_subtitle(folder: Path, video_id: str, lang: str) -> Path | None:
    """The subtitle file for ``video_id`` in ``lang`` (or ``lang-orig``).

    Strict on purpose: the cache folder may hold other languages from
    earlier runs, which must never be picked up by accident.
    """
    for code in (lang, f"{lang}-orig"):
        for ext in SUB_EXTS:
            path = folder / f"{video_id}.{code}{ext}"
            if path.exists():
                return path
    return None


def subtitle_language(path: Path, video_id: str) -> str:
    """Language code in ``<id>.<lang>.vtt``."""
    return path.name[len(video_id) + 1 : -len(path.suffix)]


def hide_folder(path: Path) -> None:
    """Mark a folder hidden on Windows (best effort)."""
    if os.name == "nt":
        try:
            import ctypes

            ctypes.windll.kernel32.SetFileAttributesW(str(path), 0x02)
        except Exception:  # noqa: BLE001
            pass


def title_from_filename(name: str) -> str:
    """``012 - My talk [dQw4w9WgXcQ].vi-orig.srt`` -> ``012 - My talk``."""
    stem = name
    for _ in range(3):
        base, dot, ext = stem.rpartition(".")
        if dot and (ext.lower() in {"srt", "vtt", "txt", "orig"} or re.fullmatch(r"[a-z]{2,3}(-[A-Za-z0-9]+)*", ext)):
            stem = base
    stem = re.sub(r"\s*\[[A-Za-z0-9_-]{11}\]$", "", stem)
    return stem.strip() or name


def title_sort_key(title: str) -> tuple:
    """A→Z key that ignores accents, case and leading symbols, and reads numbers as numbers.

    ``Ánh`` sorts with ``Anh``, ``Đà`` with ``Da``, ``Part 2`` before ``Part 10``.
    """
    text = (title or "").replace("đ", "d").replace("Đ", "D")
    text = "".join(c for c in unicodedata.normalize("NFD", text) if not unicodedata.combining(c))
    text = re.sub(r"^[\W_]+", "", text.casefold())
    return natural_key(text), title or ""


def file_order(titles: list[str], order: str) -> list[int]:
    """Indices of ``titles`` in output order (``list``, ``az`` or ``za``)."""
    idx = list(range(len(titles)))
    if order in ("az", "za"):
        idx.sort(key=lambda i: title_sort_key(titles[i]), reverse=(order == "za"))
    return idx


def choose_caption(meta: dict, requested: str, *, fallback_original: bool = True,
                   allow_auto: bool = True) -> tuple[str, str] | None:
    """Pick the caption track to fetch: ``(code, source)`` or ``None``.

    ``source`` is ``manual`` (made by a person), ``auto`` (YouTube's speech
    recognition in the spoken language, the ``xx-orig`` track) or
    ``translated`` (machine translation). YouTube rate-limits translated
    tracks hard (HTTP 429 after a few videos) and since 2025 plain ``en`` on
    an English video *is* such a translation, so translations are used only
    when the user asked for a language the video is not spoken in and turned
    the fallback off.
    """
    manual = [c for c in meta.get("subtitles", []) if c != "live_chat"]
    auto = list(meta.get("automatic_captions", [])) if allow_auto else []
    orig = [a for a in auto if a.endswith("-orig")]

    def base(code: str) -> str:
        return code.split("-")[0].lower()

    if requested != "orig":
        want = base(requested)
        exact = [c for c in manual if c == requested] or [c for c in manual if base(c) == want]
        if exact:
            return exact[0], "manual"
        own = [a for a in orig if base(a) == want]
        if own:
            return own[0], "auto"
        spoken = base(meta.get("language") or "")
        if not orig and spoken == want and requested in auto:
            return requested, "auto"  # older listings without -orig tracks
        if not fallback_original:
            return (requested, "translated") if requested in auto else None
    pick = pick_fallback_language({**meta, "subtitles": manual, "automatic_captions": auto})
    if pick is None:
        return None
    if pick in manual:
        return pick, "manual"
    return pick, "auto" if pick.endswith("-orig") or not orig else "translated"


def track_url(info: dict, code: str) -> str | None:
    """Download URL of caption ``code`` from yt-dlp's info, smallest readable format first.

    YouTube's own SRT is about 1/5 of the WebVTT size (no word-by-word timing)
    and cleans to exactly the same text, which matters on slow connections.
    """
    for key in ("subtitles", "automatic_captions"):
        tracks = (info.get(key) or {}).get(code) or []
        for fmt in ("srt", "vtt"):
            for track in tracks:
                if track.get("ext") == fmt and track.get("url"):
                    return track["url"]
    return None


class IncompleteInfo(Exception):
    """The info has no caption lists at all, which a timed-out request also produces."""


class NetworkTrouble(Exception):
    """A caption download kept timing out; the video goes to the next pass."""


class RateLimited(Exception):
    """YouTube kept answering HTTP 429 after every back-off step."""


# ---------------------------------------------------------------- the job


class DownloadJob:
    """Process a list of videos with the given options.

    Transcripts / metadata: ``workers`` long-running yt-dlp processes stream
    each video's info (no per-video start-up, no stream lists, no player JS);
    caption files are then fetched directly, in parallel, with a shared
    back-off when YouTube says 429. Failed videos get up to two more passes.
    Video / audio downloads run afterwards, one yt-dlp call per video.
    """

    BACKOFF = (15, 45, 120)  # seconds to wait after successive HTTP 429s on a caption
    PASS_WAIT = (20, 60)  # seconds before the 2nd and 3rd pass over failed videos
    CAPTION_GAP = 0.3  # seconds between caption requests (translations: x10)
    RETRYABLE = {"rate_limited", "network", "unknown", "outdated", "incomplete"}

    def __init__(self, engine: Engine, entries: list[Entry], options: JobOptions, emit: Emit,
                 cancel: threading.Event | None = None):
        self.engine = engine
        self.entries = entries
        self.opt = options
        self.emit = emit
        self.cancel = cancel or threading.Event()
        self.results: list[VideoResult] = []
        self.used_names: set[str] = set()
        self.cache = options.out_dir / ".cache"
        self.outputs: list[Path] = []
        self._lock = threading.Lock()
        self._next_request = 0.0  # shared caption pacing / back-off clock
        self._done = 0

    # ---- public

    def run(self) -> list[VideoResult]:
        """Process every entry, then write the combined files."""
        opt = self.opt
        opt.out_dir.mkdir(parents=True, exist_ok=True)
        self.cache.mkdir(exist_ok=True)
        hide_folder(self.cache)
        self.results = [VideoResult(e) for e in self.entries]
        total = len(self.results)
        # Titles from the list (playlist/channel listing or oEmbed) decide the order, so file
        # numbers are known before any download starts.
        self.ordered = file_order([e.title for e in self.entries], opt.order)
        self.rank = {i: n for n, i in enumerate(self.ordered)}
        self.width = max(3, len(str(total)))
        try:
            if opt.want_transcript or opt.save_csv or opt.want_thumbnail:
                self._metadata_phase()
            if opt.want_video or opt.want_audio:
                self._media_phase()
            for i, r in enumerate(self.results):
                if r.status == "pending":
                    r.status = "done"
                    self._row(i)
        except Cancelled:
            self.emit("log", line="Stopped by user.")
            self._finish(total, cancelled=True)
            raise
        self._finish(total)
        return self.results

    # ---- reporting

    def _row(self, i: int, status: str | None = None, detail: str | None = None) -> None:
        r = self.results[i]
        self.emit("row", index=i, status=status or r.status,
                  detail=detail if detail is not None else (r.error or r.language), available=r.available)

    def _tick(self) -> None:
        with self._lock:
            self._done += 1
            done = self._done
        total = len(self.results)
        self.emit("progress", value=done / max(total, 1), text=None, done=done, total=total)

    def _wait(self, seconds: float) -> None:
        if seconds > 0 and self.cancel.wait(seconds):
            raise Cancelled()

    # ---- phase 1: info + captions

    def _metadata_phase(self) -> None:
        todo: list[int] = []
        for i in self.ordered:
            r = self.results[i]
            if self._from_cache(r):
                r.status = "no_captions" if self.opt.want_transcript and not r.cues else "done"
                self._write_per_video(i, r)
                self._row(i)
                self._tick()
            else:
                todo.append(i)
        failures: dict[int, str] = {}  # latest error per video, across all passes
        for attempt in range(len(self.PASS_WAIT) + 1):
            if not todo:
                break
            if attempt:
                wait = self.PASS_WAIT[attempt - 1]
                self.emit("log", line=f"Retrying {len(todo)} video(s) in {wait} s (pass {attempt + 1}).")
                self.emit("progress", value=None, text="retry_wait")
                self._wait(wait)
            for i in todo:
                failures.pop(i, None)
            failures.update(self._extract_pass(todo))
            # "incomplete" gets one retry: a second empty answer means the video has no captions.
            todo = [i for i in todo if failures.get(i) in self.RETRYABLE
                    and not (failures[i] == "incomplete" and attempt >= 1)]
        for i, code in failures.items():
            r = self.results[i]
            if r.status == "pending":
                r.status, r.error = ("no_captions", "") if code == "incomplete" else ("error", code)
                self._row(i)
                self._tick()

    def _from_cache(self, r: VideoResult) -> bool:
        if not self.opt.reuse_cache or self.opt.want_thumbnail:
            return False
        meta_path = self.cache / f"{r.entry.id}.meta.json"
        if not meta_path.exists():
            return False
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        cached = None
        if self.opt.want_transcript:
            code = (meta.get("captions") or {}).get(self.opt.language, "")
            cached = self._cached_sub(r.entry.id, code) if code else None
            if cached is None:
                return False
        r.meta, r.from_cache = meta, True
        if meta.get("title"):
            r.entry.title = meta["title"]
        if cached:
            self._load_captions(r, cached)
        return True

    def _extract_pass(self, indices: list[int]) -> dict[int, str]:
        """One pass over ``indices``; returns ``{index: error_code}`` for videos that failed."""
        by_id = {self.results[i].entry.id: i for i in indices}
        errors: dict[str, str] = {}
        got: set[int] = set()
        workers = max(1, min(int(self.opt.workers or 1), len(indices), 4))
        chunks = [indices[k::workers] for k in range(workers)]
        work: queue.Queue = queue.Queue(maxsize=workers * 2)
        id_re = re.compile(r"\[youtube\] ([A-Za-z0-9_-]{11}): ")

        def on_line(line: str) -> None:
            match = id_re.search(line)
            if line.startswith("ERROR") and match:
                errors[match.group(1)] = line
            elif match and "Downloading webpage" in line and match.group(1) in by_id:
                self._row(by_id[match.group(1)], "working", "")
            if not _PERCENT.search(line):
                self.emit("log", line=line)

        def extract(k: int, chunk: list[int]) -> None:
            urls = [self.results[i].entry.url for i in chunk]
            try:
                self.engine.stream_infos(urls, self.cache / f"batch{k}.txt", work.put, on_line, self.cancel,
                                         sleep_requests=max(0.0, float(self.opt.delay)) / 2)
            except Cancelled:
                pass

        def consume() -> None:
            while True:
                info = work.get()
                if info is None:
                    return
                i = by_id.get(info.get("id", ""))
                if i is None or self.cancel.is_set():
                    continue
                got.add(i)
                self._handle_info(i, info)

        consumers = [threading.Thread(target=consume, daemon=True) for _ in range(workers)]
        producers = [threading.Thread(target=extract, args=(k, c), daemon=True) for k, c in enumerate(chunks)]
        for t in consumers + producers:
            t.start()
        for t in producers:
            t.join()
        for _ in consumers:
            work.put(None)
        for t in consumers:
            t.join()
        if self.cancel.is_set():
            raise Cancelled()
        failed: dict[int, str] = {}
        for vid, i in by_id.items():
            r = self.results[i]
            if i not in got:
                line = errors.get(vid, "")
                failed[i] = classify_error(line) if line else "unknown"
                r.error = failed[i]
                if line:
                    self.emit("log", line=line)
            elif r.status == "error" and r.error in self.RETRYABLE:
                failed[i] = r.error
                r.status, r.error = "pending", ""
        return failed

    def _handle_info(self, i: int, info: dict) -> None:
        """Captions, thumbnail and per-video files for one video's info."""
        r = self.results[i]
        try:
            r.meta = slim_meta(info)
            if r.meta.get("title"):
                r.entry.title = r.meta["title"]
            if self.opt.want_thumbnail:  # first: videos without captions still get one
                self._thumbnail(i, r, info)
            if self.opt.want_transcript:
                self._captions(r, info)
            if self.opt.want_transcript:
                self._write_per_video(i, r)
            meta_path = self.cache / f"{r.entry.id}.meta.json"
            meta_path.write_text(json.dumps(r.meta, ensure_ascii=False, indent=1), encoding="utf-8")
        except Cancelled:
            return
        except IncompleteInfo:
            r.status, r.error = "error", "incomplete"
        except RateLimited:
            r.status, r.error = "error", "rate_limited"
        except NetworkTrouble:
            r.status, r.error = "error", "network"
        except Exception as exc:  # noqa: BLE001 - one bad video must not stop the list
            r.status, r.error = "error", "unknown"
            self.emit("log", line=f"{r.entry.id}: {type(exc).__name__}: {exc}")
        if r.status == "error" and r.error in self.RETRYABLE:
            return  # reported after the pass, maybe retried
        if r.status == "pending":
            r.status = "done"  # kept even if the user stops right after
        self._row(i)
        self._tick()

    def _captions(self, r: VideoResult, info: dict) -> None:
        opt = self.opt
        if not info.get("subtitles") and not info.get("automatic_captions") and not info.get("language"):
            # Real caption-less videos look the same, so this only costs them a retry pass.
            raise IncompleteInfo()
        choice = choose_caption(r.meta, opt.language, fallback_original=opt.fallback_original,
                                allow_auto=opt.allow_auto)
        url = track_url(info, choice[0]) if choice else None
        if not choice or not url:
            r.status = "no_captions"
            r.available = r.meta.get("subtitles", []) + [
                a for a in r.meta.get("automatic_captions", []) if a.endswith("-orig")]
            return
        code, source = choice
        if source == "translated":
            self.emit("log", line=f"{r.entry.id}: no '{opt.language}' captions; using YouTube's translation (slow)")
        text = self._fetch_caption(url, source)
        if text is None:  # direct download refused: let yt-dlp try with its own client
            text = self._caption_via_ytdlp(info, code)
        if not text:
            raise RateLimited() if source == "translated" else RuntimeError("caption download failed")
        ext = ".vtt" if text.lstrip("\ufeff \n").startswith("WEBVTT") else ".srt"
        path = self.cache / f"{r.entry.id}.{code}{ext}"
        path.write_text(text, encoding="utf-8")
        r.meta.setdefault("captions", {})[opt.language] = code
        self._load_captions(r, path)

    def _fetch_caption(self, url: str, source: str) -> str | None:
        """GET a caption file with shared pacing and back-off; ``None`` = use yt-dlp instead.

        Only a real refusal (403, odd body) goes to yt-dlp. Timeouts are retried
        here: starting extra yt-dlp processes on a slow line made it slower still.
        """
        gap = self.CAPTION_GAP * (10 if source == "translated" else 1)
        for attempt in range(len(self.BACKOFF) + 1):
            with self._lock:
                start = max(time.monotonic(), self._next_request)
                self._next_request = start + gap
            self._wait(start - time.monotonic())
            try:
                body = self.engine.http_get(url, timeout=60)
            except urllib.error.HTTPError as exc:
                if exc.code != 429:
                    return None
                if attempt == len(self.BACKOFF):
                    raise RateLimited() from exc
                wait = self.BACKOFF[attempt]
                with self._lock:  # everybody pauses, not just this thread
                    self._next_request = max(self._next_request, time.monotonic() + wait)
                self.emit("log", line=f"HTTP 429 on a caption file; pausing {wait} s")
                self.emit("progress", value=None, text="rate_limited_wait")
                continue
            except OSError as exc:  # timeout, reset, DNS: the line, not YouTube
                if attempt == len(self.BACKOFF):
                    raise NetworkTrouble() from exc
                self.emit("log", line=f"Caption download timed out ({exc}); retrying")
                self._wait(min(self.BACKOFF[attempt], 15))
                continue
            text = body.decode("utf-8", errors="replace")
            return text if "-->" in text or text.lstrip().startswith("WEBVTT") else None
        return None

    def _caption_via_ytdlp(self, info: dict, code: str) -> str | None:
        vid = info.get("id", "x")
        info_path = self.cache / f"{vid}.info.json"
        info_path.write_text(json.dumps(info), encoding="utf-8")
        try:
            args = ["--skip-download", "--load-info-json", str(info_path), "-P", str(self.cache),
                    "-o", "%(id)s.%(ext)s", "--write-subs", "--write-auto-subs", "--sub-langs", code,
                    "--sub-format", "vtt/srt/best"]
            self.engine.run_download(args, "", None, self.cancel)
        finally:
            info_path.unlink(missing_ok=True)
        sub = self._cached_sub(vid, code)
        return sub.read_text(encoding="utf-8", errors="replace") if sub else None

    def _thumbnail(self, i: int, r: VideoResult, info: dict) -> None:
        thumbs = [t for t in info.get("thumbnails") or [] if ".jpg" in (t.get("url") or "")]
        thumbs.sort(key=lambda t: (t.get("preference") or 0, t.get("width") or 0))
        urls = [t["url"] for t in reversed(thumbs)] or [f"https://i.ytimg.com/vi/{r.entry.id}/hqdefault.jpg"]
        folder = self.opt.out_dir / self.opt.folders["thumbnails"]
        if any(f.parent == folder for f in r.files):
            return  # already saved in an earlier pass
        folder.mkdir(parents=True, exist_ok=True)
        for url in urls[:3]:
            try:
                data = self.engine.http_get(url)
            except OSError:
                continue
            if data[:3] == b"\xff\xd8\xff":
                path = folder / f"{self._base_name(i, r)}.jpg"
                path.write_bytes(data)
                r.files.append(path)
                return

    def _cached_sub(self, video_id: str, code: str) -> Path | None:
        for ext in SUB_EXTS:
            path = self.cache / f"{video_id}.{code}{ext}"
            if path.exists():
                return path
        return None

    def _load_captions(self, result: VideoResult, sub: Path) -> None:
        opt = self.opt
        result.language = subtitle_language(sub, result.entry.id)
        raw = cap.parse_captions(sub.read_text(encoding="utf-8", errors="replace"))
        result.cues = cap.clean_cues(
            raw,
            remove_rolling=opt.remove_rolling,
            remove_all_repeats=opt.remove_all_repeats,
            remove_tags=opt.remove_tags,
        )
        result.blocks = cap.transcript_blocks(result.cues, layout=opt.layout, timestamps=opt.timestamps)

    def _media_prefix(self, i: int) -> str:
        """``007 - `` = position in the chosen order (list, A→Z or Z→A)."""
        if not self.opt.numbered:
            return ""
        return f"{self.rank.get(i, i) + 1:0{getattr(self, 'width', 3)}d} - "

    def _base_name(self, i: int, result: VideoResult) -> str:
        return self._media_prefix(i) + safe_filename(result.meta.get("title") or result.entry.title)

    def _write_per_video(self, i: int, result: VideoResult) -> None:
        opt = self.opt
        if not opt.want_transcript or not result.cues:
            return
        base = self._base_name(i, result)
        with self._lock:
            txt_path = unique_path(opt.out_dir / opt.folders["transcripts"] / f"{base}.txt", self.used_names)
            srt_path = unique_path(opt.out_dir / opt.folders["subtitles"] / f"{base}.{result.language}.srt",
                                   self.used_names)
        if opt.save_txt:
            header = f"{result.meta.get('title') or result.entry.title}\n{result.entry.url}\n\n"
            sep = "\n\n" if opt.layout == "paragraphs" else "\n"
            result.files.append(write_text_safely(txt_path, header + sep.join(result.blocks) + "\n"))
        if opt.save_srt:
            result.files.append(write_text_safely(srt_path, cap.to_srt(result.cues)))

    # ---- phase 2: video / audio

    def _media_phase(self) -> None:
        total = len(self.results)
        meta_ran = self.opt.want_transcript or self.opt.save_csv or self.opt.want_thumbnail
        for n, i in enumerate(self.ordered):
            r = self.results[i]
            if self.cancel.is_set():
                raise Cancelled()
            if r.status == "error":
                continue
            for kind in ("video", "audio"):
                if getattr(self.opt, f"want_{kind}"):
                    self._row(i, "working", "")
                    self._download_media(i, r, kind, total)
            self._row(i)
            if not meta_ran:
                self._tick()
            if n < total - 1 and self.opt.delay > 0:
                self._wait(self.opt.delay)

    def _yt(self, args: list[str], url: str, on_line=None) -> tuple[int, str]:
        """Run yt-dlp for one video, backing off when YouTube rate-limits."""
        def log(line: str) -> None:
            if not _PERCENT.search(line):  # progress lines only update the row
                self.emit("log", line=line)
            if on_line:
                on_line(line)

        code, out = self.engine.run_download(args, url, log, self.cancel)
        for wait in self.BACKOFF:
            if code == 0 or classify_error(out) != "rate_limited":
                break
            self.emit("log", line=f"YouTube is limiting requests; waiting {wait} s, then retrying…")
            self.emit("progress", value=None, text="rate_limited_wait")
            self._wait(wait)
            code, out = self.engine.run_download(args, url, log, self.cancel)
        return code, out


    def _download_media(self, i: int, result: VideoResult, kind: str, total: int) -> None:
        opt = self.opt
        folder = opt.out_dir / opt.folders["videos" if kind == "video" else "audio"]
        title = result.meta.get("title") or result.entry.title
        if title and title != result.entry.id:
            # Same name as the transcript/subtitle files of this video.
            template = self._base_name(i, result).replace("%", "%%") + ".%(ext)s"
        else:
            template = f"{self._media_prefix(i)}%(title).150B.%(ext)s"
        args = ["-P", str(folder), "-P", f"temp:{self.cache / 'tmp'}", "-o", template,
                "--windows-filenames", "--no-part", "--retries", "10", "--fragment-retries", "10",
                "--no-write-info-json", "--no-mtime"]
        if kind == "video":
            q = opt.video_quality
            sort = "vcodec:h264,res,acodec:aac,ext:mp4:m4a" if q != "best" else "res,ext:mp4:m4a"
            if q not in ("best", ""):
                sort = f"res:{q},vcodec:h264,acodec:aac,ext:mp4:m4a"
            args += ["-f", "bv*+ba/b", "-S", sort, "--merge-output-format", "mp4"]
        else:
            args += ["-f", "ba/b", "-x", "--audio-format", "mp3", "--audio-quality", "0",
                     "--embed-metadata"]
            if self.engine.tools.ffmpeg_dir:
                args += ["--embed-thumbnail", "--convert-thumbnails", "jpg"]
        args += ["--print", "after_move:filepath", "--progress"]

        def on_line(line: str) -> None:
            match = _PERCENT.search(line)
            if match:
                pct = float(match.group(1))
                self.emit("row", index=i, status="working", detail=f"{kind} {pct:.0f}%")
                pos = self.rank.get(i, i)
                self.emit("progress", value=(pos + pct / 100) / max(total, 1), text=None)

        code, out = self._yt(args, result.entry.url, on_line)
        saved = [Path(ln) for ln in out.splitlines() if ln and Path(ln).suffix and Path(ln).is_absolute()
                 and Path(ln).exists()]
        if code != 0 or not saved:
            result.status = "error"
            result.error = classify_error(out)
            self.emit("log", line=f"{result.entry.id}: {last_error_line(out)}")
        else:
            result.files += saved

    # ---- combined outputs

    def _sections(self) -> list[DocSection]:
        labels = self.opt.docx.labels
        sections = []
        for r in (self.results[i] for i in self.ordered):
            if not self.opt.want_transcript:
                break
            if r.status == "pending":
                continue  # not reached (stopped)
            info = [x for x in (
                r.meta.get("channel"),
                format_date(r.meta.get("upload_date")),
                format_duration(r.meta.get("duration") or r.entry.duration),
            ) if x]
            blocks = r.blocks
            if not blocks:
                reason = labels.get(f"reason_{r.status}", "") or labels.get(f"err_{r.error}", "")
                blocks = [reason] if reason else []
            sections.append(DocSection(r.meta.get("title") or r.entry.title, blocks, r.entry.url, info))
        return sections

    def _finish(self, total: int, cancelled: bool = False) -> None:
        opt = self.opt
        stamp = datetime.now().strftime("%Y-%m-%d %H%M")
        name = safe_filename(opt.output_name or "Transcripts") or "Transcripts"
        name = name.replace("{date}", stamp)
        with_text = [r for r in self.results if r.blocks]
        try:
            if opt.want_transcript and opt.save_docx and with_text:
                doc_opts = opt.docx
                doc_opts.doc_title = (opt.output_name or doc_opts.doc_title).replace("{date}", stamp)
                path = save_docx_safely(self._sections(), opt.out_dir / f"{name}.docx", doc_opts)
                self.outputs.append(path)
            if opt.want_transcript and opt.save_combined_txt and with_text:
                parts = []
                for s in self._sections():
                    parts.append(f"{s.title}\n{s.url}\n\n" + "\n\n".join(s.blocks))
                rule = "\n\n" + "=" * 60 + "\n\n"
                self.outputs.append(write_text_safely(opt.out_dir / f"{name}.txt", rule.join(parts) + "\n"))
            if opt.save_csv and self.results:
                self.outputs.append(self._write_csv(opt.out_dir / f"{name} - list.csv"))
        except PermissionError as exc:
            self.emit("log", line=f"Could not save {exc}: close the file and try again.")
        counts: dict[str, int] = {}
        for r in self.results:
            if r.status != "pending":
                counts[r.status] = counts.get(r.status, 0) + 1
        self.emit("progress", value=1.0 if not cancelled else None, text=None)
        self.emit("done", counts=counts, outputs=[str(p) for p in self.outputs], total=total,
                  cancelled=cancelled, out_dir=str(opt.out_dir))

    def _write_csv(self, path: Path) -> Path:
        header = ["No", "Title", "URL", "Channel", "Upload date", "Duration", "Views", "Likes",
                  "Transcript language", "Status", "Words"]
        rows = []
        for i in self.ordered:
            r, n = self.results[i], self.rank[i] + 1
            if r.status == "pending":
                continue
            m = r.meta
            words = sum(len(b.split()) for b in r.blocks)
            rows.append([n, m.get("title") or r.entry.title, r.entry.url, m.get("channel") or r.entry.channel,
                         format_date(m.get("upload_date")), format_duration(m.get("duration") or r.entry.duration),
                         m.get("view_count") or "", m.get("like_count") or "", r.language,
                         r.status if not r.error else f"{r.status}: {r.error}", words or ""])
        for n in range(1, 50):
            target = path if n == 1 else path.with_name(f"{path.stem} ({n}){path.suffix}")
            try:
                with open(target, "w", encoding="utf-8-sig", newline="") as fh:
                    writer = csv.writer(fh)
                    writer.writerow(header)
                    writer.writerows(rows)
                return target
            except PermissionError:
                continue
        raise PermissionError(str(path))


# ---------------------------------------------------------------- files I already have


@dataclass
class FileJobOptions:
    """Options for cleaning/combining caption files from disk."""

    out_dir: Path
    layout: str = "paragraphs"
    timestamps: bool = False
    remove_rolling: bool = True
    remove_all_repeats: bool = False
    remove_tags: bool = True
    save_docx: bool = True
    save_txt: bool = False
    save_srt: bool = False
    output_name: str = "Combined transcripts"
    docx: DocOptions = field(default_factory=DocOptions)


def read_caption_file(path: Path) -> list[cap.Cue]:
    """Parse an SRT/VTT file, or treat a TXT file as one cue per line."""
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "utf-16", "cp1258", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if path.suffix.lower() in (".srt", ".vtt") or "-->" in text[:2000]:
        return cap.parse_captions(text)
    return cap.cues_from_plain_text(text)


def combine_files(paths: list[Path], opt: FileJobOptions, emit: Emit) -> list[Path]:
    """Clean each file and write the chosen outputs; returns written paths."""
    sections: list[DocSection] = []
    outputs: list[Path] = []
    used: set[str] = set()
    for n, path in enumerate(paths):
        emit("progress", value=n / max(len(paths), 1), text=path.name)
        try:
            cues = cap.clean_cues(
                read_caption_file(path),
                remove_rolling=opt.remove_rolling,
                remove_all_repeats=opt.remove_all_repeats,
                remove_tags=opt.remove_tags,
            )
        except OSError as exc:
            emit("log", line=f"{path.name}: {exc}")
            continue
        timed = any(c.end > 0 for c in cues)
        blocks = cap.transcript_blocks(cues, layout=opt.layout, timestamps=opt.timestamps and timed)
        title = title_from_filename(path.name)
        sections.append(DocSection(title, blocks))
        base = safe_filename(title)
        if opt.save_txt:
            sep = "\n\n" if opt.layout == "paragraphs" else "\n"
            outputs.append(write_text_safely(unique_path(opt.out_dir / f"{base}.txt", used), sep.join(blocks) + "\n"))
        if opt.save_srt and timed:
            outputs.append(write_text_safely(unique_path(opt.out_dir / f"{base}.clean.srt", used), cap.to_srt(cues)))
        emit("log", line=f"{path.name}: {len(cues)} lines")
    if opt.save_docx and sections:
        opt.docx.doc_title = opt.output_name
        outputs.append(save_docx_safely(sections, opt.out_dir / f"{safe_filename(opt.output_name)}.docx", opt.docx))
    emit("progress", value=1.0, text=None)
    emit("done", counts={"done": len(sections)}, outputs=[str(p) for p in outputs], total=len(paths),
         cancelled=False, out_dir=str(opt.out_dir))
    return outputs


def natural_key(text: str) -> list:
    """Sort key: ``file 2`` before ``file 10``."""
    return [int(t) if t.isdigit() else t.casefold() for t in re.split(r"(\d+)", text)]
