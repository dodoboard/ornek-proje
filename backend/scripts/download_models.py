"""Download model weights listed in backend/config/models.yaml.

Hugging Face models go to the HF cache; rembg segmentation sessions (`provider: rembg_onnx`) are fetched
by rembg itself from its GitHub releases into MODELS_DIR/rembg.

Examples (from backend/, venv active):
    python scripts/download_models.py --list
    python scripts/download_models.py --defaults            # default model of every kind
    python scripts/download_models.py image:flux2_klein_4b  # one model
    python scripts/download_models.py segmentation:birefnet_general

Gated repos need `HF_TOKEN` in the environment (never commit it). Always read the model's
license before downloading — see MODEL_LICENSES.md.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.core.runtime import apply_process_env
from app.providers.catalog import is_repo_cached, load_models_config
from app.providers.segmentation.rembg_onnx import onnx_candidates


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("models", nargs="*", help="kind:key, e.g. image:flux2_klein_4b")
    parser.add_argument("--defaults", action="store_true", help="download the default model of each kind")
    parser.add_argument("--list", action="store_true", help="list configured Hugging Face models")
    args = parser.parse_args(argv)

    settings = get_settings()
    apply_process_env(settings)
    config = load_models_config(settings.models_config_path)

    all_models = {
        f"{kind.value}:{key}": spec
        for kind, section in config.kinds.items()
        for key, spec in section.models.items()
    }
    rembg = {name: spec for name, spec in all_models.items() if spec.provider == "rembg_onnx"}
    catalog = {name: spec for name, spec in all_models.items() if spec.repo_id and name not in rembg}
    if args.list:
        for name, spec in catalog.items():
            state = "cached" if is_repo_cached(spec.repo_id or "", settings) else "not downloaded"
            print(f"{name:40} {spec.repo_id:45} {state:15} license: {spec.license_claim or 'unknown'}")
        for name, spec in rembg.items():
            session = str(spec.option("session"))
            state = (
                "cached" if any(p.is_file() for p in onnx_candidates(session, settings)) else "not downloaded"
            )
            print(f"{name:40} {'rembg:' + session:45} {state:15} license: {spec.license_claim or 'unknown'}")
        return 0

    wanted = list(args.models)
    if args.defaults:
        wanted += [f"{kind.value}:{section.default}" for kind, section in config.kinds.items()]
    targets = [(name, catalog[name]) for name in dict.fromkeys(wanted) if name in catalog]
    rembg_targets = [(name, rembg[name]) for name in dict.fromkeys(wanted) if name in rembg]
    unknown = [name for name in wanted if name not in catalog and name not in rembg]
    for name in unknown:
        print(f"skip {name}: not a downloadable model in models.yaml", file=sys.stderr)
    if not targets and not rembg_targets:
        parser.print_usage()
        return 1
    if settings.offline_mode:
        print("OFFLINE_MODE is enabled; refusing to download.", file=sys.stderr)
        return 1

    for name, spec in rembg_targets:
        from rembg import new_session  # downloads <session>.onnx into REMBG_HOME if missing

        print(f"Downloading {name} (rembg session {spec.option('session')}) — license: {spec.license_claim}")
        new_session(str(spec.option("session")), providers=["CPUExecutionProvider"])

    from huggingface_hub import snapshot_download

    for name, spec in targets:
        assert spec.repo_id is not None
        print(f"Downloading {name} ({spec.repo_id}) — license claim: {spec.license_claim or 'unknown'}")
        path = snapshot_download(
            repo_id=spec.repo_id, revision=spec.revision, token=os.environ.get("HF_TOKEN")
        )
        print(f"  -> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
