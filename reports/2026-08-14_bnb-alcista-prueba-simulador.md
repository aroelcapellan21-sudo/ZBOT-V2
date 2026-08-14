# Prueba controlada en SIMULADOR — BNB ALCISTA
## Producción vs Candidato experimental

---

## 1. Condiciones de la prueba

| Parámetro | Valor |
|-----------|-------|
| **Modo verificado** | `SIMULADOR` ✅ |
| Producción intacta | Sí — `config_cartera.py` sin modificar |
| Candidato es experimental | Sí — script aislado, tracking propio |
| Archivos de producción tocados | **Ninguno** |
| Fecha/hora de inicio | 2026-08-14 04:40:15 UTC |
| Período de observación | 2026-01-01 → 2026-08-14 |
| Fuente de datos | Binance API REST (datos reales) |
| Velas en período | 1350 × 4H |
| Símbolo | BNBUSDT |
| Comisión | 0.1%/lado |
| Monto por trade | $5.0 |
| Capital inicial (por sistema) | $20 |
| Mínimo trades para conclusión | 10 |

### Sistemas comparados

| Sistema | RSI | SL | TP | Rol |
|---------|-----|----|----|-----|
| Producción | 60–75 | 4.5% | 5.0% | Referencia (sin cambios) |
| Candidato  | 60–68 | 4.5% | 6.5% | Experimental (aislado) |

### Aislamiento garantizado

- El candidato corre en script independiente (`exp_bnb_candidato.py`).
- No escribe en `auditoria.csv`, `billetera.json` ni ningún archivo de producción.
- No modifica `config_cartera.py` ni ningún francotirador.
- Tracking propio en memoria, resultado solo en este reporte.

---

## 2. Resultados — Producción (RSI 60–75 / SL 4.5% / TP 5.0%)

| Métrica | Valor |
|---------|-------|
| Trades totales | 20 (TP: 8 / SL: 12) |
| Win Rate | 40.0% |
| Expectancy/trade | $-0.0450 |
| Profit Factor | 0.681 |
| Capital final | $19.10 ❌ |
| DD máximo | 8.0% |

**Detalle de trades:**

| # | Timestamp | RSI entrada | Precio entrada | Precio salida | Resultado | P/L neto |
|---|-----------|------------|---------------|---------------|-----------|----------|
| 1 | 2026-01-01 00:00:00 | 62.8 | $869.1600 | $912.6180 | TP | $+0.2400 |
| 2 | 2026-01-06 00:00:00 | 74.0 | $908.1400 | $953.5470 | TP | $+0.2400 |
| 3 | 2026-01-14 04:00:00 | 65.4 | $937.4500 | $895.2648 | SL | $-0.2350 |
| 4 | 2026-01-27 20:00:00 | 62.3 | $898.3600 | $857.9338 | SL | $-0.2350 |
| 5 | 2026-02-15 04:00:00 | 62.0 | $639.8600 | $611.0663 | SL | $-0.2350 |
| 6 | 2026-02-21 08:00:00 | 62.2 | $630.1800 | $601.8219 | SL | $-0.2350 |
| 7 | 2026-02-25 12:00:00 | 61.5 | $621.3800 | $593.4179 | SL | $-0.2350 |
| 8 | 2026-03-02 12:00:00 | 65.3 | $646.2500 | $617.1687 | SL | $-0.2350 |
| 9 | 2026-03-10 04:00:00 | 61.5 | $644.4800 | $676.7040 | TP | $+0.2400 |
| 10 | 2026-03-15 04:00:00 | 60.4 | $660.0200 | $630.3191 | SL | $-0.2350 |
| 11 | 2026-03-25 08:00:00 | 60.3 | $648.3600 | $619.1838 | SL | $-0.2350 |
| 12 | 2026-04-06 04:00:00 | 61.5 | $603.8000 | $633.9900 | TP | $+0.2400 |
| 13 | 2026-05-04 00:00:00 | 62.2 | $626.5700 | $657.8985 | TP | $+0.2400 |
| 14 | 2026-05-06 16:00:00 | 73.9 | $650.4500 | $682.9725 | TP | $+0.2400 |
| 15 | 2026-05-14 12:00:00 | 61.1 | $679.9800 | $649.3809 | SL | $-0.2350 |
| 16 | 2026-05-22 00:00:00 | 61.0 | $659.6100 | $629.9275 | SL | $-0.2350 |
| 17 | 2026-05-30 00:00:00 | 62.7 | $658.1900 | $691.0995 | TP | $+0.2400 |
| 18 | 2026-05-31 04:00:00 | 71.8 | $719.7100 | $687.3230 | SL | $-0.2350 |
| 19 | 2026-06-14 08:00:00 | 60.3 | $612.2600 | $584.7083 | SL | $-0.2350 |
| 20 | 2026-07-26 12:00:00 | 61.4 | $573.7900 | $602.4795 | TP | $+0.2400 |

---

## 3. Resultados — Candidato (RSI 60–68 / SL 4.5% / TP 6.5%)

