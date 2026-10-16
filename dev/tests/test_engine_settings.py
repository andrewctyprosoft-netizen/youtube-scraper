"""Engine helpers, settings and translations."""
from __future__ import annotations

import json
from datetime import date

from ytscraper import i18n, settings
from ytscraper.engine import Auth, Engine, Tools, _json_from_output, classify_error


def test_base_args_use_bundled_tools(tmp_path):
    (tmp_path / "tools").mkdir()
    for exe in ("yt-dlp.exe", "deno.exe", "ffmpeg.exe"):
        (tmp_path / "tools" / exe).write_bytes(b"")
    tools = Tools.discover(tmp_path)
    assert tools.ytdlp == [str(tmp_path / "tools" / "yt-dlp.exe")]
    args = tools.base_args()
    assert ["--js-runtimes", f"deno:{tmp_path / 'tools' / 'deno.exe'}"] == args[args.index("--js-runtimes"):][:2]
    assert args[args.index("--ffmpeg-location") + 1] == str(tmp_path / "tools")
    assert "--ignore-config" in args and "--no-update" in args


def test_auth_args():
    assert Auth().args() == []
    assert Auth(browser="firefox").args() == ["--cookies-from-browser", "firefox"]
    assert Auth(browser="firefox", cookies_file="c.txt").args() == ["--cookies", "c.txt"]


def test_classify_error():
    assert classify_error("ERROR: ... HTTP Error 429: Too Many Requests") == "rate_limited"
    assert classify_error("Sign in to confirm you're not a bot") == "bot_check"
    assert classify_error("ERROR: [youtube] x: Video unavailable") == "unavailable"
    assert classify_error("The page needs to be reloaded.") == "outdated"
    assert classify_error("something odd") == "unknown"


def test_json_from_noisy_output():
    out = 'WARNING: x\n{"title": "Bản tin", "entries": []}\n'
    assert _json_from_output(out)["title"] == "Bản tin"
    assert _json_from_output("ERROR: nope") is None


def test_list_entries_flattens_playlists(tmp_path):
    pages = {
        "https://www.youtube.com/@x/playlists": {"title": "x", "entries": [
            {"_type": "url", "ie_key": "YoutubeTab", "url": "https://www.youtube.com/playlist?list=PL1", "title": "P1"}]},
        "https://www.youtube.com/playlist?list=PL1": {"title": "P1", "entries": [
            {"id": "dQw4w9WgXcQ", "title": "Song", "duration": 213, "channel": "Rick"}, None,
            {"id": "short", "title": "bad id"}]},
    }

    def runner(cmd, on_line=None, cancel=None):
        return 0, json.dumps(pages[cmd[-1]])

    eng = Engine(Tools(["yt-dlp"], None, None, None, True), runner=runner)
    found = eng.list_entries("https://www.youtube.com/@x/playlists")
    assert [(e.id, e.source, e.duration) for e in found] == [("dQw4w9WgXcQ", "P1", 213)]


def test_version_age():
    assert Engine.version_age_days("2026.08.19", date(2026, 10, 16)) == 58
    assert Engine.version_age_days("garbage") is None


def test_settings_round_trip_and_bad_values(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"delay": 3, "language": "en", "save_txt": "yes", "unknown": 1}), encoding="utf-8")
    s = settings.load(path)
    assert s.delay == 3.0 and s.language == "en"
    assert s.save_txt is False  # wrong type ignored
    s.output_name = "Ghi chú"
    settings.save(s, path)
    assert settings.load(path).output_name == "Ghi chú"
    assert settings.load(tmp_path / "missing.json").language == "en"


def test_every_string_has_both_languages():
    for key, entry in i18n.STRINGS.items():
        assert set(entry) == {"en", "vi"}, key
        for text in entry.values():
            assert text.count("{") == text.count("}"), key


def test_translate_and_fallback():
    i18n.set_language("vi")
    assert i18n.t("start") == "Bắt đầu"
    assert i18n.t("added_n", n=3) == "Đã thêm 3 video."
    i18n.set_language("xx")
    assert i18n.t("start") == "Start"
    assert i18n.t("no-such-key") == "no-such-key"
