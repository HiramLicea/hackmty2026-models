# Consumo HTTP desde un servidor externo

Este documento describe exclusivamente cómo un servidor consumidor —incluido un posible servidor
MCP— invoca Models API. No define ni implementa tools dentro del motor.

## Responsabilidades del consumidor

Antes de llamar a esta API, el consumidor debe autenticar al usuario, validar permisos y ownership,
consultar su fuente de datos, minimizar los campos y producir los registros normalizados descritos en
`prediction-contracts.md`. No debe reenviar identidad, tokens de sesión, correos, nombres completos,
credenciales de base de datos ni vectores de features.

## Autenticación y endpoints

```http
Authorization: Bearer <INFERENCE_API_KEY>
Content-Type: application/json
```

| Operación externa | Método y endpoint |
| --- | --- |
| Pronóstico de saldo | `POST /v1/predictions/cash-balance` |
| Predicción de meta | `POST /v1/predictions/savings-goal` |
| Cargos recurrentes | `POST /v1/predictions/recurring-charges` |
| Detección de anomalías | `POST /v1/predictions/anomalies` |

El contrato autoritativo está disponible en `/openapi.json`. Se recomienda timeout total de 30 s y
de conexión de 5 s. Reintentar con backoff acotado sólo ante timeouts o errores 5xx transitorios; no
reintentar 401, 409 o 422.

## Errores

```json
{
  "error": {
    "code": "MODEL_NOT_READY",
    "message": "Requested model is not ready",
    "request_id": "b4bd287f-634c-4121-97f2-0a0ba3971afe"
  }
}
```

| HTTP | Código | Acción |
| --- | --- | --- |
| 401 | `INVALID_API_KEY` | Revisar credencial; no reintentar. |
| 409 | `MODEL_VERSION_MISMATCH` | Desplegar código y artefactos compatibles. |
| 422 | `VALIDATION_ERROR` | Corregir el contrato normalizado. |
| 503 | `SERVICE_NOT_CONFIGURED` | Configurar la credencial de inferencia. |
| 503 | `MODEL_NOT_READY` | Publicar artefactos confiables/implementación. |
| 500 | `INTERNAL_ERROR` | Correlacionar el identificador del error. |

## Ejemplo

```bash
curl --fail-with-body \
  -X POST "$MODELS_API_URL/v1/predictions/cash-balance" \
  -H "Authorization: Bearer $INFERENCE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"request_id":"25c00a42-822b-49a7-9c50-0fe913242977","as_of":"2026-09-13T00:00:00Z","currency":"MXN","current_balance":15420.75,"horizon_days":30,"transactions":[],"scheduled_cash_flows":[]}'
```

```python
from datetime import datetime
from uuid import UUID

import httpx


async def forecast_cash_balance(
    base_url: str,
    inference_api_key: str,
    request_id: UUID,
    as_of: datetime,
    current_balance: float,
) -> dict[str, object]:
    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
        response = await client.post(
            "/v1/predictions/cash-balance",
            headers={"Authorization": f"Bearer {inference_api_key}"},
            json={
                "request_id": str(request_id),
                "as_of": as_of.isoformat(),
                "currency": "MXN",
                "current_balance": current_balance,
                "horizon_days": 30,
                "transactions": [],
                "scheduled_cash_flows": [],
            },
        )
        response.raise_for_status()
        return response.json()
```

El consumidor no debe registrar la credencial ni cuerpos financieros completos.
