#!/usr/bin/env python3
"""Phase 0 environment validator for AI Influencer Studio.

Runs with the standard library only; optional packages are probed, never required.

Usage:
    python scripts/validate_env.py                 # human-readable report
    python scripts/validate_env.py --json          # machine-readable report
    python scripts/validate_env.py --check-hf      # verify model repos + license tags (needs huggingface_hub)
    python scripts/validate_env.py --smoke         # load default FLUX.2 model and render one 512x512 image

Exit code: 0 if no critical check failed, 1 otherwise.
"""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import inspect
import json
import platform
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
MODELS_CONFIG = ROOT / "backend" / "config" / "models.yaml"
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
MIN_PYTHON = (3, 12)
MIN_FREE_DISK_GB = 100
BLACKWELL_ARCH = "sm_120"

OK, WARN, MISSING, FAIL, SKIP = "ok", "warn", "missing", "fail", "skip"

# Pipeline classes and the __call__ parameters our providers rely on.
# Verified against diffusers v0.40.0 source (see docs/PHASE0_VALIDATION.md).
DIFFUSERS_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "Flux2KleinPipeline": ("image", "prompt", "height", "width", "num_inference_steps",
                           "guidance_scale", "generator", "callback_on_step_end"),
    "Flux2KleinInpaintPipeline": ("image", "image_reference", "mask_image", "strength",
                                  "callback_on_step_end"),
    "Flux2Pipeline": ("image", "prompt", "guidance_scale", "callback_on_step_end"),
    "WanPipeline": ("prompt", "negative_prompt", "num_frames", "callback_on_step_end"),
    "WanImageToVideoPipeline": ("image", "prompt", "negative_prompt", "num_frames", "last_image",
                                "output_type", "callback_on_step_end"),
    "LTX2ImageToVideoPipeline": ("image", "prompt", "negative_prompt", "callback_on_step_end"),
}

OPTIONAL_PACKAGES: dict[str, str] = {
    "transformers": "FLUX.2 / Wan text encoders",
    "accelerate": "enable_model_cpu_offload",
    "ftfy": "Wan prompt cleaning (diffusers Wan pipelines)",
    "huggingface_hub": "model download / --check-hf",
    "faster_whisper": "captions (ASR)",
    "ctranslate2": "faster-whisper backend",
    "spandrel": "upscaler loading",
    "rembg": "segmentation fallback",
    "piper": "Piper TTS (GPL-3.0)",
    "PIL": "image IO",
    "yaml": "config parsing",
}


@dataclass
class Check:
    name: str
    status: str
    detail: str
    critical: bool = False
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def failed_critical(self) -> bool:
        return self.critical and self.status in (MISSING, FAIL)


def _module_version(module: Any) -> str:
    return str(getattr(module, "__version__", "unknown"))


def _import_optional(name: str) -> Any | None:
    if importlib.util.find_spec(name) is None:
        return None
    try:
        return importlib.import_module(name)
    except Exception:  # broken installs must not crash the validator
        return None


def _run(args: list[str], timeout: float = 15.0) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None


# --------------------------------------------------------------------------- checks


def check_python() -> Check:
    version = sys.version_info[:3]
    text = ".".join(map(str, version))
    data = {"version": text, "executable": sys.executable, "platform": platform.platform()}
    if version[:2] == MIN_PYTHON:
        return Check("python", OK, f"Python {text}", critical=True, data=data)
    if version[:2] > MIN_PYTHON:
        return Check("python", WARN, f"Python {text}; project targets 3.12", critical=True, data=data)
    return Check("python", FAIL, f"Python {text}; 3.12 required", critical=True, data=data)


def check_torch() -> list[Check]:
    torch = _import_optional("torch")
    if torch is None:
        return [Check("torch", MISSING,
                      "PyTorch not installed. Install the CUDA build for your GPU (see README).",
                      critical=True)]

    checks = [Check("torch", OK, f"torch {_module_version(torch)}", critical=True,
                    data={"version": _module_version(torch),
                          "cuda_build": getattr(torch.version, "cuda", None)})]

    if not torch.cuda.is_available():
        checks.append(Check("cuda", MISSING,
                            "CUDA not available: CPU-only torch build or missing NVIDIA driver.",
                            critical=True))
        return checks

    index = torch.cuda.current_device()
    name = torch.cuda.get_device_name(index)
    major, minor = torch.cuda.get_device_capability(index)
    free_b, total_b = torch.cuda.mem_get_info(index)
    arch_list = list(torch.cuda.get_arch_list())
    device_arch = f"sm_{major}{minor}"
    data = {
        "device": name,
        "capability": f"{major}.{minor}",
        "arch_list": arch_list,
        "vram_total_gb": round(total_b / 1024**3, 2),
        "vram_free_gb": round(free_b / 1024**3, 2),
        "bf16": bool(torch.cuda.is_bf16_supported()),
    }
    checks.append(Check("cuda", OK, f"{name} ({device_arch}), "
                        f"{data['vram_free_gb']}/{data['vram_total_gb']} GB free", critical=True, data=data))

    if device_arch not in arch_list:
        checks.append(Check("cuda_arch", FAIL,
                            f"torch build lacks kernels for {device_arch} (has {', '.join(arch_list)}). "
                            "Install a newer CUDA wheel (cu128 or later for Blackwell).",
                            critical=True, data={"device_arch": device_arch}))
    else:
        checks.append(Check("cuda_arch", OK, f"torch build includes {device_arch}", critical=True))
    return checks


