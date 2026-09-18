"""Pure helpers for trim timestamps (no Qt)."""

from __future__ import annotations

import re


def ms_to_stamp(ms: int) -> str:
    ms = max(0, int(ms))
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, milli = divmod(rem, 1000)
    if h:
        return f"{h:d}:{m:02d}:{s:02d}.{milli:03d}"
    return f"{m:02d}:{s:02d}.{milli:03d}"


def stamp_to_ffmpeg(ms: int) -> str:
    return f"{max(0, ms) / 1000.0:.3f}"


def parse_time_to_ms(text: str) -> int | None:
    """Parse '1:02:03.500' / '01:05.500' / '65.5' / '65' into milliseconds."""
    raw = text.strip()
    if not raw:
        return None
    if re.fullmatch(r"\d+(\.\d+)?", raw):
        return int(float(raw) * 1000)
    m = re.fullmatch(
        r"(?:(\d+):)?(\d{1,2}):(\d{1,2})(?:\.(\d{1,3}))?",
        raw,
    )
    if not m:
        return None
    hours = int(m.group(1) or 0)
    mins = int(m.group(2))
    secs = int(m.group(3))
    frac = m.group(4) or "0"
    milli = int((frac + "000")[:3])
    return ((hours * 60 + mins) * 60 + secs) * 1000 + milli