| Métrica | Valor |
|---------|-------|
| Trades totales | 19 (TP: 6 / SL: 13) |
| Win Rate | 31.6% |
| Expectancy/trade | $-0.0613 |
| Profit Factor | 0.619 |
| Capital final | $18.84 ❌ |
| DD máximo | 8.8% |

**Detalle de trades:**

| # | Timestamp | RSI entrada | Precio entrada | Precio salida | Resultado | P/L neto |
|---|-----------|------------|---------------|---------------|-----------|----------|
| 1 | 2026-01-01 00:00:00 | 62.8 | $869.1600 | $925.6554 | TP | $+0.3150 |
| 2 | 2026-01-14 04:00:00 | 65.4 | $937.4500 | $895.2648 | SL | $-0.2350 |
| 3 | 2026-01-27 20:00:00 | 62.3 | $898.3600 | $857.9338 | SL | $-0.2350 |
| 4 | 2026-02-15 04:00:00 | 62.0 | $639.8600 | $611.0663 | SL | $-0.2350 |
| 5 | 2026-02-21 08:00:00 | 62.2 | $630.1800 | $601.8219 | SL | $-0.2350 |
| 6 | 2026-02-25 12:00:00 | 61.5 | $621.3800 | $593.4179 | SL | $-0.2350 |
| 7 | 2026-03-02 12:00:00 | 65.3 | $646.2500 | $617.1687 | SL | $-0.2350 |
| 8 | 2026-03-10 04:00:00 | 61.5 | $644.4800 | $686.3712 | TP | $+0.3150 |
| 9 | 2026-03-16 12:00:00 | 62.0 | $671.6700 | $641.4448 | SL | $-0.2350 |
| 10 | 2026-03-25 08:00:00 | 60.3 | $648.3600 | $619.1838 | SL | $-0.2350 |
| 11 | 2026-04-06 04:00:00 | 61.5 | $603.8000 | $643.0470 | TP | $+0.3150 |
| 12 | 2026-04-17 16:00:00 | 66.6 | $641.3600 | $612.4988 | SL | $-0.2350 |
| 13 | 2026-05-04 00:00:00 | 62.2 | $626.5700 | $667.2971 | TP | $+0.3150 |
| 14 | 2026-05-13 00:00:00 | 66.3 | $681.2800 | $650.6224 | SL | $-0.2350 |
| 15 | 2026-05-22 00:00:00 | 61.0 | $659.6100 | $629.9275 | SL | $-0.2350 |
| 16 | 2026-05-30 00:00:00 | 62.7 | $658.1900 | $700.9724 | TP | $+0.3150 |
| 17 | 2026-05-31 16:00:00 | 63.4 | $708.5500 | $676.6652 | SL | $-0.2350 |
| 18 | 2026-06-14 08:00:00 | 60.3 | $612.2600 | $584.7083 | SL | $-0.2350 |
| 19 | 2026-07-26 12:00:00 | 61.4 | $573.7900 | $611.0863 | TP | $+0.3150 |

---

## 4. Comparación directa

| Métrica | Producción | Candidato | Δ (Cand−Prod) |
|---------|-----------|-----------|---------------|
| Trades | 20 | 19 | -1 |
| TP | 8 | 6 | -2 |
| SL | 12 | 13 | +1 |
| Win Rate | 40.0% | 31.6% | -8.4 pp |
| Expectancy | $-0.0450 | $-0.0613 | $-0.0163 |
| PF | 0.681 | 0.619 | -0.062 |
| Capital final | $19.10 | $18.84 | $-0.27 |
| DD máximo | 8.0% | 8.8% | +0.8 pp |
| **Ganador** | | | **Producción** |

---

## 5. Limitaciones y notas

1. **Datos:** las velas descargadas de Binance API corresponden al período real de mercado.
   El candidato y producción operaron sobre **exactamente los mismos datos** — la comparación
   es justa en términos de información disponible.
2. **Simulación retrospectiva:** ambos sistemas se simulan sobre el período completo de una vez.
   En producción real, cada señal se evalúa al cierre de una vela 4H en tiempo real.
   La lógica es equivalente: una señal en la vela T solo usa datos ≤ T.
3. **Sin gates de producción:** esta prueba no replica el termómetro, spread, horario ni
   eventos macro del bot real. Las señales reales son un subconjunto de las aquí simuladas.
4. **Sin trailing stop:** se usa TP/SL fijo (misma simplificación que todos los backtests
   anteriores de esta sesión de investigación).
5. **Monto fijo $5:** la producción usa gestión de capital proporcional. Este simulador usa
   monto fijo por trade para aislar el efecto de los parámetros RSI/TP/SL.
6. **Aislamiento verificado:** el script no escribe en ningún archivo de producción.
   `auditoria.csv`, `billetera.json` y `config_cartera.py` permanecen intactos.

---

## 6. Conclusión de la prueba

Prueba ejecutada correctamente en modo **SIMULADOR**.
Período: 2026-01-01 → 2026-08-14 (1350 velas 4H).
**Ganador en el período:** Producción.
Producción: 20 trades · PF 0.681 · $19.10
Candidato:  19 trades · PF 0.619 · $18.84

Esta prueba es un punto de datos adicional en la investigación BNB ALCISTA.
No autoriza ningún cambio a producción — requiere OK explícito de Ariel.