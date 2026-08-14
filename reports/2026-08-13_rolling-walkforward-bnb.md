# Rolling Walk-Forward — BNBUSDT ALCISTA
## Producción vs Candidato

**SOLO INVESTIGACIÓN — ningún archivo de producción fue modificado.**

| Parámetro | Producción | Candidato |
|-----------|-----------|-----------|
| RSI | 60–75 | 60–68 |
| SL | 4.5% | 4.5% |
| TP | 5.0% | 6.5% |

**Metodología:** ventanas rolling, entrenamiento 3 años, validación 1 año, avance 1 año.  
**Comisión:** 0.1%/lado. **Monto:** $5/trade. **Capital inicial:** $20 por ventana (independiente).  
**Mínimo trades para considerar validación:** 10.

---

## Tabla completa de ventanas

### Ventana: Train 2021–2023 → Val 2024

#### Producción (RSI 60–75 / SL 4.5% / TP 5.0%)

| Período | Trades | WR | Expect/trade | PF | Capital final | DD máx |
|---------|--------|----|--------------|----|---------------|--------|
| Train 2021–2023 | 216 (TP:113/SL:103) | 52.3% | $+0.0135 | 1.120 | $22.92 ✅ | 12.8% |
| Val 2024 | 62 (TP:31/SL:31) | 50.0% | $+0.0025 | 1.021 | $20.16 ✅ | 7.6% |

#### Candidato (RSI 60–68 / SL 4.5% / TP 6.5%)

| Período | Trades | WR | Expect/trade | PF | Capital final | DD máx |
|---------|--------|----|--------------|----|---------------|--------|
| Train 2021–2023 | 164 (TP:78/SL:86) | 47.6% | $+0.0266 | 1.216 | $24.36 ✅ | 11.2% |
| Val 2024 | 51 (TP:23/SL:28) | 45.1% | $+0.0130 | 1.101 | $20.67 ✅ | 5.7% |

### Ventana: Train 2022–2024 → Val 2025

#### Producción (RSI 60–75 / SL 4.5% / TP 5.0%)

| Período | Trades | WR | Expect/trade | PF | Capital final | DD máx |
|---------|--------|----|--------------|----|---------------|--------|
| Train 2022–2024 | 158 (TP:81/SL:77) | 51.3% | $+0.0085 | 1.074 | $21.35 ✅ | 11.3% |
| Val 2025 | 49 (TP:27/SL:22) | 55.1% | $+0.0267 | 1.253 | $21.31 ✅ | 7.0% |

#### Candidato (RSI 60–68 / SL 4.5% / TP 6.5%)

| Período | Trades | WR | Expect/trade | PF | Capital final | DD máx |
|---------|--------|----|--------------|----|---------------|--------|
| Train 2022–2024 | 125 (TP:60/SL:65) | 48.0% | $+0.0290 | 1.237 | $23.63 ✅ | 6.9% |
| Val 2025 | 37 (TP:18/SL:19) | 48.6% | $+0.0326 | 1.270 | $21.21 ✅ | 6.3% |

### Ventana: Train 2023–2025 → Val 2026 ene–ago ⚠️ MUESTRA INSUFICIENTE

#### Producción (RSI 60–75 / SL 4.5% / TP 5.0%)

| Período | Trades | WR | Expect/trade | PF | Capital final | DD máx |
|---------|--------|----|--------------|----|---------------|--------|
| Train 2023–2025 | 152 (TP:81/SL:71) | 53.3% | $+0.0181 | 1.165 | $22.76 ✅ | 12.3% |
| Val 2026 ene–ago | 6 | — | — | — | — | — | MUESTRA INSUFICIENTE |

#### Candidato (RSI 60–68 / SL 4.5% / TP 6.5%)

| Período | Trades | WR | Expect/trade | PF | Capital final | DD máx |
|---------|--------|----|--------------|----|---------------|--------|
| Train 2023–2025 | 118 (TP:58/SL:60) | 49.2% | $+0.0353 | 1.296 | $24.17 ✅ | 7.2% |
| Val 2026 ene–ago | 5 | — | — | — | — | — | MUESTRA INSUFICIENTE |

---

## Tabla consolidada — ventanas válidas
*(Solo ventanas con ≥ 10 trades en validación — excluye muestra insuficiente)*

| Métrica | Producción | Candidato |
|---------|-----------|-----------|
| Ventanas válidas | 2 | 2 |
| Ventanas positivas | 2/2 | 2/2 |
| Ventanas negativas | 0 | 0 |
| % ventanas positivas | 100% | 100% |
| PF promedio | 1.137 | 1.185 |
| Expectancy promedio/trade | $+0.0146 | $+0.0228 |
| Capital final promedio | $20.73 | $20.94 |
| DD máximo promedio | 7.3% | 6.0% |
| Mejor ventana (capital) | $21.31 | $21.21 |
| Peor ventana (capital) | $20.16 | $20.67 |

---

## Comparación producción vs candidato

| Pregunta | Producción | Candidato |
|----------|-----------|-----------|
| ¿En cuántas ventanas gana? | 1 | 1 |
| Ventanas con PF > 1.0 | 2/2 | 2/2 |
| DD promedio | 7.3% | 6.0% |
| Expectancy promedio | $+0.0146 | $+0.0228 |
| Capital promedio | $20.73 | $20.94 |

---

## Análisis de estabilidad temporal

- **Val 2024:** prod $20.16 (PF 1.021) vs cand $20.67 (PF 1.101) → **Candidato adelante**
- **Val 2025:** prod $21.31 (PF 1.253) vs cand $21.21 (PF 1.270) → **Producción adelante**
- **Val 2026 ene–ago:** ⚠️ MUESTRA INSUFICIENTE — prod: 6 trades, cand: 5 trades. No usar como evidencia.

**Rango de capital entre ventanas (prod):** $1.16  
**Rango de capital entre ventanas (cand):** $0.54  

*(Rango alto = resultado muy dependiente del período elegido)*

---

## Análisis específico 2026

- Período: ene–ago 2026 (ventana parcial ~8 meses)
- Producción: 6 trades | Candidato: 5 trades
- **⚠️ MUESTRA INSUFICIENTE** (umbral: 10 trades mínimos)
- El resultado de 2026 **NO es evidencia concluyente** en ninguna dirección.
- Usar solo como referencia de tendencia reciente, no como argumento.

---

## Conclusión técnica

✅ **A) CANDIDATO ROBUSTO** — merece pasar a una siguiente prueba.

**Fundamento:** El candidato valida positivo en 2/2 ventanas, PF promedio 1.185, expectancy $+0.0228/trade. Supera a producción en capital promedio y expectancy.

---

## Recomendación final

- Este análisis es **solo investigación**. No autoriza ningún cambio.
- El siguiente paso lógico si el veredicto es A: backtestear el filtro BTC/EMA200w de forma aislada.
- Si el veredicto es C: esperar al cierre de 2026 para tener una tercera ventana completa.
- Cualquier cambio a `config_cartera.py` o francotiradores requiere OK explícito de Ariel.