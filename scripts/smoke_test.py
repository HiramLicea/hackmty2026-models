"""Non-destructive smoke test for a local, preview, or production Models API."""

import json
import os
import sys
from datetime import UTC, datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4


def request_json(url: str, *, api_key: str | None = None) -> tuple[int, dict[str, object]]:
    """Issue one sanitized request without ever printing request headers."""
    data = None
    headers = {"Accept": "application/json"}
    method = "GET"
    if api_key is not None:
        method = "POST"
        headers["Authorization"] = f"Bearer {api_key}"
        headers["Content-Type"] = "application/json"
        data = json.dumps(
            {
                "request_id": str(uuid4()),
                "as_of": datetime.now(UTC).isoformat(),
                "currency": "MXN",
                "historical_transactions": [],
                "candidate_transactions": [],
            }
        ).encode()
    request = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(request, timeout=30) as response:  # noqa: S310 - operator-provided URL
            return response.status, json.loads(response.read())
    except HTTPError as error:
        return error.code, json.loads(error.read())


def main() -> int:
    """Check public operations and verify that the protected route accepts authentication."""
    base_url = os.getenv("MODELS_API_URL", "").rstrip("/")
    api_key = os.getenv("INFERENCE_API_KEY", "")
    if not base_url or not api_key:
        print("MODELS_API_URL and INFERENCE_API_KEY are required", file=sys.stderr)
        return 2

    try:
        health_status, _ = request_json(f"{base_url}/health")
        ready_status, ready_body = request_json(f"{base_url}/ready")
        prediction_status, prediction_body = request_json(
            f"{base_url}/v1/predictions/anomalies",
            api_key=api_key,
        )
    except (URLError, TimeoutError, ValueError, json.JSONDecodeError) as error:
        print(
            f"Smoke test could not reach a valid JSON API: {type(error).__name__}", file=sys.stderr
        )
        return 1

    prediction_code = prediction_body.get("error", {})
    error_code = prediction_code.get("code") if isinstance(prediction_code, dict) else None
    auth_accepted = prediction_status in {200, 503} and error_code not in {
        "INVALID_API_KEY",
        "SERVICE_NOT_CONFIGURED",
    }
    print(f"health: HTTP {health_status}")
    print(f"ready: HTTP {ready_status}, ready={ready_body.get('ready')}")
    print(f"authenticated prediction: HTTP {prediction_status}, auth_accepted={auth_accepted}")
    return 0 if health_status == ready_status == 200 and auth_accepted else 1


if __name__ == "__main__":
    raise SystemExit(main())
