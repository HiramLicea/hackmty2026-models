# AGENTS.md

## Scope

- Make changes only in this repository (`hackmty2026-models`).
- Treat sibling repositories, especially `HackMTY2026_Mobile`, as read-only references.
- Do not add React Native, A2UI, agent orchestration, MCP tools, database clients, or ownership logic.

## Runtime and architecture

- Target Python 3.12.
- Keep HTTP routes, Pydantic contracts, preprocessing, artifact loading, and prediction services
  separated.
- Operate as a stateless inference engine: accept normalized financial records and make no outbound
  calls.
- Prediction services return structured financial data only; callers decide how to present it.
- Preserve the sign convention `credit = +amount`, `debit = -amount` in every financial
  calculation.
- Use timezone-aware UTC datetimes at service boundaries.

## Security and data

- Never commit secrets or real banking data.
- Do not accept user identity, session tokens, service-role credentials, emails, or names in
  prediction contracts.
- Authenticate callers with the server-side `INFERENCE_API_KEY`; never log it.
- Keep feature engineering inside the same serialized pipelines used for training.
- Load only trusted, integrity-checked artifacts from the configured read-only root.

## Quality

- Add or update tests for behavior and contracts.
- Run `pytest`, `ruff check .`, `ruff format --check .`, and `mypy app tests` before handoff.
- Use temporal train/validation splits for future model evaluation; never randomly split time-series
  records.
