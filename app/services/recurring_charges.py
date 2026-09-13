"""Calibrated statistical recurring-charge inference."""

from app.ml.recurring import detect_patterns
from app.models.common import ModelName, PredictionDriver
from app.models.recurring_charges import (
    RecurringChargePoint,
    RecurringChargesRequest,
    RecurringChargesResponse,
    RecurringChargesSummary,
)
from app.services.base import ArtifactLoader, require_descriptor, require_json_artifact

MODEL_NAME: ModelName = "forecast_recurring_charges"


class RecurringChargesForecastService:
    def __init__(self, artifacts: ArtifactLoader | None = None) -> None:
        self._artifacts = artifacts

    async def predict(self, request: RecurringChargesRequest) -> RecurringChargesResponse:
        config = await require_json_artifact(self._artifacts, MODEL_NAME, "detector_config")
        descriptor = require_descriptor(self._artifacts, MODEL_NAME)
        items = [
            RecurringChargePoint.model_validate(row)
            for row in detect_patterns(
                request.transactions, request.as_of.date(), request.forecast_days, config
            )
        ]
        confidence = sum(item.confidence for item in items) / len(items) if items else 0.35
        return RecurringChargesResponse(
            request_id=request.request_id,
            model_version=descriptor.model_version,
            trained_until=descriptor.trained_until,
            confidence=round(confidence, 4),
            summary=RecurringChargesSummary(
                currency=request.currency,
                patterns_detected=len(items),
                expected_total=round(sum(item.expected_amount for item in items), 2),
            ),
            items=items,
            drivers=[
                PredictionDriver(
                    name="merchant_periodicity",
                    impact=float(len(items)),
                    description="Repeated normalized merchants with stable median intervals.",
                )
            ],
            limitations=descriptor.limitations,
        )
