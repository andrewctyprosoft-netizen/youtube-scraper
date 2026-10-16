"""Caption parsing and cleaning."""
from __future__ import annotations

from conftest import ROLLING_VTT, SRT_FROM_FFMPEG
from ytscraper import captions as cap


def lines(cues):
    return [ln for c in cues for ln in c.lines]


def test_parse_vtt_keeps_cues_with_space_only_lines():
    cues = cap.parse_captions(ROLLING_VTT)
    assert cues[0].lines == ["[âm nhạc]"]
    assert cues[0].start == 1.964
    assert cues[2].lines == ["Kính chào quý vị"]  # word-timing tags stripped
    assert cues[-1].lines[-1] == "của báo & đài."  # entities decoded


def test_rolling_captions_appear_once():
    cleaned = cap.clean_cues(cap.parse_captions(ROLLING_VTT))
    assert lines(cleaned) == ["[âm nhạc]", "Kính chào quý vị", "và các bạn năm 2024", "của báo & đài."]


def test_numbers_at_line_end_survive():
    # The old srt_to_txt_converter.py deleted any line ending in digits.
    cleaned = cap.clean_cues(cap.parse_captions(SRT_FROM_FFMPEG))
    assert "it is 2024" in lines(cleaned)


def test_srt_identifiers_are_not_text():
    cues = cap.parse_captions(SRT_FROM_FFMPEG)
    assert all(not ln.isdigit() for ln in lines(cues))
    assert cues[1].lines == ["Hello everyone", "welcome to the show"]


def test_remove_sound_tags():
    cleaned = cap.clean_cues(cap.parse_captions(SRT_FROM_FFMPEG), remove_tags=True)
    assert "[Music]" not in lines(cleaned)
    assert cap.remove_sound_tags(">> [Vỗ tay] Xin chào ♪") == "Xin chào"


def test_remove_all_repeats_vs_rolling_window():
    cues = [cap.Cue(i, i + 1, [txt]) for i, txt in enumerate(["A", "B", "C", "D", "A"])]
    assert lines(cap.clean_cues(cues)) == ["A", "B", "C", "D", "A"]
    assert lines(cap.clean_cues(cues, remove_all_repeats=True)) == ["A", "B", "C", "D"]


def test_growing_karaoke_line_is_merged():
    cues = [cap.Cue(0, 1, ["Hello"]), cap.Cue(1, 2, ["Hello world"]), cap.Cue(2, 3, ["Next one"])]
    out = cap.clean_cues(cues)
    assert lines(out) == ["Hello world", "Next one"]
    assert out[0].end == 2


def test_rolling_off_keeps_duplicates():
    cues = cap.parse_captions(SRT_FROM_FFMPEG)
    assert lines(cap.clean_cues(cues, remove_rolling=False)).count("Hello everyone") == 2


def test_to_srt_round_trip():
    cleaned = cap.clean_cues(cap.parse_captions(ROLLING_VTT))
    srt = cap.to_srt(cleaned)
    assert srt.startswith("1\n00:00:01,964 --> 00:00:09,815\n[âm nhạc]")
    again = cap.parse_captions(srt)
    assert lines(again) == lines(cleaned)


def test_paragraphs_break_on_pause_and_speaker():
    cues = [cap.Cue(0, 1, ["x" * 130 + "."]), cap.Cue(5, 6, ["After a pause"]), cap.Cue(6, 7, [">> New speaker"])]
    paras = cap.to_paragraphs(cues)
    assert [p[1] for p in paras] == ["x" * 130 + ".", "After a pause", "New speaker"]
    assert paras[1][0] == 5


def test_paragraph_joins_cjk_without_spaces():
    cues = [cap.Cue(0, 1, ["你好"]), cap.Cue(1, 2, ["世界"])]
    assert cap.to_paragraphs(cues)[0][1] == "你好世界"


def test_transcript_blocks_timestamps_and_lines():
    cues = [cap.Cue(65, 66, ["one"]), cap.Cue(3725, 3726, ["two"])]
    assert cap.transcript_blocks(cues, layout="lines", timestamps=True) == ["[01:05] one", "[1:02:05] two"]


def test_format_timestamp_rounding():
    assert cap.format_timestamp(1.9999, srt=True) == "00:00:01,999"
    assert cap.format_timestamp(3661.5, srt=True) == "01:01:01,500"


def test_plain_text_input():
    cues = cap.cues_from_plain_text("a\n\n a \nb\nb\n")
    assert lines(cap.clean_cues(cues)) == ["a", "b"]
