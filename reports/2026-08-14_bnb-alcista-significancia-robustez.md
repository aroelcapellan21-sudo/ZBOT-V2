# Análisis de significancia y robustez — BNB ALCISTA

**SOLO INVESTIGACIÓN. Ningún archivo de producción fue modificado.**

## Configuraciones
| | RSI | SL | TP |
|--|-----|----|----|
| **Producción** | 60–75 | 4.5% | 5.0% |
| **Candidato**  | 60–68 | 4.5% | 6.5% |

Comisión 0.1%/lado · $5/trade · Capital inicial $20 · Sin filtro BTC/EMA200w

---

## 1. Resultados anuales

### Producción (RSI 60–75 / SL 4.5% / TP 5.0%)

| Año | Trades | WR | Expect/trade | PF | Capital final | DD máx |
|-----|--------|----|--------------|----|---------------|--------|
| 2021 | 119 (TP:63/SL:56) | 52.9% | $+0.0165 | 1.149 | $21.96 ✅ | 12.2% |
| 2022 | 55 (TP:27/SL:28) | 49.1% | $-0.0018 | 0.985 | $19.90 ❌ | 11.3% |
| 2023 | 42 (TP:22/SL:20) | 52.4% | $+0.0138 | 1.123 | $20.58 ✅ | 5.6% |
| 2024 | 62 (TP:31/SL:31) | 50.0% | $+0.0025 | 1.021 | $20.16 ✅ | 7.6% |
| 2025 | 49 (TP:27/SL:22) | 55.1% | $+0.0267 | 1.253 | $21.31 ✅ | 7.0% |

### Candidato  (RSI 60–68 / SL 4.5% / TP 6.5%)

| Año | Trades | WR | Expect/trade | PF | Capital final | DD máx |
|-----|--------|----|--------------|----|---------------|--------|
| 2021 | 89 (TP:41/SL:48) | 46.1% | $+0.0184 | 1.145 | $21.64 ✅ | 11.2% |
| 2022 | 43 (TP:20/SL:23) | 46.5% | $+0.0208 | 1.166 | $20.90 ✅ | 6.9% |
| 2023 | 32 (TP:17/SL:15) | 53.1% | $+0.0572 | 1.519 | $21.83 ✅ | 5.4% |
| 2024 | 51 (TP:23/SL:28) | 45.1% | $+0.0130 | 1.101 | $20.67 ✅ | 5.7% |
| 2025 | 37 (TP:18/SL:19) | 48.6% | $+0.0326 | 1.270 | $21.21 ✅ | 6.3% |

---

## 2. Diferencias anuales (Candidato − Producción)

| Año | ΔExpect | ΔPF | ΔWR | ΔDD | ΔCapital | Ganador |
|-----|---------|-----|-----|-----|----------|---------|
| 2021 | $+0.0019 | -0.004 | -6.9 pp | -1.0 pp | $-0.33 | **Producción** |
| 2022 | $+0.0226 | +0.181 | -2.6 pp | -4.4 pp | $+1.00 | **Candidato** |
| 2023 | $+0.0434 | +0.396 | +0.7 pp | -0.2 pp | $+1.25 | **Candidato** |
| 2024 | $+0.0105 | +0.080 | -4.9 pp | -1.9 pp | $+0.51 | **Candidato** |
| 2025 | $+0.0058 | +0.016 | -6.5 pp | -0.7 pp | $-0.11 | **Producción** |

---

## 3. Análisis de consistencia — años válidos (≥10 trades)

Años válidos: 5 de 5

| Condición | Años que cumple | % |
|-----------|----------------|---|
| Candidato gana (capital) | 3/5 | 60% |
| Producción gana | 2/5 | 40% |
| Empate | 0/5 | 0% |
| Candidato PF > 1.0 | 5/5 | 100% |
| Candidato expectancy > 0 | 5/5 | 100% |
| Candidato DD ≤ Producción | 5/5 | 100% |
| Candidato supera en expectancy | 5/5 | 100% |

**Promedios anuales (solo años válidos):**

| Métrica | Producción | Candidato | Δ |
|---------|-----------|-----------|---|
| PF promedio | 1.106 | 1.240 | +0.134 |
| Expectancy promedio | $+0.0115 | $+0.0284 | $+0.0169 |
| DD promedio | 8.7% | 7.1% | -1.6 pp |
| Capital promedio | $20.78 | $21.25 | $+0.46 |

---

## 4. Análisis bootstrap — diferencia de expectancy (Candidato − Producción)

### Limitaciones importantes


1. **Dependencia serial:** los trades no son independientes — cada trade bloquea la entrada
   siguiente hasta que cierra (estructura secuencial). El bootstrap de observaciones i.i.d.
   subestima la varianza real. Los resultados son **orientativos**, no inferenciales formales.
2. **Muestra total reducida:** con ~250–330 trades en 5 años, la distribución empírica
   tiene colas delgadas. Los percentiles extremos pueden ser poco estables.
3. **Dos distribuciones distintas:** candidato y producción no son muestras del mismo
   proceso — el candidato tiene RSI más estrecho, así que sus señales son un subconjunto
   diferente. La diferencia de expectancy **no** es la diferencia de dos tratamientos
   sobre los mismos trades; hay selección de señal diferente en cada sistema.

**Con esas advertencias, el bootstrap da:**