def check_diffusers() -> list[Check]:
    diffusers = _import_optional("diffusers")
    if diffusers is None:
        return [Check("diffusers", MISSING, "diffusers not installed", critical=True)]

    checks = [Check("diffusers", OK, f"diffusers {_module_version(diffusers)}", critical=True,
                    data={"version": _module_version(diffusers)})]
    for class_name, required in DIFFUSERS_REQUIREMENTS.items():
        # Only FLUX.2 klein is critical for the MVP image engine.
        critical = class_name == "Flux2KleinPipeline"
        cls = getattr(diffusers, class_name, None)
        if cls is None:
            checks.append(Check(f"diffusers.{class_name}", MISSING,
                                "class not exported by this diffusers version", critical=critical))
            continue
        try:
            params = set(inspect.signature(cls.__call__).parameters)
        except (TypeError, ValueError):
            checks.append(Check(f"diffusers.{class_name}", WARN, "could not inspect __call__"))
            continue
        absent = [p for p in required if p not in params]
        status = OK if not absent else FAIL
        detail = "signature ok" if not absent else f"missing parameters: {', '.join(absent)}"
        checks.append(Check(f"diffusers.{class_name}", status, detail, critical=critical,
                            data={"missing": absent}))
    return checks


def check_optional_packages() -> list[Check]:
    checks = []
    for module_name, purpose in OPTIONAL_PACKAGES.items():
        module = _import_optional(module_name)
        if module is None:
            checks.append(Check(f"pkg.{module_name}", MISSING, f"not installed ({purpose})"))
        else:
            checks.append(Check(f"pkg.{module_name}", OK, f"{_module_version(module)} ({purpose})"))
    return checks


def check_ffmpeg(which: Callable[[str], str | None] = shutil.which) -> list[Check]:
    checks = []
    ffmpeg = which("ffmpeg")
    if ffmpeg is None:
        checks.append(Check("ffmpeg", MISSING, "ffmpeg not found on PATH (set FFMPEG_PATH)", critical=True))
    else:
        version = _run([ffmpeg, "-hide_banner", "-version"])
        first_line = version.stdout.splitlines()[0] if version and version.stdout else "unknown"
        checks.append(Check("ffmpeg", OK, first_line, critical=True, data={"path": ffmpeg}))
        encoders = _run([ffmpeg, "-hide_banner", "-encoders"])
        has_x264 = bool(encoders and "libx264" in encoders.stdout)
        checks.append(Check("ffmpeg.libx264", OK if has_x264 else WARN,
                            "libx264 available" if has_x264 else "libx264 missing; H.264 output unavailable"))

    ffprobe = which("ffprobe")
    checks.append(Check("ffprobe", OK if ffprobe else MISSING,
                        ffprobe or "ffprobe not found on PATH (set FFPROBE_PATH)", critical=True))
    return checks


def check_ollama(base_url: str = DEFAULT_OLLAMA_URL, timeout: float = 3.0) -> Check:
    url = f"{base_url.rstrip('/')}/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310 (localhost only)
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        return Check("ollama", MISSING, f"Ollama not reachable at {base_url} ({exc.__class__.__name__}); "
                     "script generation will use the template fallback")
    models = [m.get("name", "?") for m in payload.get("models", [])]
    status = OK if models else WARN
    detail = f"{len(models)} model(s): {', '.join(models)}" if models else "running, but no models pulled"
    return Check("ollama", status, detail, data={"models": models})


def check_disk(path: Path = ROOT) -> Check:
    usage = shutil.disk_usage(path)
    free_gb = round(usage.free / 1024**3, 1)
    status = OK if free_gb >= MIN_FREE_DISK_GB else WARN
    detail = f"{free_gb} GB free" + ("" if status == OK else f" (models + video need >= {MIN_FREE_DISK_GB} GB)")
    return Check("disk", status, detail, data={"free_gb": free_gb})


# --------------------------------------------------------------------------- model config / HF


def load_models_config(path: Path = MODELS_CONFIG) -> dict[str, Any] | None:
    yaml = _import_optional("yaml")
    if yaml is None or not path.exists():
        return None
    with path.open(encoding="utf-8") as fh:
        loaded = yaml.safe_load(fh)
    return loaded if isinstance(loaded, dict) else None


def iter_repo_ids(config: dict[str, Any]) -> list[tuple[str, str]]:
    """Return (config_key, repo_id) pairs for every configured Hugging Face repo."""
    pairs = []
    for section_name, section in config.items():
        if not isinstance(section, dict):
            continue
        for group in ("models", "inpaint"):
            for key, entry in (section.get(group) or {}).items():
                if isinstance(entry, dict) and entry.get("repo_id"):
                    pairs.append((f"{section_name}.{key}", str(entry["repo_id"])))
    return pairs


