# LISTA MAESTRA DE INVESTIGACIONES PENDIENTES — Z-Bot Padre v2

**Creado:** 2026-08-31 · **Archivo permanente, versionado en git** (vive en la raíz junto a
`CLAUDE.md` e `INVESTIGACION.md`). Se actualiza a medida que se completan pruebas.
Complemento de `INDICE_RESULTADOS.md` (lo que YA se corrió, en la raíz del repo). Este archivo es lo
que FALTA correr. Detalle largo de cómo se armó:
`reports/2026-08-31_inventario-investigaciones-pendientes.md`.

---

# 🎯 OBJETIVO REAL DE ESTAS PRUEBAS — LEER ANTES DE CADA UNA

> **OBJETIVO REAL DE ESTAS PRUEBAS: no es solo encontrar una estrategia que no pierda dinero — es
> encontrar una que sea rentable de forma realista para el capital de Ariel, convertida siempre a
> pesos dominicanos (1 USDT = RD$62), con la meta de que el bot pueda cerrar el mes completo con una
> ganancia razonable. Cualquier resultado que solo diga "esto funciona mejor" sin traducirlo a
> cuánto significa eso en pesos dominicanos por mes, con el capital real de Ariel, está incompleto.**

**Esto no es un preámbulo: es criterio de aceptación.** Una prueba sin la traducción a RD$/mes está
**incompleta** y no se da por cerrada. Cada ficha de abajo repite el recordatorio en su propia línea
"Traducción obligatoria", porque el riesgo es justamente olvidarlo en la prueba número 5.

**Datos de referencia para la conversión (actualizar cuando cambien):**

| Dato | Valor al 2026-08-31 |
|---|---|
| Capital real | **$37,21 USDT** = **RD$2.307** |
| Monto por operación | $10 BTC · $7 ETH/SOL/AVAX |
| Tipo de cambio fijado | **1 USDT = RD$62** |
| Frecuencia real observada | ~8 operaciones en 14 días |

**Ejemplo de traducción correcta:** *"PF 1,35 sobre 40 trades"* está incompleto. Completo es:
*"PF 1,35 → +$2,10 USDT/mes con el capital actual → **RD$130/mes**, con n=40"*. Y si el resultado es
RD$130/mes, hay que decirlo aunque suene poco: **el número honesto es el que sirve para decidir.**

---

# Orden de ejecución

## 1️⃣ Rompimientos de techo (segundo rompimiento)

- **Estado:** script **terminado y nunca corrido**. No existe reporte de resultados.
- **Script:** `investigacion/scripts/analizar_rompimientos_techo.py` (15,2 KB, 30-ago), con CLI:
  `--csv BTCUSDT_1d.csv --moneda BTC ...`
- **Datos:** ✅ listos — `data/super_base_datos_top20/*_1d_completo.csv`
- **Preparación:** 🟢 **la más lista de todas**
- **Tiempo:** ~1 h
- **Mide:** cuántas veces al año se toca un techo nuevo, cuántas "descansan" cerca sin desplomarse,
  y qué % de techos terminan rompiéndose.
- **Traducción obligatoria:** si el patrón sirve como señal, ¿cuántas operaciones extra al mes
  genera y cuánto suman en **RD$/mes** con $7-10 por trade?

## 2️⃣ Tiempo al año en cada fase ("qué tan dormido está el bot")

- **Estado:** cortado en el paso 1. El inventario de datos se hizo el 30-ago; el análisis
  **nunca se ejecutó** (quedó esperando OK y lo tapó el corte de luz).
- **Script:** ❌ no existe — hay que escribirlo aplicando `utils.detectar_fase()` sobre las velas.
- **Datos:** ✅ listos — 20 monedas × 4 timeframes hasta 2026-08-26
- **Preparación:** 🟢 datos completos y verificados
- **Tiempo:** 1-2 h
- **Por qué va segundo:** condiciona al #4. Si las monedas pasan la mayor parte del año en fases
  donde el bot no opera, el cuello de botella no es TP/SL sino cobertura de fases.
- **Traducción obligatoria:** ¿cuántos meses al año el bot está estructuralmente impedido de operar,
  y cuánto RD$/mes se deja de ganar por eso?

## 3️⃣ MFE/MAE — amplitud de ganancia por operación

- **Estado:** hay 1 reporte (`reports/2026-08-22_ventana-optima-mfe.md`) y **4 scripts posteriores
  sin documentar**: `investigacion/scripts/calcular_matriz_mfe_mae4.py` (26-ago), `investigacion/scripts/analizar_mfe_mae_actual.py`,
  `investigacion/scripts/analizar_mfe_mae_trades_reales.py`, `investigacion/scripts/analizar_movimiento_actual.py` (28-ago).
- **Preparación:** 🟡 scripts existen, falta consolidar en un resultado único
- **Tiempo:** ~2 h
- **Mide:** cuánto recorre a favor un trade antes de darse vuelta → dice si el TP está bien puesto.
- **Traducción obligatoria:** si el TP óptimo cambia, ¿cuántos RD$/mes más produce ese TP con la
  frecuencia real de operaciones?

## 4️⃣ Guía de optimización TP/SL completa

