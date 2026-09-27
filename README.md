# AI Influencer Studio

Local-first AI content studio: consistent AI influencers, product ads, real-estate/land videos. FLUX.2 for images, a separate local video model for motion, FFmpeg for final composition. No paid cloud API is required at runtime.

> Status: **Phase 0 — technical validation.** The application itself is not implemented yet.
> See `docs/PHASE0_VALIDATION.md` for verified integrations and open items, and `MODEL_LICENSES.md` before downloading any model.

## Phase 0: validate your machine

Requires Python 3.12. The validator uses only the standard library; optional packages are detected if present.

### Windows (PowerShell)

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python scripts\validate_env.py
python scripts\validate_env.py --json > phase0_report.json
```

### Linux (Ubuntu)

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python scripts/validate_env.py
python scripts/validate_env.py --json > phase0_report.json
```

### Optional deeper checks

```bash
pip install huggingface_hub pyyaml
python scripts/validate_env.py --check-hf           # repo reachability + license tags from backend/config/models.yaml

# GPU smoke test: install a CUDA 12.8+ PyTorch build for Blackwell first (see pytorch.org "Get Started"),
# then diffusers/transformers/accelerate:
pip install diffusers==0.40.0 transformers accelerate pillow pyyaml
python scripts/validate_env.py --smoke              # renders data/temp/phase0_smoke.png
```

### Validator tests

```bash
pip install pytest pyyaml
python -m pytest scripts/tests -q
```

## "Free" / local-first

No paid API is needed at runtime; internet is only used to download models. Hardware, electricity, disk space and each model's license terms still apply. See `MODEL_LICENSES.md`.
