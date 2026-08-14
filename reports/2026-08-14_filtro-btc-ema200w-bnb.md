# Backtest aislado — Filtro BTC/EMA200w para BNB ALCISTA

**SOLO INVESTIGACIÓN. Ningún archivo de producción fue modificado.**

## Parámetros del sistema base

| Parámetro | Valor |
|-----------|-------|
| Activo | BNBUSDT |
| Fase | ALCISTA |
| RSI (14) | 60–68 |
| SL | 4.5% |
| TP | 6.5% |
| Comisión | 0.1%/lado |
| Monto | $5/trade |
| Capital inicial por período | $20 |

---

## Metodología y anti look-ahead bias

### Cálculo de la EMA200 semanal de BTC

1. Se cargan todas las velas BTC 4H disponibles (18,677 velas, desde 2017).
2. Se agrupan por semana ISO (lunes 00:00 UTC → domingo 23:59 UTC).
3. El **cierre semanal** es el precio de cierre de la última vela 4H de esa semana.
4. Se calcula EMA(200) sobre la secuencia de cierres semanales (α = 2/201).
   La semilla es la media simple de las primeras 200 semanas.
5. **El resultado de la semana N se registra como disponible desde el lunes de la semana N+1.**
   Ninguna señal BNB 4H que ocurra DENTRO de la semana N puede ver el cierre de esa semana.

**Primera semana con EMA200w disponible:** `2021-06-14 00:00:00 UTC`
Señales BNB anteriores a esa fecha quedan automáticamente descartadas en los escenarios filtrados.

### Alineación vela 4H ↔ semana (sin look-ahead)

Para una vela BNB 4H que abre en tiempo T:
- Se toma el lunes de la semana ISO que contiene T.
- Se consulta `ema_por_lunes[ese_lunes]` → EMA calculada sobre la **semana anterior cerrada**.
- El precio de BTC se lee de la vela BTC 4H con el mismo timestamp (o el más reciente ≤ T).
- Tanto EMA como precio BTC son información pasada o contemporánea — sin look-ahead.

### Condición de filtro

| Escenario | Condición para operar |
|-----------|----------------------|
| SIN FILTRO | Cualquier RSI 60–68 válido |
| BTC SOBRE EMA200w | `precio_BTC > EMA200w` en el momento de la señal |
| BTC BAJO EMA200w | `precio_BTC < EMA200w` en el momento de la señal |

---

## Resultados por escenario

### Escenario 1: SIN FILTRO

| Período | Trades | WR | Expect/trade | PF | Capital final | DD máx |
|---------|--------|----|--------------|----|---------------|--------|
| Entrenamiento 2021–2023 | 164 (TP:78/SL:86) | 47.6% | $+0.0266 | 1.216 | $24.36 | 11.2% |
| Validación 2024 | 51 (TP:23/SL:28) | 45.1% | $+0.0130 | 1.101 | $20.67 ✅ | 5.7% |
| Validación 2025 | 37 (TP:18/SL:19) | 48.6% | $+0.0326 | 1.270 | $21.21 ✅ | 6.3% |
| Test 2026 ene–ago ⚠️ INSUF | 5 (TP:1/SL:4) | 20.0% | $−0.1250 | 0.335 | $19.38 ❌ | 4.6% |
| Validación 2024–2026 | 92 (TP:41/SL:51) | 44.6% | $+0.0101 | 1.078 | $20.93 ✅ | 9.8% |

---

### Escenario 2: BTC SOBRE EMA200w

| Período | Trades | WR | Expect/trade | PF | Capital final | DD máx |
|---------|--------|----|--------------|----|---------------|--------|
| Entrenamiento 2021–2023 | 79 (TP:32/SL:47) | 40.5% | $−0.0122 | 0.913 | $19.04 ❌ | 12.8% |
| Validación 2024 | 51 (TP:23/SL:28) | 45.1% | $+0.0130 | 1.101 | $20.67 ✅ | 5.7% |
| Validación 2025 | 37 (TP:18/SL:19) | 48.6% | $+0.0326 | 1.270 | $21.21 ✅ | 6.3% |
| Test 2026 ene–ago ⚠️ INSUF | 5 (TP:1/SL:4) | 20.0% | $−0.1250 | 0.335 | $19.38 ❌ | 4.6% |
| Validación 2024–2026 | 92 (TP:41/SL:51) | 44.6% | $+0.0101 | 1.078 | $20.93 ✅ | 9.8% |

