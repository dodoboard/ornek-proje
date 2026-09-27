"""Parser for `ffmpeg -progress pipe:1` key=value output."""

from __future__ import annotations

from collections.abc import Callable


class FfmpegProgress:
    """Feed stdout lines; calls `on_fraction(0..1)` whenever out_time advances."""

    def __init__(self, total_duration_s: float, on_fraction: Callable[[float], None]) -> None:
        self.total_us = max(1, int(total_duration_s * 1_000_000))
        self.on_fraction = on_fraction
        self.done = False

    def feed(self, line: str) -> None:
        key, sep, value = line.strip().partition("=")
        if not sep:
            return
        if key in ("out_time_us", "out_time_ms"):  # both are microseconds in modern ffmpeg
            try:
                elapsed = int(value)
            except ValueError:
                return
            self.on_fraction(min(1.0, max(0.0, elapsed / self.total_us)))
        elif key == "progress" and value == "end":
            self.done = True
            self.on_fraction(1.0)
