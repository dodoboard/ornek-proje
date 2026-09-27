# AI Influencer Studio

Local-first AI content studio: consistent AI influencers, product ads, real-estate/land videos. FLUX.2 for images, a separate local video model for motion, FFmpeg for final composition. No paid cloud API is required at runtime.

> Status: **Phase 4 — model/provider architecture.** Provider interfaces, model registry with live status, central ModelManager (VRAM/precision/offload), Models and Settings pages. **No real AI model is integrated yet** — FLUX.2 arrives in Phase 5. Only clearly labelled dev placeholders can run.
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

The dev script starts three processes: API (`uvicorn`), job worker (`python -m app.workers.supervisor`) and the Next.js dev server. Open http://127.0.0.1:3000 (API: http://127.0.0.1:8000/docs). Everything binds to localhost only.

To run the worker on its own (from `backend/`, venv active): `python -m app.workers` (add `--once` to process a single job).

## Database

SQLite at `data/studio.db` by default (`DATABASE_URL` to override). Schema is managed by Alembic; the API applies pending migrations on startup (`AUTO_MIGRATE=true`). Manual use, from `backend/` with the venv active:

```bash
alembic upgrade head        # apply migrations
alembic check               # fail if models and migrations diverge
alembic revision --autogenerate -m "describe change"   # after changing app/models
```

## API

Interactive docs: http://127.0.0.1:8000/docs. All errors use `{"error": {"code", "message"}}`.

| Resource | Endpoints |
|---|---|
| Assets | `POST /api/assets` (multipart), `GET /api/assets/{id}`, `GET /api/assets/{id}/content`, `DELETE /api/assets/{id}` |
| Characters | `GET/POST /api/characters`, `GET/PATCH/DELETE /api/characters/{id}`, `POST /api/characters/{id}/assets`, `DELETE /api/characters/{id}/assets/{asset_id}` |
| Products | same shape under `/api/products` |
| Properties / land | same shape under `/api/properties` (`?category=property|land`) |
| Projects | `GET/POST /api/projects`, `GET/PATCH/DELETE /api/projects/{id}` |
| Consents | `GET/POST /api/consents`, `GET /api/consents/{id}`, `POST /api/consents/{id}/revoke` |
| Jobs | `GET /api/jobs` (`?active=`, `?status=`, `?type=`, `?project_id=`), `GET /api/jobs/{id}`, `DELETE /api/jobs/{id}` (cancel), `GET /api/jobs/{id}/events` (SSE) |
| System | `GET /api/health`, `GET /api/system` (incl. worker status and runtime), `POST /api/system/diagnostics` |
| Models | `GET /api/models` |
| Settings | `GET /api/settings`, `PATCH /api/settings` (performance profile, default models, model paths, FFmpeg paths, offline mode, watermark, defaults) |

Data rules enforced server-side:

- **Uploads:** JPEG/PNG/WEBP/MP4/MOV/WAV/MP3/M4A only, detected from file contents (not the name). Images are fully decoded with a pixel limit; video/audio are checked with `ffprobe`. SVG, GIF and anything else are rejected. Files are stored as `AST_<id>.<ext>`; the original name is kept only as metadata.
- **Characters:** `adult_age` must be 18–120 (API and DB constraint). Descriptions that reference minors (EN/TR keyword guard) are rejected. `is_real_person=true` requires an active **face** consent record; revoking it blocks further edits and reference uploads.
- **Products / properties:** price requires a currency; coordinates must be given as a pair; unknown facts stay `null`. `mark_facts_verified` stamps `facts_verified_at`; changing any fact later clears it.

## Job system (Phase 3)

Generation work never runs inside an HTTP request. The API writes a row to the `jobs` table; a separate worker process claims it and runs it.

- **Queue:** the `jobs` table itself. Claiming is one atomic `UPDATE … WHERE status='queued' … RETURNING`, so two workers can never take the same job (tested with 3 concurrent processes). Order: priority, then FIFO. One job at a time per worker (single GPU).
- **Status:** `queued → running / loading_model / generating_* / processing_product / lip_sync / creating_captions / encoding → completed | failed | cancelled`, with `progress` 0–100, `stage` text and elapsed time.
- **Progress:** `GET /api/jobs/{id}/events` streams Server-Sent Events (`event: job`) until the job ends; the UI falls back to polling if the stream is unavailable.
- **Cancel:** `DELETE /api/jobs/{id}`. Queued jobs are cancelled immediately. Running jobs stop at the next checkpoint (progress report or model step callback); child processes (FFmpeg, lip-sync) are terminated, then killed after 5 s. The job's temp directory is always removed.
- **Crashes:** the worker heart-beats every 5 s. If it dies, jobs it was running are marked `WORKER_LOST` after 60 s; the supervisor restarts the worker with exponential backoff. Errors shown to users are codes and short messages; tracebacks stay in the worker log.
- **Self-test:** "Run diagnostics" on the dashboard (or `POST /api/system/diagnostics`) runs a real job: storage write, disk space, an FFmpeg H.264 test encode with live progress, GPU driver query and ML package check.

Relevant settings (`.env`): `WORKER_POLL_INTERVAL_S`, `WORKER_HEARTBEAT_INTERVAL_S`, `WORKER_STALE_AFTER_S`, `JOB_PROGRESS_MIN_INTERVAL_S`, `SSE_POLL_INTERVAL_S`.

## Models & providers (Phase 4)

- **Catalog:** `backend/config/models.yaml` is the only place model repo IDs live. Each entry names a provider implementation, a repo ID and/or local path, a `verification` state and an unverified `license_claim`.
- **Status** (Models page / `GET /api/models`), computed without importing torch:
  | Status | Meaning |
  |---|---|
  | Ready | integration exists, packages installed, weights found |
  | Not downloaded | weights not in the Hugging Face cache or the local path does not exist |
  | Packages missing | a required Python package is not installed |
  | Not implemented | the integration has not been written yet — it cannot be selected |
- **Downloading:** `cd backend && python scripts/download_models.py --list`, then e.g. `python scripts/download_models.py image:flux2_klein_4b`. Gated repos need `HF_TOKEN` in your environment. Read each license first (`MODEL_LICENSES.md`).
- **Local paths:** set per model on the Models page (or `FLUX_MODEL_PATH`, `VIDEO_MODEL_PATH`, … in `.env` for the catalog default). Relative paths resolve under `MODELS_DIR`.
- **ModelManager** (worker only): one heavy model on the GPU at a time; switching models unloads the previous one and runs `gc.collect()` + `torch.cuda.empty_cache()`. CUDA out-of-memory is reported as `VRAM_OOM` instead of crashing; load failures as `MODEL_LOAD_FAILED`.
- **Performance profiles** (Settings page): *Performance* keeps the pipeline on the GPU; *Balanced* uses model CPU offload; *Low VRAM* uses sequential offload, VAE tiling, attention slicing and unloads after every job. Only optimisations the pipeline object actually provides are called.
- **Device detection** runs inside the worker and is shown on the Settings page (PyTorch/CUDA version, compute capability, whether the installed build has kernels for your GPU — e.g. `sm_120` for RTX 50-series).
- **Dev placeholders:** `ENABLE_FAKE_PROVIDERS=true` adds `dev_fake_image` / `dev_fake_video`. They draw labelled gradients ("DEV PLACEHOLDER - NOT AI OUTPUT") and are refused in `APP_ENV=production`. Never mistake them for model output.

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
