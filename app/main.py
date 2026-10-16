"""Start YouTube Scraper (double-click target for PyInstaller and dev runs).

``YouTube Scraper.exe --selftest FOLDER [VIDEO_URL] [--media]`` runs one real
transcript download without the window and writes ``FOLDER/selftest.txt``
(used to check a build; also handy for support).
"""
import sys
from pathlib import Path


def selftest(folder: Path, url: str, media: bool = False) -> int:
    """Download one transcript (and with ``media`` a 360p MP4 + MP3) and report."""
    from ytscraper.engine import Engine, Entry, Tools
    from ytscraper.jobs import DownloadJob, JobOptions

    folder.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    tools = Tools.discover()
    engine = Engine(tools)
    lines.append(f"tools: {tools}")
    lines.append(f"yt-dlp version: {engine.version()}")
    vid = url.split("v=")[-1].split("/")[-1][:11]
    opts = JobOptions(out_dir=folder, language="orig", save_txt=True, delay=0, reuse_cache=False,
                      output_name="selftest", want_video=media, want_audio=media, video_quality="360")
    results = DownloadJob(engine, [Entry(vid, vid, url)], opts,
                          lambda kind, **d: lines.append(f"{kind}: {d}")).run()
    for r in results:
        lines.append(f"RESULT {r.status} lang={r.language} error={r.error} blocks={len(r.blocks)} title={r.entry.title}")
        lines += [f"FILE {p.stat().st_size} {p.name}" for p in r.files if p.exists()]
    (folder / "selftest.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0 if results and results[0].status == "done" else 1


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--selftest":
        urls = [a for a in sys.argv[3:] if not a.startswith("--")]
        target = urls[0] if urls else "https://www.youtube.com/watch?v=4QEDPfuQfCQ"
        sys.exit(selftest(Path(sys.argv[2]), target, media="--media" in sys.argv))
    from ytscraper.gui import main

    main()