- **Estado:** existe solo **2 de 15 combinaciones** (ETH y BNB, solo ALCISTA,
  `reports/2026-08-13_optimizacion-walk-forward.md`). Falta el 87%.
- **Verificado:** **0 menciones de DOP** en los reportes de TP/SL existentes → la conversión nunca
  se hizo, y es justamente lo que pide el objetivo de arriba.
- **Script:** ❌ no existe uno que barra las 3 fases; puede partir del enfoque "evaluar() literal"
  de `sistema_c/`
- **Datos:** ✅ listos
- **Tiempo:** 3-5 h (el más pesado)
- **Ojo:** con 1-2 trades alcistas por mes por símbolo, muchas celdas quedarán con n<30. Fijar el
  criterio de aceptación **antes** de correr.
- **Traducción obligatoria:** la tabla final debe tener una columna **RD$/mes** por moneda y fase.
  Sin esa columna, la guía no está terminada.

## 5️⃣ Retest SOL con filtro de volatilidad k=2.0

- **Estado:** el estudio original **sí se hizo** (`reports/2026-08-24_sol-filtro-volatilidad-k-alto.md`).
  Veredicto: *"No implementable con la evidencia actual"*. k=2.0 mejora en las 8 métricas
  (PF 1,768 · Sharpe 1,704 · WR 60% · n=40) pero **el bootstrap nunca deja de cruzar cero** y el
  walk-forward mostró que depende de **una sola ventana excepcional**.
- **Script:** `sistema_c/volatilidad_filtro_entrada.py` ✅
- **Datos:** 🟡 llegan al 26-ago — hay que bajar los días faltantes primero
- **Tiempo:** 1,5-2 h
- **Expectativa honesta:** pocos días nuevos suman poquísimos trades a n=40; es improbable que muevan
  el bootstrap. Vale más como chequeo de no-degradación que como prueba capaz de aprobarlo.
- **Traducción obligatoria:** si alguna vez aprueba, ¿cuánto RD$/mes agrega sobre SOL sin filtro?

---

# Después (sin orden fijo)

## 6️⃣ Multi-timeframe out-of-sample
`investigacion/scripts/evaluar_multi_tf_oos.py` (8,4 KB), `investigacion/scripts/evaluar_multi_tf_oos_fechas.py`,
`investigacion/scripts/comparativa_francotiradores_tf.py`, `investigacion/scripts/simular_multi_tf.py` — todos del 26-ago, **sin reporte**.
¿Rinde mejor en 1h o 15m que en 4h? · ~2 h · **Traducción obligatoria: RD$/mes por timeframe.**

## 7️⃣ Duración del trade vs win rate
`investigacion/scripts/analisis_duracion_wr.py` pesa **44 bytes** (stub vacío); `investigacion/scripts/analisis_historico_duracion.py` sí tiene
contenido. La hipótesis de que "los trades cortos ganan más seguido" viene de `prueba_meta_100.py`,
donde era un **supuesto inventado, nunca medido**. · 2-3 h · **Traducción obligatoria: RD$/mes.**

## 8️⃣ Segunda lista Sistema C — XRP, LINK, UNI, NEAR, ADA
Scoreadas el 15-ago, **ninguna backtesteada**. Existen `sistema_c/xrp_sistema_c_prueba1.py` y
`link_sistema_c_prueba1.py` (empezadas); UNI, NEAR y ADA sin tocar. · 4-6 h con el rigor del
Sistema C (OOS + walk-forward + bootstrap) · **Traducción obligatoria: RD$/mes por moneda nueva.**

## 9️⃣ Scripts sueltos de gates (decidir si vale rescatarlos)
`investigacion/scripts/auditar_clean_targets_btc.py`, `investigacion/scripts/gate_maestro_definitivo.py`, `investigacion/scripts/gate_cuantico_pro_v2.py`,
`investigacion/scripts/gate_confianza_pro.py`, ~20 `test_*_btc.py` (donchian, rvol, squeeze, pullback). Exploraciones sin
reporte. Decidir cuáles merecen tiempo **antes** de invertirlo.

---

# Advertencia metodológica común

Los ítems 3, 4, 5, 6, 7 y 8 comparten el riesgo que ya invalidó varios hallazgos de esta serie:
**muestras chicas**. Con 1-2 trades por mes por símbolo, casi cualquier corte por fase/moneda cae
bajo n=30. Fijar el criterio de aceptación (n mínimo, bootstrap, walk-forward) **antes** de correr,
para no interpretar ruido — es lo que pasó con SOL k=2.0 y con el "WR 100%" de ETH.

Los ítems **1 y 2 no tienen ese problema**: son mediciones descriptivas sobre miles de velas, no
inferencias sobre trades.

---

# Archivos relacionados

| Archivo | Qué contiene |
|---|---|
| `INDICE_RESULTADOS.md` (raíz) | Todas las pruebas **ya corridas**, con métricas y veredicto |
| `INVESTIGACION.md` (raíz) | Historial largo de investigación y backtests |
| `reports/2026-08-31_inventario-investigaciones-pendientes.md` | Cómo se armó esta lista, con la evidencia de cada estado |
| `CLAUDE.md` (raíz) | Reglas del proyecto, incluido el umbral PF ≥ 1,6 y qué NO tocar |
