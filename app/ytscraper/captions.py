"""Parse, clean and format caption files (WebVTT / SRT). Pure logic, no I/O.

YouTube auto-captions are "rolling": every cue repeats the line before it,
so a naive conversion prints each sentence twice. ``clean_cues`` removes
that, plus optional sound tags such as ``[Music]`` / ``[âm nhạc]``.
"""
from __future__ import annotations

import html
import re
from collections import deque
from dataclasses import dataclass, field

_TIMING = re.compile(
    r"^\s*((?:\d+:)?\d{1,2}:\d{2}[.,]\d{1,3})\s*-->\s*((?:\d+:)?\d{1,2}:\d{2}[.,]\d{1,3})"
)
_TAG = re.compile(r"<[^>]*>")
_ASS_TAG = re.compile(r"\{\\[^}]*\}")
_SOUND_TAG = re.compile(r"\[[^\]\n]{1,40}\]|\([A-Za-zÀ-ỹ ]{1,25}\)|[♪♫]+")
_SPACES = re.compile(r"\s+")
_SENTENCE_END = re.compile(r"[.!?…。！？]\W*$")
_CJK = re.compile(r"[぀-ヿ㐀-鿿가-힯]")


@dataclass
class Cue:
    """One caption: start/end in seconds and its text lines."""

    start: float
    end: float
    lines: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        """Lines joined with a space."""
        return " ".join(self.lines)


def parse_timestamp(value: str) -> float:
    """Convert ``HH:MM:SS.mmm`` / ``MM:SS,mmm`` to seconds."""
    value = value.replace(",", ".")
    parts = value.split(":")
    seconds = float(parts[-1])
    minutes = int(parts[-2]) if len(parts) >= 2 else 0
    hours = int(parts[-3]) if len(parts) >= 3 else 0
    return hours * 3600 + minutes * 60 + seconds


def strip_markup(line: str) -> str:
    """Remove VTT/HTML/ASS tags and entities, collapse whitespace."""
    line = _ASS_TAG.sub("", _TAG.sub("", line))
    line = html.unescape(line).replace(" ", " ")
    return _SPACES.sub(" ", line).strip()


def parse_captions(text: str) -> list[Cue]:
    """Parse WebVTT or SRT text into cues (tags stripped, blank lines dropped).

    Works line by line rather than splitting on blank lines, because YouTube
    VTT cues contain lines holding a single space.
    """
    text = text.lstrip("﻿").replace("\r\n", "\n").replace("\r", "\n")
    raw = text.split("\n")
    cues: list[Cue] = []
    current: Cue | None = None
    in_note = False
    for i, line in enumerate(raw):
        match = _TIMING.match(line)
        if match:
            # A non-blank line right before the timing is the cue identifier.
            if current is not None and i > 0 and raw[i - 1].strip() and current.lines:
                if strip_markup(raw[i - 1]) == current.lines[-1]:
                    current.lines.pop()
            current = Cue(parse_timestamp(match.group(1)), parse_timestamp(match.group(2)))
            cues.append(current)
            in_note = False
            continue
        if current is None:
            continue  # header (WEBVTT, Kind:, Language:, STYLE ...)
        if not line.strip():
            in_note = False
            continue
        if line.startswith("NOTE") and (i == 0 or not raw[i - 1].strip()):
            in_note = True
        if in_note:
            continue
        cleaned = strip_markup(line)
        if cleaned:
            current.lines.append(cleaned)
    return cues


def remove_sound_tags(line: str) -> str:
    """Drop ``[Music]``, ``(applause)``, ``♪`` and leading ``>>`` markers."""
    line = _SOUND_TAG.sub(" ", line)
    line = re.sub(r"^\s*>>\s*", "", line)
    return _SPACES.sub(" ", line).strip()


def _norm(line: str) -> str:
    return _SPACES.sub(" ", line).strip().casefold()


