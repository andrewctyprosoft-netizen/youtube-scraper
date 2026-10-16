"""Build the portable Windows app: ``dist/YouTube Scraper/`` and a zip of it.

Steps: PyInstaller one-folder build (no console) -> copy ``tools/*.exe``
(yt-dlp, deno, ffmpeg, ffprobe) -> write the start-here note -> zip.

Usage::

    python dev/tools/fetch_tools.py --ffmpeg-dir <ffmpeg bin>   # once
    python dev/tools/build.py [--no-zip]
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app"))
from ytscraper import __version__  # noqa: E402

NAME = "YouTube Scraper"
DIST = ROOT / "dist"
WORK = ROOT / "dev" / "build"
REQUIRED_TOOLS = ["yt-dlp.exe"]
OPTIONAL_TOOLS = ["deno.exe", "ffmpeg.exe", "ffprobe.exe"]

START_HERE = f"""YouTube Scraper {__version__}
==========================

1. Double-click "{NAME}.exe".
2. Paste YouTube links (videos, playlists, channels) and click "Add to list".
3. Choose what you want (transcript, video, audio) and press Start.
Files are saved in Documents\\YouTube Scraper (you can change this).
If downloads stop working one day: Settings -> Update engine.
Keep this whole folder together; the "tools" folder holds the download engine.
Windows SmartScreen may warn the first time: click "More info" -> "Run anyway".
"""


def run_pyinstaller(distpath: Path) -> Path:
    """Build the one-folder app into ``distpath`` and return its folder."""
    sep = ";"
    cmd = [
        sys.executable, "-m", "PyInstaller", str(ROOT / "app" / "main.py"),
        "--name", NAME, "--noconfirm", "--clean", "--windowed", "--onedir",
        "--icon", str(ROOT / "app" / "assets" / "icon.ico"),
        "--add-data", f"{ROOT / 'app' / 'assets'}{sep}assets",
        "--collect-data", "customtkinter",
        "--paths", str(ROOT / "app"),
        "--exclude-module", "PIL", "--exclude-module", "numpy", "--exclude-module", "yt_dlp",
        "--exclude-module", "pytest", "--exclude-module", "PyInstaller",
        "--distpath", str(distpath), "--workpath", str(WORK), "--specpath", str(WORK),
        "--version-file", str(write_version_file()),
    ]
    subprocess.run(cmd, check=True)
    return distpath / NAME


def same_file(a: Path, b: Path) -> bool:
    """True when both files have the same bytes."""
    if a.stat().st_size != b.stat().st_size:
        return False
    return hashlib.sha256(a.read_bytes()).digest() == hashlib.sha256(b.read_bytes()).digest()


def sync_into(src: Path, dst: Path) -> None:
    """Update ``dst`` to match ``src`` file by file.

    Never deletes the folder itself, so a user's settings.json and tools/ stay, and a
    file another program holds open (Word loaded VCRUNTIME140.dll once) is skipped when
    it is already identical.
    """
    dst.mkdir(parents=True, exist_ok=True)
    wanted = {p.relative_to(src) for p in src.rglob("*") if p.is_file()}
    for old in sorted(p for p in dst.rglob("*") if p.is_file()):
        rel = old.relative_to(dst)
        if rel.parts[0] in ("tools", "settings.json", "START HERE.txt") or rel in wanted:
            continue
        try:
            old.unlink()
        except PermissionError:
            print(f"  WARNING: could not remove old {rel} (in use)")
    for rel in sorted(wanted):
        new, old = src / rel, dst / rel
        old.parent.mkdir(parents=True, exist_ok=True)
        if old.exists() and same_file(new, old):
            continue
        try:
            shutil.copy2(new, old)
        except PermissionError as exc:
            raise SystemExit(f"{rel} is in use by another program; close it and build again") from exc


def write_version_file() -> Path:
    """Windows file properties (shown in Explorer)."""
    nums = tuple(int(x) for x in __version__.split(".")) + (0,)
    text = f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={nums}, prodvers={nums}, mask=0x3f, flags=0x0, OS=0x40004,
                    fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[StringFileInfo([StringTable('040904B0', [
    StringStruct('FileDescription', 'YouTube Scraper - transcripts, videos and audio'),
    StringStruct('FileVersion', '{__version__}'),
    StringStruct('ProductName', 'YouTube Scraper'),
    StringStruct('ProductVersion', '{__version__}'),
    StringStruct('OriginalFilename', '{NAME}.exe')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])]
)
"""
    WORK.mkdir(parents=True, exist_ok=True)
    path = WORK / "version.txt"
    path.write_text(text, encoding="utf-8")
    return path


def copy_tools(app: Path) -> None:
    """Copy the engines next to the exe."""
    src = ROOT / "tools"
    dest = app / "tools"
    dest.mkdir(exist_ok=True)
    for name in REQUIRED_TOOLS + OPTIONAL_TOOLS:
        if (src / name).exists():
            if not ((dest / name).exists() and same_file(src / name, dest / name)):
                shutil.copy2(src / name, dest / name)
            print("  tool", name)
        elif name in REQUIRED_TOOLS:
            raise SystemExit(f"tools/{name} missing: run dev/tools/fetch_tools.py first")
        else:
            print(f"  WARNING: tools/{name} missing (feature limited)")


def make_zip(app: Path) -> Path:
    """Zip the folder (top-level folder kept so unzipping stays tidy)."""
    target = DIST / f"YouTube-Scraper-{__version__}-win64.zip"
    target.unlink(missing_ok=True)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for path in sorted(app.rglob("*")):
            if path.is_file() and path.name != "settings.json":
                zf.write(path, Path(NAME) / path.relative_to(app))
    return target


def main() -> None:
    """Entry point."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-zip", action="store_true")
    args = ap.parse_args()
    # Build elsewhere, then update dist/<app>/ in place: PyInstaller would delete the folder
    # users run from (their settings.json with it) and fails half-way if a file is in use.
    fresh = run_pyinstaller(WORK / "out")
    app = DIST / NAME
    sync_into(fresh, app)
    if (app / "settings.json").exists():
        print("  kept settings.json")
    copy_tools(app)
    (app / "START HERE.txt").write_text(START_HERE, encoding="utf-8-sig")
    size = sum(p.stat().st_size for p in app.rglob("*") if p.is_file())
    print(f"app folder: {app} ({size / 1e6:.0f} MB)")
    if not args.no_zip:
        z = make_zip(app)
        print(f"zip: {z} ({z.stat().st_size / 1e6:.0f} MB)")


if __name__ == "__main__":
    main()
