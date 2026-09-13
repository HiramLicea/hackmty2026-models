"""Prediction service interfaces and placeholders."""

from app.services.anomalies import AnomalyDetectionService
from app.services.base import ModelNotReadyError, PredictionService
from app.services.cash_balance import CashBalanceForecastService
from app.services.recurring_charges import RecurringChargesForecastService
from app.services.savings_goal import SavingsGoalPredictionService

INFERENCE_IMPLEMENTED = True

__all__ = [
    "AnomalyDetectionService",
    "CashBalanceForecastService",
    "ModelNotReadyError",
    "PredictionService",
    "RecurringChargesForecastService",
    "SavingsGoalPredictionService",
    "INFERENCE_IMPLEMENTED",
]
