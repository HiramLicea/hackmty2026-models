# AGENTS.md

## Scope

- Make changes only in this repository (`hackmty2026-models`).
- Treat sibling repositories, especially `HackMTY2026_Mobile`, as read-only references.
- Do not add React Native, A2UI rendering, agent orchestration, or MCP tool implementations here.

## Runtime and architecture

- Target Python 3.11.
- Keep HTTP routes, Pydantic contracts, data access, and prediction services separated.
- Prediction services return structured domain data and visualization hints; callers decide how to
  present it.
- Preserve the sign convention `credit = +amount`, `debit = -amount` in every financial
  calculation.
- Use timezone-aware UTC datetimes at service boundaries.

## Security and data

- Never commit secrets or real banking data.
- The Supabase service-role key is server-side configuration only.
- A `user_id` must come from an authenticated, trusted internal caller. Do not derive or accept
  identity from LLM-generated text.
- Filter all future financial queries through ownership (`accounts.user_id`), including joins from
  transactions through accounts.
- Do not invent database columns or relationships. Update `docs/database-contract.md` only after
  checking authoritative DDL or generated database types.

## Quality

- Add or update tests for behavior and contracts.
- Run `pytest`, `ruff check .`, `ruff format --check .`, and `mypy app tests` before handoff.
- Use temporal train/validation splits for future model evaluation; never randomly split time-series
  records.

