# Phase 0 — Technical Validation

Date: 2026-09-27 · Target machine: RTX 5080 (16 GB, Blackwell `sm_120`), Core Ultra 9 275HX, 32 GB RAM, Windows/Linux · Usage: personal/research · Languages: TR + EN.

## Method and limits

| Source | Reachable from build env | Used for |
|---|---|---|
| PyPI JSON API | yes | package versions, wheel tags, declared licenses |
| npm registry | yes | frontend versions / peer deps |
| GitHub raw (upstream source) | yes | class exports, `__call__` signatures, CLI args, LICENSE files |
| huggingface.co | **no (proxy 403)** | model cards, licenses, gating → **needs-user-machine** |
| download.pytorch.org | **no (proxy 403)** | CUDA wheel variants → **needs-user-machine** |
| GPU / FFmpeg | not present | runtime checks → `scripts/validate_env.py` on the target machine |

Status legend: **verified** (confirmed from upstream source) · **changed** (plan adjusted) · **needs-user-machine** · **experimental** · **not_implemented**.

Run on the target machine and keep the report:

```powershell
python scripts/validate_env.py --check-hf --json > phase0_report.json
python scripts/validate_env.py --smoke     # after the default FLUX.2 model is downloaded
```

---

## 1. FLUX.2 integration

- **Selected:** FLUX.2 [klein] via Diffusers `Flux2KleinPipeline` (default 4B distilled; 9B and base-9B optional). Inpaint/outpaint via `Flux2KleinInpaintPipeline`.
- **Why:** Only FLUX.2 family members realistic on 16 GB VRAM / 32 GB RAM. Native multi-image `image=` input supports reference-based generation.
- **Evidence (diffusers v0.40.0 source):**
  - `src/diffusers/__init__.py` exports `Flux2Pipeline`, `Flux2KleinPipeline`, `Flux2KleinInpaintPipeline`, `Flux2KleinKVPipeline` (+ modular variants).
  - `Flux2KleinPipeline.__call__(image, prompt, height, width, num_inference_steps, sigmas, guidance_scale, num_images_per_prompt, generator, latents, prompt_embeds, negative_prompt_embeds, output_type, return_dict, attention_kwargs, callback_on_step_end, callback_on_step_end_tensor_inputs, max_sequence_length, text_encoder_out_layers)`.
  - **No string `negative_prompt`**: the pipeline uses `""` as negative when CFG is active.
  - `do_classifier_free_guidance = guidance_scale > 1 and not config.is_distilled` → guidance only meaningful for **base** (non-distilled) checkpoints.
  - `model_cpu_offload_seq = "text_encoder->transformer->vae"`; `interrupt` property present.
  - `Flux2KleinInpaintPipeline.__call__` adds `image_reference`, `mask_image`, `strength`, `padding_mask_crop`.
  - Docstring model id: `black-forest-labs/FLUX.2-klein-base-9B`; `Flux2Pipeline` docstring: `black-forest-labs/FLUX.2-dev`.
- **License caveat:** klein 4B reportedly Apache-2.0; klein 9B and FLUX.2 [dev] reportedly non-commercial. **needs-user-machine** (read the model cards).
- **Integration:** `from_pretrained(<models.yaml repo_id or local_path>, torch_dtype=bf16)`; cancel via `callback_on_step_end` raising a cancellation exception; capabilities: `supports_negative_prompt=False`, `supports_guidance=not distilled`, `supports_reference_images=True`.
- **VRAM expectation:** 4B comfortable at 1024² with model offload; 9B requires `enable_model_cpu_offload`. Exact peaks measured by `--smoke` / later benchmark (not guessed).
- **Fallback:** FLUX.2 [dev] via optional ComfyUI provider (quantized) → marked experimental; `FakeImageProvider` for dev only.
- **Status:** API **verified**; distilled 4B/9B repo ids **needs-user-machine**; plan **changed** (negative prompt hidden for klein).

## 2. Video model integration

