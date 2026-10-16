"""Fetch the external engines the app drives into ``tools/``.

- yt-dlp.exe  : latest official release, SHA-256 checked against SHA2-256SUMS
- deno.exe    : latest official release (JS runtime yt-dlp needs for YouTube)
- ffmpeg.exe / ffprobe.exe : copied from a local FFmpeg build (``--ffmpeg-dir``)

Usage::

    python dev/tools/fetch_tools.py [--ffmpeg-dir PATH] [--deno-zip ZIP] [--force]
"""
from __future__ import annotations

import argparse
import hashlib
import io
import re
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2]
TOOLS = APP_ROOT / "tools"

YTDLP_URL = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
YTDLP_SUMS = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/SHA2-256SUMS"
DENO_ZIP = "deno-x86_64-pc-windows-msvc.zip"
DENO_URL = f"https://github.com/denoland/deno/releases/latest/download/{DENO_ZIP}"
DENO_SUM = DENO_URL + ".sha256sum"


def fetch(url: str) -> bytes:
    """Download ``url`` in chunks (with progress) and return its bytes."""
    print(f"  GET {url}", flush=True)
    req = urllib.request.Request(url, headers={"User-Agent": "youtube-scraper-build"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        total = int(resp.headers.get("Content-Length") or 0)
        buf = bytearray()
        step = max(total // 10, 1 << 20)
        mark = step
        while chunk := resp.read(1 << 18):
            buf += chunk
            if total > 2 << 20 and len(buf) >= mark:
                print(f"    {len(buf) * 100 // total}%", flush=True)
                mark += step
        return bytes(buf)


def expected_sha(sums_text: str, name: str) -> str:
    """Return the hex digest listed for ``name`` in a checksum file.

    Handles ``<hash>  <name>`` lists, bare digests and PowerShell
    ``Get-FileHash`` tables (deno publishes the latter).
    """
    digest = re.compile(r"\b[0-9a-fA-F]{64}\b")
    found = digest.findall(sums_text)
    if len(found) == 1:  # single-file checksum (bare or Get-FileHash table)
        return found[0].lower()
    for line in sums_text.splitlines():
        if line.rstrip().endswith(name) and (match := digest.search(line)):
            return match.group(0).lower()
    raise SystemExit(f"No checksum for {name}")


def verify(data: bytes, digest: str, name: str) -> None:
    """Abort when ``data`` does not hash to ``digest``."""
    actual = hashlib.sha256(data).hexdigest()
    if actual != digest:
        raise SystemExit(f"Checksum mismatch for {name}: {actual} != {digest}")
    print(f"  sha256 ok ({name})")


def get_ytdlp(force: bool) -> None:
    """Download and verify yt-dlp.exe."""
    dest = TOOLS / "yt-dlp.exe"
    if dest.exists() and not force:
        print("yt-dlp.exe present, skipping")
        return
    print("yt-dlp.exe")
    data = fetch(YTDLP_URL)
    verify(data, expected_sha(fetch(YTDLP_SUMS).decode(), "yt-dlp.exe"), "yt-dlp.exe")
    dest.write_bytes(data)


def get_deno(force: bool, local_zip: Path | None = None) -> None:
    """Download (or take ``local_zip``), verify and unzip deno.exe."""
    dest = TOOLS / "deno.exe"
    if dest.exists() and not force:
        print("deno.exe present, skipping")
        return
    print("deno.exe")
    data = local_zip.read_bytes() if local_zip else fetch(DENO_URL)
    verify(data, expected_sha(fetch(DENO_SUM).decode(errors="replace"), DENO_ZIP), DENO_ZIP)
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        dest.write_bytes(zf.read("deno.exe"))


def copy_ffmpeg(src_dir: Path | None, force: bool) -> None:
    """Copy ffmpeg.exe and ffprobe.exe from a local build."""
    for exe in ("ffmpeg.exe", "ffprobe.exe"):
        dest = TOOLS / exe
        if dest.exists() and not force:
            print(f"{exe} present, skipping")
            continue
        if src_dir is None or not (src_dir / exe).exists():
            print(f"WARNING: {exe} missing; pass --ffmpeg-dir (video/MP3 need it)")
            continue
        print(f"{exe} <- {src_dir}")
        shutil.copy2(src_dir / exe, dest)


def main() -> None:
    """Entry point."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ffmpeg-dir", type=Path, default=None)
    ap.add_argument("--deno-zip", type=Path, default=None,
                    help="use an already downloaded deno zip (slow networks); still checksum-verified")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    TOOLS.mkdir(exist_ok=True)
    get_ytdlp(args.force)
    get_deno(args.force, args.deno_zip)
    copy_ffmpeg(args.ffmpeg_dir, args.force)
    print("done:", ", ".join(sorted(p.name for p in TOOLS.glob("*.exe"))))


if __name__ == "__main__":
    sys.exit(main())
