# Contrato provisional de base de datos

Este documento distingue hechos proporcionados por el contexto del proyecto de hechos verificados
en código. Antes de implementar consultas se debe cotejar todo con DDL, migraciones o tipos generados
de la instancia real de Supabase.

## Tablas declaradas por el proyecto

`users`, `accounts`, `account_details`, `transactions`, `bank_statements`, `cards`,
`credit_card_terms`, `beneficiaries`, `budgets`, `debts`, `debt_scenarios`, `financial_alerts`,
`payment_orders`, `savings_goals`, `savings_contributions`, `scheduled_cash_flows`, `subscriptions`,
`transaction_disputes`, `transfers` y `accessibility_preferences`.

El móvil no incluye consultas financieras ni tipos generados, así que su existencia y forma no
pudieron verificarse desde ese repositorio.

## Convenciones aceptadas provisionalmente

### Propiedad y aislamiento

La propiedad de una transacción se resuelve mediante:

```text
transactions.account_id -> accounts.id -> accounts.user_id
```

Toda consulta futura debe filtrar por el `user_id` verificado. Un filtro directo sobre un campo no
confirmado de `transactions` no sustituye este join de propiedad.

### Signo de movimientos

`transactions.amount` es positivo y `transactions.direction` determina el signo:

```python
signed_amount = amount if direction == "credit" else -amount
```

Los agregados y series no deben sumar `amount` sin aplicar esta transformación.

### Saldos y metas

- `accounts.available_balance` representa el saldo disponible actual.
- El avance de una meta se deriva principalmente de la suma de `savings_contributions`.

### Datos incompletos

No se asume que `subscriptions` tenga siempre `account_id` o `currency`. La implementación debe
comprobar la nulabilidad y definir una estrategia explícita de moneda antes de incluir registros en
un cálculo.

## Datos requeridos por capacidad

| Capacidad | Tablas candidatas |
| --- | --- |
| Saldo futuro | `accounts`, `transactions`, `scheduled_cash_flows`, `subscriptions`, `bank_statements` |
| Meta de ahorro | `savings_goals`, `savings_contributions`, `accounts`, `transactions`, `scheduled_cash_flows` |
| Cargos recurrentes | `transactions`, `subscriptions`, `scheduled_cash_flows` |
| Anomalías | `transactions`, `accounts` |

## Pendientes antes del acceso a datos

- Confirmar columnas, tipos, claves foráneas, índices, nulabilidad y políticas RLS.
- Confirmar si `users.id` coincide con `auth.users.id` o existe otra relación.
- Confirmar timestamps, zona horaria y semántica de fechas de contabilización/autorización.
- Confirmar moneda por cuenta/transacción y reglas para múltiples monedas.
- Confirmar estados de transacciones (pendiente, contabilizada, cancelada, reversada).
- Confirmar semántica, frecuencia y estado de `scheduled_cash_flows` y `subscriptions`.
- Confirmar relación exacta entre `savings_goals` y `savings_contributions`.
- Definir qué saldo bancario es autoritativo cuando `bank_statements` y
  `accounts.available_balance` difieren.

