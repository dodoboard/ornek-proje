"""Device/precision detection. Imports torch lazily so the API process never initialises CUDA."""

from __future__ import annotations

import importlib.util
from dataclasses import asdict, dataclass, field
from typing import Any

from app.core.config import Device


@dataclass(frozen=True)
class DeviceInfo:
    device: str  # "cuda" | "cpu"
    dtype: str  # "bfloat16" | "float16" | "float32"
    torch_version: str | None = None
    cuda_version: str | None = None
    gpu_name: str | None = None
    capability: str | None = None
    arch_supported: bool | None = None
    arch_list: list[str] = field(default_factory=list)
    total_vram_gb: float | None = None
    bf16_supported: bool = False
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def detect_device(preference: Device = Device.AUTO) -> DeviceInfo:
    if importlib.util.find_spec("torch") is None:
        return DeviceInfo(device="cpu", dtype="float32", notes=["PyTorch is not installed."])

    import torch

    version = str(torch.__version__)
    cuda_build = getattr(torch.version, "cuda", None)
    if preference is Device.CPU or not torch.cuda.is_available():
        note = "CPU forced by DEVICE=cpu." if preference is Device.CPU else "CUDA is not available."
        return DeviceInfo(
            device="cpu", dtype="float32", torch_version=version, cuda_version=cuda_build, notes=[note]
        )

    index = torch.cuda.current_device()
    major, minor = torch.cuda.get_device_capability(index)
    arch = f"sm_{major}{minor}"
    arch_list = [str(a) for a in torch.cuda.get_arch_list()]
    bf16 = bool(torch.cuda.is_bf16_supported())
    props = torch.cuda.get_device_properties(index)
    notes = []
    arch_ok = arch in arch_list
    if not arch_ok:
        notes.append(f"Installed PyTorch has no kernels for {arch}; install a newer CUDA build.")
    return DeviceInfo(
        device="cuda",
        dtype="bfloat16" if bf16 else "float16",
        torch_version=version,
        cuda_version=cuda_build,
        gpu_name=torch.cuda.get_device_name(index),
        capability=f"{major}.{minor}",
        arch_supported=arch_ok,
        arch_list=arch_list,
        total_vram_gb=round(props.total_memory / 1024**3, 2),
        bf16_supported=bf16,
        notes=notes,
    )