- **Selected:** Wan 2.2 TI2V-5B (`Wan-AI/Wan2.2-TI2V-5B-Diffusers`). Secondary: LTX-2 (`LTX2ImageToVideoPipeline`, experimental).
- **Why:** 5B dense model supports text+image→video; the only Wan 2.2 variant sized for 16 GB with offload.
- **Evidence:** `docs/source/en/api/pipelines/wan.md` lists `Wan-AI/Wan2.2-TI2V-5B-Diffusers`. `WanPipeline` and `WanImageToVideoPipeline` accept `expand_timesteps` in their config (commented "Wan2.2 ti2v"); `__call__` has `image` (I2V), `prompt`, `negative_prompt`, `height`, `width`, `num_frames`, `guidance_scale`, `callback_on_step_end`, `last_image`. `ltx2.md` lists `Lightricks/LTX-2`, `Lightricks/LTX-2.5-Diffusers`; `LTX2ImageToVideoPipeline` example uses `enable_model_cpu_offload()`.
- **License caveat:** Wan 2.2 reportedly Apache-2.0; LTX-2 under Lightricks' own community license (revenue terms). needs-user-machine.
- **Integration:** load with `DiffusionPipeline.from_pretrained` and assert the resolved class (the repo's `model_index.json` decides which Wan class is used for TI2V); `enable_model_cpu_offload` + `vae.enable_tiling` when present.
- **VRAM expectation:** short clips at 480p–720p with offload; duration/throughput to be benchmarked on the laptop (thermals matter). Not practical below ~12 GB.
- **Fallback:** LTX-2 (experimental) → `ffmpeg_motion` (deterministic Ken Burns/parallax, no AI) → `FakeVideoProvider` (dev only).
- **Status:** API **verified**; runtime **needs-user-machine**.

## 3. Python

- **Selected:** Python 3.12.
- **Evidence:** cp312 wheels exist on PyPI for `torch` 2.14.0 (win_amd64, manylinux x86_64) and `ctranslate2` 4.8.2 (win_amd64, manylinux). `sqlalchemy` 2.1.1 requires ≥3.11, `rembg` 2.0.85 requires 3.11–3.x.
- **Caveat:** build env has 3.11 only; the validator targets 3.12 and warns on newer.
- **Status:** **verified** (wheels); interpreter **needs-user-machine**.

## 4. PyTorch / 8. CUDA

- **Selected:** latest stable torch with a CUDA ≥ 12.8 build (Blackwell `sm_120` requires it).
- **Integration:** not pinned in requirements; installed per platform from the official PyTorch selector. The validator fails if `sm_120` is absent from `torch.cuda.get_arch_list()`.
- **Attention:** PyTorch SDPA; xformers/flash-attn not required.
- **Status:** **needs-user-machine** (wheel index unreachable from build env).

## 5. Diffusers · 6. Transformers · 7. Accelerate

| Package | Latest (PyPI) | Pin plan |
|---|---|---|
| diffusers | 0.40.0 | `==0.40.0` (first version confirmed to contain every class above) |
| transformers | 5.17.0 | pin after `--smoke` passes with FLUX.2 klein text encoder |
| accelerate | 1.15.0 | pin with transformers |

Status: versions **verified**; exact compatible set **needs-user-machine** (smoke test).

## 9. FFmpeg

- **Selected:** FFmpeg ≥ 6 with `libx264` (GPL build). Windows: gyan.dev / BtbN builds, or `winget install Gyan.FFmpeg`; Ubuntu: `sudo apt install ffmpeg`.
- **Integration:** `subprocess` with argument lists only; path from `FFMPEG_PATH`/`FFPROBE_PATH` or `PATH`.
- **Status:** **needs-user-machine** (validator checks `-version` and `-encoders` for libx264).

## 10. TTS

| Option | Evidence | License | Decision |
|---|---|---|---|
| **Chatterbox Multilingual** | `ChatterboxMultilingualTTS.from_pretrained(device, t3_model=None)`, `generate(text, language_id, audio_prompt_path=None, exaggeration=0.5, cfg_weight=0.5, temperature=0.8, repetition_penalty=1.2, …)`; `SUPPORTED_LANGUAGES` contains `"tr": "Turkish"` | MIT (repo LICENSE) | Default TR/EN. **pyproject pins `torch==2.6.0`** → incompatible with the main env and with Blackwell. Runs in an **isolated venv** via subprocess adapter with a newer torch override; compatibility **needs-user-machine**. |
| **Piper** (`piper-tts` 1.8.0) | `PiperVoice.load(...)`, `PiperVoice.synthesize_wav(...)` | GPL-3.0-or-later (code); voices per-voice | CPU fallback with Turkish voices. |
| Kokoro | not re-verified in Phase 0 | — | English-only candidate; revisit in Phase 12. |

Voice cloning (Chatterbox `audio_prompt_path`) gated behind a consent record.

## 11. Lip-sync

- **Selected:** LatentSync **1.5** (isolated venv + cloned repo, CLI subprocess).
- **Evidence:** `scripts/inference.py` args: `--unet_config_path --inference_ckpt_path --video_path --audio_path --video_out_path --inference_steps --guidance_scale --temp_dir --seed --enable_deepcache`. README: minimum inference VRAM **8 GB (1.5)**, **18 GB (1.6)** → 1.6 does not fit 16 GB. LICENSE: Apache-2.0.
- **Caveat:** `requirements.txt` pins `torch==2.5.1` (cu121), `mediapipe==0.10.11`, `diffusers==0.32.2` — the pinned torch has no Blackwell kernels. Needs an override to a CUDA 12.8+ torch inside its venv; whether its other pins accept that is **needs-user-machine**.
- **Fallback:** MuseTalk (not verified in Phase 0) → no lip-sync: voice-over over presenter I2V clip (explicitly labeled).
- **Status:** CLI/license **verified**; Blackwell runtime **needs-user-machine**; provider will ship as **experimental**.

## 12. LLM runtime

- **Selected:** Ollama over localhost HTTP.
- **Evidence:** `docs/api.md`: `format` accepts `json` or a JSON schema (structured outputs); `keep_alive` controls residency, `0` unloads the model.
- **Model:** configurable (`qwen3:8b` default tag); Turkish quality to be judged by the user.
- **Fallback:** deterministic template script (no LLM) — never crashes, never invents facts.
- **Status:** **verified** (API); model availability **needs-user-machine**.

## Supporting libraries

| Package | Version | Note |
|---|---|---|
| faster-whisper | 1.2.1 (MIT) | ASR with word timestamps; CPU int8 fallback |
| spandrel | 0.4.2 (MIT) | upscaler weight loading |
| rembg | 2.0.85 (MIT) | segmentation fallback |
| fastapi / pydantic / sqlalchemy / alembic | 0.141.1 / 2.13.5 / 2.1.1 / 1.20.0 | backend |

## Frontend

next 16.3.6 · react 19.3.0 · tailwindcss 4.3.3 · @tanstack/react-query 5.104.0 · @dnd-kit/core 6.3.1 · @dnd-kit/sortable 10.0.0 · zustand 5.0.15 · vitest 5.0.2 · openapi-typescript 7.13.0 · TypeScript **6.0.3** (7.x native port skipped until Next's type-check compatibility is confirmed). Next 16.3.6 peer deps accept React ^19.

## Plan changes from Phase 0

1. TTS (Chatterbox) and lip-sync (LatentSync) both run through an isolated-venv subprocess runner.
2. FLUX.2 klein: negative prompt not exposed; guidance only for base checkpoints.
3. Inpaint/outpaint use `Flux2KleinInpaintPipeline` (outpaint = pad + mask).
4. LatentSync 1.5 is the default (1.6 exceeds 16 GB).
5. All model repo ids live in `backend/config/models.yaml` with a `verification` field.
