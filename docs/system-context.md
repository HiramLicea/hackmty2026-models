# Contexto del sistema

## Responsabilidad

`hackmty2026-models` calcula predicciones y devuelve JSON de dominio. No conversa con el usuario, no
elige componentes concretos, no genera árboles A2UI y no contiene código del frontend.

Flujo objetivo:

```text
Expo / React Native
  -> agente conversacional (autentica y verifica identidad)
  -> herramientas MCP
  -> hackmty2026-models
  -> Supabase
```

La respuesta vuelve por las mismas capas. El agente redacta el texto y transforma el resultado y su
`visualization_hint` en una superficie A2UI.

## Hallazgos confirmados en el móvil

La revisión de solo lectura de `HackMTY2026_Mobile` confirmó:

- Expo SDK 57, React Native 0.86, Expo Router y TypeScript.
- Supabase JS se configura con variables `EXPO_PUBLIC_*` y una llave pública. En el móvil se utiliza
  para Auth y edición de metadatos del perfil, no para consultar tablas financieras.
- Antes de cada consulta, el cliente recupera la sesión, llama `auth.getUser(access_token)`, rechaza
  usuarios anónimos/no confirmados y comprueba que el UUID verificado coincide con el usuario activo.
- El móvil envía `POST /api/v1/agent/chat`, cuerpo `{query, user_id}` y el access token en el header
  `Authorization`. Sólo admite un origen HTTPS para el agente.
- El transporte de respuesta actual es estricto: `{message, data, a2ui}`. `data` debe ser JSON; el
  móvil actualmente lo valida pero no lo conserva ni lo presenta.
- El cliente procesa exclusivamente A2UI `v0.9.1`. Permite los catálogos Basic oficial y Finance
  v1 propio. Por red, los adaptadores implementados son `Text`, `Button`, `Card`, `Column` y `Chart`;
  `Chart` admite únicamente `area` y `heatmap`.
- El móvil nunca resuelve una URI MCP ni se conecta directamente al MCP. El agente resuelve recursos
  y entrega los mensajes A2UI ordenados.

## Diferencias frente al contexto inicial

1. La documentación móvil describe hoy `app -> agente -> MCP -> Supabase`; el servicio de modelos es
   una extensión nueva entre MCP y Supabase.
2. Componentes como `Page`, `Grid`, `AccountBalanceCard`, `TransactionList`, `ProgressBar` y otros sí
   existen o están planeados en la biblioteca local, pero no son actualmente componentes aceptados
   por el contrato A2UI de red.
3. El repositorio móvil no contiene DDL, tipos Supabase generados ni consultas a tablas financieras.
   En consecuencia, no permite verificar nombres de columnas, nulabilidad, claves o relaciones de
   esas tablas.
4. Aunque el móvil transmite `user_id`, ese campo por sí solo no autentica. La verificación debe
   mantenerse en el agente/MCP y este servicio sólo debe ser alcanzable por callers internos de
   confianza.

## Límites de esta fase

- Único endpoint público implementado: `GET /health`.
- Los cuatro servicios predictivos son placeholders tipados y producen un error explícito si se
  invocan.
- No hay cliente Supabase, repositorios de datos, entrenamiento, artefactos joblib, fixtures
  financieros, A2UI ni herramientas MCP.

