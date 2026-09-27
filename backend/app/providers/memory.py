"""GPU memory helpers. Only call optimisation methods that the pipeline object actually has."""

from __future__ import annotations

import gc
import logging
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from app.core.config import PerformanceProfile
from app.core.errors import AppError, ModelLoadError, VramOutOfMemoryError

logger = logging.getLogger(__name__)


def free_memory() -> None:
    gc.collect()
    torch = sys.modules.get("torch")  # never import torch just to clean up
    if torch is not None and torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.ipc_collect()


def _is_oom(exc: BaseException) -> bool:
    torch = sys.modules.get("torch")
    if torch is not None and isinstance(exc, getattr(torch.cuda, "OutOfMemoryError", ())):
        return True
    return isinstance(exc, RuntimeError) and "out of memory" in str(exc).lower()


@contextmanager
def translate_gpu_errors(*, loading: bool = False) -> Iterator[None]:
    """Map low-level failures to user-facing AppErrors (details stay in the log)."""
    try:
        yield
    except AppError:
        raise
    except Exception as exc:
        if _is_oom(exc):
            free_memory()
            raise VramOutOfMemoryError() from exc
        if loading:
            logger.exception("model_load_failed")
            raise ModelLoadError() from exc
        raise


def apply_pipeline_optimizations(pipe: Any, profile: PerformanceProfile, device: str) -> list[str]:
    """Configure a diffusers pipeline for the selected profile. Returns what was applied."""
    applied: list[str] = []
    if device != "cuda":
        return applied

    def call(name: str, target: Any = pipe) -> bool:
        method = getattr(target, name, None)
        if callable(method):
            method()
            applied.append(name)
            return True
        return False

    if profile is PerformanceProfile.PERFORMANCE:
        pipe.to("cuda")
        applied.append("to_cuda")
    elif profile is PerformanceProfile.BALANCED:
        if not call("enable_model_cpu_offload"):
            pipe.to("cuda")
            applied.append("to_cuda")
    else:
        if not call("enable_sequential_cpu_offload") and not call("enable_model_cpu_offload"):
            pipe.to("cuda")
            applied.append("to_cuda")
        vae = getattr(pipe, "vae", None)
        if vae is not None and call("enable_tiling", vae):
            applied[-1] = "vae.enable_tiling"
        call("enable_attention_slicing")
    return applied
