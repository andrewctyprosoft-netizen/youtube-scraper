"""Make ``app/`` importable and share sample captions."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app"))

ROLLING_VTT = """WEBVTT
Kind: captions
Language: vi

00:00:01.964 --> 00:00:09.815 align:start position:0%

[âm nhạc]

00:00:09.815 --> 00:00:09.825 align:start position:0%



00:00:14.599 --> 00:00:16.189 align:start position:0%

Kính<00:00:14.799><c> chào</c><00:00:15.000><c> quý</c><00:00:15.160><c> vị</c>

00:00:16.189 --> 00:00:16.199 align:start position:0%
Kính chào quý vị


00:00:16.199 --> 00:00:17.750 align:start position:0%
Kính chào quý vị
và<00:00:16.359><c> các</c><00:00:16.480><c> bạn</c><00:00:16.600><c> năm</c><00:00:16.760><c> 2024</c>

00:00:17.750 --> 00:00:17.760 align:start position:0%
và các bạn năm 2024


00:00:17.760 --> 00:00:19.109 align:start position:0%
và các bạn năm 2024
của<00:00:17.880><c> báo &amp; đài.</c>
"""

SRT_FROM_FFMPEG = """1
00:00:01,000 --> 00:00:03,000
Hello everyone

2
00:00:03,000 --> 00:00:05,000
Hello everyone
welcome to the show

3
00:00:05,000 --> 00:00:07,000
welcome to the show
[Music]

4
00:00:07,000 --> 00:00:09,000
it is 2024
"""
