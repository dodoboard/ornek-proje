from __future__ import annotations

from app.services.ffmpeg.progress import FfmpegProgress


def test_progress_parses_out_time_and_end() -> None:
    fractions: list[float] = []
    tracker = FfmpegProgress(4, fractions.append)
    for line in [
        "frame=10",
        "out_time_us=1000000",
        "out_time_ms=3000000",
        "out_time_us=N/A",
        "bogus",
        "progress=end",
    ]:
        tracker.feed(line)
    assert fractions == [0.25, 0.75, 1.0]
    assert tracker.done
