# Plan: ETH solo, alcista+lateral, capital $20, monto fijo $5

Fecha: 2026-08-13  
Estado: PLAN — ningún cambio aplicado todavía

---

## Objetivo

Configurar el bot para que opere **solo ETHUSDT**, solo fases **ALCISTA y LATERAL**,
bajista completamente desactivado, con capital base de **$20** y monto fijo de **$5 por trade**.

---

## Archivos a tocar (5 en total)

---

### 1. `config_cartera.py`

**Cambio A — línea 20: capital base**
```python
# ANTES
CAPITAL_BASE = 1000.0

# DESPUÉS
CAPITAL_BASE = 20.0
```

**Cambio B — líneas 11-17: pesos de cartera**

Dejar solo ETH al 100%. Los otros 4 símbolos quedan con peso 0 o se eliminan.
```python
# ANTES
PESOS_CARTERA = {
    "BTCUSDT":  21.68,
    "ETHUSDT":  18.97,
    "SOLUSDT":  23.85,
    "BNBUSDT":  18.97,
    "AVAXUSDT": 16.53,
}

# DESPUÉS
PESOS_CARTERA = {
    "ETHUSDT": 100.0,
}
```

> **Nota:** este cambio es solo documental — ningún francotirador lee `PESOS_CARTERA` para
> calcular el monto. Cada francotirador hace `capital * CAPITAL_MAX_POR_OP`. Lo importante
> es el cambio C de abajo y el cambio en los francotiradores.

**Cambio C — línea 23: porcentaje por operación**

Con `capital = $20` y `CAPITAL_MAX_POR_OP = 0.02`: el monto sería `$0.40` → rechazado por
Binance (mínimo $5). La opción más limpia es imponer el monto fijo directamente en los
francotiradores (ver sección 4 y 5), no aquí. Pero si se prefiere mantener la fórmula
porcentual, habría que subir a `0.25` (25% de $20 = $5) con el riesgo de que el factor
de memoria (0.6 min) lo baje a $3 → también rechazado.

**Decisión recomendada: monto fijo $5 directamente en los francotiradores (sección 4 y 5),
no tocar `CAPITAL_MAX_POR_OP` en este archivo.**

---

### 2. `director_eth.py`

**Cambio A — línea 13: eliminar el import del bajista**
```python
# ANTES
from francotirador_bajista_eth import evaluar as evaluar_bajista

# DESPUÉS
# (línea eliminada)
```

**Cambio B — líneas 51-53: bloque BAJISTA**
```python
# ANTES
elif fase == "BAJISTA":
    print(f"  🔻 Activando FRANCOTIRADOR BAJISTA ETH")
    evaluar_bajista()

# DESPUÉS
elif fase == "BAJISTA":
    print(f"  ⏸️ BAJISTA desactivado — solo ALCISTA y LATERAL.")
```

> **Por qué:** el bajista ya tiene un gate en `gestor_bajistas.py` que lo frena si no hay
> saldo en Futuros (y hoy retorna `False` por el error 401 de la API key). Pero si en algún
> momento la API key tuviera permisos de futuros y se fondeara accidentalmente, el gate se
> abriría solo. Eliminar la llamada aquí es la garantía más fuerte.

---

### 3. `main.py` (no leído en esta sesión, pero necesario)

Para que el bot opere **solo** ETH hay que desactivar las llamadas a los otros 4 directores.
Antes de tocar este archivo, **leerlo primero** para ver cómo está estructurado el loop
principal y elegir la forma menos invasiva (comentar las llamadas a `dirigir_btc()`,
`dirigir_sol()`, `dirigir_bnb()`, `dirigir_avax()` o poner una lista de símbolos activos).

---

### 4. `francotirador_alcista_eth.py`

**Cambio — líneas 358-359 (dentro de `evaluar()`, bloque `if RSI_MIN <= rsi <= RSI_MAX`)**
```python
# ANTES
monto_base = capital * CAPITAL_MAX_POR_OP
monto_op   = round(monto_base * factor_mem, 2)

# DESPUÉS
monto_op = 5.0
```

> **Por qué $5 fijo y no porcentaje:** con $20 de capital y `CAPITAL_MAX_POR_OP = 0.02`
> el monto sería $0.40, muy por debajo del `MONTO_MINIMO_BINANCE = 5.0` de Binance
> → la orden es rechazada antes de salir. Si se sube el porcentaje a 0.25 para llegar a $5,
> el `factor_mem` (mínimo 0.6) lo bajaría a $3.00 → igual rechazada. El monto fijo es lo
> más simple y correcto para capital chico.

---

### 5. `francotirador_lateral_eth.py`

**Cambio — líneas 360-361 (dentro de `evaluar()`, bloque `if RSI_MIN <= rsi <= RSI_MAX`)**
```python
# ANTES
monto_base = capital * CAPITAL_MAX_POR_OP
monto_op   = round(monto_base * factor_mem, 2)

# DESPUÉS
monto_op = 5.0
```

> Mismo razonamiento que alcista. El `CAPITAL_MAX_POR_OP` en la línea 32 de este archivo
> ya se usa solo para `monto_base`; al reemplazar el bloque entero, puede quedar como está
> (no afecta nada).

---

## `francotirador_bajista_eth.py`

**No tocar.** El archivo queda intacto. El bajista ya tiene `if not bajistas_activos(): return`
en su `evaluar()` (línea 282-285). Como `director_eth.py` ya no lo va a llamar (cambio 2A/2B),
este archivo queda inerte de forma segura.

---

## Impacto en el guardián de riesgo

Con capital $20:
- **DD máximo 10%** = bloqueo al perder $2.00
- **Pérdida diaria máx 5%** = $1.00/día
- Con SL de 4.5% (ETH alcista) sobre $5 → pérdida máxima por trade: **$0.225**
- Necesitaría ~8-9 trades perdedores seguidos para disparar el DD del 10%
- Es razonable y seguro

---

## Impacto en `billetera.json`

Al pasar a REAL con $20, el archivo `signals/billetera.json` debe actualizarse a mano
para reflejar el saldo real: `{"USDT": 20.0, "BTC": 0, "ETH": 0, "SOL": 0, "BNB": 0, "AVAX": 0}`.
No es código — se edita el JSON directamente antes de iniciar.

---

## Orden de aplicación sugerido

1. Leer `main.py` para ver cómo desactivar los otros directores
2. Cambiar `config_cartera.py` (capital $20, pesos solo ETH)
3. Cambiar `director_eth.py` (eliminar import + bloque bajista)
4. Cambiar `francotirador_alcista_eth.py` (monto $5 fijo)
5. Cambiar `francotirador_lateral_eth.py` (monto $5 fijo)
6. Desactivar los otros directores en `main.py`
7. Actualizar `signals/billetera.json` con $20
8. Reiniciar `v2_main`

---

## Lo que NO cambia

- Parámetros RSI, SL, TP, EMA de ETH alcista y lateral → no se tocan
- Toda la lógica de SL/TP/BE/Trailing → no se toca
- Guardian de riesgo, limitador diario, filtros de horario/eventos → no se tocan
- `francotirador_bajista_eth.py` → queda intacto, solo no se llama
