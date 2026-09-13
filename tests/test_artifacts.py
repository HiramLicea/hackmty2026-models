"""Artifact path, manifest, integrity, compatibility, and cache tests."""

import hashlib
import json
from pathlib import Path

import joblib
import pytest

from app.artifacts.manifest import MODEL_NAMES
from app.artifacts.store import ArtifactStore, InvalidManifestError
from app.core.errors import ModelVersionMismatchError


def write_valid_bundle(root: Path) -> Path:
    root.mkdir()
    entries: dict[str, dict[str, str]] = {}
    for index, model_name in enumerate(MODEL_NAMES):
        filename = f"{model_name}.joblib"
        artifact_path = root / filename
        joblib.dump({"model": model_name, "index": index}, artifact_path)
        entries[model_name] = {
            "filename": filename,
            "format": "joblib",
            "model_version": "0.1.0",
            "sha256": hashlib.sha256(artifact_path.read_bytes()).hexdigest(),
        }
    manifest_path = root / "manifest.json"
    manifest_path.write_text(
        json.dumps({"schema_version": "1", "artifacts": entries}),
        encoding="utf-8",
    )
    return manifest_path


def test_artifact_is_loaded_once_per_store_instance(tmp_path: Path) -> None:
    root = tmp_path / "artifacts"
    manifest = write_valid_bundle(root)
    store = ArtifactStore(root, manifest)

    first = store.load("forecast_cash_balance")
    second = store.load("forecast_cash_balance")

    assert first is second
    assert store.inspect().ready is True


def test_artifact_path_cannot_escape_root(tmp_path: Path) -> None:
    root = tmp_path / "artifacts"
    manifest = write_valid_bundle(root)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["artifacts"]["forecast_cash_balance"]["filename"] = "../outside.joblib"
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    store = ArtifactStore(root, manifest)
    with pytest.raises(InvalidManifestError, match="escapes"):
        store.load("forecast_cash_balance")


def test_invalid_manifest_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "artifacts"
    root.mkdir()
    manifest = root / "manifest.json"
    manifest.write_text("not-json", encoding="utf-8")

    store = ArtifactStore(root, manifest)
    with pytest.raises(InvalidManifestError):
        store.load("forecast_cash_balance")
    assert store.inspect().ready is False


def test_model_version_mismatch_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "artifacts"
    manifest = write_valid_bundle(root)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["artifacts"]["forecast_cash_balance"]["model_version"] = "9.0.0"
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    store = ArtifactStore(root, manifest)
    with pytest.raises(ModelVersionMismatchError):
        store.load("forecast_cash_balance")
