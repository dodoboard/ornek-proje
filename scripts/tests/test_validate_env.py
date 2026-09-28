from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import validate_env as ve  # noqa: E402


def _names(checks: list[ve.Check]) -> dict[str, ve.Check]:
    return {c.name: c for c in checks}


def test_check_python_reports_version() -> None:
    check = ve.check_python()
    assert check.critical
    assert check.data["version"].startswith(f"{sys.version_info.major}.{sys.version_info.minor}")
    expected = ve.OK if sys.version_info[:2] == ve.MIN_PYTHON else (
        ve.WARN if sys.version_info[:2] > ve.MIN_PYTHON else ve.FAIL)
    assert check.status == expected


def test_missing_torch_is_critical(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ve, "_import_optional", lambda name: None)
    [check] = ve.check_torch()
    assert check.status == ve.MISSING
    assert check.failed_critical


def _fake_torch(arch_list: list[str], capability: tuple[int, int]) -> types.SimpleNamespace:
    cuda = types.SimpleNamespace(
        is_available=lambda: True,
        current_device=lambda: 0,
        get_device_name=lambda i: "Fake GPU",
        get_device_capability=lambda i: capability,
        mem_get_info=lambda i: (8 * 1024**3, 16 * 1024**3),
        get_arch_list=lambda: arch_list,
        is_bf16_supported=lambda: True,
    )
    return types.SimpleNamespace(__version__="9.9.9", version=types.SimpleNamespace(cuda="12.8"), cuda=cuda)


def test_blackwell_arch_missing_from_build_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    torch = _fake_torch(["sm_80", "sm_90"], (12, 0))
    monkeypatch.setattr(ve, "_import_optional", lambda name: torch if name == "torch" else None)
    checks = _names(ve.check_torch())
    assert checks["cuda"].status == ve.OK
    assert checks["cuda"].data["vram_total_gb"] == 16.0
    assert checks["cuda_arch"].status == ve.FAIL
    assert checks["cuda_arch"].failed_critical


def test_blackwell_arch_present_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    torch = _fake_torch(["sm_90", "sm_120"], (12, 0))
    monkeypatch.setattr(ve, "_import_optional", lambda name: torch if name == "torch" else None)
    assert _names(ve.check_torch())["cuda_arch"].status == ve.OK


def test_diffusers_signature_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    class GoodKlein:
        def __call__(self, image=None, prompt=None, height=None, width=None, num_inference_steps=4,
                     guidance_scale=1.0, generator=None, callback_on_step_end=None): ...

    class BadWan:
        def __call__(self, prompt=None): ...

    fake = types.SimpleNamespace(__version__="0.40.0", Flux2KleinPipeline=GoodKlein, WanPipeline=BadWan)
    monkeypatch.setattr(ve, "_import_optional", lambda name: fake if name == "diffusers" else None)
    checks = _names(ve.check_diffusers())

    assert checks["diffusers.Flux2KleinPipeline"].status == ve.OK
    assert checks["diffusers.WanPipeline"].status == ve.FAIL
    assert "negative_prompt" in checks["diffusers.WanPipeline"].data["missing"]
    assert not checks["diffusers.WanPipeline"].critical
    assert checks["diffusers.Flux2Pipeline"].status == ve.MISSING


def test_missing_klein_is_critical(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = types.SimpleNamespace(__version__="0.30.0")
    monkeypatch.setattr(ve, "_import_optional", lambda name: fake if name == "diffusers" else None)
    assert _names(ve.check_diffusers())["diffusers.Flux2KleinPipeline"].failed_critical


def test_ffmpeg_missing_is_critical() -> None:
    checks = _names(ve.check_ffmpeg(which=lambda name: None))
    assert checks["ffmpeg"].failed_critical
    assert checks["ffprobe"].failed_critical


def test_ollama_unreachable_is_not_critical() -> None:
    check = ve.check_ollama("http://127.0.0.1:9", timeout=0.5)
    assert check.status == ve.MISSING
    assert not check.critical


def test_iter_repo_ids_reads_all_sections() -> None:
    config = {
        "image": {"default": "a", "models": {"a": {"repo_id": "org/a"}, "b": {"local_path": "/x"}},
                  "inpaint": {"c": {"repo_id": "org/c"}}},
        "video": {"models": {"v": {"repo_id": "org/v"}}},
        "notes": "ignored",
    }
    assert ve.iter_repo_ids(config) == [("image.a", "org/a"), ("image.c", "org/c"), ("video.v", "org/v")]


def test_repo_config_parses_and_has_defaults() -> None:
    yaml = pytest.importorskip("yaml")
    config = yaml.safe_load(ve.MODELS_CONFIG.read_text(encoding="utf-8"))
    for section in ("image", "video", "llm", "tts", "lipsync", "asr", "segmentation", "upscale"):
        assert config[section]["default"] in config[section]["models"], section
    assert ve.iter_repo_ids(config)


def test_main_exit_code_reflects_critical_failures(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setattr(ve, "collect", lambda args: [ve.Check("x", ve.OK, "fine", critical=True)])
    assert ve.main(["--json"]) == 0
    monkeypatch.setattr(ve, "collect", lambda args: [ve.Check("x", ve.FAIL, "bad", critical=True)])
    assert ve.main([]) == 1
    assert "1 critical check(s) failed" in capsys.readouterr().out