**Señales descartadas por el filtro:**

| Período | Señales RSI válidas | Descartadas | % descartado |
|---------|-------------------|-------------|--------------|
| Entrenamiento 2021–2023 | 446 | 364 | **81.6%** |
| Validación 2024 | 53 | 0 | **0.0%** |
| Validación 2025 | 38 | 0 | **0.0%** |
| Test 2026 ene–ago | 7 | 1 | 14.3% |
| Validación 2024–2026 | 97 | 1 | 1.0% |

> **Hallazgo crítico:** el filtro descartó el 81.6% de señales en entrenamiento (2021-2023, período de bear market en BTC)
> pero **0% en 2024 y 2025**. BTC estuvo continuamente sobre su EMA200w durante todo el período de validación.
> El escenario "BTC SOBRE" es **idéntico** a SIN FILTRO en las ventanas de validación.

---

### Escenario 3: BTC BAJO EMA200w

| Período | Trades | WR | Expect/trade | PF | Capital final | DD máx |
|---------|--------|----|--------------|----|---------------|--------|
| Entrenamiento 2021–2023 | 32 (TP:18/SL:14) | 56.2% | $+0.0744 | 1.723 | $22.38 ✅ | 6.6% |
| Validación 2024 | **0** | — | — | — | — | — |
| Validación 2025 | **0** | — | — | — | — | — |
| Test 2026 ene–ago ⚠️ INSUF | **0** | — | — | — | — | — |
| Validación 2024–2026 | **0** | — | — | — | — | — |

**Señales descartadas por el filtro:**

| Período | Señales RSI válidas | Descartadas | % descartado |
|---------|-------------------|-------------|--------------|
| Entrenamiento 2021–2023 | 704 | 672 | 95.5% |
| Validación 2024 | 347 | 347 | **100.0%** |
| Validación 2025 | 287 | 287 | **100.0%** |
| Test 2026 ene–ago | 30 | 29 | 96.7% |
| Validación 2024–2026 | 667 | 666 | **99.9%** |

> **Hallazgo crítico:** BTC estuvo sobre su EMA200w el **100% del tiempo** en 2024 y 2025.
> El filtro "BTC BAJO" no generó **ningún trade** en las ventanas de validación — es imposible evaluarlo out-of-sample.

---

## Comparación vs SIN FILTRO — diferencias absolutas

*(Positivo = mejora. ΔDD negativo = menor drawdown = mejor.)*

### BTC SOBRE EMA200w vs SIN FILTRO

| Período | ΔPF | ΔExpect/trade | ΔWR | ΔDD |
|---------|-----|--------------|-----|-----|
| Entrenamiento 2021–2023 | −0.303 | −$0.0388 | −7.1 pp | +1.6 pp |
| Validación 2024 | **±0.000** | **±$0.0000** | **±0.0 pp** | **±0.0 pp** |
| Validación 2025 | **±0.000** | **±$0.0000** | **±0.0 pp** | **±0.0 pp** |
| Test 2026 ene–ago ⚠️ | ±0.000 | ±$0.0000 | ±0.0 pp | ±0.0 pp |
| Validación 2024–2026 | **±0.000** | **±$0.0000** | **±0.0 pp** | **±0.0 pp** |

### BTC BAJO EMA200w vs SIN FILTRO

| Período | ΔPF | ΔExpect/trade | ΔWR | ΔDD |
|---------|-----|--------------|-----|-----|
| Entrenamiento 2021–2023 | +0.508 | +$0.0478 | +8.7 pp | −4.6 pp |
| Validación 2024 | — (sin trades) | — | — | — |
| Validación 2025 | — (sin trades) | — | — | — |
| Test 2026 ene–ago ⚠️ | — (sin trades) | — | — | — |
| Validación 2024–2026 | — (sin trades) | — | — | — |

---

## Hallazgo central — invalidación del resultado anterior

En la sesión anterior (2026-08-13) se calculó que:
> *"BTC bajo EMA200w: 31 trades | WR 58.1% | PF 1.856"*

