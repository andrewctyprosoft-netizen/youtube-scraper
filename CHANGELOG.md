# Changelog

## 2.2.1 — 2026-10-16

- Changed: English-only interface; the English / Tiếng Việt switch is gone.
- Changed: captions default to English for new installs, and English is first in the caption-language list (other languages stay available there).
- Changed: the start-here note is English only (`START HERE.txt`).

## 2.2.0 — 2026-10-16

- Added: step 3 "Order" — As listed, Title A → Z, Title Z → A.
  It sets the file numbers, the download order, and the order in the Word file, combined text file and CSV; the video list shows the same order.
  A → Z ignores accents, capitals and leading symbols (Ánh with Anh, Đà with Da) and reads numbers as numbers (Part 2 before Part 10).
- Added: "Number file names in this order (001 - …)" moved from Settings to step 3; numbers widen past 999 videos.
- Fixed: video and audio files now get exactly the same name as the transcript, subtitle and thumbnail of the same video (yt-dlp used its own title formatting, e.g. "｜" instead of "-").
- Fixed: videos without captions now get their thumbnail too.
- Fixed: files opened from the app ("Open Word file") made Word load a DLL from the app folder, which then stayed locked while Word was open.
- Changed: building updates the app folder file by file, so settings.json and a folder in use survive a rebuild.

## 2.1.0 — 2026-10-16

Transcripts are about 7× faster and no longer get blocked.

- Fixed: "Failed: YouTube is limiting requests" after a few videos.
  YouTube rate-limits machine-translated caption tracks (HTTP 429), and since 2025 plain `en` on an English video is such a track.
  The app now takes human captions, else the spoken-language track (`en-orig`), and uses a translation only when you untick the fallback.
- Changed: transcripts and metadata come from 2 long-running yt-dlp processes that skip the stream lists and player JavaScript; caption files download directly.
  Measured on `@theAIsearch` over a slow line: 4.7 s per video instead of about 35 s, 40 of 40 done, no 429.
- Added: shared back-off on HTTP 429 (15 s, 45 s, 120 s) and up to two automatic retry passes for failed videos.
- Changed: captions download as YouTube's own SRT (about 1/5 the size of WebVTT, same text after cleaning).
- Fixed: on a slow line, caption time-outs started extra yt-dlp processes, which slowed everything further; time-outs are now retried in place.
- Added: videos whose info comes back empty after a network timeout are retried instead of being reported as "no captions".
- Added: Settings → "Parallel downloads" (1–4, default 2), live "s per video · min left" in the status bar, and a "Tick failed only" button.
- Fixed: a video finished just before Stop is kept in the Word file; videos that fail for good in an early pass are no longer counted as done.
- Fixed: the list's buttons (Tick all, Remove…) were pushed off-screen on 768-pixel-high screens.
- Fixed: thumbnails download directly as JPG; rebuilding the app keeps `settings.json`.

## 2.0.0 — 2026-10-16

Rebuilt as a portable desktop app for non-technical users.

- Added a bilingual (English / Tiếng Việt) window with light and dark themes that fits 1366×768 laptop screens.
- Added links box: single videos, link lists, playlists, channels, `.txt` files and YouTube search, all in one list with tick-boxes and a filter.
- Added transcript downloads in any language or the video's spoken language, with fallback when the chosen language is missing.
- Added duplicate-line removal for rolling auto-captions, optional removal of lines repeated anywhere, and sound-tag removal.
- Added one combined Word file with each video's title as a heading, a clickable contents list and a channel/date/link line.
- Added TXT, clean SRT, combined TXT and CSV outputs; MP4 (quality choice), MP3 with cover art, thumbnails.
- Added "Combine my files" tab that replaces `file_combiner.py` and `srt_to_txt_converter.py`.
- Added "Update engine" button, per-video status, HTTP 429 wait-and-retry, caption cache for fast re-runs, and safe saving when a Word file is open.
- Fixed: downloads failed with the bundled yt-dlp 2025.09.05 ("The page needs to be reloaded"); now uses yt-dlp 2026.08.19 plus Deno.
- Fixed: the old SRT→TXT converter deleted any caption line ending in a number (for example "năm 2024").
- Fixed: transcripts kept every auto-caption line twice.
- Moved the old commands and scripts to `legacy/`.

## 1.0 — 2025-09

- yt-dlp command lines in `instruction.txt`, `file_combiner.py` and `srt_to_txt_converter.py`.
