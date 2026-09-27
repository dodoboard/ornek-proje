"""Typed application errors. Only `code` and `message` ever reach the client."""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class ErrorCode(StrEnum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    CUDA_UNAVAILABLE = "CUDA_UNAVAILABLE"
    GPU_UNSUPPORTED = "GPU_UNSUPPORTED"
    VRAM_OOM = "VRAM_OOM"
    MODEL_MISSING = "MODEL_MISSING"
    MODEL_LOAD_FAILED = "MODEL_LOAD_FAILED"
    MODEL_INVALID = "MODEL_INVALID"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    FFMPEG_MISSING = "FFMPEG_MISSING"
    DISK_FULL = "DISK_FULL"
    FILE_INVALID = "FILE_INVALID"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    UNSUPPORTED_FORMAT = "UNSUPPORTED_FORMAT"
    GENERATION_FAILED = "GENERATION_FAILED"
    GENERATION_CANCELLED = "GENERATION_CANCELLED"
    DATABASE_ERROR = "DATABASE_ERROR"
    CONSENT_REQUIRED = "CONSENT_REQUIRED"
    FACT_VIOLATION = "FACT_VIOLATION"


class AppError(Exception):
    """Base error. `message` must be safe to show to end users (no paths, no tracebacks)."""

    code: ErrorCode = ErrorCode.INTERNAL_ERROR
    status_code: int = 500
    default_message: str = "An unexpected error occurred."

    def __init__(self, message: str | None = None, *, details: dict[str, Any] | None = None) -> None:
        self.message = message or self.default_message
        self.details = details or {}
        super().__init__(self.message)

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"code": self.code.value, "message": self.message}
        if self.details:
            payload["details"] = self.details
        return payload


class NotFoundError(AppError):
    code = ErrorCode.NOT_FOUND
    status_code = 404
    default_message = "The requested resource was not found."


class ConflictError(AppError):
    code = ErrorCode.CONFLICT
    status_code = 409
    default_message = "The request conflicts with the current state."


class CudaUnavailableError(AppError):
    code = ErrorCode.CUDA_UNAVAILABLE
    status_code = 503
    default_message = "No CUDA GPU is available. Check the NVIDIA driver and the PyTorch CUDA build."


class GpuUnsupportedError(AppError):
    code = ErrorCode.GPU_UNSUPPORTED
    status_code = 503
    default_message = "This GPU is not supported by the installed PyTorch build."


class VramOutOfMemoryError(AppError):
    code = ErrorCode.VRAM_OOM
    status_code = 507
    default_message = "The GPU ran out of memory. Try the Low VRAM profile or a lower resolution."


class ModelMissingError(AppError):
    code = ErrorCode.MODEL_MISSING
    status_code = 503
    default_message = "The selected model is not downloaded or its path is invalid."


class ModelLoadError(AppError):
    code = ErrorCode.MODEL_LOAD_FAILED
    status_code = 500
    default_message = "The model failed to load. See the server log for details."


class ModelInvalidError(AppError):
    code = ErrorCode.MODEL_INVALID
    status_code = 422
    default_message = "The selected model is not valid for this operation."


class ProviderUnavailableError(AppError):
    code = ErrorCode.PROVIDER_UNAVAILABLE
    status_code = 503
    default_message = "The selected provider is not available on this machine."


class FfmpegMissingError(AppError):
    code = ErrorCode.FFMPEG_MISSING
    status_code = 503
    default_message = "FFmpeg was not found. Install it or set FFMPEG_PATH."


class DiskFullError(AppError):
    code = ErrorCode.DISK_FULL
    status_code = 507
    default_message = "Not enough disk space to complete the operation."


class FileInvalidError(AppError):
    code = ErrorCode.FILE_INVALID
    status_code = 422
    default_message = "The uploaded file is invalid or corrupted."


class FileTooLargeError(AppError):
    code = ErrorCode.FILE_TOO_LARGE
    status_code = 413
    default_message = "The uploaded file exceeds the size limit."


class UnsupportedFormatError(AppError):
    code = ErrorCode.UNSUPPORTED_FORMAT
    status_code = 415
    default_message = "This file format is not supported."


class GenerationFailedError(AppError):
    code = ErrorCode.GENERATION_FAILED
    status_code = 500
    default_message = "Generation failed. See the server log for details."


class GenerationCancelledError(AppError):
    code = ErrorCode.GENERATION_CANCELLED
    status_code = 409
    default_message = "Generation was cancelled."


class DatabaseError(AppError):
    code = ErrorCode.DATABASE_ERROR
    status_code = 500
    default_message = "A database error occurred."


class ConsentRequiredError(AppError):
    code = ErrorCode.CONSENT_REQUIRED
    status_code = 403
    default_message = "A consent record is required before using a real person's likeness or voice."


class FactViolationError(AppError):
    code = ErrorCode.FACT_VIOLATION
    status_code = 422
    default_message = "Generated text contained facts that are not in the verified data."
