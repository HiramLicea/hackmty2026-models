"""Integrity-checked, read-only loading for trusted inference artifacts."""

import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import cast

import joblib
from pydantic import JsonValue, ValidationError

from app.artifacts.manifest import (
    INPUT_CONTRACT_VERSION,
    MODEL_NAMES,
    SUPPORTED_MODEL_VERSIONS,
    ArtifactFile,
    ModelArtifactDescriptor,
    ModelManifest,
)
from app.core.errors import ModelVersionMismatchError
from app.models.common import ModelName


class InvalidManifestError(RuntimeError):
    """The artifact manifest is missing, malformed, incompatible, or unsafe."""


class ArtifactNotReadyError(RuntimeError):
    """A required model artifact cannot be loaded safely."""

    def __init__(self, model_name: ModelName) -> None:
        super().__init__("required model artifact is not ready")
        self.model_name = model_name


@dataclass(frozen=True)
class ArtifactStatus:
    """Sanitized readiness state; paths and hashes are deliberately excluded."""

    manifest_valid: bool
    models: dict[ModelName, bool]

    @property
    def ready(self) -> bool:
        return self.manifest_valid and all(self.models.values())


class ArtifactStore:
    """Validate and cache immutable artifacts once per warm service instance."""

    def __init__(self, root: Path, manifest_path: Path) -> None:
        self._root = root.resolve()
        candidate = manifest_path if manifest_path.is_absolute() else Path.cwd() / manifest_path
        self._manifest_path = self._resolve_under_root(candidate)
        self._object_cache: dict[tuple[ModelName, str], object] = {}
        self._json_cache: dict[tuple[ModelName, str], dict[str, JsonValue]] = {}
        self._manifest_cache: ModelManifest | None = None
        self._status: ArtifactStatus | None = None
        self._lock = Lock()

    def inspect(self) -> ArtifactStatus:
        """Validate metadata, compatibility, paths, sizes, files, and hashes."""
        with self._lock:
            if self._status is None:
                self._status = self._inspect_uncached()
            return self._status

    def descriptor(self, model_name: ModelName) -> ModelArtifactDescriptor:
        """Return validated, non-secret provenance for a model."""
        return self._manifest().artifacts[model_name]

    def load(self, model_name: ModelName, artifact_key: str) -> object:
        """Load one verified joblib file and cache it by model and logical key."""
        cache_key = (model_name, artifact_key)
        with self._lock:
            if cache_key in self._object_cache:
                return self._object_cache[cache_key]
            file = self._file(model_name, artifact_key, expected_format="joblib")
            path = self._resolve_artifact(file.path)
            self._verify_file(model_name, file, path)
            try:
                loaded: object = joblib.load(path)
            except Exception as error:
                raise ArtifactNotReadyError(model_name) from error
            self._object_cache[cache_key] = loaded
            return loaded

    def load_json(self, model_name: ModelName, artifact_key: str) -> dict[str, JsonValue]:
        """Parse one verified JSON artifact and cache its object representation."""
        cache_key = (model_name, artifact_key)
        with self._lock:
            if cache_key in self._json_cache:
                return self._json_cache[cache_key]
            file = self._file(model_name, artifact_key, expected_format="json")
            path = self._resolve_artifact(file.path)
            self._verify_file(model_name, file, path)
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as error:
                raise ArtifactNotReadyError(model_name) from error
            if not isinstance(payload, dict):
                raise ArtifactNotReadyError(model_name)
            typed_payload = cast(dict[str, JsonValue], payload)
            self._json_cache[cache_key] = typed_payload
            return typed_payload

    def check_loadable(self) -> dict[ModelName, bool]:
        """Load every declared joblib and parse every JSON file."""
        results = dict.fromkeys(MODEL_NAMES, False)
        try:
            manifest = self._manifest()
        except (InvalidManifestError, ModelVersionMismatchError):
            return results
        for model_name, descriptor in manifest.artifacts.items():
            try:
                for key, file in descriptor.files.items():
                    if file.format == "joblib":
                        self.load(model_name, key)
                    else:
                        self.load_json(model_name, key)
            except (ArtifactNotReadyError, InvalidManifestError, ModelVersionMismatchError):
                continue
            results[model_name] = True
        return results

    def _inspect_uncached(self) -> ArtifactStatus:
        unavailable = dict.fromkeys(MODEL_NAMES, False)
        try:
            manifest = self._manifest()
            states = {
                model_name: all(
                    self._file_is_ready(model_name, file) for file in descriptor.files.values()
                )
                for model_name, descriptor in manifest.artifacts.items()
            }
        except (InvalidManifestError, ModelVersionMismatchError):
            return ArtifactStatus(manifest_valid=False, models=unavailable)
        return ArtifactStatus(manifest_valid=True, models=states)

    def _manifest(self) -> ModelManifest:
        if self._manifest_cache is not None:
            return self._manifest_cache
        try:
            payload = json.loads(self._manifest_path.read_text(encoding="utf-8"))
            manifest = ModelManifest.model_validate(payload)
        except (OSError, json.JSONDecodeError, ValidationError) as error:
            raise InvalidManifestError("artifact manifest is invalid") from error
        if manifest.python_version != f"{sys.version_info.major}.{sys.version_info.minor}":
            raise InvalidManifestError("artifact Python version is incompatible")
        if manifest.input_contract_version != INPUT_CONTRACT_VERSION:
            raise InvalidManifestError("artifact input contract is incompatible")
        for model_name, descriptor in manifest.artifacts.items():
            if descriptor.model_version != SUPPORTED_MODEL_VERSIONS[model_name]:
                raise ModelVersionMismatchError(model_name)
            for file in descriptor.files.values():
                self._resolve_artifact(file.path)
        self._manifest_cache = manifest
        return manifest

    def _file(
        self,
        model_name: ModelName,
        artifact_key: str,
        *,
        expected_format: str,
    ) -> ArtifactFile:
        descriptor = self._manifest().artifacts[model_name]
        try:
            file = descriptor.files[artifact_key]
        except KeyError as error:
            raise ArtifactNotReadyError(model_name) from error
        if file.format != expected_format:
            raise ArtifactNotReadyError(model_name)
        return file

    def _file_is_ready(self, model_name: ModelName, file: ArtifactFile) -> bool:
        path = self._resolve_artifact(file.path)
        try:
            self._verify_file(model_name, file, path)
        except ArtifactNotReadyError:
            return False
        return True

    def _verify_file(self, model_name: ModelName, file: ArtifactFile, path: Path) -> None:
        if not path.is_file():
            raise ArtifactNotReadyError(model_name)
        try:
            if path.stat().st_size != file.size_bytes or self._sha256_file(path) != file.sha256:
                raise ArtifactNotReadyError(model_name)
        except OSError as error:
            raise ArtifactNotReadyError(model_name) from error

    def _resolve_artifact(self, relative_path: str) -> Path:
        candidate = Path(relative_path)
        if candidate.is_absolute():
            raise InvalidManifestError("artifact path must be relative")
        return self._resolve_under_root(self._root / candidate)

    def _resolve_under_root(self, candidate: Path) -> Path:
        resolved = candidate.resolve()
        try:
            resolved.relative_to(self._root)
        except ValueError as error:
            raise InvalidManifestError("artifact path escapes the configured root") from error
        return resolved

    @staticmethod
    def _sha256_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as artifact:
            for chunk in iter(lambda: artifact.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
