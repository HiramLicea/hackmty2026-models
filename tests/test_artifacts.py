"""Artifact path, rich manifest, integrity, compatibility, and cache tests."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import joblib
import pytest

from app.artifacts.manifest import MODEL_NAMES
from app.artifacts.store import ArtifactStore, InvalidManifestError
from app.core.errors import ModelVersionMismatchError


def write_valid_bundle(root: Path) -> Path:
    root.mkdir()
    artifacts: dict[str, object] = {}
    for index, model_name in enumerate(MODEL_NAMES):
        filename = f"{model_name}.joblib"
        artifact_path = root / filename
        joblib.dump({"model": model_name, "index": index}, artifact_path)
        content = artifact_path.read_bytes()
        artifacts[model_name] = {
            "model_version": "0.1.0",
            "trained_until": datetime(2026, 8, 31, tzinfo=UTC).isoformat(),
            "features": ["example_feature"],
            "metrics": {"test": 0.5},
            "files": {
                "model": {
                    "path": filename,
                    "format": "joblib",
                    "size_bytes": len(content),
                    "sha256": hashlib.sha256(content).hexdigest(),
                }
            },
            "limitations": ["test fixture"],
        }
    manifest_path = root / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_version": "1",
                "input_contract_version": "1",
                "python_version": "3.12",
                "libraries": {
                    "scikit-learn": "1.7.2",
                    "numpy": "2.3.3",
                    "joblib": "1.5.2",
                },
                "trained_at": datetime(2026, 9, 1, tzinfo=UTC).isoformat(),
                "seed": 2026,
                "dataset_fingerprint": "a" * 64,
                "artifacts": artifacts,
            }
        ),
        encoding="utf-8",
    )
    return manifest_path


def test_artifact_is_loaded_once_per_store_instance(tmp_path: Path) -> None:
    root = tmp_path / "artifacts"
    manifest = write_valid_bundle(root)
    store = ArtifactStore(root, manifest)
    first = store.load("forecast_cash_balance", "model")
    second = store.load("forecast_cash_balance", "model")
    assert first is second
    assert store.inspect().ready is True
    assert all(store.check_loadable().values())


def test_artifact_path_cannot_escape_root(tmp_path: Path) -> None:
    root = tmp_path / "artifacts"
    manifest = write_valid_bundle(root)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["artifacts"]["forecast_cash_balance"]["files"]["model"]["path"] = "../outside.joblib"
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    store = ArtifactStore(root, manifest)
    with pytest.raises(InvalidManifestError, match="escapes"):
        store.load("forecast_cash_balance", "model")


def test_invalid_manifest_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "artifacts"
    root.mkdir()
    manifest = root / "manifest.json"
    manifest.write_text("not-json", encoding="utf-8")
    store = ArtifactStore(root, manifest)
    with pytest.raises(InvalidManifestError):
        store.load("forecast_cash_balance", "model")
    assert store.inspect().ready is False


def test_hash_mismatch_marks_model_unavailable(tmp_path: Path) -> None:
    root = tmp_path / "artifacts"
    manifest = write_valid_bundle(root)
    (root / "forecast_cash_balance.joblib").write_bytes(b"tampered")
    store = ArtifactStore(root, manifest)
    assert store.inspect().models["forecast_cash_balance"] is False


def test_model_version_mismatch_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "artifacts"
    manifest = write_valid_bundle(root)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["artifacts"]["forecast_cash_balance"]["model_version"] = "9.0.0"
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    store = ArtifactStore(root, manifest)
    with pytest.raises(ModelVersionMismatchError):
        store.load("forecast_cash_balance", "model")