Este backtest confirma que **esos 31 trades eran 100% in-sample** (período 2021-2023, bear market de BTC).
No existían trades BAJO la EMA200w en el período de validación 2024-2025 porque BTC estuvo continuamente
sobre su EMA200w durante esos dos años completos. El resultado prometedor era un artefacto del régimen
de mercado del período de entrenamiento, no una propiedad estructural del sistema.

**El filtro BTC/EMA200w no puede validarse out-of-sample con los datos disponibles actualmente.**

---

## Análisis de estabilidad temporal — resumen

| Escenario | Ventanas val. válidas | Positivas | PF prom | Expect prom | Cap prom |
|-----------|-----------------------|-----------|---------|-------------|---------|
| SIN FILTRO | 3 (2024/2025/2024–2026) | 3/3 | 1.150 | $+0.0186 | $20.93 |
| BTC SOBRE EMA200w | 3 (idénticas) | 3/3 | 1.150 | $+0.0186 | $20.93 |
| BTC BAJO EMA200w | **0** (sin trades) | — | — | — | — |

---

## Conclusión técnica y veredictos

### BTC SOBRE EMA200w
⚪ **C) No aporta mejora**

El filtro es **neutral**: produce exactamente los mismos resultados que SIN FILTRO en las ventanas
de validación (ΔPF = 0.000, ΔExpect = $0.0000). La razón es estructural: BTC estuvo sobre su
EMA200w el 100% del tiempo en 2024–2025, por lo que el filtro no discrimina ninguna señal.
En el período de entrenamiento (2021–2023, que incluye el bear market) el filtro **empeora**:
PF 0.913 vs 1.216 base — descartó las señales de la corrección (el régimen donde BNB sí funcionó).

Implementar este filtro solo añadiría complejidad sin beneficio medible.

### BTC BAJO EMA200w
⚠️ **Evidencia insuficiente — no evaluable out-of-sample**

El resultado de entrenamiento (WR 56.2%, PF 1.723, 32 trades) corresponde **exclusivamente**
al bear market de BTC de 2021–2023. En 2024 y 2025 no hubo ningún trade BAJO la EMA200w.
El hallazgo de la sesión anterior ("WR 58.1%, PF 1.856") era enteramente in-sample.

Para poder evaluar este escenario sería necesario:
- Esperar a que BTC vuelva a estar bajo su EMA200w y acumular suficientes señales (≥10 trades)
- O usar datos de otros activos/exchanges que hayan tenido correcciones profundas en 2024-2026

---

## Posibles sesgos y limitaciones

1. **Régimen único en validación:** 2024–2025 fue un bull market continuo. La EMA200w como filtro
   solo discrimina en regímenes mixtos o bajistas. Un backtest sobre un período exclusivamente alcista
   no puede evaluar la hipótesis de selección de régimen.

2. **Sin gates de producción:** El backtest no replica termómetro, spread, horario ni eventos macro.
   Las señales reales son un subconjunto de las aquí simuladas.

3. **Trailing stop no modelado:** El bot usa trailing (activación 0.5%, distancia 1%). El backtest
   usa TP/SL fijos — sobreestima ligeramente el TP.

4. **EMA200 semanal necesita 200 semanas:** La primera semana disponible es junio 2021. Señales
   anteriores no pueden ser filtradas → quedan descartadas automáticamente en escenarios filtrados.
   El entrenamiento 2021–2023 comienza efectivamente desde jun 2021, no ene 2021.

5. **Precio BTC contemporáneo:** El filtro usa el precio BTC del mismo timestamp 4H que la señal BNB.
   En producción esto es correcto (ambas velas se leen simultáneamente), pero introduce una correlación
   implícita entre movimientos BTC y BNB en la misma vela que el backtest no captura completamente.

---

## Recomendación final

- **No implementar el filtro BTC/EMA200w** con los datos disponibles actualmente.
  - El escenario SOBRE es redundante (no filtra nada en 2024–2025).
  - El escenario BAJO no tiene evidencia out-of-sample.
- El hallazgo prometedor de la sesión anterior queda **invalidado** — era in-sample.
- Si en el futuro BTC corrige profundamente (vuelve bajo su EMA200w durante varias semanas),
  acumular los trades de ese período y reevaluar el filtro BAJO con datos frescos.
- **Ningún cambio a `config_cartera.py` ni francotiradores.** Requiere OK explícito de Ariel.
