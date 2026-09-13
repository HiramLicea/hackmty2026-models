"""Isolation Forest anomaly ranking with deterministic explanatory rules."""

import asyncio
from typing import Any, cast

import numpy as np
from sklearn.base import TransformerMixin

from app.ml.features import anomaly_features
from app.models.anomalies import (
    AnomalyDetectionRequest,
    AnomalyDetectionResponse,
    AnomalyPoint,
    AnomalySeverity,
    AnomalySummary,
)
from app.models.common import ModelName, PredictionDriver
from app.services.base import (
    ArtifactLoader,
    require_artifact,
    require_descriptor,
    require_json_artifact,
)

MODEL_NAME: ModelName = "detect_transaction_anomalies"


class AnomalyDetectionService:
    def __init__(self, artifacts: ArtifactLoader | None = None) -> None:
        self._artifacts = artifacts

    async def predict(self, request: AnomalyDetectionRequest) -> AnomalyDetectionResponse:
        preprocessor, forest = await asyncio.gather(
            require_artifact(self._artifacts, MODEL_NAME, "preprocessor"),
            require_artifact(self._artifacts, MODEL_NAME, "isolation_forest"),
        )
        rules = await require_json_artifact(self._artifacts, MODEL_NAME, "rule_config")
        descriptor = require_descriptor(self._artifacts, MODEL_NAME)
        features = anomaly_features(request.historical_transactions, request.candidate_transactions)
        scores = (
            -cast(Any, forest).score_samples(
                cast(TransformerMixin, preprocessor).transform(features)
            )
            if len(features)
            else np.array([], dtype=float)
        )
        items: list[AnomalyPoint] = []
        for transaction, row, raw_score in zip(
            request.candidate_transactions, features, scores, strict=True
        ):
            reasons: list[str] = []
            if raw_score >= float(rules["score_threshold"]):
                reasons.append("unusual multivariate transaction pattern")
            if row[6] >= float(rules["category_amount_ratio"]):
                reasons.append("amount is high for this category")
            if row[7] >= float(rules["merchant_amount_ratio"]):
                reasons.append("amount is high for this merchant")
            if row[12] == 1 and transaction.amount >= float(rules["new_merchant_min_amount"]):
                reasons.append("large transaction at a new merchant")
            if not reasons:
                continue
            normalized = float(
                np.clip(0.5 + max(0.0, raw_score - float(rules["score_threshold"])) * 5, 0, 1)
            )
            severity = (
                AnomalySeverity.HIGH
                if raw_score >= float(rules["high_score_threshold"]) or len(reasons) >= 3
                else AnomalySeverity.MEDIUM
                if len(reasons) >= 2
                else AnomalySeverity.LOW
            )
            items.append(
                AnomalyPoint(
                    transaction_id=transaction.transaction_id,
                    occurred_at=transaction.occurred_at,
                    signed_amount=transaction.signed_amount(),
                    anomaly_score=round(normalized, 4),
                    severity=severity,
                    reasons=reasons,
                )
            )
        return AnomalyDetectionResponse(
            request_id=request.request_id,
            model_version=descriptor.model_version,
            trained_until=descriptor.trained_until,
            confidence=0.8 if request.historical_transactions else 0.55,
            summary=AnomalySummary(
                transactions_analyzed=len(request.candidate_transactions),
                anomalies_detected=len(items),
            ),
            items=items,
            drivers=[
                PredictionDriver(
                    name="behavioral_outlier_score",
                    description=(
                        "Isolation Forest score combined with transparent amount and novelty rules."
                    ),
                )
            ],
            limitations=descriptor.limitations,
        )