def check_hf_models(config: dict[str, Any] | None) -> list[Check]:
    if config is None:
        return [Check("hf", SKIP, "models.yaml not readable (PyYAML missing?)")]
    hub = _import_optional("huggingface_hub")
    if hub is None:
        return [Check("hf", MISSING, "huggingface_hub not installed")]

    checks = []
    for key, repo_id in iter_repo_ids(config):
        try:
            info = hub.model_info(repo_id)
        except Exception as exc:  # gated, missing, offline, auth — all reported, none fatal
            checks.append(Check(f"hf.{key}", FAIL, f"{repo_id}: {exc.__class__.__name__}",
                                data={"repo_id": repo_id}))
            continue
        tags = list(getattr(info, "tags", None) or [])
        licenses = [t.split(":", 1)[1] for t in tags if t.startswith("license:")]
        gated = getattr(info, "gated", False)
        detail = f"{repo_id}: license={','.join(licenses) or 'unknown'} gated={gated}"
        checks.append(Check(f"hf.{key}", OK, detail,
                            data={"repo_id": repo_id, "licenses": licenses, "gated": gated,
                                  "sha": getattr(info, "sha", None)}))
    return checks


# --------------------------------------------------------------------------- smoke test


def run_smoke(config: dict[str, Any] | None) -> Check:
    """Render one small image with the default FLUX.2 model. Requires GPU + downloaded weights."""
    if config is None:
        return Check("smoke", SKIP, "models.yaml not readable")
    torch = _import_optional("torch")
    diffusers = _import_optional("diffusers")
    if torch is None or diffusers is None or not torch.cuda.is_available():
        return Check("smoke", SKIP, "requires torch with CUDA and diffusers")

    image_cfg = config["image"]
    entry = image_cfg["models"][image_cfg["default"]]
    source = entry.get("local_path") or entry["repo_id"]
    pipeline_cls = getattr(diffusers, entry["pipeline_class"], None)
    if pipeline_cls is None:
        return Check("smoke", FAIL, f"{entry['pipeline_class']} not in diffusers")

    output = ROOT / "data" / "temp" / "phase0_smoke.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    pipe = None
    try:
        pipe = pipeline_cls.from_pretrained(source, torch_dtype=dtype)
        pipe.enable_model_cpu_offload()
        torch.cuda.reset_peak_memory_stats()
        result = pipe(
            prompt="studio portrait photo of an adult woman, soft light",
            height=512,
            width=512,
            num_inference_steps=4,
            generator=torch.Generator(device="cpu").manual_seed(0),
        )
        result.images[0].save(output)
        peak_gb = round(torch.cuda.max_memory_allocated() / 1024**3, 2)
        return Check("smoke", OK, f"rendered {output.relative_to(ROOT)} (peak VRAM {peak_gb} GB)",
                     data={"peak_vram_gb": peak_gb, "source": source})
    except torch.cuda.OutOfMemoryError:
        return Check("smoke", FAIL, "CUDA out of memory")
    except Exception as exc:
        return Check("smoke", FAIL, f"{exc.__class__.__name__}: {exc}")
    finally:
        del pipe
        torch.cuda.empty_cache()


# --------------------------------------------------------------------------- report


def collect(args: argparse.Namespace) -> list[Check]:
    checks: list[Check] = [check_python()]
    checks += check_torch()
    checks += check_diffusers()
    checks += check_optional_packages()
    checks += check_ffmpeg()
    checks.append(check_ollama(args.ollama_url))
    checks.append(check_disk())
    config = load_models_config() if (args.check_hf or args.smoke) else None
    if args.check_hf:
        checks += check_hf_models(config)
    if args.smoke:
        checks.append(run_smoke(config))
    return checks


def render_text(checks: list[Check]) -> str:
    symbols = {OK: "[ OK ]", WARN: "[WARN]", MISSING: "[MISS]", FAIL: "[FAIL]", SKIP: "[SKIP]"}
    width = max(len(c.name) for c in checks)
    lines = [f"{symbols[c.status]} {c.name:<{width}}  {c.detail}{'  (critical)' if c.failed_critical else ''}"
             for c in checks]
    failed = sum(c.failed_critical for c in checks)
    lines.append("")
    lines.append("RESULT: " + ("all critical checks passed" if not failed else f"{failed} critical check(s) failed"))
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json", action="store_true", help="emit JSON")
    parser.add_argument("--check-hf", action="store_true", help="query Hugging Face for configured repos")
    parser.add_argument("--smoke", action="store_true", help="run a real FLUX.2 generation (GPU)")
    parser.add_argument("--ollama-url", default=DEFAULT_OLLAMA_URL)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    checks = collect(args)
    if args.json:
        print(json.dumps([asdict(c) for c in checks], indent=2))
    else:
        print(render_text(checks))
    return 1 if any(c.failed_critical for c in checks) else 0


if __name__ == "__main__":
    sys.exit(main())
