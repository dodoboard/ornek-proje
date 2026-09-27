from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import AppEnv, Settings
from app.core.errors import ModelMissingError, ProviderUnavailableError
from app.providers.base import Maturity, ProviderKind, ProviderStatus
from app.providers.catalog import (
    ModelSpec,
    is_repo_cached,
    load_models_config,
    parse_models_config,
    weights_status,
)
from app.providers.registry import ProviderRegistry


def test_repo_catalog_parses_every_kind(settings: Settings) -> None:
    config = load_models_config(settings.models_config_path)
    assert set(config.kinds) == set(ProviderKind)
    for catalog in config.kinds.values():
        assert catalog.default in catalog.models
    klein = config.kinds[ProviderKind.IMAGE].models["flux2_klein_4b"]
    assert klein.pipeline_class == "Flux2KleinPipeline"
    assert klein.option("distilled") is True


def test_unimplemented_providers_are_reported_honestly(settings: Settings) -> None:
    infos = {i.key: i for i in ProviderRegistry(settings).describe_all()}
    assert infos["wan22_ti2v_5b"].status is ProviderStatus.NOT_IMPLEMENTED
    assert infos["wan22_ti2v_5b"].capabilities is None
    assert infos["ltx2"].maturity is Maturity.EXPERIMENTAL
    assert "dev_fake_image" not in infos
    with pytest.raises(ProviderUnavailableError):
        ProviderRegistry(settings).get(ProviderKind.VIDEO)


def test_fake_providers_only_when_enabled(settings: Settings) -> None:
    dev = settings.model_copy(update={"enable_fake_providers": True})
    infos = {i.key: i for i in ProviderRegistry(dev).describe_all()}
    assert infos["dev_fake_image"].status is ProviderStatus.AVAILABLE
    assert infos["dev_fake_image"].maturity is Maturity.DEV_ONLY
    # Even if the flag leaks into production, fakes stay hidden.
    prod = settings.model_copy(update={"enable_fake_providers": True, "app_env": AppEnv.PRODUCTION})
    assert "dev_fake_image" not in {e.key for e in ProviderRegistry(prod).entries()}


def test_default_override_and_env_path(settings: Settings, tmp_path: Path) -> None:
    weights = tmp_path / "klein"
    weights.mkdir()
    env = settings.model_copy(update={"flux_model_path": weights})
    registry = ProviderRegistry(env, default_overrides={"image": "flux2_klein_9b"})
    assert registry.default_key(ProviderKind.IMAGE) == "flux2_klein_9b"
    # FLUX_MODEL_PATH applies to the catalog default (klein 4B), not the UI-selected one.
    assert registry.entry(ProviderKind.IMAGE, "flux2_klein_4b").spec.local_path == str(weights)
    assert registry.entry(ProviderKind.IMAGE, "flux2_klein_9b").spec.local_path is None

    bogus = ProviderRegistry(settings, default_overrides={"image": "nope"})
    assert bogus.default_key(ProviderKind.IMAGE) == "flux2_klein_4b"


def test_weights_status(settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path / "hub"))
    spec = ModelSpec(provider="x", repo_id="org/model")
    assert weights_status(spec, settings).status is ProviderStatus.MODEL_MISSING
    offline = settings.model_copy(update={"offline_mode": True})
    assert "offline" in (weights_status(spec, offline).detail or "")

    snapshot = tmp_path / "hub" / "models--org--model" / "snapshots" / "abc123"
    snapshot.mkdir(parents=True)
    assert not is_repo_cached("org/model", settings)  # empty snapshot is not a download
    (snapshot / "model_index.json").write_text("{}")
    assert weights_status(spec, settings).status is ProviderStatus.AVAILABLE

    local = ModelSpec(provider="x", local_path=str(tmp_path / "missing"))
    assert weights_status(local, settings).status is ProviderStatus.MODEL_MISSING
    relative = ModelSpec(provider="x", local_path="sub")
    (settings.models_dir / "sub").mkdir(parents=True)
    assert weights_status(relative, settings).status is ProviderStatus.AVAILABLE


def test_get_raises_model_missing_for_implemented_provider(settings: Settings, tmp_path: Path) -> None:
    from app.providers.image.fake import FakeImageProvider
    from app.providers.registry import IMPLEMENTED

    config = parse_models_config(
        {
            "image": {
                "default": "m",
                "models": {"m": {"provider": "test_needs_weights", "local_path": "/nope"}},
            }
        }
    )

    class NeedsWeights(FakeImageProvider):
        def availability(self):  # type: ignore[no-untyped-def]
            from app.providers.base import Provider

            return Provider.availability(self)

    IMPLEMENTED["test_needs_weights"] = NeedsWeights
    try:
        with pytest.raises(ModelMissingError):
            ProviderRegistry(settings, config=config).get(ProviderKind.IMAGE)
    finally:
        IMPLEMENTED.pop("test_needs_weights")
