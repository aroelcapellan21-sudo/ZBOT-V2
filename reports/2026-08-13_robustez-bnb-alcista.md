# Análisis de robustez BNB ALCISTA — sensibilidad de parámetros

**Objetivo:** determinar si RSI 60–68 / SL 4.5% / TP 6.5% es un pico aislado o una zona robusta.  
**Metodología:** idéntica al walk-forward previo. Comisión 0.1%/lado, $5/trade, capital inicial $20.  
**Sin cambios a producción.** Solo investigación.

---

## Parte 1 — Sensibilidad de parámetros

Cada fila es una combinación independiente. Capital siempre parte de $20 por período.

### ACTUAL producción 🔵
RSI 60–75 | SL 4.5% | TP 5.0%

| Período | Trades | WR | Expect/trade | PF | Capital final | DD máx |
|---------|--------|----|--------------|----|---------------|--------|
| Train 2021–2023 | 216 (TP:113/SL:103) | 52.3% | $+0.0135 | 1.120 | $22.92 | 12.8% |
| Val 2024 | 62 (TP:31/SL:31) | 50.0% | $+0.0025 | 1.021 | $20.16 ✅ | 7.6% |
| Val 2025 | 49 (TP:27/SL:22) | 55.1% | $+0.0267 | 1.253 | $21.31 ✅ | 7.0% |
| Test 2026 ene–ago | 6 (TP:2/SL:4) | 33.3% | $-0.0767 | 0.511 | $19.54 ❌ | 4.6% |
| Val 2024–2026 combinado | 116 (TP:59/SL:57) | 50.9% | $+0.0066 | 1.057 | $20.77 ✅ | 13.0% |

### Vecino TP-6.0
RSI 60–68 | SL 4.5% | TP 6.0%

| Período | Trades | WR | Expect/trade | PF | Capital final | DD máx |
|---------|--------|----|--------------|----|---------------|--------|
| Train 2021–2023 | 174 (TP:82/SL:92) | 47.1% | $+0.0124 | 1.100 | $22.16 | 11.3% |
| Val 2024 | 55 (TP:25/SL:30) | 45.5% | $+0.0036 | 1.028 | $20.20 ✅ | 6.0% |
| Val 2025 | 38 (TP:19/SL:19) | 50.0% | $+0.0275 | 1.234 | $21.04 ✅ | 6.4% |
| Test 2026 ene–ago | 6 (TP:1/SL:5) | 16.7% | $-0.1475 | 0.247 | $19.12 ❌ | 5.8% |
| Val 2024–2026 combinado | 97 (TP:44/SL:53) | 45.4% | $+0.0031 | 1.024 | $20.30 ✅ | 10.2% |

### CANDIDATO 🟡
RSI 60–68 | SL 4.5% | TP 6.5%

| Período | Trades | WR | Expect/trade | PF | Capital final | DD máx |
|---------|--------|----|--------------|----|---------------|--------|
| Train 2021–2023 | 164 (TP:78/SL:86) | 47.6% | $+0.0266 | 1.216 | $24.36 | 11.2% |
| Val 2024 | 51 (TP:23/SL:28) | 45.1% | $+0.0130 | 1.101 | $20.67 ✅ | 5.7% |
| Val 2025 | 37 (TP:18/SL:19) | 48.6% | $+0.0326 | 1.270 | $21.21 ✅ | 6.3% |
| Test 2026 ene–ago | 5 (TP:1/SL:4) | 20.0% | $-0.1250 | 0.335 | $19.38 ❌ | 4.6% |
| Val 2024–2026 combinado | 92 (TP:41/SL:51) | 44.6% | $+0.0101 | 1.078 | $20.93 ✅ | 9.8% |

### Vecino TP-7.0
RSI 60–68 | SL 4.5% | TP 7.0%

