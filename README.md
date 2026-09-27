# AI Influencer Studio

Local-first AI content studio: consistent AI influencers, product ads, real-estate/land videos. FLUX.2 for images, a separate local video model for motion, FFmpeg for final composition. No paid cloud API is required at runtime.

> Status: **Phase 2 — database + API foundation.** CRUD for characters, products, properties/land, projects, consents and validated asset uploads. No generation features yet.
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

## Database

SQLite at `data/studio.db` by default (`DATABASE_URL` to override). Schema is managed by Alembic; the API applies pending migrations on startup (`AUTO_MIGRATE=true`). Manual use, from `backend/` with the venv active:

```bash
alembic upgrade head        # apply migrations
alembic check               # fail if models and migrations diverge
alembic revision --autogenerate -m "describe change"   # after changing app/models
```

## API (Phase 2)

Interactive docs: http://127.0.0.1:8000/docs. All errors use `{"error": {"code", "message"}}`.

| Resource | Endpoints |
|---|---|
| Assets | `POST /api/assets` (multipart), `GET /api/assets/{id}`, `GET /api/assets/{id}/content`, `DELETE /api/assets/{id}` |
| Characters | `GET/POST /api/characters`, `GET/PATCH/DELETE /api/characters/{id}`, `POST /api/characters/{id}/assets`, `DELETE /api/characters/{id}/assets/{asset_id}` |
| Products | same shape under `/api/products` |
| Properties / land | same shape under `/api/properties` (`?category=property|land`) |
| Projects | `GET/POST /api/projects`, `GET/PATCH/DELETE /api/projects/{id}` |
| Consents | `GET/POST /api/consents`, `GET /api/consents/{id}`, `POST /api/consents/{id}/revoke` |

Data rules enforced server-side:

- **Uploads:** JPEG/PNG/WEBP/MP4/MOV/WAV/MP3/M4A only, detected from file contents (not the name). Images are fully decoded with a pixel limit; video/audio are checked with `ffprobe`. SVG, GIF and anything else are rejected. Files are stored as `AST_<id>.<ext>`; the original name is kept only as metadata.
- **Characters:** `adult_age` must be 18–120 (API and DB constraint). Descriptions that reference minors (EN/TR keyword guard) are rejected. `is_real_person=true` requires an active **face** consent record; revoking it blocks further edits and reference uploads.
- **Products / properties:** price requires a currency; coordinates must be given as a pair; unknown facts stay `null`. `mark_facts_verified` stamps `facts_verified_at`; changing any fact later clears it.

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
