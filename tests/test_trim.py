"""Trim helpers."""

from core.trim_time import ms_to_stamp, parse_time_to_ms, stamp_to_ffmpeg


def test_ms_to_stamp() -> None:
    assert ms_to_stamp(0) == "00:00.000"
    assert ms_to_stamp(65_500) == "01:05.500"
    assert ms_to_stamp(3_661_000) == "1:01:01.000"


def test_stamp_to_ffmpeg() -> None:
    assert stamp_to_ffmpeg(1500) == "1.500"


def test_parse_time_to_ms() -> None:
    assert parse_time_to_ms("65.5") == 65_500
    assert parse_time_to_ms("01:05.500") == 65_500
    assert parse_time_to_ms("1:01:01.000") == 3_661_000
    assert parse_time_to_ms("") is None
    assert parse_time_to_ms("bad") is None