| Período | Trades | WR | Expect/trade | PF | Capital final | DD máx |
|---------|--------|----|--------------|----|---------------|--------|
| Train 2021–2023 | 157 (TP:71/SL:86) | 45.2% | $+0.0250 | 1.194 | $23.93 | 11.5% |
| Val 2024 | 46 (TP:20/SL:26) | 43.5% | $+0.0150 | 1.113 | $20.69 ✅ | 5.5% |
| Val 2025 | 33 (TP:15/SL:18) | 45.5% | $+0.0264 | 1.206 | $20.87 ✅ | 6.4% |
| Test 2026 ene–ago | 5 (TP:1/SL:4) | 20.0% | $-0.1200 | 0.362 | $19.40 ❌ | 4.6% |
| Val 2024–2026 combinado | 83 (TP:35/SL:48) | 42.2% | $+0.0075 | 1.055 | $20.62 ✅ | 9.8% |

### Vecino RSI-max 72
RSI 60–72 | SL 4.5% | TP 6.5%

| Período | Trades | WR | Expect/trade | PF | Capital final | DD máx |
|---------|--------|----|--------------|----|---------------|--------|
| Train 2021–2023 | 177 (TP:82/SL:95) | 46.3% | $+0.0198 | 1.157 | $23.51 | 14.9% |
| Val 2024 | 52 (TP:23/SL:29) | 44.2% | $+0.0083 | 1.063 | $20.43 ✅ | 6.8% |
| Val 2025 | 39 (TP:18/SL:21) | 46.2% | $+0.0188 | 1.149 | $20.74 ✅ | 6.6% |
| Test 2026 ene–ago | 5 (TP:1/SL:4) | 20.0% | $-0.1250 | 0.335 | $19.38 ❌ | 4.6% |
| Val 2024–2026 combinado | 93 (TP:41/SL:52) | 44.1% | $+0.0075 | 1.057 | $20.70 ✅ | 11.8% |

### Vecino RSI-max 65
RSI 60–65 | SL 4.5% | TP 6.5%

| Período | Trades | WR | Expect/trade | PF | Capital final | DD máx |
|---------|--------|----|--------------|----|---------------|--------|
| Train 2021–2023 | 148 (TP:69/SL:79) | 46.6% | $+0.0214 | 1.171 | $23.17 | 9.7% |
| Val 2024 | 48 (TP:22/SL:26) | 45.8% | $+0.0171 | 1.134 | $20.82 ✅ | 7.0% |
| Val 2025 | 33 (TP:16/SL:17) | 48.5% | $+0.0317 | 1.262 | $21.05 ✅ | 6.4% |
| Test 2026 ene–ago | 5 (TP:1/SL:4) | 20.0% | $-0.1250 | 0.335 | $19.38 ❌ | 4.6% |
| Val 2024–2026 combinado | 85 (TP:38/SL:47) | 44.7% | $+0.0109 | 1.084 | $20.93 ✅ | 10.1% |

### Vecino SL-4.0
RSI 60–68 | SL 4.0% | TP 6.5%

| Período | Trades | WR | Expect/trade | PF | Capital final | DD máx |
|---------|--------|----|--------------|----|---------------|--------|
| Train 2021–2023 | 176 (TP:79/SL:97) | 44.9% | $+0.0257 | 1.222 | $24.51 | 11.5% |
| Val 2024 | 55 (TP:22/SL:33) | 40.0% | $-0.0000 | 1.000 | $20.00 ❌ | 6.5% |
| Val 2025 | 37 (TP:18/SL:19) | 48.6% | $+0.0454 | 1.421 | $21.68 ✅ | 5.6% |
| Test 2026 ene–ago | 5 (TP:1/SL:4) | 20.0% | $-0.1050 | 0.375 | $19.47 ❌ | 4.1% |
| Val 2024–2026 combinado | 96 (TP:40/SL:56) | 41.7% | $+0.0087 | 1.071 | $20.84 ✅ | 8.7% |

### Vecino SL-5.0
RSI 60–68 | SL 5.0% | TP 6.5%

