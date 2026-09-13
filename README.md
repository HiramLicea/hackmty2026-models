# HackMTY 2026 Models

Servicio interno de predicciones financieras para el proyecto de banca personal de HackMTY 2026.
Expone contratos JSON estables para que la capa MCP y el agente consuman resultados de modelos sin
acoplar este repositorio a React Native o A2UI.

Esta primera fase contiene la base de FastAPI, configuración segura, contratos Pydantic e interfaces
placeholder para cuatro capacidades. Todavía no consulta Supabase, entrena modelos, genera datos
sintéticos ni implementa endpoints de predicción.

## Capacidades previstas

- `forecast_cash_balance`: saldo esperado a 7, 15 o 30 días.
- `predict_savings_goal`: escenarios conservador, esperado y optimista para una meta.
- `forecast_recurring_charges`: detección estadística de periodicidad y próximo cargo.
- `detect_transaction_anomalies`: Isolation Forest acompañado de reglas explicables.

## Requisitos

- Python 3.11
- Una URL y una llave server-side de Supabase serán necesarias cuando se implemente el acceso a
  datos. No se requieren para `/health`.

## Ejecución local

```powershell
uv venv --python 3.11 .uv-venv
uv pip install --python .uv-venv\Scripts\python.exe -e ".[dev]"
Copy-Item .env.example .env
.uv-venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

El servicio queda disponible en `http://127.0.0.1:8000` y la comprobación de salud en
`GET /health`.

## Validaciones

```powershell
.uv-venv\Scripts\python.exe -m pytest
.uv-venv\Scripts\python.exe -m ruff check .
.uv-venv\Scripts\python.exe -m ruff format --check .
.uv-venv\Scripts\python.exe -m mypy app tests
```

## Docker

```powershell
docker build -t hackmty2026-models .
docker run --rm -p 8000:8000 --env-file .env hackmty2026-models
```

## Documentación

- [Contexto del sistema](docs/system-context.md)
- [Contrato de base de datos](docs/database-contract.md)
- [Contratos de predicción](docs/prediction-contracts.md)

## Seguridad

El servicio es interno. `user_id` es un UUID transportado para autorización y filtrado, no una
prueba de identidad. La capa MCP o el gateway debe autenticar al usuario y verificar que el UUID
coincide con el token antes de invocar este servicio. `SUPABASE_SERVICE_ROLE_KEY` nunca debe llegar
al agente, al móvil, a logs ni a respuestas.
