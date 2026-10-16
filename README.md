# YouTube Scraper

A portable Windows app that gets transcripts, videos and audio from YouTube.
Paste links, tick the videos you want, press Start.
Built for people who never open a command prompt; English interface.

Version 2.2.1 replaces the old set of yt-dlp commands and scripts (kept in `legacy/`).

## Download

Get `YouTube-Scraper-<version>-win64.zip` from the [Releases page](../../releases/latest), unzip it and run `YouTube Scraper.exe`.
No Python or install needed.
The source in this repository is for people who want to read, change or build it themselves (see [Building](#building)).

Download only content you have the right to use, and follow YouTube's Terms of Service.
Released under the [MIT License](LICENSE).

## What It Does

| Feature | How |
|:--------|:----|
| Single video, many videos, link lists | Paste links (even inside sentences) or open a `.txt` file |
| Playlists and channels | Expanded into their videos; tick or untick each one |
| YouTube search | Lines that are not links are searched (top 20 by default) |
| Transcripts | Any caption language, or the video's own spoken language |
| Remove duplicated lines | Cleans the rolling repeats of auto-captions; optional "repeated anywhere" |
| Remove sound tags | Drops `[Music]`, `[âm nhạc]`, `♪`, `>>` |
| One Word file | All transcripts in one `.docx`, video title as Heading 1, clickable contents, channel/date/link line |
| Other outputs | TXT per video, clean SRT per video, one combined TXT, CSV list for Excel |
| Video and audio | MP4 (best, 1080p, 720p, 480p, 360p), MP3 with cover art, thumbnails |
| File names and order | Every file is named after the video title (TXT, SRT, MP4, MP3, JPG share one name); optional `001 - ` numbers in list order, title A → Z or Z → A, which also orders the Word file and CSV |
| Files you already have | "Combine my files" tab cleans `.srt` / `.vtt` / `.txt` files into one Word file |
| Keeps working | "Update engine" button updates yt-dlp in place when YouTube changes |

## Files

| Path | What it is | Ships to users |
|:-----|:-----------|:---------------|
| `app/main.py` | Entry point | Built into the exe |
| `app/ytscraper/gui.py` | Window, tabs, list, events (customtkinter) | Built into the exe |
| `app/ytscraper/jobs.py` | Per-video download, caching, language fallback, outputs | Built into the exe |
| `app/ytscraper/engine.py` | Finds and runs `yt-dlp.exe`, `deno.exe`, `ffmpeg.exe` | Built into the exe |
| `app/ytscraper/captions.py` | VTT/SRT parser, duplicate-line cleaner, paragraphs (pure) | Built into the exe |
| `app/ytscraper/links.py` | Pasted text → videos, playlists, channels, searches (pure) | Built into the exe |
| `app/ytscraper/docx_export.py` | Combined Word document | Built into the exe |
| `app/ytscraper/i18n.py` | Interface text (English; Vietnamese kept but not shown) | Built into the exe |
| `app/ytscraper/settings.py` | `settings.json` beside the exe | Built into the exe |
| `app/assets/icon.ico` | App icon (from `dev/tools/make_icon.py`) | Yes |
| `tools/` | `yt-dlp.exe`, `deno.exe`, `ffmpeg.exe`, `ffprobe.exe` (not in source control) | Yes |
| `dev/tests/` | pytest suite with a fake yt-dlp | No |
| `dev/tools/` | fetch engines, build, icon, GUI screenshots, GUI end-to-end run | No |
| `legacy/` | The old commands and scripts, kept for reference | No |

## Using the Portable App

1. Unzip `YouTube-Scraper-2.2.1-win64.zip` anywhere (Desktop, USB stick).
2. Double-click `YouTube Scraper.exe` inside the folder.
3. Paste links, click "Add to list", choose what you want, press Start.

Output goes to `Documents\YouTube Scraper` unless you pick another folder:

```text
YouTube Scraper/
├── Transcripts 2026-10-16 2015.docx      ← all transcripts, one heading per video
├── Transcripts 2026-10-16 2015 - list.csv
├── Transcripts/   Subtitles/   Videos/   Audio/   Thumbnails/
└── .cache/        ← hidden: raw captions, so re-runs need no download
```

Windows SmartScreen may warn on first start because the exe is not code-signed: "More info" → "Run anyway".

## Building

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r dev/requirements-dev.txt
.venv/Scripts/python dev/tools/fetch_tools.py --ffmpeg-dir "ffmpeg-2025-09-04-git-2611874a50-full_build/bin"
.venv/Scripts/python dev/tools/make_icon.py
.venv/Scripts/python dev/tools/build.py
```

`fetch_tools.py` downloads the latest official `yt-dlp.exe` and `deno.exe` and checks their SHA-256 sums.
`build.py` writes `dist/YouTube Scraper/` and `dist/YouTube-Scraper-<version>-win64.zip`.

Run from source without building:

```bash
.venv/Scripts/python app/main.py
```

## Testing

```bash
.venv/Scripts/python -m pytest dev/tests -q
.venv/Scripts/python dev/tools/gui_e2e.py <scratch folder> --media
.venv/Scripts/python dev/tools/gui_shots.py <scratch folder> --size zoomed --lang vi --theme dark
```

The unit tests use a fake yt-dlp and need no network.
`gui_e2e.py` drives the real window against YouTube: playlist, channel, search and single video, then MP4/MP3/thumbnail.
Check a finished build on any PC with `"YouTube Scraper.exe" --selftest <folder> [<video URL>] [--media]`; it writes `<folder>/selftest.txt`.

## How It Works

- yt-dlp runs as a separate `tools/yt-dlp.exe`, so "Update engine" (`yt-dlp -U`) fixes YouTube changes without a new app build.
  A stale bundled yt-dlp is why the old setup stopped working ("The page needs to be reloaded").
- Deno is the JavaScript runtime yt-dlp needs to solve YouTube's player challenges for full video formats.
- Captions are downloaded as WebVTT and cleaned by the app itself, so transcripts never need ffmpeg.
- Transcripts and metadata: 2 long-running yt-dlp processes (`-j -a <batch>`) stream each video's info, skipping stream lists and the player JavaScript (`youtube:skip=hls,dash;player_skip=js`).
  The app then downloads the chosen caption file itself (YouTube's SRT, about 1/5 the size of WebVTT), with shared pacing, back-off on HTTP 429 (15/45/120 s), in-place retries on time-outs and up to two retry passes.
  Measured on `@theAIsearch` over a slow line: 4.7 s per video (about 35 s with one full yt-dlp call per video).
- Which caption track: human captions in the chosen language, else YouTube's auto captions in the spoken language (`en-orig`).
  Machine-translated tracks (including plain `en` on an English video since 2025) are rate-limited hard by YouTube, so they are used only when "Else use the video's own language" is unticked.
- An info with no language and no caption lists is what a timed-out request returns, so it gets one retry before "no captions" is reported.
- Video and audio downloads still run one yt-dlp call per video.
- "Original language" reads the video's info first, then takes human captions in the spoken language, else the `<spoken>-orig` auto track.
  YouTube also lists `-orig` tracks for AI-dubbed audio (a Vietnamese video can have `en-orig`), so the spoken language decides.

## Limits

- Videos that need a login (age-restricted, members-only, "confirm you're not a bot") need Settings → "Use my browser login".
  Chrome and Edge lock their cookie database while open; Firefox is the most reliable.
- Asking for a language the video is not spoken in (with the fallback off) uses YouTube's translations, which YouTube throttles: expect waits.
- On a slow connection keep "Parallel downloads" at 2; 4 caused timeouts in testing.
- The portable folder is about 540 MB (228 MB zipped) because ffmpeg (390 MB) and Deno (97 MB) are bundled.
- Download only content you have the right to use.
