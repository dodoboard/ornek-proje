# AI Influencer Studio

Local-first AI content studio: consistent AI influencers, product ads, real-estate/land videos. FLUX.2 for images, a separate local video model for motion, FFmpeg for final composition. No paid cloud API is required at runtime.

> Status: **Phase 1 — project skeleton.** Backend API foundation and the studio UI shell run; no generation features yet.
> See `docs/PHASE0_VALIDATION.md` for verified integrations and open items, and `MODEL_LICENSES.md` before downloading any model.

## Layout

```
backend/    FastAPI app (Python 3.12) — app/{api,core,schemas,services}, tests/, config/models.yaml
frontend/   Next.js 16 + TypeScript + Tailwind 4 studio UI
scripts/    validate_env.py (Phase 0), dev.sh / dev.ps1
data/       runtime files (git-ignored)
models/     optional local model weights (git-ignored)
docs/       design and validation docs
```

## Requirements

- Python **3.12**
- Node.js **22.12+** (npm)
- FFmpeg + FFprobe (needed from Phase 15; reported on the dashboard now)
- NVIDIA driver (GPU status on the dashboard uses `nvidia-smi`; PyTorch is installed in a later phase)

## Setup

### Windows (PowerShell)

```powershell
Copy-Item .env.example .env

py -3.12 -m venv backend\.venv
backend\.venv\Scripts\python -m pip install -r backend\requirements\dev.txt

cd frontend; npm ci; cd ..

.\scripts\dev.ps1
```

If script execution is blocked: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.
FFmpeg: `winget install Gyan.FFmpeg` (or set `FFMPEG_PATH`/`FFPROBE_PATH` in `.env` using forward slashes, e.g. `C:/ffmpeg/bin/ffmpeg.exe`).

### Linux (Ubuntu)

```bash
cp .env.example .env
sudo apt install -y python3.12 python3.12-venv ffmpeg

python3.12 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements/dev.txt

(cd frontend && npm ci)

./scripts/dev.sh
```

Open http://127.0.0.1:3000 (API: http://127.0.0.1:8000/docs). Both servers bind to localhost only.

## Checks

```bash
# backend (from backend/)
ruff check . && ruff format --check . && mypy && python -m pytest

# frontend (from frontend/)
npm run lint && npm run typecheck && npm test && npm run build

# Phase 0 validator tests (from repo root)
python -m pytest scripts/tests
```

Regenerate frontend API types after changing backend schemas (backend venv active, from `frontend/`): `npm run gen:api`.

## Phase 0: validate your machine

```bash
python scripts/validate_env.py
pip install huggingface_hub
python scripts/validate_env.py --check-hf --json > phase0_report.json
# after installing a CUDA 12.8+ PyTorch build and diffusers==0.40.0 transformers accelerate pillow:
python scripts/validate_env.py --smoke
```

## Privacy

- Telemetry and analytics: off. The backend has no telemetry code; `HF_HUB_DISABLE_TELEMETRY=1` and `NEXT_TELEMETRY_DISABLED=1` are set by the dev scripts/app.
- `OFFLINE_MODE=true` sets `HF_HUB_OFFLINE=1` / `TRANSFORMERS_OFFLINE=1`; models must already be downloaded.
- Files are stored under `data/` and never uploaded anywhere.

## "Free" / local-first

No paid API is needed at runtime; internet is only used to download models. Hardware, electricity, disk space and each model's license terms still apply. See `MODEL_LICENSES.md`.
