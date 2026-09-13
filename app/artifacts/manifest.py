"""Strict contract for complete, reproducible model artifact manifests."""

from datetime import UTC, datetime
from typing import Literal

from pydantic import AwareDatetime, Field, JsonValue, field_validator, model_validator

from app.models.common import ModelName, StrictModel

MANIFEST_VERSION = "1"
INPUT_CONTRACT_VERSION = "1"
MODEL_NAMES: tuple[ModelName, ...] = (
    "forecast_cash_balance",
    "predict_savings_goal",
    "forecast_recurring_charges",
    "detect_transaction_anomalies",
)
SUPPORTED_MODEL_VERSIONS: dict[ModelName, str] = dict.fromkeys(MODEL_NAMES, "0.1.0")


class ArtifactFile(StrictModel):
    """Integrity metadata for one file relative to the artifact root."""

    path: str = Field(min_length=1, max_length=240)
    format: Literal["joblib", "json"]
    size_bytes: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ModelArtifactDescriptor(StrictModel):
    """Training provenance and files for one prediction capability."""

    model_version: str = Field(pattern=r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
    trained_until: AwareDatetime
    features: list[str] = Field(min_length=1)
    metrics: dict[str, JsonValue]
    files: dict[str, ArtifactFile] = Field(min_length=1)
    limitations: list[str]

    @field_validator("trained_until")
    @classmethod
    def normalize_trained_until(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)


class ModelManifest(StrictModel):
    """Versioned manifest covering every file required for inference."""

    manifest_version: Literal["1"] = "1"
    input_contract_version: Literal["1"] = "1"
    python_version: Literal["3.12"]
    libraries: dict[str, str]
    trained_at: AwareDatetime
    seed: int
    dataset_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    artifacts: dict[ModelName, ModelArtifactDescriptor]

    @field_validator("trained_at")
    @classmethod
    def normalize_trained_at(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def require_every_model_and_library(self) -> "ModelManifest":
        missing_models = set(MODEL_NAMES).difference(self.artifacts)
        if missing_models:
            raise ValueError("manifest must declare every required model")
        missing_libraries = {"scikit-learn", "numpy", "joblib"}.difference(self.libraries)
        if missing_libraries:
            raise ValueError("manifest must declare required runtime library versions")
        return self
