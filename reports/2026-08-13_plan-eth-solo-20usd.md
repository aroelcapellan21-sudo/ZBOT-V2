# Plan: Bot solo ETH, $20 capital, $5 fijo por trade

Análisis realizado el 2026-08-13. Archivos leídos: `config_cartera.py`,
`director_eth.py`, `francotirador_alcista_eth.py`, `francotirador_lateral_eth.py`,
`francotirador_bajista_eth.py`, `director_orquesta.py` (parcial).

---

## Objetivo

Configurar el bot para que opere **exclusivamente** ETH/USDT, solo fases
ALCISTA y LATERAL, bajistas desactivados, capital base $20 y monto fijo
$5 por trade.

---

## Resumen ejecutivo

Son **4 archivos** con cambios reales de código y **1 archivo de estado**
(billetera.json) que se ajusta al momento de activar REAL. Nada en los
francotiradores bajista o en director_eth.py requiere toque: ya están
protegidos por sus propios gates.

---

## Cambio 1 — `director_orquesta.py`

**Objetivo:** que solo se llame al director de ETH en cada ciclo.

Este archivo es el que llama a los 5 directors. Hay 3 ramas (ALCISTA,
BAJISTA, LATERAL) y en cada una se llaman los 5 directors en secuencia.

### Líneas a comentar — imports (tope del archivo)
```
línea 18:  from director_btc  import dirigir as dirigir_btc   # ← COMENTAR
línea 19:  from director_eth  import dirigir as dirigir_eth   # ← DEJAR
línea 20:  from director_sol  import dirigir as dirigir_sol   # ← COMENTAR
línea 21:  from director_bnb  import dirigir as dirigir_bnb   # ← COMENTAR
línea 22:  from director_avax import dirigir as dirigir_avax  # ← COMENTAR
```

### Líneas a comentar — rama ALCISTA (~líneas 248-252)
```python
# DEJAR:
dirigir_eth("ALCISTA")
# COMENTAR:
# dirigir_btc("ALCISTA")
# dirigir_sol("ALCISTA")
# dirigir_bnb("ALCISTA")
# dirigir_avax("ALCISTA")
```

### Líneas a comentar — rama BAJISTA (~líneas 256-260)
```python
# DEJAR (aunque bajista está gateado internamente, no llamarlo es más limpio):
dirigir_eth("BAJISTA")
# COMENTAR:
# dirigir_btc("BAJISTA")
# dirigir_sol("BAJISTA")
# dirigir_bnb("BAJISTA")
# dirigir_avax("BAJISTA")
```

### Líneas a comentar — rama LATERAL (~líneas 264-268)
```python
# DEJAR:
dirigir_eth("LATERAL")
# COMENTAR:
# dirigir_btc("LATERAL")
# dirigir_sol("LATERAL")
# dirigir_bnb("LATERAL")
# dirigir_avax("LATERAL")
```

**Por qué no tocar `MONEDAS = [...]` (línea 31):** esa lista la usa
`cerrar_huerfanas()` para vigilar posiciones abiertas de todos los activos.
Si cambiamos a solo `["ETHUSDT"]`, las posiciones huérfanas de BTC/SOL/BNB/AVAX
que pueda haber del periodo de simulador **nunca se cerrarían**. Se deja la
lista como está; solo se cortan las llamadas a los directors.

---

## Cambio 2 — `config_cartera.py`

**Objetivo:** documentar el capital real del bot.

```
línea 20:  CAPITAL_BASE = 1000.0  →  CAPITAL_BASE = 20.0
```

Nota: este valor es **referencial**. El capital operativo real vive en
`signals/billetera.json`. Este cambio actualiza el número que aparece en
los prints de diagnóstico y en `capital_por_moneda()`, pero no afecta
directamente cuánto se invierte por trade (eso lo controlan los francotiradores).

---

## Cambio 3 — `francotirador_alcista_eth.py`

**El problema central:** con $20 de capital, el cálculo actual produce montos
inoperables.

El código actual (líneas 358-359):
```python
monto_base = capital * CAPITAL_MAX_POR_OP   # $20 * 0.02 = $0.40
monto_op   = round(monto_base * factor_mem, 2)  # $0.40 * 0.6~1.0 = $0.24–$0.40
```

$0.40 está muy por debajo del mínimo de Binance ($5 de notional). La orden
sería rechazada con error `-1013` (filter failure) y la posición quedaría
en estado `ANULADA` sin operación.

**El fix:** reemplazar las 2 líneas de cálculo por un monto fijo.

