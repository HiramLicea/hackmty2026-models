"""Generic boundary implemented by each prediction capability."""

import asyncio
from typing import Any, Protocol

from app.artifacts.manifest import ModelArtifactDescriptor
from app.artifacts.store import ArtifactNotReadyError, InvalidManifestError
from app.models.common import CommonPredictionRequest, CommonPredictionResponse, ModelName


class ModelNotReadyError(RuntimeError):
    """Raised while a deliberately unimplemented model has no trained strategy."""

    def __init__(self, model_name: ModelName) -> None:
        super().__init__("the requested model is not ready")
        self.model_name = model_name


class ArtifactLoader(Protocol):
    """Minimal read-only loader needed by prediction services."""

    def load(self, model_name: ModelName, artifact_key: str) -> object:
        """Load a validated artifact for a model."""
        ...

    def load_json(self, model_name: ModelName, artifact_key: str) -> dict[str, Any]: ...

    def descriptor(self, model_name: ModelName) -> ModelArtifactDescriptor: ...


async def require_artifact(
    loader: ArtifactLoader | None, model_name: ModelName, artifact_key: str
) -> object:
    """Load outside the event loop and normalize unavailable files as model readiness errors."""
    if loader is None:
        raise ModelNotReadyError(model_name)
    try:
        return await asyncio.to_thread(loader.load, model_name, artifact_key)
    except (ArtifactNotReadyError, InvalidManifestError) as error:
        raise ModelNotReadyError(model_name) from error


async def require_json_artifact(
    loader: ArtifactLoader | None, model_name: ModelName, artifact_key: str
) -> dict[str, Any]:
    if loader is None:
        raise ModelNotReadyError(model_name)
    try:
        return await asyncio.to_thread(loader.load_json, model_name, artifact_key)
    except (ArtifactNotReadyError, InvalidManifestError) as error:
        raise ModelNotReadyError(model_name) from error


def require_descriptor(
    loader: ArtifactLoader | None, model_name: ModelName
) -> ModelArtifactDescriptor:
    if loader is None:
        raise ModelNotReadyError(model_name)
    try:
        return loader.descriptor(model_name)
    except (ArtifactNotReadyError, InvalidManifestError) as error:
        raise ModelNotReadyError(model_name) from error


class PredictionService[
    RequestT: CommonPredictionRequest,
    ResponseT: CommonPredictionResponse[Any, Any, Any],
](Protocol):
    """Async interface used by future HTTP adapters and tests."""

    async def predict(self, request: RequestT) -> ResponseT:
        """Generate one prediction for a verified user's request."""
        ...
