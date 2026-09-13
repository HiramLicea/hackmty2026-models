# Contratos de predicción

## Metadatos comunes

Todas las respuestas futuras extienden `CommonPredictionResponse`:

```json
{
  "model_name": "forecast_cash_balance",
  "model_version": "0.1.0",
  "user_id": "c1a3797d-b335-5a9d-98a1-402311f82c7a",
  "generated_at": "2026-09-12T18:00:00Z",
  "trained_until": "2026-09-11T23:59:59Z",
  "confidence": 0.82,
  "summary": {},
  "series": [],
  "drivers": [],
  "limitations": [],
  "visualization_hint": {
    "type": "area_chart",
    "x_field": "date",
    "y_fields": ["expected", "lower_bound", "upper_bound"]
  }
}
```

- Fechas y datetimes usan ISO-8601; los datetimes deben incluir zona horaria y se normalizan a UTC.
- `confidence` está entre 0 y 1 y describe confianza calibrada del resultado, no una garantía.
- `drivers` ofrece factores explicables con impacto firmado y detalles JSON opcionales.
- `limitations` hace visibles escasez de historia, datos faltantes y supuestos.
- `visualization_hint` es una recomendación semántica. El agente decide el árbol A2UI final.
- Tipos permitidos: `area_chart`, `line_chart`, `progress`, `transaction_list`, `anomaly_list` y
  `summary_card`.

## Solicitudes comunes

Todas incluyen `user_id` (UUID) y `as_of` opcional. `user_id` debe haber sido verificado por el
caller interno. `as_of` permite backtesting reproducible y nunca debe ocasionar lectura de datos
posteriores a esa fecha.

## `forecast_cash_balance`

Entrada: `account_id`, `horizon_days` (`7`, `15` o `30`) y metadatos comunes.

Resumen: saldo inicial, saldo final esperado, mínimo esperado, moneda e ingresos/egresos programados.
La serie diaria contiene `expected`, `lower_bound` y `upper_bound`. Los límites deben respetar
`lower_bound <= expected <= upper_bound`.

En una fase posterior, el baseline combinará una serie temporal (SARIMAX cuando los datos lo
justifiquen) con flujos programados determinísticos.

## `predict_savings_goal`

Entrada: `goal_id`, cantidad de simulaciones y metadatos comunes.

Resumen: monto objetivo, progreso, probabilidad de alcanzar la meta, fecha esperada y aportación
mensual recomendada. La serie contiene percentiles conservador, esperado y optimista por fecha.

La simulación futura usará particiones temporales y una semilla controlable en evaluación.

## `forecast_recurring_charges`

Entrada: `account_id` opcional, ventanas de historia/pronóstico y metadatos comunes.

Resumen: total de patrones y monto previsto. Cada elemento de serie describe comercio normalizado,
fecha/monto estimados, periodicidad, confianza y evidencia. Esta capacidad se reportará como método
estadístico basado en reglas mientras no exista un modelo supervisado.

## `detect_transaction_anomalies`

Entrada: `account_id` opcional, ventana histórica, contaminación y metadatos comunes.

Resumen: transacciones analizadas y anomalías detectadas. Cada elemento contiene identificador,
fecha, monto firmado, score, severidad y razones explicables.

Isolation Forest será una señal inicial, complementada con reglas sobre monto, horario, categoría,
comercio, frecuencia y desviación histórica. Un resultado es una alerta para revisión, no una
afirmación de fraude.

## Versionado

`model_version` versiona el comportamiento predictivo y sus artefactos. Los cambios incompatibles
del contrato HTTP requerirán además una nueva versión de ruta cuando se publiquen endpoints de
predicción. En esta fase no se publican esas rutas.

