"""Generate synthetic data, train all four capabilities, evaluate, and serialize."""

import argparse
import hashlib
import importlib.metadata
import json
import platform
import shutil
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.ensemble import GradientBoostingRegressor, IsolationForest
from sklearn.metrics import (
    average_precision_score,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    recall_score,
)
from sklearn.preprocessing import StandardScaler

from app.ml.features import (
    ANOMALY_FEATURES,
    CASH_FEATURES,
    SAVINGS_FEATURES,
    anomaly_features,
    cash_features,
    savings_features,
)
from app.ml.recurring import detect_patterns, normalize_merchant
from scripts.synthetic import generate_dataset, load_profiles

MODEL_VERSION = "0.1.0"
TRAINED_AT = datetime(2026, 9, 1, tzinfo=UTC)


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _signed(record: dict[str, Any]) -> float:
    return float(record["amount"]) if record["direction"] == "credit" else -float(record["amount"])


def _split(
    records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Temporal 70/15/15 split within one synthetic profile."""
    first = max(1, int(len(records) * 0.70))
    second = max(first + 1, int(len(records) * 0.85))
    return records[:first], records[first:second], records[second:]


def _metrics(y: np.ndarray, predictions: np.ndarray) -> dict[str, float]:
    return {
        "mae": round(float(mean_absolute_error(y, predictions)), 4),
        "rmse": round(float(mean_squared_error(y, predictions) ** 0.5), 4),
    }


def _fit_quantiles(
    x_train: np.ndarray, y_train: np.ndarray, seed: int
) -> tuple[StandardScaler, dict[str, GradientBoostingRegressor]]:
    scaler = StandardScaler().fit(x_train)
    transformed = scaler.transform(x_train)
    models = {}
    for name, alpha in (("p10", 0.1), ("p50", 0.5), ("p90", 0.9)):
        model = GradientBoostingRegressor(
            loss="quantile",
            alpha=alpha,
            n_estimators=90,
            max_depth=3,
            learning_rate=0.05,
            random_state=seed,
        )
        models[name] = model.fit(transformed, y_train)
    return scaler, models


def _cash_samples(
    profiles: list[dict[str, Any]],
) -> tuple[
    np.ndarray, np.ndarray, np.ndarray, np.ndarray, dict[int, tuple[np.ndarray, np.ndarray]]
]:
    partitions: dict[str, list[tuple[np.ndarray, float, int]]] = defaultdict(list)
    for profile in profiles:
        records = profile["transactions"]
        train, validation, test = _split(records)
        boundaries = (
            ("train", len(train)),
            ("validation", len(train) + len(validation)),
            ("test", len(train) + len(validation) + max(1, len(test) // 2)),
        )
        starting_balance = float(profile["monthly_income"]) * 0.8
        for partition, boundary in boundaries:
            boundary = min(boundary, len(records) - 1)
            as_of = _dt(records[boundary - 1]["occurred_at"])
            history = records[:boundary]
            current_balance = starting_balance + sum(_signed(item) for item in history)
            for horizon in (7, 15, 30):
                future_end = as_of + timedelta(days=horizon)
                target = sum(
                    _signed(item)
                    for item in records[boundary:]
                    if _dt(item["occurred_at"]) <= future_end
                )
                feature = cash_features(history, current_balance, as_of, horizon, [])
                partitions[partition].append((feature[0], target, horizon))

    def xy(name: str) -> tuple[np.ndarray, np.ndarray]:
        rows = partitions[name]
        return np.asarray([row[0] for row in rows]), np.asarray([row[1] for row in rows])

    train_x, train_y = xy("train")
    val_x, val_y = xy("validation")
    test_x, test_y = xy("test")
    by_horizon = {
        horizon: (
            np.asarray([row[0] for row in partitions["test"] if row[2] == horizon]),
            np.asarray([row[1] for row in partitions["test"] if row[2] == horizon]),
        )
        for horizon in (7, 15, 30)
    }
    return train_x, train_y, val_x, val_y, by_horizon


def train_cash(profiles: list[dict[str, Any]], root: Path, seed: int) -> dict[str, Any]:
    train_x, train_y, val_x, val_y, by_horizon = _cash_samples(profiles)
    scaler, models = _fit_quantiles(train_x, train_y, seed)
    directory = root / "cash_balance"
    directory.mkdir(parents=True)
    joblib.dump(scaler, directory / "preprocessor.joblib", compress=3)
    for name, model in models.items():
        joblib.dump(model, directory / f"forecast_{name}.joblib", compress=3)
    val = scaler.transform(val_x)
    lower, median, upper = (models[name].predict(val) for name in ("p10", "p50", "p90"))
    metrics: dict[str, Any] = {
        "validation": _metrics(val_y, median),
        "interval_coverage_p10_p90": round(float(np.mean((val_y >= lower) & (val_y <= upper))), 4),
        "by_horizon_days": {},
    }
    for horizon, (test_x, test_y) in by_horizon.items():
        prediction = models["p50"].predict(scaler.transform(test_x))
        metrics["by_horizon_days"][str(horizon)] = _metrics(test_y, prediction)
    metadata = {
        "schema_version": "1",
        "algorithm": "global GradientBoostingRegressor quantile residual forecast",
        "features": CASH_FEATURES,
        "metrics": metrics,
        "temporal_split": "per-profile chronological 70/15/15",
    }
    _write_json(directory / "metadata.json", metadata)
    return {
        "features": CASH_FEATURES,
        "metrics": metrics,
        "files": {
            "preprocessor": directory / "preprocessor.joblib",
            **{f"forecast_{name}": directory / f"forecast_{name}.joblib" for name in models},
            "metadata": directory / "metadata.json",
        },
        "limitations": [
            "Synthetic MXN behavior may not represent every household.",
            "Known scheduled flows are added deterministically and assumed to occur.",
        ],
    }


def _savings_samples(
    profiles: list[dict[str, Any]],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    partitions: dict[str, list[tuple[np.ndarray, float]]] = defaultdict(list)
    for profile in profiles:
        records = profile["transactions"]
        contributions = profile["contributions"]
        train, validation, _ = _split(records)
        boundaries = (
            ("train", len(train)),
            ("validation", len(train) + len(validation)),
            ("test", len(records)),
        )
        for partition, boundary in boundaries:
            as_of = _dt(records[boundary - 1]["occurred_at"])
            seen_contributions = [
                item for item in contributions if _dt(item["contributed_at"]) <= as_of
            ]
            saved = sum(float(item["amount"]) for item in seen_contributions) * 0.75
            goal = dict(profile["savings_goal"])
            goal["current_saved_amount"] = saved
            if datetime.fromisoformat(goal["target_date"]).date() <= as_of.date():
                goal["target_date"] = (as_of + timedelta(days=180)).date().isoformat()
            feature = savings_features(goal, seen_contributions, records[:boundary], as_of)
            monthly = np.mean(
                [float(item["amount"]) for item in seen_contributions[-6:]]
                or [max(100.0, profile["monthly_income"] * 0.08)]
            )
            days_remaining = max(
                1.0, (float(goal["target_amount"]) - saved) / max(1.0, monthly) * 30.44
            )
            partitions[partition].append((feature[0], days_remaining))
    arrays: list[np.ndarray] = []
    for name in ("train", "validation", "test"):
        arrays.extend(
            (
                np.asarray([row[0] for row in partitions[name]]),
                np.asarray([row[1] for row in partitions[name]]),
            )
        )
    return tuple(arrays)  # type: ignore[return-value]


def train_savings(profiles: list[dict[str, Any]], root: Path, seed: int) -> dict[str, Any]:
    train_x, train_y, val_x, val_y, test_x, test_y = _savings_samples(profiles)
    scaler, models = _fit_quantiles(train_x, train_y, seed + 1)
    directory = root / "savings_goal"
    directory.mkdir(parents=True)
    joblib.dump(scaler, directory / "preprocessor.joblib", compress=3)
    for name, model in models.items():
        joblib.dump(model, directory / f"goal_days_{name}.joblib", compress=3)
    validation_prediction = models["p50"].predict(scaler.transform(val_x))
    test_prediction = models["p50"].predict(scaler.transform(test_x))
    residuals = val_y - validation_prediction
    config = {
        "schema_version": "1",
        "seed_offset": 31,
        "samples": 1000,
        "residual_std_days": round(float(max(1.0, residuals.std())), 6),
        "residual_p10_days": round(float(np.quantile(residuals, 0.1)), 6),
        "residual_p90_days": round(float(np.quantile(residuals, 0.9)), 6),
    }
    _write_json(directory / "simulation_config.json", config)
    lower = models["p10"].predict(scaler.transform(test_x))
    upper = models["p90"].predict(scaler.transform(test_x))
    coverage = float(
        np.mean((test_y >= np.minimum(lower, upper)) & (test_y <= np.maximum(lower, upper)))
    )
    predicted_contribution = test_x[:, 0] / np.maximum(1.0, test_x[:, 1] / 30.44)
    actual_contribution = test_x[:, 0] / np.maximum(1.0, test_y / 30.44)
    probability = 1.0 / (
        1.0 + np.exp((test_prediction - test_x[:, 1]) / max(1.0, float(residuals.std())))
    )
    outcome = (test_y <= test_x[:, 1]).astype(float)
    metrics = {
        "validation": _metrics(val_y, validation_prediction),
        "test": _metrics(test_y, test_prediction),
        "quantile_coverage_p10_p90": round(coverage, 4),
        "recommended_contribution_mae": round(
            float(mean_absolute_error(actual_contribution, predicted_contribution)), 4
        ),
        "probability_brier_score": round(float(np.mean((probability - outcome) ** 2)), 4),
        "date_within_30_days": round(float(np.mean(np.abs(test_y - test_prediction) <= 30)), 4),
    }
    metadata = {
        "schema_version": "1",
        "algorithm": "global quantile gradient boosting + residual Monte Carlo",
        "features": SAVINGS_FEATURES,
        "metrics": metrics,
        "temporal_split": "per-profile chronological 70/15/15",
    }
    _write_json(directory / "metadata.json", metadata)
    return {
        "features": SAVINGS_FEATURES,
        "metrics": metrics,
        "files": {
            "preprocessor": directory / "preprocessor.joblib",
            **{f"goal_days_{name}": directory / f"goal_days_{name}.joblib" for name in models},
            "simulation_config": directory / "simulation_config.json",
            "metadata": directory / "metadata.json",
        },
        "limitations": [
            "Completion scenarios assume recent contribution behavior remains informative.",
            "Monte Carlo uncertainty is calibrated on synthetic residuals.",
        ],
    }


def train_recurring(profiles: list[dict[str, Any]], root: Path) -> dict[str, Any]:
    candidates = [
        {
            "min_observations": observations,
            "absolute_tolerance_days": tolerance,
            "relative_tolerance": 0.2,
            "min_confidence": confidence,
        }
        for observations in (3, 4)
        for tolerance in (2.0, 4.0, 6.0)
        for confidence in (0.35, 0.5)
    ]
    best, best_f1 = candidates[0], -1.0
    best_truth: list[int] = []
    best_predicted: list[int] = []
    for config in candidates:
        truth: list[int] = []
        predicted: list[int] = []
        for profile in profiles:
            _, validation, test = _split(profile["transactions"])
            history = profile["transactions"][: len(profile["transactions"]) - len(test)]
            as_of = _dt(history[-1]["occurred_at"]).date()
            found = {
                row["normalized_merchant"] for row in detect_patterns(history, as_of, 45, config)
            }
            expected = {
                normalize_merchant(item["merchant"])
                for item in profile["evaluation"]["recurring_patterns"]
            }
            universe = found | expected
            truth.extend(int(item in expected) for item in universe)
            predicted.extend(int(item in found) for item in universe)
            del validation
        score = float(f1_score(truth, predicted, zero_division=0))
        if score > best_f1:
            best, best_f1 = config, score
            best_truth, best_predicted = truth, predicted
    date_errors: list[float] = []
    amount_errors: list[float] = []
    for profile in profiles:
        _, validation, test = _split(profile["transactions"])
        history = profile["transactions"][: len(profile["transactions"]) - len(test)]
        as_of = _dt(history[-1]["occurred_at"]).date()
        detected = detect_patterns(history, as_of, 45, best)
        future_by_merchant: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for transaction in test:
            future_by_merchant[normalize_merchant(transaction["merchant"])].append(transaction)
        for row in detected:
            future = future_by_merchant.get(str(row["normalized_merchant"]), [])
            if not future:
                continue
            actual = future[0]
            date_errors.append(
                abs((row["next_expected_date"] - _dt(actual["occurred_at"]).date()).days)
            )
            amount_errors.append(abs(float(row["expected_amount"]) - float(actual["amount"])))
        del validation
    directory = root / "recurring_charges"
    directory.mkdir(parents=True)
    _write_json(directory / "detector_config.json", {"schema_version": "1", **best})
    normalization = {
        "schema_version": "1",
        "method": "lowercase, strip punctuation, remove locale/payment/numeric tokens",
        "removed_tokens": ["mx", "mex", "payment", "pago", "online", "numeric tokens"],
    }
    _write_json(directory / "merchant_normalization.json", normalization)
    metadata = {
        "method": "merchant normalization + median interval/MAD",
        "validation_precision": round(
            float(precision_score(best_truth, best_predicted, zero_division=0)), 4
        ),
        "validation_recall": round(
            float(recall_score(best_truth, best_predicted, zero_division=0)), 4
        ),
        "validation_f1": round(float(f1_score(best_truth, best_predicted, zero_division=0)), 4),
        "mean_next_date_error_days": round(float(np.mean(date_errors or [0.0])), 4),
        "mean_expected_amount_error": round(float(np.mean(amount_errors or [0.0])), 4),
        "candidate_configurations": len(candidates),
        "temporal_split": "per-profile chronological 70/15/15",
    }
    _write_json(directory / "metadata.json", metadata)
    return {
        "features": [
            "normalized_merchant",
            "interval_days",
            "interval_mad",
            "median_amount",
            "observations",
        ],
        "metrics": metadata,
        "files": {
            "detector_config": directory / "detector_config.json",
            "merchant_normalization": directory / "merchant_normalization.json",
            "metadata": directory / "metadata.json",
        },
        "limitations": [
            "At least three historical debits per merchant are required.",
            "Merchant normalization is language-agnostic but intentionally conservative.",
        ],
    }


def train_anomalies(profiles: list[dict[str, Any]], root: Path, seed: int) -> dict[str, Any]:
    train_rows: list[np.ndarray] = []
    val_rows: list[np.ndarray] = []
    val_labels: list[int] = []
    test_rows: list[np.ndarray] = []
    test_labels: list[int] = []
    for profile in profiles:
        train, validation, test = _split(profile["transactions"])
        labels = set(profile["evaluation"]["anomaly_transaction_ids"])
        train_rows.append(anomaly_features([], train))
        val_rows.append(anomaly_features(train, validation))
        val_labels.extend(int(item["transaction_id"] in labels) for item in validation)
        test_rows.append(anomaly_features(train + validation, test))
        test_labels.extend(int(item["transaction_id"] in labels) for item in test)
    train_x = np.vstack(train_rows)
    val_x = np.vstack(val_rows)
    test_x = np.vstack(test_rows)
    scaler = StandardScaler().fit(train_x)
    forest = IsolationForest(
        n_estimators=120,
        contamination=0.02,
        max_samples=min(2048, len(train_x)),
        random_state=seed + 2,
        n_jobs=1,
    ).fit(scaler.transform(train_x))
    train_scores = -forest.score_samples(scaler.transform(train_x))
    threshold = float(np.quantile(train_scores, 0.98))
    val_scores = -forest.score_samples(scaler.transform(val_x))
    test_scores = -forest.score_samples(scaler.transform(test_x))
    val_prediction = (val_scores >= threshold).astype(int)
    test_prediction = (test_scores >= threshold).astype(int)
    rules = {
        "schema_version": "1",
        "score_threshold": threshold,
        "high_score_threshold": float(np.quantile(train_scores, 0.995)),
        "category_amount_ratio": 5.0,
        "merchant_amount_ratio": 6.0,
        "new_merchant_min_amount": 5000.0,
    }
    directory = root / "anomalies"
    directory.mkdir(parents=True)
    joblib.dump(scaler, directory / "preprocessor.joblib", compress=3)
    joblib.dump(forest, directory / "isolation_forest.joblib", compress=3)
    _write_json(directory / "rule_config.json", rules)

    def classification(
        labels: list[int], prediction: np.ndarray, scores: np.ndarray
    ) -> dict[str, float]:
        negatives = max(1, sum(label == 0 for label in labels))
        false_positives = sum(
            label == 0 and predicted == 1
            for label, predicted in zip(labels, prediction, strict=True)
        )
        return {
            "precision": round(float(precision_score(labels, prediction, zero_division=0)), 4),
            "recall": round(float(recall_score(labels, prediction, zero_division=0)), 4),
            "f1": round(float(f1_score(labels, prediction, zero_division=0)), 4),
            "alert_rate": round(float(np.mean(prediction)), 4),
            "pr_auc": round(float(average_precision_score(labels, scores)), 4),
            "false_positive_rate": round(false_positives / negatives, 4),
        }

    metrics = {
        "validation": classification(val_labels, val_prediction, val_scores),
        "test": classification(test_labels, test_prediction, test_scores),
        "fit_labels_used": False,
    }
    metadata = {
        "schema_version": "1",
        "algorithm": "StandardScaler + unsupervised IsolationForest + explainable rules",
        "features": ANOMALY_FEATURES,
        "metrics": metrics,
        "temporal_split": "per-profile chronological 70/15/15",
    }
    _write_json(directory / "metadata.json", metadata)
    return {
        "features": ANOMALY_FEATURES,
        "metrics": metrics,
        "files": {
            "preprocessor": directory / "preprocessor.joblib",
            "isolation_forest": directory / "isolation_forest.joblib",
            "rule_config": directory / "rule_config.json",
            "metadata": directory / "metadata.json",
        },
        "limitations": [
            "Isolation Forest ranks unusual behavior; it does not prove fraud.",
            "Rules require sufficient merchant/category history for strongest explanations.",
        ],
    }


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )


def _file_descriptor(path: Path, root: Path) -> dict[str, Any]:
    content = path.read_bytes()
    return {
        "path": path.relative_to(root).as_posix(),
        "format": "json" if path.suffix == ".json" else "joblib",
        "size_bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def train_all(
    seed: int, users: int, months: int, data_dir: Path, artifact_dir: Path
) -> dict[str, Any]:
    summary = generate_dataset(seed, users, months, data_dir)
    profiles = load_profiles(data_dir / "profiles.jsonl")
    partition_cutoffs = []
    for profile in profiles:
        train, validation, test = _split(profile["transactions"])
        partition_cutoffs.append(
            {
                "profile_id": profile["profile_id"],
                "train_from": train[0]["occurred_at"],
                "train_until": train[-1]["occurred_at"],
                "validation_from": validation[0]["occurred_at"],
                "validation_until": validation[-1]["occurred_at"],
                "test_from": test[0]["occurred_at"],
                "test_until": test[-1]["occurred_at"],
            }
        )
    if artifact_dir.exists():
        shutil.rmtree(artifact_dir)
    artifact_dir.mkdir(parents=True)
    trained_until = datetime.fromisoformat(summary["end_date"] + "T23:59:59+00:00")
    trained = {
        "forecast_cash_balance": train_cash(profiles, artifact_dir, seed),
        "predict_savings_goal": train_savings(profiles, artifact_dir, seed),
        "forecast_recurring_charges": train_recurring(profiles, artifact_dir),
        "detect_transaction_anomalies": train_anomalies(profiles, artifact_dir, seed),
    }
    artifacts: dict[str, Any] = {}
    for name, result in trained.items():
        artifacts[name] = {
            "model_version": MODEL_VERSION,
            "trained_until": trained_until.isoformat(),
            "features": result["features"],
            "metrics": result["metrics"],
            "files": {
                key: _file_descriptor(path, artifact_dir) for key, path in result["files"].items()
            },
            "limitations": result["limitations"],
        }
    manifest = {
        "manifest_version": "1",
        "input_contract_version": "1",
        "python_version": "3.12",
        "libraries": {
            name: importlib.metadata.version(name) for name in ("scikit-learn", "numpy", "joblib")
        },
        "trained_at": TRAINED_AT.isoformat(),
        "seed": seed,
        "dataset_fingerprint": summary["dataset_fingerprint"],
        "artifacts": artifacts,
        "training": {
            "profiles": users,
            "months": months,
            "temporal_split": "per-profile chronological 70/15/15",
            "generator": "scripts/generate_synthetic_data.py",
            "partition_cutoffs": partition_cutoffs,
        },
    }
    # Keep manifest contract strict while retaining training metadata in a separate report.
    training = manifest.pop("training")
    _write_json(artifact_dir / "manifest.json", manifest)
    _write_json(
        artifact_dir / "training-report.json",
        training | {"metrics": {name: value["metrics"] for name, value in trained.items()}},
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--users", type=int, default=120)
    parser.add_argument("--months", type=int, default=18)
    parser.add_argument("--data-dir", type=Path, default=Path("data/generated"))
    parser.add_argument("--artifact-dir", type=Path, default=Path("artifacts"))
    args = parser.parse_args()
    if platform.python_version_tuple()[:2] != ("3", "12"):
        parser.error("training requires Python 3.12")
    manifest = train_all(args.seed, args.users, args.months, args.data_dir, args.artifact_dir)
    print(
        json.dumps(
            {
                "status": "trained",
                "models": list(manifest["artifacts"]),
                "dataset_fingerprint": manifest["dataset_fingerprint"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
