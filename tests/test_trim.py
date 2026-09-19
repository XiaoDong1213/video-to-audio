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
    assert parse_time_to_ms("1.500") == 1_500
    assert parse_time_to_ms("01:05.500") == 65_500
    assert parse_time_to_ms("1:01:01.000") == 3_661_000
    assert parse_time_to_ms("") is None
    assert parse_time_to_ms("bad") is None


def test_parse_optional_positive_int() -> None:
    from core.utils import parse_optional_positive_int

    assert parse_optional_positive_int("  ", "采样率") is None
    assert parse_optional_positive_int("44100", "采样率") == 44100
    try:
        parse_optional_positive_int("44.1k", "采样率")
    except ValueError as exc:
        assert "正整数" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_move_selected_keeps_gaps() -> None:
    from core.utils import move_selected

    items = ["a", "b", "c", "d"]
    assert move_selected(items, [0, 2], -1) == [0, 1]
    assert items == ["a", "c", "b", "d"]
