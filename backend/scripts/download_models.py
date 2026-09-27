"""Download model weights listed in backend/config/models.yaml into the Hugging Face cache.

Examples (from backend/, venv active):
    python scripts/download_models.py --list
    python scripts/download_models.py --defaults            # default model of every kind
    python scripts/download_models.py image:flux2_klein_4b  # one model

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

    catalog = {
        f"{kind.value}:{key}": spec
        for kind, section in config.kinds.items()
        for key, spec in section.models.items()
        if spec.repo_id
    }
    if args.list:
        for name, spec in catalog.items():
            state = "cached" if is_repo_cached(spec.repo_id or "", settings) else "not downloaded"
            print(f"{name:40} {spec.repo_id:45} {state:15} license: {spec.license_claim or 'unknown'}")
        return 0

    wanted = list(args.models)
    if args.defaults:
        wanted += [f"{kind.value}:{section.default}" for kind, section in config.kinds.items()]
    targets = [(name, catalog[name]) for name in dict.fromkeys(wanted) if name in catalog]
    unknown = [name for name in wanted if name not in catalog]
    for name in unknown:
        print(f"skip {name}: not a Hugging Face model in models.yaml", file=sys.stderr)
    if not targets:
        parser.print_usage()
        return 1
    if settings.offline_mode:
        print("OFFLINE_MODE is enabled; refusing to download.", file=sys.stderr)
        return 1

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
