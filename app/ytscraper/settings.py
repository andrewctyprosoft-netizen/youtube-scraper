"""Remembered choices, kept in ``settings.json`` next to the app (portable)."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from .engine import app_dir


def default_out_dir() -> str:
    """``Documents\\YouTube Scraper`` for the current user."""
    docs = Path.home() / "Documents"
    return str((docs if docs.exists() else Path.home()) / "YouTube Scraper")


@dataclass
class Settings:
    """Every remembered option (names match the GUI variables)."""

    ui_language: str = "en"
    theme: str = "system"
    out_dir: str = ""
    output_name: str = "Transcripts {date}"
    want_transcript: bool = True
    want_video: bool = False
    want_audio: bool = False
    want_thumbnail: bool = False
    video_quality: str = "720"
    language: str = "en"
    fallback_original: bool = True
    allow_auto: bool = True
    layout: str = "paragraphs"
    timestamps: bool = False
    remove_rolling: bool = True
    remove_all_repeats: bool = False
    remove_tags: bool = True
    save_docx: bool = True
    save_txt: bool = False
    save_srt: bool = False
    save_combined_txt: bool = False
    save_csv: bool = True
    doc_contents: bool = True
    doc_breaks: bool = False
    doc_info: bool = True
    doc_numbered: bool = False
    numbered: bool = False
    file_order: str = "list"
    reuse_cache: bool = True
    delay: float = 1.0
    workers: int = 2
    search_count: int = 20
    list_limit: int = 0
    login_browser: str = ""
    cookies_file: str = ""
    files_sort: str = "name"
    files_out_dir: str = ""
    files_output_name: str = "Combined transcripts"
    files_save_txt: bool = False
    files_save_srt: bool = False
    geometry: str = ""

    def __post_init__(self) -> None:
        if not self.out_dir:
            self.out_dir = default_out_dir()


def settings_path() -> Path:
    """``<app>/settings.json`` if writable, else ``%APPDATA%\\YouTube Scraper``."""
    local = app_dir() / "settings.json"
    try:
        if local.exists():
            with open(local, "a", encoding="utf-8"):
                pass
            return local
        local.write_text("{}", encoding="utf-8")
        return local
    except OSError:
        folder = Path(os.environ.get("APPDATA", Path.home())) / "YouTube Scraper"
        folder.mkdir(parents=True, exist_ok=True)
        return folder / "settings.json"


def load(path: Path | None = None) -> Settings:
    """Read settings, ignoring unknown or broken values."""
    path = path or settings_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    known = {f.name: f for f in fields(Settings)}
    clean = {}
    defaults = Settings()
    for key, value in data.items():
        if key in known and isinstance(value, type(getattr(defaults, key))):
            clean[key] = value
        elif key in known and isinstance(getattr(defaults, key), float) and isinstance(value, int):
            clean[key] = float(value)
    return Settings(**clean)


def save(settings: Settings, path: Path | None = None) -> None:
    """Write settings (best effort)."""
    path = path or settings_path()
    try:
        path.write_text(json.dumps(asdict(settings), ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass
