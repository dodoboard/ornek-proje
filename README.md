# AI Influencer Studio

Local-first AI content studio: consistent AI influencers, product ads, real-estate/land videos. FLUX.2 for images, a separate local video model for motion, FFmpeg for final composition. No paid cloud API is required at runtime.

> Status: **Phase 6 — Character Studio (Demo A).** Create an AI influencer, generate portrait candidates, pick a canonical portrait, derive front / 3/4 / full-body views and generate the same influencer in new scenes — all conditioned on the character's reference images. FLUX.2 is verified against the diffusers v0.40.0 API with contract tests; **it has not yet been run on a GPU** (see "Image generation" for the GPU check).
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
| Generation | `POST /api/generate/image`, `POST /api/generate/image-edit` (→ job), `GET /api/generations` (`?kind=image,image_edit`), `GET /api/generations/{id}`, `GET /api/assets/{id}/thumbnail` |

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

## Image generation (Phase 5)

### Install the AI stack (worker machine)

1. **PyTorch with CUDA** — pick the command for your OS/CUDA on the official PyTorch "Get Started" selector. RTX 50-series (Blackwell, `sm_120`) needs a **CUDA 12.8 or newer** build; older builds install fine but cannot run on the GPU. Example (check the selector for the current index URL):
   ```powershell
   backend\.venv\Scripts\python -m pip install torch --index-url https://download.pytorch.org/whl/cu128
   ```
2. **Diffusers & co:** `backend\.venv\Scripts\python -m pip install -r backend\requirements\ai.txt`
3. **Check:** `python scripts\validate_env.py` — `cuda_arch` must be `ok`, and `diffusers.Flux2KleinPipeline` must pass.
4. **Download FLUX.2 [klein] 4B** (read its license first): `cd backend; python scripts\download_models.py image:flux2_klein_4b`
5. Restart the worker; the Models page should show the model as **Ready**.

### Use

