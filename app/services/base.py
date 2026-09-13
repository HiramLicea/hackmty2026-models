"""Generic boundary implemented by each prediction capability."""

import asyncio
from typing import Any, Generic, Protocol, TypeVar

from app.artifacts.store import ArtifactNotReadyError, InvalidManifestError
from app.models.common import CommonPredictionRequest, CommonPredictionResponse, ModelName

RequestT = TypeVar("RequestT", bound=CommonPredictionRequest, contravariant=True)
ResponseT = TypeVar("ResponseT", bound=CommonPredictionResponse[Any, Any], covariant=True)


class ModelNotReadyError(RuntimeError):
    """Raised while a deliberately unimplemented model has no trained strategy."""

    def __init__(self, model_name: ModelName) -> None:
        super().__init__("the requested model is not ready")
        self.model_name = model_name


class ArtifactLoader(Protocol):
    """Minimal read-only loader needed by prediction services."""

    def load(self, model_name: ModelName) -> object:
        """Load a validated artifact for a model."""
        ...


async def require_artifact(loader: ArtifactLoader | None, model_name: ModelName) -> object:
    """Load outside the event loop and normalize unavailable files as model readiness errors."""
    if loader is None:
        raise ModelNotReadyError(model_name)
    try:
        return await asyncio.to_thread(loader.load, model_name)
    except (ArtifactNotReadyError, InvalidManifestError) as error:
        raise ModelNotReadyError(model_name) from error


class PredictionService(Protocol, Generic[RequestT, ResponseT]):
    """Async interface used by future HTTP adapters and tests."""

    async def predict(self, request: RequestT) -> ResponseT:
        """Generate one prediction for a verified user's request."""
        ...