def clean_cues(
    cues: list[Cue],
    *,
    remove_rolling: bool = True,
    remove_all_repeats: bool = False,
    remove_tags: bool = False,
    window: int = 3,
) -> list[Cue]:
    """Return new cues holding only lines not already shown.

    - ``remove_rolling``: drop lines repeated from the previous few lines and
      merge karaoke-style growing lines ("Hello" -> "Hello world").
    - ``remove_all_repeats``: drop any line that appeared anywhere before.
    - ``remove_tags``: strip sound tags; lines left empty are dropped.
    """
    out: list[Cue] = []
    recent: deque[str] = deque(maxlen=window)
    seen: set[str] = set()
    for cue in cues:
        new_lines: list[str] = []
        for line in cue.lines:
            if remove_tags:
                line = remove_sound_tags(line)
            if not line:
                continue
            key = _norm(line)
            if remove_rolling and key in recent:
                continue
            if remove_all_repeats and key in seen:
                continue
            if (
                remove_rolling
                and not new_lines
                and out
                and len(out[-1].lines) == 1
                and key.startswith(_norm(out[-1].lines[0]))
            ):
                # Growing line: replace the shorter version shown before.
                old = _norm(out[-1].lines[0])
                if old in recent:
                    recent.remove(old)
                out[-1].lines[0] = line
                out[-1].end = max(out[-1].end, cue.end)
                recent.append(key)
                seen.add(key)
                continue
            new_lines.append(line)
            recent.append(key)
            seen.add(key)
        if new_lines:
            out.append(Cue(cue.start, cue.end, new_lines))
    return out


def format_timestamp(seconds: float, *, srt: bool = False) -> str:
    """``01:02:03,456`` for SRT; ``1:02:03`` / ``02:03`` for transcripts."""
    seconds = max(0.0, seconds)
    hours, rem = divmod(int(seconds), 3600)
    minutes, secs = divmod(rem, 60)
    if srt:
        millis = int(round((seconds - int(seconds)) * 1000))
        if millis == 1000:
            millis = 999
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def to_srt(cues: list[Cue]) -> str:
    """Render cues as SRT text."""
    blocks = []
    for n, cue in enumerate(cues, 1):
        end = max(cue.end, cue.start + 0.001)
        blocks.append(
            f"{n}\n{format_timestamp(cue.start, srt=True)} --> "
            f"{format_timestamp(end, srt=True)}\n" + "\n".join(cue.lines)
        )
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def _join(a: str, b: str) -> str:
    if not a:
        return b
    if _CJK.match(a[-1]) and _CJK.match(b[0]):
        return a + b
    return f"{a} {b}"


def to_paragraphs(
    cues: list[Cue],
    *,
    pause: float = 2.0,
    soft_limit: int = 450,
    hard_limit: int = 1200,
) -> list[tuple[float, str]]:
    """Merge cues into readable paragraphs: ``[(start_seconds, text), ...]``.

    A new paragraph starts after a pause of ``pause`` seconds (once the
    current one has some length), at a sentence end past ``soft_limit``
    characters, at a ``>>`` speaker change, or at ``hard_limit``.
    """
    paragraphs: list[tuple[float, str]] = []
    start = 0.0
    buf = ""
    prev_end: float | None = None
    for cue in cues:
        for line in cue.lines:
            speaker = line.lstrip().startswith(">>")
            line = re.sub(r"^\s*>>\s*", "", line)
            if not line:
                continue
            gap = prev_end is not None and cue.start - prev_end >= pause and len(buf) >= 120
            if buf and (
                speaker
                or gap
                or len(buf) >= hard_limit
                or (len(buf) >= soft_limit and _SENTENCE_END.search(buf))
            ):
                paragraphs.append((start, buf))
                buf = ""
            if not buf:
                start = cue.start
            buf = _join(buf, line)
        prev_end = cue.end
    if buf:
        paragraphs.append((start, buf))
    return paragraphs


def transcript_blocks(
    cues: list[Cue], *, layout: str = "paragraphs", timestamps: bool = False
) -> list[str]:
    """Plain-text blocks for TXT/DOCX output.

    ``layout`` is ``"paragraphs"`` or ``"lines"`` (one caption per line).
    """
    if layout == "lines":
        items = [(cue.start, line) for cue in cues for line in cue.lines]
    else:
        items = to_paragraphs(cues)
    if timestamps:
        return [f"[{format_timestamp(t)}] {text}" for t, text in items]
    return [text for _, text in items]


def plain_text_lines(text: str) -> list[str]:
    """Treat a ``.txt`` file as one cue per non-empty line (for the tools tab)."""
    return [_SPACES.sub(" ", ln).strip() for ln in text.splitlines() if ln.strip()]


def cues_from_plain_text(text: str) -> list[Cue]:
    """Wrap plain text lines in zero-timed cues so the cleaners apply."""
    return [Cue(0.0, 0.0, [ln]) for ln in plain_text_lines(text)]
