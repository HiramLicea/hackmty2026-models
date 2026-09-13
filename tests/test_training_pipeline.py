"""Synthetic generation and temporal-training invariants."""

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from app.artifacts.store import ArtifactStore
from app.models.cash_balance import CashBalanceForecastRequest
from scripts.synthetic import generate_dataset
from scripts.train_all import train_all


def test_generator_is_reproducible_and_labels_are_evaluation_only(tmp_path: Path) -> None:
    first = generate_dataset(2026, 2, 3, tmp_path / "first")
    second = generate_dataset(2026, 2, 3, tmp_path / "second")
    assert first["dataset_fingerprint"] == second["dataset_fingerprint"]
    profile = json.loads(
        (tmp_path / "first" / "profiles.jsonl").read_text(encoding="utf-8").splitlines()[0]
    )
    assert 300 <= len(profile["transactions"]) <= 600
    assert profile["profile_id"].startswith("syn-profile-")
    assert profile["evaluation"]["anomaly_transaction_ids"]
    assert all("is_synthetic_anomaly" not in item for item in profile["transactions"])
    request = CashBalanceForecastRequest(
        request_id=UUID("25c00a42-822b-49a7-9c50-0fe913242977"),
        as_of=datetime(2026, 8, 31, 23, 59, 59, tzinfo=UTC),
        currency="MXN",
        current_balance=10_000,
        transactions=profile["transactions"],
        scheduled_cash_flows=profile["scheduled_cash_flows"],
    )
    assert len(request.transactions) == len(profile["transactions"])


def test_generator_changes_when_seed_changes(tmp_path: Path) -> None:
    first = generate_dataset(2026, 1, 3, tmp_path / "first-seed")
    second = generate_dataset(2027, 1, 3, tmp_path / "second-seed")
    assert first["dataset_fingerprint"] != second["dataset_fingerprint"]


def test_training_report_documents_per_profile_temporal_split(
    trained_artifact_store: ArtifactStore,
) -> None:
    root = Path(trained_artifact_store._root)
    report = json.loads((root / "training-report.json").read_text(encoding="utf-8"))
    assert report["temporal_split"] == "per-profile chronological 70/15/15"
    assert report["partition_cutoffs"]
    first = report["partition_cutoffs"][0]
    assert first["train_until"] <= first["validation_from"]
    assert first["validation_until"] <= first["test_from"]
    assert set(report["metrics"]) == {
        "forecast_cash_balance",
        "predict_savings_goal",
        "forecast_recurring_charges",
        "detect_transaction_anomalies",
    }


def test_training_twice_is_equivalent_and_creates_required_artifacts(tmp_path: Path) -> None:
    first = train_all(2026, 4, 4, tmp_path / "data-a", tmp_path / "artifacts-a")
    second = train_all(2026, 4, 4, tmp_path / "data-b", tmp_path / "artifacts-b")
    assert first["dataset_fingerprint"] == second["dataset_fingerprint"]
    for model_name in first["artifacts"]:
        first_files = first["artifacts"][model_name]["files"]
        second_files = second["artifacts"][model_name]["files"]
        assert set(first_files) == set(second_files)
        assert {key: value["sha256"] for key, value in first_files.items()} == {
            key: value["sha256"] for key, value in second_files.items()
        }