```python
# ANTES (líneas 358-359):
monto_base = capital * CAPITAL_MAX_POR_OP
monto_op   = round(monto_base * factor_mem, 2)

# DESPUÉS:
monto_op = 5.0
```

**Efecto secundario del factor_mem:** al fijar el monto en $5, el factor
de memoria (0.6–1.0) deja de aplicarse. Esto significa que el módulo
`puede_operar_memoria()` todavía bloquea o permite la entrada, pero ya no
reduce el monto cuando el WR histórico es bajo. Con solo 32 trades y ningún
símbolo llegando a `MIN_TRADES=15`, el factor hoy siempre es 1.0, así que
en la práctica no hay diferencia.

---

## Cambio 4 — `francotirador_lateral_eth.py`

Exactamente el mismo problema y la misma solución que el alcista.

```python
# ANTES (líneas 360-361):
monto_base = capital * CAPITAL_MAX_POR_OP
monto_op   = round(monto_base * factor_mem, 2)

# DESPUÉS:
monto_op = 5.0
```

---

## Sin cambio — `francotirador_bajista_eth.py`

El bajista ya está desactivado en la primera línea de `evaluar()` (línea 283):
```python
if not bajistas_activos():
    print("  ⏸️ Bajistas desactivados...")
    return
```

`bajistas_activos()` devuelve `False` porque no hay `BOT_BAJISTAS_CONFIRMADO=true`
en el entorno y tampoco saldo en futuros USDT-M. No hay nada que tocar aquí.

---

## Sin cambio — `director_eth.py`

El director llama a `evaluar_bajista()` cuando la fase es BAJISTA, pero
como el francotirador bajista retorna inmediatamente por el gate anterior,
es inocuo. Se podría comentar la llamada por claridad, pero no es necesario
para la seguridad del bot.

---

## Sin cambio — `guardian_riesgo.py`

Los umbrales son proporcionales y funcionan bien con $20:
- DD máximo 10% → bloqueo si el capital cae de $20 a menos de $18
- Pérdida diaria 5% → bloqueo si pierde más de $1 en el día

Con una sola posición de $5, el peor SL posible es -4.5% de $5 = -$0.225,
que es el 1.1% del capital. El guardián nunca se dispararía por un solo
trade — lo cual es correcto.

---

## Ajuste de estado (no es código) — `signals/billetera.json`

Al momento de activar REAL, inicializar manualmente:
```json
{
  "USDT": 20.0,
  "capital_inicial": 20.0,
  "BTC": 0.0,
  "ETH": 0.0,
  "SOL": 0.0,
  "BNB": 0.0,
  "AVAX": 0.0,
  "ultima_actualizacion": "2026-08-13"
}
```

El guardián toma `capital_maximo_historico` de `estado_riesgo` en la DB.
Si no existe, lo inicializa al capital actual en ese momento. Nada especial
que hacer ahí.

---

## Resumen de todos los cambios

| Archivo | Líneas | Qué cambia |
|---|---|---|
| `director_orquesta.py` | 18,20,21,22 + 6 llamadas en 3 ramas | Comentar los 4 directors no-ETH |
| `config_cartera.py` | 20 | `CAPITAL_BASE` 1000 → 20 |
| `francotirador_alcista_eth.py` | 358-359 | Monto fijo $5 (reemplaza % de capital) |
| `francotirador_lateral_eth.py` | 360-361 | Monto fijo $5 (reemplaza % de capital) |
| `francotirador_bajista_eth.py` | ninguna | Ya desactivado |
| `director_eth.py` | ninguna | Sin cambio necesario |
| `signals/billetera.json` | todo | Inicializar con $20 USDT (manual, al activar REAL) |

**Total: 4 archivos de código, ~14 líneas modificadas.**

---

## Orden recomendado de aplicación

1. Esperar "Ciclo completado" en v2_main + verificar que no haya filas RESERVADA en auditoria.csv
2. Aplicar los 4 cambios de código
3. Commitear y pushear
4. Reiniciar v2_main (esperar que levante y confirmar primer ciclo en el log)
5. Al activar REAL: ajustar billetera.json + exportar `BOT_REAL_CONFIRMADO=true`

---

## Riesgo residual

Con monto fijo $5 y un solo activo (ETH), el bot tendrá como máximo 1 posición
abierta a la vez (MAX_OP_TOTAL=1). Si el trade va mal, el SL máximo es -4.5%
de $5 = -$0.225 más comisión (0.2% round-trip ≈ $0.01). Desde $20 de capital,
se necesitarían ~44 SL seguidos para tocar el DD máximo del 10%.