| Período | Trades | WR | Expect/trade | PF | Capital final | DD máx |
|---------|--------|----|--------------|----|---------------|--------|
| Train 2021–2023 | 161 (TP:80/SL:81) | 49.7% | $+0.0257 | 1.197 | $24.14 | 11.1% |
| Val 2024 | 49 (TP:23/SL:26) | 46.9% | $+0.0099 | 1.072 | $20.48 ✅ | 6.6% |
| Val 2025 | 35 (TP:18/SL:17) | 51.4% | $+0.0357 | 1.283 | $21.25 ✅ | 6.9% |
| Test 2026 ene–ago | 5 (TP:1/SL:4) | 20.0% | $-0.1450 | 0.303 | $19.27 ❌ | 5.1% |
| Val 2024–2026 combinado | 87 (TP:41/SL:46) | 47.1% | $+0.0110 | 1.080 | $20.95 ✅ | 9.8% |

### Vecino RSI-min 55
RSI 55–68 | SL 4.5% | TP 6.5%

| Período | Trades | WR | Expect/trade | PF | Capital final | DD máx |
|---------|--------|----|--------------|----|---------------|--------|
| Train 2021–2023 | 223 (TP:103/SL:120) | 46.2% | $+0.0190 | 1.151 | $24.25 | 11.0% |
| Val 2024 | 60 (TP:25/SL:35) | 41.7% | $-0.0058 | 0.957 | $19.65 ❌ | 6.7% |
| Val 2025 | 45 (TP:20/SL:25) | 44.4% | $+0.0094 | 1.072 | $20.43 ✅ | 7.4% |
| Test 2026 ene–ago | 4 (TP:1/SL:3) | 25.0% | $-0.0975 | 0.447 | $19.61 ❌ | 3.5% |
| Val 2024–2026 combinado | 107 (TP:45/SL:62) | 42.1% | $-0.0037 | 0.973 | $19.61 ❌ | 12.6% |

### Vecino RSI-min 65
RSI 65–68 | SL 4.5% | TP 6.5%

| Período | Trades | WR | Expect/trade | PF | Capital final | DD máx |
|---------|--------|----|--------------|----|---------------|--------|
| Train 2021–2023 | 102 (TP:47/SL:55) | 46.1% | $+0.0184 | 1.145 | $21.88 | 8.3% |
| Val 2024 | 31 (TP:16/SL:15) | 51.6% | $+0.0489 | 1.430 | $21.52 ✅ | 4.3% |
| Val 2025 | 27 (TP:15/SL:12) | 55.6% | $+0.0706 | 1.676 | $21.91 ✅ | 5.2% |
| Test 2026 ene–ago | 3 (TP:1/SL:2) | 33.3% | $-0.0517 | 0.670 | $19.85 ❌ | 2.3% |
| Val 2024–2026 combinado | 61 (TP:31/SL:30) | 50.8% | $+0.0445 | 1.385 | $22.72 ✅ | 6.4% |

---

## Tabla resumen — validación 2024–2026 combinada

