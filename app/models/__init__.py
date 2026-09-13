"""Public normalized request and prediction response contracts."""

from app.models.anomalies import AnomalyDetectionRequest, AnomalyDetectionResponse
from app.models.cash_balance import CashBalanceForecastRequest, CashBalanceForecastResponse
from app.models.common import CommonPredictionRequest, CommonPredictionResponse, ModelName
from app.models.inputs import NormalizedTransaction, ScheduledCashFlow
from app.models.recurring_charges import RecurringChargesRequest, RecurringChargesResponse
from app.models.savings_goal import SavingsGoalPredictionRequest, SavingsGoalPredictionResponse

__all__ = [
    "AnomalyDetectionRequest",
    "AnomalyDetectionResponse",
    "CashBalanceForecastRequest",
    "CashBalanceForecastResponse",
    "CommonPredictionRequest",
    "CommonPredictionResponse",
    "ModelName",
    "NormalizedTransaction",
    "RecurringChargesRequest",
    "RecurringChargesResponse",
    "SavingsGoalPredictionRequest",
    "SavingsGoalPredictionResponse",
    "ScheduledCashFlow",
]
