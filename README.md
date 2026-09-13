# HackMTY 2026 Models

Motor HTTP stateless de inferencia financiera. Recibe registros normalizados, ejecuta modelos
locales y devuelve datos de dominio estructurados. No consulta bases de datos, no acepta identidad
de usuario, no implementa MCP/A2UI y no realiza conexiones salientes.

## Modelos

- `forecast_cash_balance`: Gradient Boosting cuantílico global p10/p50/p90 y flujos programados
  aplicados de forma determinista.
- `predict_savings_goal`: Gradient Boosting cuantílico global y Monte Carlo reproducible por
  `request_id`.
- `forecast_recurring_charges`: normalización de comercio, mediana de intervalos y MAD con umbrales
  calibrados.
- `detect_transaction_anomalies`: Isolation Forest no supervisado más reglas explicables.

Cada respuesta incluye `model_version`, `trained_until`, confianza, drivers y limitaciones. Los
montos siempre usan `credit = +amount` y `debit = -amount` internamente.

## Instalación, datos y entrenamiento

Requiere Python 3.12. Las dependencias de runtime son también suficientes para el entrenamiento;
el extra `dev` agrega únicamente validación y pruebas. No se necesitan pandas, statsmodels ni
frameworks de deep learning.

```powershell
uv venv --python 3.12 .uv-venv
uv pip install --python .uv-venv\Scripts\python.exe -e ".[dev]"
.uv-venv\Scripts\python.exe scripts\generate_synthetic_data.py --seed 2026 --users 120 --months 18 --output-dir data\generated
.uv-venv\Scripts\python.exe scripts\train_all.py --seed 2026
```

El generador crea exclusivamente perfiles `syn-profile-*` con 300–600 transacciones por perfil.
`data/generated/` está ignorado; se conservan configuración, schema y resumen pequeños. Las
etiquetas sintéticas viven en `evaluation` y sólo se usan para métricas, nunca como features. El
entrenamiento usa cortes cronológicos 70/15/15 dentro de cada perfil.

`train_all.py` recrea `artifacts/`, registra hashes SHA-256, tamaños, versiones, fingerprint del
dataset, features, métricas, fecha de entrenamiento y `trained_until`. Los archivos joblib deben
tratarse como código: cargar sólo los producidos por este pipeline controlado.

## Ejecución HTTP

```powershell
Copy-Item .env.example .env
.uv-venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

- `GET /health`: liveness; siempre 200 si el proceso está vivo.
- `GET /ready`: 200 con `ready=true` sólo si configuración, manifest, hashes y todos los archivos
  cargan; de otro modo 503 con `ready=false`.
- `POST /v1/predictions/*`: exige `Authorization: Bearer <INFERENCE_API_KEY>`.

## Validación

```powershell
.uv-venv\Scripts\python.exe -m pytest
.uv-venv\Scripts\python.exe -m ruff check .
.uv-venv\Scripts\python.exe -m ruff format --check .
.uv-venv\Scripts\python.exe -m mypy app tests
.uv-venv\Scripts\python.exe -m pip check
.uv-venv\Scripts\python.exe scripts\estimate_bundle_size.py
```

## Documentación

- [Contexto y límites](docs/system-context.md)
- [Contratos HTTP](docs/prediction-contracts.md)
- [Consumo desde servidores externos](docs/mcp-integration.md)
- [Despliegue en Vercel](docs/vercel-deployment.md)

`INFERENCE_API_KEY` es server-side: nunca debe aparecer en clientes públicos, cuerpos, respuestas
o logs. Este repositorio no contiene datos bancarios reales ni secretos.
