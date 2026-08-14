# Optimización walk-forward — ETH y BNB ALCISTA

**Metodología:** grid search sobre RSI_MIN, RSI_MAX, SL%, TP%.  
**Entrenamiento:** 2021–2023 (3 años).  
**Validación:** 2024–2025 (2 años, datos no vistos).  
**Métrica de optimización:** expectancy/trade máxima, con filtro PF ≥ 1.0 y WR ≥ 40%.  
**Mínimo trades para ser válido:** 15.  
**Comisión:** 0.1% por lado. **Monto:** $5/trade. **Capital inicial:** $20.

**Espacio de búsqueda:**
- RSI_MIN: [50, 55, 60, 65]
- RSI_MAX: [68, 72, 75, 78, 82]
- SL: [3.0, 3.5, 4.0, 4.5, 5.0]%
- TP: [4.0, 4.5, 5.0, 5.5, 6.0, 6.5, 7.0]%

---

## ETHUSDT

### Parámetros actuales en producción

RSI 60–75 | SL 4.5% | TP 5.0%

| Período | WR | Expect/trade | PF | Capital final | DD máx | Trades |
|---------|----|--------------|----|---------------|--------|--------|
| Entrenamiento 2021–2023 | 51.2% | $+0.0080 | 1.070 | $21.73 | 11.1% | 215 |
| Validación 2024–2025 | 45.6% | $-0.0184 | 0.856 | $17.70 | 23.3% | 125 |

### Parámetros optimizados (entrenamiento 2021–2023)

RSI 60–72 | SL 5.0% | TP 7.0%

| Período | WR | Expect/trade | PF | Capital final | DD máx | Trades |
|---------|----|--------------|----|---------------|--------|--------|
| Entrenamiento 2021–2023 | 49.7% | $+0.0382 | 1.292 | $26.38 | 8.7% | 167 |
| **Validación 2024–2025** | 40.0% | $-0.0200 | 0.872 | $18.00 | 23.3% | 100 |

### Comparación directa — actuales vs optimizados

| Métrica | Actuales | Optimizados | Diferencia |
|---------|----------|-------------|------------|
| WR validación | 45.6% | 40.0% | -5.6% ❌ |
| Expect/trade validación | $-0.0184 | $-0.0200 | $-0.0016 ❌ |
| PF validación | 0.856 | 0.872 | 0.016 ✅ |
| Capital final validación | $17.70 | $18.00 | $0.30 ✅ |
| DD máx validación | 23.3% | 23.3% | 0.1% ❌ |

### Top 5 combinaciones en entrenamiento

| # | RSI | SL | TP | WR | Expect | PF | Trades | Capital |
|---|-----|----|----|----|--------|----|--------|---------|
| 1 | 60–72 | 5.0% | 7.0% | 49.7% | $+0.0382 | 1.292 | 167 | $26.38 (val: $18.00) |
| 2 | 60–75 | 5.0% | 7.0% | 49.1% | $+0.0348 | 1.263 | 173 | $26.02 (val: $19.28) |
| 3 | 65–75 | 4.5% | 7.0% | 46.6% | $+0.0327 | 1.261 | 131 | $24.29 (val: $21.90) |
| 4 | 65–72 | 4.5% | 7.0% | 46.3% | $+0.0315 | 1.250 | 123 | $23.87 (val: $20.88) |
| 5 | 60–75 | 4.5% | 7.0% | 46.2% | $+0.0306 | 1.242 | 184 | $25.64 (val: $19.11) |

---

## BNBUSDT

### Parámetros actuales en producción

RSI 60–75 | SL 4.5% | TP 5.0%

| Período | WR | Expect/trade | PF | Capital final | DD máx | Trades |
|---------|----|--------------|----|---------------|--------|--------|
| Entrenamiento 2021–2023 | 52.3% | $+0.0135 | 1.120 | $22.92 | 12.8% | 216 |
| Validación 2024–2025 | 52.3% | $+0.0132 | 1.118 | $21.47 | 13.0% | 111 |

### Parámetros optimizados (entrenamiento 2021–2023)

RSI 60–68 | SL 4.5% | TP 6.5%

| Período | WR | Expect/trade | PF | Capital final | DD máx | Trades |
|---------|----|--------------|----|---------------|--------|--------|
| Entrenamiento 2021–2023 | 47.6% | $+0.0266 | 1.216 | $24.36 | 11.2% | 164 |
| **Validación 2024–2025** | 47.1% | $+0.0242 | 1.195 | $22.11 | 7.8% | 87 |

### Comparación directa — actuales vs optimizados

| Métrica | Actuales | Optimizados | Diferencia |
|---------|----------|-------------|------------|
| WR validación | 52.3% | 47.1% | -5.1% ❌ |
| Expect/trade validación | $+0.0132 | $+0.0242 | $+0.0110 ✅ |
| PF validación | 1.118 | 1.195 | 0.077 ✅ |
| Capital final validación | $21.47 | $22.11 | $0.64 ✅ |
| DD máx validación | 13.0% | 7.8% | -5.1% ✅ |

### Top 5 combinaciones en entrenamiento

| # | RSI | SL | TP | WR | Expect | PF | Trades | Capital |
|---|-----|----|----|----|--------|----|--------|---------|
| 1 | 60–68 | 4.5% | 6.5% | 47.6% | $+0.0266 | 1.216 | 164 | $24.36 (val: $22.11) |
| 2 | 60–78 | 4.5% | 7.0% | 45.5% | $+0.0264 | 1.206 | 176 | $24.64 (val: $21.75) |
| 3 | 60–68 | 5.0% | 6.5% | 49.7% | $+0.0257 | 1.197 | 161 | $24.14 (val: $21.99) |
| 4 | 60–68 | 4.0% | 6.5% | 44.9% | $+0.0257 | 1.222 | 176 | $24.51 (val: $21.89) |
| 5 | 60–68 | 4.5% | 7.0% | 45.2% | $+0.0250 | 1.194 | 157 | $23.93 (val: $21.80) |

---

## Notas metodológicas

- **Walk-forward estricto:** los parámetros se seleccionaron viendo SOLO los datos 2021–2023.
  Los datos 2024–2025 no se usaron para ninguna decisión de optimización.
- **Riesgo de overfitting:** el grid search puede encontrar parámetros que se ajustan bien al
  período de entrenamiento por azar. Si el resultado en validación es significativamente peor
  que en entrenamiento, es señal de overfitting.
- **Muestra pequeña por año:** ~1-2 trades alcistas por mes en algunos símbolos.
  Los resultados son indicativos, no concluyentes estadísticamente.
- **No implementar cambios sin OK de Ariel** — este análisis es evidencia, no una orden.
- El criterio de optimización fue expectancy máxima con filtros PF ≥ 1.0 y WR ≥ 40%.
  Otros criterios (PF máximo, capital final máximo) pueden dar parámetros distintos.