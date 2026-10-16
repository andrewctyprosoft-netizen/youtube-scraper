"""Drive the real window against YouTube: paste links, add, start, check files.

Usage::

    python dev/tools/gui_e2e.py OUT_DIR [--media]

Run 1: a playlist, a channel, a search and a single video -> transcripts in
the spoken language, Word + TXT + SRT + CSV. Run 2 (``--media``): one video
as 360p MP4 + MP3 + thumbnail.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app"))
sys.stdout.reconfigure(encoding="utf-8")

from ytscraper import gui, settings as settings_mod  # noqa: E402

LINKS = """\
https://www.youtube.com/playlist?list=PLLojVvWCZ5N4
Watch this: https://youtu.be/B3G9oTQ3a-k?si=abc and also
https://www.youtube.com/@TED
bản tin thời sự sáng
"""


def pump(app: gui.App, until, timeout: float) -> None:
    """Run the Tk loop until ``until()`` is true."""
    end = time.time() + timeout
    while not until():
        app.update()
        time.sleep(0.05)
        if time.time() > end:
            raise TimeoutError("GUI step timed out")


def main() -> None:
    """Entry point."""
    ap = argparse.ArgumentParser()
    ap.add_argument("out", type=Path)
    ap.add_argument("--media", action="store_true")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    cfg = args.out / "settings.json"
    cfg.write_text(json.dumps({
        "out_dir": str(args.out / "result"), "language": "orig", "save_txt": True, "save_srt": True,
        "save_combined_txt": True, "search_count": 2, "list_limit": 2, "delay": 1.0, "numbered": True,
        "doc_breaks": True, "geometry": "zoomed", "output_name": "E2E transcripts",
    }), encoding="utf-8")
    settings_mod.settings_path = lambda: cfg  # type: ignore[assignment]

    app = gui.App()
    app.links_box.insert("1.0", LINKS)
    app.on_add_links()
    pump(app, lambda: not app.busy, 300)
    print("STATUS:", app.status.cget("text"))
    for e in app.entries:
        print(f"  {e.id} | {e.source} | {e.title[:60]}")
    assert len(app.entries) >= 6, "expected playlist(2) + video + channel(2) + search(2)"

    app.on_start()
    pump(app, lambda: not app.busy, 900)
    print("STATUS:", app.status.cget("text"))
    for e in app.entries:
        print(f"  {app.status_by_id.get(e.id)} | {e.title[:60]}")

    if args.media:
        app.v["want_transcript"].set(False)
        app.v["want_video"].set(True)
        app.v["want_audio"].set(True)
        app.v["want_thumbnail"].set(True)
        app.v["video_quality"].set("360")
        app.v["output_name"].set("E2E media")
        app.set_all(False)
        app.checked.add("B3G9oTQ3a-k")
        app.refresh_tree()
        app.on_start()
        pump(app, lambda: not app.busy, 900)
        print("STATUS:", app.status.cget("text"))
    app.on_close()
    for p in sorted((args.out / "result").rglob("*")):
        if ".cache" not in p.parts and p.is_file():
            print(f"FILE {p.stat().st_size:>10}  {p.relative_to(args.out)}")


if __name__ == "__main__":
    main()
