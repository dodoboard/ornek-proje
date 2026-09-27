# Model Licenses

**Nothing in this file is legal advice, and nothing here is a verified license statement.** Model licenses change, and "open weights", "free to download", "open source" and "commercial use allowed" are four different things. Before using any model, read its model card and license file yourself.

This project is configured for **personal / research use**. Several default models are reportedly **non-commercial**. If you use outputs commercially, re-check every model in the chain (image, video, TTS, lip-sync, LLM, upscaler, segmentation, face scoring).

| Component | Model / package | Reported license (unverified unless marked) | Commercial use | Verify at |
|---|---|---|---|---|
| Image | FLUX.2 [klein] 4B | Apache-2.0 | check | huggingface.co/black-forest-labs |
| Image | FLUX.2 [klein] 9B / base-9B | non-commercial | likely no | huggingface.co/black-forest-labs |
| Image | FLUX.2 [dev] | FLUX.2 [dev] Non-Commercial License | no (outputs: read terms) | huggingface.co/black-forest-labs/FLUX.2-dev |
| Video | Wan 2.2 TI2V-5B | Apache-2.0 | check | huggingface.co/Wan-AI |
| Video | LTX-2 | Lightricks LTX-2 community license | revenue-dependent | huggingface.co/Lightricks |
| LLM | Qwen3 (via Ollama) | Apache-2.0 | check | model card of the pulled tag |
| LLM | Gemma 3 (via Ollama) | Gemma Terms of Use | conditional | ai.google.dev/gemma/terms |
| TTS | Chatterbox (code) | MIT — **verified** from repo LICENSE | check weights | github.com/resemble-ai/chatterbox |
| TTS | Piper (`piper-tts`) | GPL-3.0-or-later — **verified** from PyPI | copyleft obligations | github.com/OHF-Voice/piper1-gpl |
| TTS | Piper voices | per voice | per voice | voice MODEL_CARD |
| Lip-sync | LatentSync (code) | Apache-2.0 — **verified** from repo LICENSE | check weights | github.com/bytedance/LatentSync |
| Lip-sync | MuseTalk | code MIT; weights separate | check | github.com/TMElyralab/MuseTalk |
| Lip-sync | Wav2Lip | non-commercial research | no | github.com/Rudrabha/Wav2Lip |
| ASR | faster-whisper | MIT — **verified** from PyPI | yes (code) | github.com/SYSTRAN/faster-whisper |
| ASR | Whisper weights | MIT | check | github.com/openai/whisper |
| Segmentation | BiRefNet | MIT | check | huggingface.co/ZhengPeng7/BiRefNet |
| Segmentation | rembg 2.0.85 (code) | MIT — **verified** from PyPI metadata | model-dependent | github.com/danielgatis/rembg |
| Segmentation | BiRefNet ONNX exports used via rembg (`birefnet-general`, `birefnet-general-lite`) | MIT (upstream BiRefNet) — unverified for the ONNX re-export | check | github.com/danielgatis/rembg/releases |
| Segmentation | ISNet `isnet-general-use` via rembg | Apache-2.0 (DIS) — unverified | check | github.com/xuebinqin/DIS |
| Segmentation | `bria-rmbg` (rembg's own default; **not used** by this project) | BRIA RMBG-2.0: non-commercial (CC BY-NC 4.0) — unverified | no | huggingface.co/briaai/RMBG-2.0 |
| Upscale | Real-ESRGAN weights | BSD-3-Clause | check | github.com/xinntao/Real-ESRGAN |
| Upscale | spandrel | MIT — **verified** from PyPI | yes (code) | github.com/chaiNNer-org/spandrel |
| Face score (optional) | InsightFace models | non-commercial | no | github.com/deepinsight/insightface |
| Video encode | FFmpeg + libx264 | GPL (with libx264) | distribution obligations | ffmpeg.org/legal.html |

`python scripts/validate_env.py --check-hf` prints the `license:` tag of every repo configured in `backend/config/models.yaml`. Treat that tag as a pointer, not as proof.

## "Free" does not mean zero cost

No paid API is required at runtime, but you still pay for the GPU, electricity, disk space (hundreds of GB for models and video), and you remain bound by each model's license.