| Combinación | RSI | SL | TP | WR | Expect | PF | Capital | DD% |
|-------------|-----|----|----|----|--------|----|---------|-----|
| ACTUAL producción 🔵 | 60–75 | 4.5% | 5.0% | 50.9% | $+0.0066 | 1.057 | $20.77 ✅ | 13.0% |
| Vecino TP-6.0 | 60–68 | 4.5% | 6.0% | 45.4% | $+0.0031 | 1.024 | $20.30 ✅ | 10.2% |
| CANDIDATO 🟡 | 60–68 | 4.5% | 6.5% | 44.6% | $+0.0101 | 1.078 | $20.93 ✅ | 9.8% |
| Vecino TP-7.0 | 60–68 | 4.5% | 7.0% | 42.2% | $+0.0075 | 1.055 | $20.62 ✅ | 9.8% |
| Vecino RSI-max 72 | 60–72 | 4.5% | 6.5% | 44.1% | $+0.0075 | 1.057 | $20.70 ✅ | 11.8% |
| Vecino RSI-max 65 | 60–65 | 4.5% | 6.5% | 44.7% | $+0.0109 | 1.084 | $20.93 ✅ | 10.1% |
| Vecino SL-4.0 | 60–68 | 4.0% | 6.5% | 41.7% | $+0.0087 | 1.071 | $20.84 ✅ | 8.7% |
| Vecino SL-5.0 | 60–68 | 5.0% | 6.5% | 47.1% | $+0.0110 | 1.080 | $20.95 ✅ | 9.8% |
| Vecino RSI-min 55 | 55–68 | 4.5% | 6.5% | 42.1% | $-0.0037 | 0.973 | $19.61 ❌ | 12.6% |
| Vecino RSI-min 65 | 65–68 | 4.5% | 6.5% | 50.8% | $+0.0445 | 1.385 | $22.72 ✅ | 6.4% |

---

## Parte 2 — Filtro BTC/EMA200 semanal

**Candidato RSI 60–68 / SL 4.5% / TP 6.5% sobre datos 2021–2025.**  
EMA200 semanal calculada como EMA de los cierres semanales de BTC (cada 7 días).  
Se clasifica cada señal según si BTC estaba sobre o bajo su EMA200w en ese momento.

| Contexto BTC | Señales | WR | Expect/trade | PF |
|--------------|---------|----|--------------|----|
| BTC **sobre** EMA200w | 164 (TP:73/SL:91) | 44.5% | $+0.0098 | 1.075 |
| BTC **bajo** EMA200w | 31 (TP:18/SL:13) | 58.1% | $+0.0844 | 1.856 |
| Sin dato EMA200w | 55 | — | — | — |

*(Período 2021–2025 completo, sin separar por año en esta tabla para tener muestra suficiente)*

---

## Conclusiones del análisis

### 1. ¿Es 60–68 / 4.5% / 6.5% un pico aislado?

De los 9 vecinos evaluados en validación 2024–2026:
- **8 combinaciones con capital > $20** (positivas)
- **1 combinaciones con capital ≤ $20** (negativas)

**No es un pico aislado.** Existe una zona de robustez: varios parámetros vecinos también validan positivo.

### 2. ¿Qué combinación tiene mejor comportamiento fuera de muestra?

**Mejor PF en validación 2024–2026:** `Vecino RSI-min 65` con PF 1.385, capital $22.72.
**Candidato (60–68/4.5/6.5):** PF 1.078, capital $20.93.
**Actual producción (60–75/4.5/5.0):** PF 1.057, capital $20.77.

### 3. ¿El 2026 cambia la conclusión?

- Candidato 2026: 5 trades, WR 20.0%, capital $19.38
- Actual 2026:    6 trades, WR 33.3%, capital $19.54

Con menos de 10 trades en 2026, el resultado es ruido estadístico. Debe considerarse señal de alerta, no evidencia.

### 4. ¿El filtro BTC/EMA200 semanal predice la calidad de las señales BNB?

- BTC sobre EMA200w: WR 44.5%, PF 1.075
- BTC bajo EMA200w:  WR 58.1%, PF 1.856
- Diferencia WR: -13.6pp | Diferencia PF: -0.781

**Diferencia moderada:** hay cierta señal pero no es concluyente. Explorar con período más largo o separado por año.

### 5. Recomendación

- **No cambiar producción** — este análisis es solo investigación.
- Si la zona de robustez es amplia, el candidato merece consideración formal.
- El paso siguiente sería un walk-forward con ventanas rodantes (rolling windows) para confirmar estabilidad temporal.
- **BTC/EMA200w como prefiltro:** si la diferencia de WR es ≥ 5pp, vale la pena diseñar el filtro correctamente y backtestarlo de forma aislada.
- Cualquier cambio a parámetros de producción requiere OK explícito de Ariel.