- **Diferencia observada:** $+0.01278/trade
- **IC 95% bootstrap:** [$-0.02868, $+0.05566]
- **IC 90% bootstrap:** [$-0.02286, $+0.04842]
- **P(diferencia > 0):** 72.0% de las 10,000 remuestras
- **Trades usados:** 327 producción · 252 candidato

**Interpretación:** si P(diff>0) ≥ 90% y el IC 95% no cruza cero, la ventaja
observada es difícil de explicar solo por variación aleatoria *bajo los supuestos
del bootstrap*. Dado que los supuestos no se cumplen perfectamente, interpretar
como evidencia de tendencia, no como prueba estadística formal.

⚠️ **El IC 90% cruza cero** → la ventaja no es estadísticamente distinguible
del ruido bajo el bootstrap.

---

## 5. Análisis por régimen (2021–2025)

*(¿La ventaja del candidato aparece en años concretos o está repartida?)*

| Año | Régimen de mercado | Candidato gana | ΔPF | ΔExpect |
|-----|--------------------|---------------|-----|---------|
| 2021 | Bull run BTC (máx ~$69K, corrección Q2) | ❌ No | -0.004 | $+0.0019 |
| 2022 | Bear market (-75% BTC anual) | ✅ Sí | +0.181 | $+0.0226 |
| 2023 | Recuperación gradual (+150% BTC) | ✅ Sí | +0.396 | $+0.0434 |
| 2024 | Bull run (ETF spot, máx ~$108K) | ✅ Sí | +0.080 | $+0.0105 |
| 2025 | Consolidación / corrección (-20% desde máx) | ❌ No | +0.016 | $+0.0058 |

**Distribución de la ventaja:** 
Verificar si la ventaja del candidato se concentra en un solo régimen (overfitting)
o aparece en bull y bear market por igual (robustez estructural).

---

## 6. Análisis de sensibilidad — vecinos del candidato (2021–2025)

| Configuración | Trades | WR | Expect/trade | PF | Capital final | DD máx |
|---------------|--------|----|--------------|----|---------------|--------|
| **[PROD]** Producción (60–75/4.5/5.0) | 326 | 52.1% | $+0.0127 | 1.113 | $24.14 ✅ | 12.8% |
| **[CAND]** Candidato  (60–68/4.5/6.5) | 250 | 47.6% | $+0.0268 | 1.218 | $26.70 ✅ | 11.2% |
| — | — | — | — | — | — | — |
| RSI 60–65 / SL 4.5 / TP 6.5 | 227 | 47.1% | $+0.0243 | 1.195 | $25.51 ✅ | 9.7% |
| RSI 60–68 / SL 4.0 / TP 6.5 | 267 | 44.6% | $+0.0240 | 1.206 | $26.40 ✅ | 11.5% |
| RSI 60–68 / SL 5.0 / TP 6.5 | 244 | 49.6% | $+0.0251 | 1.192 | $26.13 ✅ | 11.1% |
| RSI 60–68 / SL 4.5 / TP 6.0 | 265 | 47.5% | $+0.0146 | 1.119 | $23.87 ✅ | 11.3% |
| RSI 60–68 / SL 4.5 / TP 7.0 | 234 | 45.3% | $+0.0255 | 1.198 | $25.96 ✅ | 11.5% |
| RSI 60–72 / SL 4.5 / TP 6.5 | 264 | 46.2% | $+0.0192 | 1.152 | $25.06 ✅ | 14.1% |

**Vecinos con PF > candidato (1.218):** 0/6
**Vecinos con PF > 1.0:** 6/6
→ El candidato es el mejor de su vecindad. Verificar si es pico aislado o si los vecinos también son positivos (PF>1).

---

## 7–8. Veredicto y justificación

### 🟡 B) PROMETEDOR

**Justificación detallada:**

**Consistencia anual:**
- Candidato gana 3/5 años válidos (60%)
- PF > 1.0 en 5/5 años (100%)
- Expectancy > 0 en 5/5 años (100%)
- DD menor o igual en 5/5 años (100%)
- Supera en expectancy en 5/5 años (100%)

**Bootstrap (10,000 muestras, bajo supuesto i.i.d. — orientativo):**
- Diferencia observada: $+0.01278/trade
- IC 95%: [-0.0287, +0.0557]
- P(diff > 0): 72.0%
- **Limitación:** trades serialmente dependientes → bootstrap subestima varianza.
  No interpretar como prueba estadística formal.

**Sensibilidad de vecindad:**
- 6/6 vecinos con PF > 1.0 → zona robusta amplia
- Candidato PF 1.218 vs mejor vecino PF 1.206

**Motivo del veredicto:** Candidato gana 3/5 años con PF>1.0 en 5/5. Bootstrap: P(diff>0)=72.0%, IC 95% [-0.0287, +0.0557]. Zona robusta: 6/6 vecinos con PF>1. Evidencia positiva pero no suficiente para declarar robustez plena sin un año de simulador controlado.

---

## Recomendación final
- **No implementar el candidato en producción basándose en este análisis.**
- Si el veredicto es A o B: el siguiente paso es activar REAL con $20 y acumular
  30+ trades reales antes de comparar formalmente.
- Cualquier cambio a `config_cartera.py` o francotiradores requiere OK explícito de Ariel.