Image Studio → prompt, format (1:1 / 4:5 / 9:16 / 16:9, all multiples of 16), steps (empty = model default), seed (empty = random), 1–4 images, optional reference images (FLUX.2 multi-reference; limit from the model's capabilities). Progress streams live; Cancel stops at the next diffusion step.

- The API rejects a request **before queueing** if the model is not ready or the request does not fit the model's capabilities (size multiple, max references, guidance on a distilled checkpoint).
- FLUX.2 has **no negative-prompt parameter** (the pipeline fixes it to empty), and **distilled** checkpoints ignore guidance — the UI hides both instead of pretending they work.
- Prompts and character descriptions referencing minors are rejected; characters marked as real people need an active face-consent record.
- Every output is a PNG with an `ai_disclosure` text chunk (model, seed, generation id, source assets, timestamp) plus a DB `generations` record. The visible "AI generated" label is optional (Settings). Dev placeholders are marked `dev_placeholder: true` and `generated_with_ai: false`.
- Seeds are reproducible for the same model, settings and hardware; they are **not** a character-consistency mechanism — use reference images (Phase 6 builds the Character Bible on top of this).

Unverified until run on your GPU: default step counts and reference limits in `models.yaml` (check the model card), VRAM use and speed per profile.

## Character Studio (Phase 6)

Influencers → create a character (adult age 18–120 is enforced; a real person's likeness requires ticking "I have permission to use this person's likeness", which stores a consent record). On the character page:

1. **Canonical portrait** — optionally add reference photos, generate 1–4 candidates, pick one as canonical.
2. **Views** — front, 3/4 and full body are generated with the canonical portrait as FLUX.2 reference image; pick one per slot.
3. **New scene** — describe a scene; the canonical portrait plus the chosen views (up to the model's reference limit) are sent as references.

**How consistency works (and its limits):** the model receives the character's own images as multi-reference input plus the same identity text (`Character Bible → identity`, built from the profile and immutable traits by `CharacterPromptBuilder`, templates in `backend/config/prompts/character.yaml`). Seeds are stored in the bible's seed history for reproducibility only — they do **not** keep a face consistent. Results still vary; regenerate and pick. LoRA training is not implemented (the bible has a `lora` field reserved for it).

API: `GET/PATCH /api/characters/{id}/bible`, `POST /api/characters/{id}/prompt-preview`, `POST /api/characters/{id}/generate` (`purpose`: candidates | front | three_quarter | full_body | scene), `PUT /api/characters/{id}/views/{canonical|front|three_quarter|full_body}`.

Rules: views and scenes need a canonical portrait first; an image generated for one character cannot become another character's view; scene text and prompts referencing minors are rejected; revoking a real person's consent blocks further generation.

## Image editing (Phase 7)

Image Studio tabs: **Generate | Edit | Inpaint | Outpaint**. A tab appears only if a ready model supports it (FLUX.2 [klein] via `Flux2KleinInpaintPipeline`; FLUX.2 [dev] has no inpaint pipeline in diffusers, so it only offers Generate/Edit).

| Mode | What happens |
|---|---|
| Edit | Instruction edit: the source is sent as the first FLUX.2 reference image (it takes one reference slot) and the result has the source's size. The whole image may change. |
| Inpaint | Paint the area to change on the source (brush / erase / clear). The mask is exported as a white-on-black PNG at source resolution. |
| Outpaint | Extend any side by 0–1024 px (UI step 64). The new area plus a 16 px overlap band is generated; the preview shows the final size. |

- **Pixel preservation:** for inpaint/outpaint the result is composited back onto the original with the (feathered) mask, so pixels outside the mask/overlap are **byte-identical** to the source (tested). `feather` (0–64 px) only softens the inside edge of the mask.
- `strength` (0.05–1; default inpaint 0.9, outpaint 1.0) controls how much of the masked area is re-noised; fewer denoising steps run below 1.
- Sources are cropped down to a multiple of 16 (FLUX.2 requirement). Result size must stay within the model's `min_size`/`max_size`; the API rejects violations before queueing.
- Outputs are `image_edit` generations with disclosure fields `ai_edited`, `edit_mode`, `edited_asset_id`; the gallery labels them "AI edited".

Unverified until run on your GPU: inpaint quality/speed with klein 4B, the best `strength` per use.

## Product Studio (Phase 8)

Product Ads → create a product (name/brand/description are your verified facts) → upload a photo → **Cut out product** → **Scene**.

**How product fidelity is guaranteed:** the product is never generated. Its cutout keeps the photo's exact RGB pixels (only the alpha channel comes from segmentation); the scene is a background plus that cutout composited on top. After rendering, every protected product pixel is compared with the cutout — if a single one differs, the job **fails** instead of saving. Each output stores this report (`params.preservation`) and the disclosure `product_pixels: original_photo`.

| Step | Details |
|---|---|
| Cutout | `rembg` ONNX sessions: `birefnet_general` (default), `birefnet_general_lite`, `isnet_general_use` — or `color_key` (classical, no AI, plain backgrounds only; keeps white labels inside the product), or your own mask. Near-opaque alpha (≥240) is snapped to 255 so the interior is exact. |
| Placement | Horizontal centre, standing line (bottom edge) and height as a fraction of the image; the product is clamped into the frame. **Original size** = no resampling (pixel-identical to the photo). Otherwise it is scaled with Lanczos and the report says `scaled`/`upscaled` — upscaling makes small text soft. |
| Background | FLUX.2 text-to-image ("empty surface … where a product will be placed", brand names are never put into the prompt) or your own photo (no AI involved → the output is marked `generated_with_ai: false`). |
| Contact shadow | Blurred ellipse under the product; changes background pixels only. |
| Blend edges with AI (optional) | FLUX.2 inpaint on a 2–16 px ring around the silhouette only; the product interior inside the ring is copied back and verified. |
| Watermark | If enabled, the "AI generated" label is placed in a corner that does not cover the product, then verified. |

Install segmentation (worker machine): `pip install -r backend/requirements/segmentation.txt` (CPU `onnxruntime`; for CUDA use `onnxruntime-gpu==1.30.0` with matching CUDA/cuDNN libraries), then `cd backend && python scripts/download_models.py segmentation:birefnet_general`. Weights come from the rembg GitHub releases and are stored in `MODELS_DIR/rembg` (`U2NET_HOME` overrides).

API: `POST /api/products/{id}/cutout`, `POST /api/products/{id}/scene`, `GET /api/generations?product_id=…&kind=product_scene`.

Limits: an influencer *holding* the product is not composited in this phase (the product would have to be AI-rendered — see H2 in the plan); relighting of the product itself is intentionally not done because it would change its pixels. Verified here: rembg 2.0.85 API, BiRefNet-lite end-to-end on CPU (~40 s per 1024² image in this container). Unverified until your machine: CUDA speed of onnxruntime-gpu on RTX 50-series.

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
