# Contratos de predicción

## Reglas comunes

Todos los requests incluyen:

```json
{
  "request_id": "25c00a42-822b-49a7-9c50-0fe913242977",
  "as_of": "2026-09-13T00:00:00Z",
  "currency": "MXN"
}
```

- `request_id` es un UUID de correlación, no una identidad.
- `as_of` requiere zona horaria y se normaliza a UTC.
- `currency` es un código de tres letras normalizado a mayúsculas.
- Los campos desconocidos y números no finitos se rechazan.
- Cada request admite como máximo 10 000 registros sumando todas sus colecciones.
- La historia debe estar ordenada ascendentemente y no puede ser posterior a `as_of`.

Una transacción normalizada contiene `transaction_id` opaco, `amount > 0`, `direction` (`debit` o
`credit`), `category`, `merchant` opcional y `occurred_at` con zona. El monto firmado se deriva como
`credit = +amount` y `debit = -amount`.

Un flujo programado contiene `cash_flow_id` opaco, `name`, `amount > 0`, `direction` (`income` o
`expense`) y `scheduled_date`. Su signo es `income = +amount`, `expense = -amount`.

## Cash balance

`POST /v1/predictions/cash-balance`

```json
{
  "request_id": "25c00a42-822b-49a7-9c50-0fe913242977",
  "as_of": "2026-09-13T00:00:00Z",
  "currency": "MXN",
  "current_balance": 15420.75,
  "horizon_days": 30,
  "transactions": [],
  "scheduled_cash_flows": []
}
```

`horizon_days` acepta 7, 15 o 30. Las transacciones son historia; los flujos programados no pueden
ser anteriores a `as_of`.

## Savings goal

`POST /v1/predictions/savings-goal`

```json
{
  "request_id": "25c00a42-822b-49a7-9c50-0fe913242977",
  "as_of": "2026-09-13T00:00:00Z",
  "currency": "MXN",
  "goal": {
    "goal_id": "goal-opaque-id",
    "target_amount": 50000,
    "target_date": "2027-03-01",
    "current_saved_amount": 18500
  },
  "contributions": [],
  "cash_flow_history": []
}
```

Cada contribución admite `contribution_id` opaco opcional, `amount > 0` y `contributed_at`. La fecha
objetivo no puede ser anterior a `as_of`.

## Recurring charges

`POST /v1/predictions/recurring-charges`

```json
{
  "request_id": "25c00a42-822b-49a7-9c50-0fe913242977",
  "as_of": "2026-09-13T00:00:00Z",
  "currency": "MXN",
  "forecast_days": 30,
  "transactions": []
}
```

`forecast_days` acepta entre 7 y 365 días.

## Anomalies

`POST /v1/predictions/anomalies`

```json
{
  "request_id": "25c00a42-822b-49a7-9c50-0fe913242977",
  "as_of": "2026-09-13T00:00:00Z",
  "currency": "MXN",
  "historical_transactions": [],
  "candidate_transactions": []
}
```

Ambas colecciones deben estar ordenadas. Las candidatas no pueden preceder al último elemento de la
historia ni ser posteriores a `as_of`.

## Respuesta común

```json
{
  "request_id": "25c00a42-822b-49a7-9c50-0fe913242977",
  "model_name": "forecast_cash_balance",
  "model_version": "0.1.0",
  "trained_until": "2026-08-31T23:59:59Z",
  "generated_at": "2026-09-13T00:00:01Z",
  "confidence": 0.84,
  "summary": {},
  "series": [],
  "items": [],
  "drivers": [],
  "limitations": []
}
```

En saldo, `lower_bound`, `expected` y `upper_bound` son p10, p50 y p90 ordenados; los flujos
programados se suman exactamente en la fecha indicada. En metas, el summary incluye fechas de
finalizacion conservadora, esperada y optimista, ademas de probabilidad Monte Carlo. En
recurrencias y anomalias, `items` contiene evidencia y razones explicables.

Los resultados contienen exclusivamente predicción, intervalos, scores, identificadores opacos,
explicaciones, limitaciones y metadatos del modelo. La presentación corresponde al consumidor.
