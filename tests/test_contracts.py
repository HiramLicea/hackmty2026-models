"""Contract invariants independent of model training."""

from datetime import date, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.models.cash_balance import CashBalanceForecastRequest, CashBalancePoint
from app.models.common import CommonPredictionResponse, VisualizationHint

USER_ID = UUID("c1a3797d-b335-5a9d-98a1-402311f82c7a")
ACCOUNT_ID = UUID("799bb0e5-b590-56b6-b30a-8f89538b65df")


def test_cash_balance_horizon_is_restricted() -> None:
    request = CashBalanceForecastRequest(user_id=USER_ID, account_id=ACCOUNT_ID, horizon_days=15)
    assert request.horizon_days == 15

    with pytest.raises(ValidationError):
        CashBalanceForecastRequest(user_id=USER_ID, account_id=ACCOUNT_ID, horizon_days=14)


def test_cash_balance_bounds_must_contain_expected_value() -> None:
    with pytest.raises(ValidationError):
        CashBalancePoint(
            date=date(2026, 9, 13),
            expected=100,
            lower_bound=110,
            upper_bound=120,
        )


def test_common_response_rejects_naive_timestamps() -> None:
    with pytest.raises(ValidationError, match="timezone"):
        CommonPredictionResponse[VisualizationHint, VisualizationHint](
            model_name="forecast_cash_balance",
            model_version="0.1.0",
            user_id=USER_ID,
            generated_at=datetime(2026, 9, 12, 12, 0),
            trained_until=None,
            confidence=0.8,
            summary=VisualizationHint(type="area_chart"),
            series=[],
            visualization_hint=VisualizationHint(type="area_chart"),
        )
