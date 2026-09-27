from __future__ import annotations

import subprocess
from pathlib import Path

from app.services.system_info import detect_binary, detect_gpu, parse_nvidia_smi


def _completed(stdout: str, code: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=code, stdout=stdout, stderr="")


def test_parse_nvidia_smi_skips_malformed_lines() -> None:
    out = "0, NVIDIA GeForce RTX 5080 Laptop GPU, 580.10, 16303, 512, 15791\ngarbage\n"
    [gpu] = parse_nvidia_smi(out)
    assert gpu.name == "NVIDIA GeForce RTX 5080 Laptop GPU"
    assert gpu.memory_total_mb == 16303


def test_detect_gpu_without_driver() -> None:
    status = detect_gpu(which=lambda name: None)
    assert status.status == "missing"


def test_detect_gpu_ok() -> None:
    status = detect_gpu(
        which=lambda n: "/usr/bin/nvidia-smi", run=lambda a: _completed("0, GPU, 1.0, 100, 10, 90")
    )
    assert status.status == "ok"
    assert status.devices[0].memory_free_mb == 90


def test_detect_gpu_nonzero_exit() -> None:
    status = detect_gpu(which=lambda n: "nvidia-smi", run=lambda a: _completed("", code=9))
    assert status.status == "error"


def test_detect_binary_missing_and_ok(tmp_path: Path) -> None:
    assert detect_binary("ffmpeg", None, which=lambda n: None).status == "missing"
    assert detect_binary("ffmpeg", tmp_path / "nope.exe").status == "missing"

    calls: list[list[str]] = []

    def run(args: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return _completed("ffmpeg version 7.1\nmore")

    status = detect_binary("ffmpeg", None, which=lambda n: "/usr/bin/ffmpeg", run=run)
    assert status.status == "ok"
    assert status.version == "ffmpeg version 7.1"
    assert calls == [["/usr/bin/ffmpeg", "-hide_banner", "-version"]]
