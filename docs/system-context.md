# Contexto del motor de inferencia

## Responsabilidad

`hackmty2026-models` es un proceso stateless con una única frontera externa: HTTP entrante. Recibe
datos financieros normalizados, valida sus invariantes, carga pipelines confiables y devuelve JSON de
dominio. No abre conexiones de red salientes.

```text
Consumidor confiable
  -> autentica y autoriza
  -> obtiene y minimiza datos financieros
  -> normaliza registros
  -> HTTPS + Bearer INFERENCE_API_KEY
  -> hackmty2026-models
  -> pipeline serializado
  -> resultado financiero estructurado
```

## Límites de confianza

El consumidor externo es responsable de identidad, sesiones, ownership, acceso a bases de datos y
presentación. El motor no acepta identificadores de usuario, correos, nombres completos, tokens de
sesión ni credenciales de infraestructura. Los identificadores de transacciones, flujos y metas son
opacos y sólo sirven para correlacionar entradas con resultados.

La autenticación Bearer identifica a un servicio consumidor confiable, no a una persona. El cuerpo
normalizado sigue siendo no confiable y pasa por contratos Pydantic estrictos.

## Preprocesamiento e inferencia

La frontera HTTP normaliza direcciones, moneda y timestamps, aplica signos y valida orden/cutoff sin
reordenar ni mutar el request. Entrenamiento e inferencia importan los mismos feature builders; los
preprocesadores ajustados se serializan y se reutilizan sin volver a ajustarlos.

No se entrena durante build, startup o solicitudes. Los artefactos se leen desde un directorio
controlado, se verifican contra el manifest y se almacenan en caché sólo como optimización de una
instancia caliente.

## Estado actual

Los cuatro servicios ejecutan inferencia real. Sin manifest compatible, un archivo faltante o un
hash inválido, las rutas responden `503 MODEL_NOT_READY` y `/ready` responde HTTP 503.

El dataset local es completamente sintético y reproducible. Cada perfil se divide cronológicamente
70/15/15. La etiqueta sintética de anomalía vive fuera de las transacciones y sólo calcula métricas;
Isolation Forest se ajusta sin labels. Las limitaciones de generalización se incluyen en el manifest
y en cada respuesta.
