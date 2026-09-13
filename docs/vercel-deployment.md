# Despliegue en Vercel

## Runtime y entrypoint

El proyecto usa Python 3.12 mediante `requires-python = ">=3.12,<3.13"`, `.python-version` y la imagen
Docker 3.12. `app/main.py` exporta `app` y `pyproject.toml` conserva:

```toml
[tool.vercel]
entrypoint = "app.main:app"
```

Vercel detecta FastAPI sin configuración legacy y crea una sola Function. No se requiere
`vercel.json` mientras no sea necesario excluir archivos o cambiar duración.

Referencias oficiales:

- <https://vercel.com/docs/frameworks/backend/fastapi>
- <https://vercel.com/docs/functions/runtimes/python>
- <https://vercel.com/docs/functions/limitations>

## Variables

```env
APP_ENV=production
LOG_LEVEL=INFO
DOCS_ENABLED=true
INFERENCE_API_KEY=
MODEL_ARTIFACT_DIR=artifacts
MODEL_MANIFEST_PATH=artifacts/manifest.json
```

La credencial es server-side. Para deshabilitar Swagger, ReDoc y OpenAPI en producción se configura
`DOCS_ENABLED=false`.

## Artefactos y readiness

El manifest `manifest_version: "1"` declara los cuatro modelos y el contrato de entrada. Cada
entrada enumera archivos relativos, formato, tamaño, SHA-256, versión, `trained_until`, features,
métricas y limitaciones. La raíz registra Python/librerías, seed, fecha y fingerprint del dataset.
Readiness valida configuración, manifest, rutas, versiones, existencia, hashes y deserialización de
todos los modelos sin abrir conexiones externas. Responde HTTP 503 mientras falte cualquier pieza.

Joblib usa pickle: sólo se deben desplegar artefactos creados por un pipeline controlado. El hash
detecta corrupción, pero no hace confiable un pickle desconocido.

## Flujo de despliegue manual

Mediante GitHub: importar el repositorio, conservar detección automática, configurar variables por
ambiente, verificar primero Preview y promover el deployment validado.

Mediante CLI:

```bash
vercel link
vercel build
vercel deploy --prebuilt
vercel deploy --prod --prebuilt
```

Estos comandos son instrucciones para el operador. El repositorio no inicia sesión ni despliega por
sí mismo.

## Verificación

```bash
curl --fail-with-body "$MODELS_API_URL/health"
curl --fail-with-body "$MODELS_API_URL/ready"
python scripts/smoke_test.py
```

El smoke test toma `MODELS_API_URL` e `INFERENCE_API_KEY` del ambiente y nunca imprime la llave. Una
respuesta autenticada debe ser HTTP 200 después de ejecutar `python scripts/train_all.py --seed
2026` y empaquetar `artifacts/` junto con la aplicación.

## Logs, rollback y límites

Buscar incidentes por `request_id` en los logs del deployment, sin copiar headers ni cuerpos. Para
rollback, promover el último deployment verificado que contenga código, manifest y artefactos
compatibles; repetir después health, readiness y smoke test.

El límite estándar documentado del bundle Python es 500 MB sin comprimir y el payload máximo es 4.5
MB. Ejecutar `python scripts/estimate_bundle_size.py` con el entorno de producción. El filesystem y
la memoria son efímeros: no entrenar ni escribir artefactos durante build, startup o solicitudes.
