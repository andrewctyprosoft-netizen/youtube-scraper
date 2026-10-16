"""Turning pasted text into targets."""
from __future__ import annotations

import pytest

from ytscraper.links import classify_url, parse_input, search_url


@pytest.mark.parametrize("url,kind,label", [
    ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "video", "dQw4w9WgXcQ"),
    ("https://youtu.be/dQw4w9WgXcQ?si=xyz", "video", "dQw4w9WgXcQ"),
    ("youtube.com/shorts/dQw4w9WgXcQ", "video", "dQw4w9WgXcQ"),
    ("https://m.youtube.com/watch?v=dQw4w9WgXcQ&list=PL123456789012&index=2", "video", "dQw4w9WgXcQ"),
    ("https://www.youtube.com/live/dQw4w9WgXcQ", "video", "dQw4w9WgXcQ"),
    ("https://www.youtube.com/embed/dQw4w9WgXcQ", "video", "dQw4w9WgXcQ"),
    ("https://www.youtube.com/playlist?list=PLLojVvWCZ5N4", "playlist", "PLLojVvWCZ5N4"),
    ("https://www.youtube.com/@TED", "channel", "@TED"),
    ("https://www.youtube.com/@TED/shorts", "channel", "@TED"),
    ("https://www.youtube.com/channel/UCAuUUnT6oDeKwE6v1NGQxug/featured", "channel", "channel/UCAuUUnT6oDeKwE6v1NGQxug"),
])
def test_classify(url, kind, label):
    target = classify_url(url)
    assert target is not None
    assert (target.kind, target.label) == (kind, label)


def test_channel_defaults_to_videos_tab():
    assert classify_url("https://www.youtube.com/@TED").url.endswith("/@TED/videos")
    assert classify_url("https://www.youtube.com/@TED/featured").url.endswith("/@TED/videos")
    assert classify_url("https://www.youtube.com/@TED/streams").url.endswith("/@TED/streams")


def test_non_youtube_is_ignored():
    assert classify_url("https://vimeo.com/123") is None
    assert classify_url("https://www.youtube.com/") is None


def test_parse_messy_text():
    text = """# my list
    Watch https://youtu.be/dQw4w9WgXcQ and https://www.youtube.com/watch?v=dQw4w9WgXcQ (dup)
    https://www.youtube.com/playlist?list=PLLojVvWCZ5N4, next
    B3G9oTQ3a-k
    bản tin thời sự
    programming
    """
    targets, searches = parse_input(text)
    assert [t.label for t in targets] == ["dQw4w9WgXcQ", "PLLojVvWCZ5N4", "B3G9oTQ3a-k"]
    assert searches == ["bản tin thời sự", "programming"]  # 11-letter word is not an ID


def test_search_url_clamps():
    assert search_url("x", 0) == "ytsearch1:x"
    assert search_url("x", 999) == "ytsearch200:x"
