# Índice de resultados — Z-Bot Padre v2

Tabla de todos los backtests/pruebas cuantitativas corridos entre 2026-07-12 y 2026-08-25, con
métricas y veredicto. Fuente: los 176 reportes de `reports/*.md` + `INVESTIGACION.md`. Los
reportes que son diagnóstico/infraestructura (no backtests de estrategia) no están acá — ver
`ESTADO_ACTUAL.md` para esos.

**Agrupado por moneda** (dentro de cada moneda, orden cronológico) — responde más rápido
"¿ya probamos X en esta moneda/fase?" que el orden puramente cronológico.

**"—"** = dato no disponible/no aplicable en el reporte fuente, no inventado.

**Protocolo de actualización — permanente desde 2026-08-24**: al cerrar cualquier investigación
nueva (backtest, prueba, auditoría con veredicto), se agrega una fila acá y se actualiza
`ESTADO_ACTUAL.md` como parte del cierre, sin que haga falta pedirlo.

---

## BTC

| Fase | Qué se probó | n | WR | PF | Sharpe | Resultado | Reporte fuente |
|---|---|---|---|---|---|---|---|
| ALCISTA | Sistema C (RSI 55-60 + gate EMA200d) | OOS 59 | 54.2% | 1.322 | — | 🟡 Prometedor (14-ago) → 🔴 Descartado tras retest con 12 gates + walk-forward (24-ago) | `2026-08-14_btc-bootstrap-sistema-c-vs-produccion.md` → `2026-08-24_fase2b-gates-restantes.md` |
| ALCISTA | RSI 55-60 aislado (sin gate EMA200) | — | — | — | — | 🔴 Descartado | `2026-08-14_btc-alcista-rsi-55-60.md` |
| ALCISTA | Régimen EMA200 forense + robustez de vecindad walk-forward | 23 (train) | 65% | 2.091 | — | 🟢 Evidencia fuerte de régimen (contexto de Sistema C) | `2026-08-14_btc-alcista-forense-regimen-ema200-historico.md`, `-robustez-vecindad-sistema-c.md` |
| ALCISTA | Perfil de gates — RSI/EMA/MAX_OP_TOTAL/multitimeframe (Fase 2) + 6 gates restantes + EMA50-BASE20 + compresión (Fase 2-B) | 243 baseline | 47-49% | 1.04-1.88 | 1.07-3.21 | Ninguno significativo; MAX_OP_TOTAL=2 sube Sharpe pero empeora DD — NO implementado (decisión Ariel) | `2026-08-23_fase2-aporte-individual-gates.md`, `2026-08-24_fase2b-gates-restantes.md` |
| ALCISTA | RSI 55-75 + MAX_OP_TOTAL=2 combinados | 470 | 49.6% | 1.470 | 4.025 | 🔴 Descartado — no significativo, trade-off desproporcionado (DD ×2.5) | `2026-08-24_combinacion-rsi-maxop-btc.md` |
| ALCISTA | Auditoría gates inertes (limitador_diario, correlación maxdir, multitimeframe removidos del todo) | 243→249 | — | 1.368-1.369 | — | Sin efecto medible, no tocar | `2026-08-24_auditoria-gates-inertes.md` |
| ALCISTA | Torneo francotiradores — individual (`evaluar()` literal, 9 años) | 243 | 48.6% | 1.369 | 2.346 | 🟢 Activo, puesto 4/15 | `2026-08-24_torneo-francotiradores-fase1.md` |
| LATERAL | Torneo francotiradores — individual | 349 | 45.6% | 0.895 | −1.003 | 🔴 Confirma la pausa en el director | `2026-08-24_torneo-francotiradores-fase1.md` |
| BAJISTA | Torneo francotiradores — individual (gate `gestor_bajistas` ignorado a propósito) | 228 | 33.3% | 0.877 | −0.917 | 🔴 Peor WR de los 15 | `2026-08-24_torneo-francotiradores-fase1.md` |

## ETH

| Fase | Qué se probó | n | WR | PF | Sharpe | Resultado | Reporte fuente |
|---|---|---|---|---|---|---|---|
| ALCISTA | Sistema C (RSI+EMA200d) | OOS 67 | 46.3% | 0.960 | — | 🔴 Descartado (0/4 EMAs) | `2026-08-16_eth-bootstrap-sistema-c-vs-produccion.md` |
| ALCISTA | Forense baseline (5 años) + optimización walk-forward grid + validación extendida 2024-26 | 254 (forense) / 58-67/año | 44.8-52.0% | 0.828-1.216 | — | Positivo en backtest 2021-23, débil en años recientes (coincide con torneo) | `2026-08-13_forense-5-monedas.md`, `-optimizacion-walk-forward.md`, `-validacion-extendida.md` |
| (todas) | Expectancy real forense (630 trades) | 630 | 46.2% | 0.977 | — | Negativo agregado, arrastrado por LATERAL | `2026-08-13_expectancy-real.md` |
| ALCISTA | Perfil de gates individual (Fase 2 + 2-B) + auditoría gates inertes | 288 baseline | 54-58% | 1.30-1.47 | 2.15-3.5 | Ninguno significativo | `2026-08-23_fase2-aporte-individual-gates.md`, `2026-08-24_fase2b-gates-restantes.md`, `-auditoria-gates-inertes.md` |
| ALCISTA | Torneo francotiradores — individual | 288 | 57.3% | 1.437 | 2.953 | 🟢 Mejor de los 15 | `2026-08-24_torneo-francotiradores-fase1.md` |
| LATERAL | Referencia (desactivado por código desde 13-ago, `evaluar()` retorna incondicional) | 376 | 42.3% | 0.904 | — | 🔴 Descartado; no re-testeable con `evaluar()` literal (0 trades siempre) | `2026-08-13_forense-5-monedas.md`, citado en `2026-08-24_torneo-francotiradores-fase1.md` |
| BAJISTA | Torneo francotiradores — individual (gate ignorado a propósito) | 297 | 38.4% | 1.074 | 0.576 | Positivo modesto, inejecutable en SPOT | `2026-08-24_torneo-francotiradores-fase1.md` |

## SOL

| Fase | Qué se probó | n | WR | PF | Sharpe | Resultado | Reporte fuente |
|---|---|---|---|---|---|---|---|
| LATERAL | `evaluar()` literal ventana corta (2026, ~8 meses) | 38 | 50-51.4% | — | — | Parecía prometedor — luego contradicho por ventana larga | `2026-08-17_evaluar-literal-sol-lateral.md`, `-resim-gates-reales-sol-lateral.md` |
| LATERAL | `evaluar()` literal completo 5.9 años (12 gates) + auditoría de los 12 gates individuales + compresión EMA20/100 | 379 | 44.3% | ~plano | −0.697 | 🔴 Descartado — el hallazgo corto era artefacto de ventana; ningún gate individual cambia el veredicto | `INVESTIGACION.md` (22-ago), serie `2026-08-18_auditoria-*.md`, `-profundizacion-compresion-sol-lateral.md` |
| LATERAL | Volatilidad elevada como filtro de entrada, k=1.5-2.5 (extensión) | 14-107 | 47.7-60.0% | 1.081-1.768 | 0.377-1.704 | Mejor punto de toda la línea de volatilidad, pero depende de 1 ventana de 6 meses (PF 5.88) — no confirmado | `2026-08-24_sol-filtro-volatilidad-k-alto.md` |
| LATERAL | Torneo francotiradores — individual | 379 | 44.3% | 0.928 | −0.697 | Puesto 12/15 — eslabón más débil de la config actual | `2026-08-24_torneo-francotiradores-fase1.md` |
| ALCISTA | Trades reales simulados 2026 (muestra corta) | 9 | 11.1% | — | — | 🔴 Peor de 6 medidos en esa muestra | `2026-08-16_trades-reales-simulados-sol-2026.md` |
| ALCISTA | Torneo francotiradores — individual (`evaluar()` literal 5.9 años) | 250 | 43.2% | 1.247 | 1.558 | 🟢 Mucho mejor que la muestra corta sugería — candidato fuerte para reemplazar SOL LATERAL | `2026-08-24_torneo-francotiradores-fase1.md` |
| BAJISTA | Sistema C | OOS 96 | 46.9% | 0.984 | — | 🔴 Descartado | `2026-08-14_sol-bootstrap-sistema-c-vs-produccion.md` |
| BAJISTA | Torneo francotiradores — individual (gate ignorado a propósito) | 230 | 41.3% | 1.150 | 0.999 | Positivo, inejecutable en SPOT | `2026-08-24_torneo-francotiradores-fase1.md` |

## BNB

| Fase | Qué se probó | n | WR | PF | Sharpe | Resultado | Reporte fuente |
|---|---|---|---|---|---|---|---|
| ALCISTA | Sistema C (RSI+EMA200d) | OOS 72 | 54.2% | 1.318 | — | 🟡 Prometedor en backtest | `2026-08-14_bnb-bootstrap-sistema-c-vs-produccion.md` |
| ALCISTA | Candidato RSI 60-68/TP6.5% — walk-forward backtest → forward 2026 real | WF prom PF 1.19-1.30 / Fwd n=19 | Fwd 31.6% | Fwd 0.619 | — | 🟡 Prometedor en backtest → ❌ Negativo en forward real 2026 — no implementado | `2026-08-13_rolling-walkforward-bnb.md`, `2026-08-14_bnb-alcista-acumulativo.md`, `2026-08-15_auditoria_francotirador_frecuencia.md` |
| ALCISTA | Gate EMA250(1D) adicional (filtro de calidad) | — | — | — | — | 🔴 BNB no pasa el filtro | `2026-08-15_bnb-gate-ema250-analisis.md` |
| ALCISTA | Trades reales simulados 2026 | 8 | — | — | — | PnL −9.18% | `2026-08-16_trades-reales-simulados-bnb-2026.md` |
| ALCISTA | Torneo francotiradores — individual (`evaluar()` literal 8.8 años) | 223 | 45.3% | 1.060 | 0.422 | Modesto positivo, director huérfano | `2026-08-24_torneo-francotiradores-fase1.md` |
| LATERAL | Torneo francotiradores — individual | 293 | 51.5% | 1.130 | 1.018 | Sorpresa positiva — mejor que la metodología de ranking anterior sugería | `2026-08-24_torneo-francotiradores-fase1.md` |
| BAJISTA | Torneo francotiradores — individual (gate ignorado a propósito) | 201 | 34.3% | 0.967 | −0.220 | Cerca de breakeven, negativo | `2026-08-24_torneo-francotiradores-fase1.md` |

## AVAX

| Fase | Qué se probó | n | WR | PF | Sharpe | Resultado | Reporte fuente |
|---|---|---|---|---|---|---|---|
| ALCISTA | Sistema C | OOS 67 | 38.8% | 0.707 | — | 🔴 Descartado, la peor de las 5 | `2026-08-14_avax-bootstrap-sistema-c-vs-produccion.md` |
| ALCISTA | Trades reales simulados 2026 | 10 | — | — | — | PnL −27.80% | `2026-08-16_trades-reales-simulados-avax-2026.md` |
| ALCISTA | Torneo francotiradores — individual (`evaluar()` literal 5.9 años) | 260 | 42.3% | 1.231 | 1.528 | Bueno, director huérfano | `2026-08-24_torneo-francotiradores-fase1.md` |
| LATERAL | Torneo francotiradores — individual | 205 | 45.9% | 0.985 | −0.103 | Cerca de breakeven | `2026-08-24_torneo-francotiradores-fase1.md` |
| BAJISTA | Torneo francotiradores — individual (gate ignorado a propósito) | 254 | 42.1% | 1.262 | 1.694 | 🟢 2° mejor de los 15, inejecutable en SPOT hoy | `2026-08-24_torneo-francotiradores-fase1.md` |

## Segunda lista Sistema C (monedas fuera de las 5 de producción)

| Moneda | Qué se probó | n | WR | PF | Resultado | Reporte fuente |
|---|---|---|---|---|---|---|
| XRP | Sistema C prueba 1 | — | — | 0.800 | 🔴 Descartado | `2026-08-15_xrp-sistema-c-prueba1.md` |
| LINK | Sistema C prueba 1 | — | — | 0.902 | 🔴 Descartado | `2026-08-15_link-sistema-c-prueba1.md` |

## Multi-moneda / cross-symbol

| Moneda | Fase | Qué se probó | n | WR | PF | Sharpe | Resultado | Reporte fuente |
|---|---|---|---|---|---|---|---|---|
| Multi (5) | N/A | SL actual vs SL uniforme 3.0% (2021-2026) | 10067 vs 10388 | 55.3% vs 53.6% | — | — | SL actual (config vigente) mejor, no cambiar | `2026-07-13_backtest_sl_actual_vs_sl3.md` |
| Multi (5) | N/A | TRAILING_DISTANCIA 1/1.5/2/3% (5.5 años) | ~10000 | — | — | — | 1% actual da mejor retorno y menor DD temprano | `2026-07-13_backtest_trailing_2021-2026.md`, `-drawdown_maximo_por_escenario.md` |
| Multi (5) | ALC+LAT | Ranking frecuencia/expectancy 15 francotiradores (metodología antigua, 2021-2026 ~62 meses) | vario | — | 0.845-1.147 | — | **Superado por el Torneo `evaluar()`-literal del 24-ago — ver esa sección abajo** | `2026-08-16_ranking-frecuencia-expectancy-15-francotiradores.md` |
| Multi (5) | ALCISTA | Config mixta MAX_OP_TOTAL variable — 3 escenarios (2026, muestra corta) | 99-117 | — | — | — | Mejor escenario: sin BNB/AVAX, +$7.54 (8.6× mejor que con las 5); M=2 uniforme empeora PnL neto | `2026-08-16_backtest-configuracion-mixta-final.md`, `-sin-bnb-avax.md`, `-max-op-total-2.md` |
| Multi | N/A | Búsqueda estrategia frecuente — Señal D (RSI+volumen LINK/BTC) | — | — | — | — | 🟡 B Interesante, no llega a grado A | `2026-08-20_busqueda_estrategia_frecuente_rentable.md` |
| Multi | N/A | Búsqueda estrategia frecuente — comprar tras vela fuerte, cierre cerca del máximo | — | — | — | — | 🔴 C Descartado | `2026-08-20_busqueda_estrategia_frecuente_rentable.md` |
| BTC/ETH/SOL | ALCISTA | Dennis/Turtle — Sistema B (gestión de riesgo sobre señal real) + Sistema C (Turtle puro, referencia) | — | — | — | — | Sin mejora significativa (IC95% cruza cero); Turtle puro revela que la señal de entrada del bot no aporta en BTC/SOL | `2026-08-23_experimento-dennis-abc.md` |
| BTC | ALCISTA | Prueba D (entrada bot + salida estilo Turtle) — barrido de granularidad 4h→4min | 243 | — | 2.115→1.509 | 3.724→1.922 | 🔴 Archivado — pierde contra buy&hold en mitad reciente y a frecuencia real | `2026-08-23_veredicto-final-prueba-d.md`, `-barrido-granularidad-prueba-d.md` |
| ETH | ALCISTA | Prueba D (entrada bot + salida estilo Turtle) — barrido de granularidad 4h→4min | 288 | — | 2.223→0.91 | 3.799→−0.429 | 🔴 Archivado — pérdida neta de capital a frecuencia real | `2026-08-23_eth-d-granularidad-vs-buyhold.md`, `-barrido-granularidad-prueba-d.md` |
| BTC/ETH/SOL | ALC/LAT | TP postergado — detector vela fuerte, trailing % fijo (4h→1h) | 64/68/43 | — | — | — | Mejora aparente a 4h se diluye a ~0 con evaluación 1h realista | `2026-08-20_backtest-tp-postergado-detector-fuerza.md`, `-1h.md`, `-anchos-trailing.md` |
| BTC/ETH/SOL | ALC/LAT | TP postergado — trailing dinámico k×ATR(14) | 64/68/44 afectados | — | — | — | 🔴 Descartado — piso elimina downside pero 94-100% del efecto en 1-2 trades por moneda | `2026-08-23_tp-postergado-trailing-atr.md` |
| BTC/ETH/SOL | ALC/LAT | Ajuste por mecha en el TP (decisión de una sola vela, sin postergar) | 7/10/4 (mejor k) | — | — | — | 🔴 Descartado — máx. 17 eventos de calendario independientes | `2026-08-24_ajuste-mecha-tp.md` |
| BTC/ETH/SOL | ALC/LAT | Volatilidad elevada como aviso de salida (postergación) | 59-82/moneda | — | — | — | 🔴 Descartado — mediana 0.00pp en 9/9 combinaciones pese a n≥30 | `2026-08-24_backtest-volatilidad-aviso.md` |
| BTC/ETH/SOL | ALC/LAT | Volatilidad elevada como filtro de ENTRADA, k=1.16-1.31 | 134-178/combo | 44-58% | 0.99-1.47 | −0.06-2.35 | BTC/ETH empeoran; SOL es el único prometedor (ver fila SOL k=1.5-2.5) | `2026-08-24_volatilidad-como-filtro-entrada.md` |

## Torneo de francotiradores 24-ago — REFERENCIA PRINCIPAL para comparaciones entre fases y combinaciones

*(Reemplaza al ranking del 16-ago para cualquier pregunta de "¿qué fase/combinación rinde mejor?" — mismo método `evaluar()` literal riguroso de toda la sesión, no la metodología antigua.)*

| Qué se probó | n | WR | PF | Sharpe | Resultado | Reporte fuente |
|---|---|---|---|---|---|---|
| **Grupo ALCISTA combinado** (BTC+ETH+SOL+BNB+AVAX, capital repartido) | 1264 | 47.6% | 1.264 | 3.865 | 🟢 Significativamente mejor que LATERAL (bootstrap IC99% no cruza cero); único grupo con PF>1 en 3/3 ventanas walk-forward | `2026-08-24_torneo-francotiradores-fase1.md` |
| **Grupo LATERAL combinado** (BTC+SOL+BNB+AVAX, ETH excluido por hard-disable) | 1226 | 46.7% | 0.980 | −0.347 | 🔴 Grupo más débil, degrada con el tiempo (PF cae a 0.841 en ventana 2) | `2026-08-24_torneo-francotiradores-fase1.md` |
| **Grupo BAJISTA combinado** (gate `gestor_bajistas` ignorado a propósito) | 1210 | 38.1% | 1.074 | 1.147 | Positivo, mejor que LATERAL, no significativo vs ALCISTA; fragilidad reciente igual que el resto | `2026-08-24_torneo-francotiradores-fase1.md` |
| **Combo A — actual** (BTC-ALC + ETH-ALC + SOL-LAT) | 910 | 49.6% | 1.200 | 2.621 | Config actual — se debilita a PF 1.011 en la ventana más reciente | `2026-08-24_torneo-francotiradores-fase1.md` |
| **Combo B** (BTC-ALC + ETH-ALC + SOL-ALC, swap de fase de SOL) | 781 | 50.1% | 1.347 | 3.860 | 🟢 Mejor alternativa ejecutable — más robusta en walk-forward que A (nunca <1.13 en 3 ventanas) | `2026-08-24_torneo-francotiradores-fase1.md` |
| Combo C (BTC-ALC + ETH-ALC + AVAX-ALC) | 791 | 49.7% | 1.338 | 3.833 | Casi empatada con B, también más robusta que A | `2026-08-24_torneo-francotiradores-fase1.md` |
| Combo D (BTC-ALC + ETH-ALC + BNB-LAT) | 824 | 52.7% | 1.303 | 3.654 | Mejor que A | `2026-08-24_torneo-francotiradores-fase1.md` |
| Combo E (ETH-ALC + SOL-ALC + AVAX-ALC, sin BTC) | 798 | 48.0% | 1.300 | 3.399 | Mejor que A, racha de pérdidas peor (15) | `2026-08-24_torneo-francotiradores-fase1.md` |
| Combo F (BTC-ALC + ETH-ALC + BNB-ALC) | 754 | 50.9% | 1.283 | 3.287 | Mejor que A | `2026-08-24_torneo-francotiradores-fase1.md` |
| Combo G — hipotético (BTC-ALC + ETH-ALC + AVAX-BAJ, no ejecutable hoy) | 785 | 49.7% | 1.352 | 3.956 | Mejor de todos los probados, pero requiere Futuros | `2026-08-24_torneo-francotiradores-fase1.md` |

### Fase 2 (25-ago) — 10 combinaciones nuevas, capital $100 (no comparable celda a celda con la tabla de arriba, base $1,000)

| Combinación | n | WR | PF | Sharpe | Resultado | Reporte fuente |
|---|---|---|---|---|---|---|
| Combo N — BTC-ALC+ETH-ALC+AVAX-BAJ (confirmado real, no hipotético) | 785 | 49.7% | 1.352 | 3.956 | 🟢 Mejor de 3 de toda la investigación; requiere Futuros | `2026-08-25_torneo-francotiradores-fase2.md` |
| Combo H — BTC-ALC+SOL-ALC+AVAX-ALC | 753 | 44.6% | 1.273 | 3.020 | Mejor que A, no supera a B/N | `2026-08-25_torneo-francotiradores-fase2.md` |
| Combo I — BTC-ALC+SOL-ALC+BNB-LAT | 786 | 48.0% | 1.237 | 2.773 | Mejor que A, no supera a B/N | `2026-08-25_torneo-francotiradores-fase2.md` |
| Combo J — BTC-ALC+AVAX-ALC+BNB-LAT | 796 | 47.6% | 1.231 | 2.750 | Mejor que A, no supera a B/N | `2026-08-25_torneo-francotiradores-fase2.md` |
| Combo K — ETH-ALC+SOL-ALC+BNB-LAT | 831 | 51.0% | 1.267 | 3.180 | Mejor que A, no supera a B/N | `2026-08-25_torneo-francotiradores-fase2.md` |
| Combo L — ETH-ALC+AVAX-ALC+BNB-LAT (sin BTC, sin SOL) | 841 | 50.7% | 1.261 | 3.157 | Mejor que A; combinaciones sin BTC nunca superan a las que sí lo incluyen | `2026-08-25_torneo-francotiradores-fase2.md` |
| Combo M — SOL-ALC+AVAX-ALC+BNB-LAT (sin BTC, sin ETH) | 803 | 46.0% | 1.203 | 2.399 | Peor de las 10 nuevas | `2026-08-25_torneo-francotiradores-fase2.md` |
| **Combo O — B + AVAX-ALC** (4 francotiradores, 100% ejecutable SPOT) | 1041 | 48.1% | 1.314 | **4.060** | 🟢 Mejor candidato ejecutable de toda la investigación (Sharpe y retorno), racha de pérdidas más larga (13) | `2026-08-25_torneo-francotiradores-fase2.md` |
| Combo P — B + BNB-LAT (4 francotiradores) | 1074 | 50.5% | 1.288 | 3.880 | Mejor que B, no supera a O | `2026-08-25_torneo-francotiradores-fase2.md` |
| Combo Q — B + AVAX-BAJ (4 francotiradores, hipotético) | 1035 | 48.1% | 1.324 | **4.159** | Mejor Sharpe de toda la investigación, requiere Futuros | `2026-08-25_torneo-francotiradores-fase2.md` |

**Perfil de perdedoras + circuit breaker (25-ago, capital $20 real)**: sin señal de aviso previo
clara — RSI/volumen relativo/ATR% de entrada casi idénticos entre ganadoras y perdedoras en A y O.
El tamaño del movimiento en contra en las perdedoras es esencialmente el SL configurado (mediana
−4.83% A / −5.13% O), no una variable con distribución propia. Circuit breaker (3 pérdidas→pausa 7
días, único parámetro probado, sin optimizar): mejora drawdown en ambas (A −15.38%→−12.51%, O
−12.92%→−10.03%) pero es mixto — cuesta $1.48 en A, y en O **empeora la racha máxima de pérdidas
(13→15)** pese a mejorar PF/WR/$ — resultado no limpio, reportado tal como salió. El 58-59% del
costo total en $ viene de rachas cortas (1-3 pérdidas), no de las largas. Ver
`2026-08-25_perfil-perdidas-circuit-breaker.md`.

**Recálculo A vs. O con capital real $20** (mismos n/WR/PF/Sharpe que arriba, invariantes al
capital): ganancia en $ idéntica en cualquier base ($24.03 A / $47.84 O, por `MONTO_FIJO` fijo);
con $20, DD sube a −14.97% (A) / −12.92% (O), retorno a +120.17% (A) / +239.18% (O) — ver
`2026-08-25_torneo-recalculo-capital-real-20.md` para el detalle de por qué cambia solo lo que
depende de una base de capital y no lo demás.

## Correlación entre monedas 25-ago — moneda líder vs. moneda operada

*(Familia de 40 pruebas por fase — no una sola combinación n/WR/PF/Sharpe. Se resume en bloque,
mismo criterio que el torneo.)*

| Qué se probó | n | WR | PF | Sharpe | Resultado | Reporte fuente |
|---|---|---|---|---|---|---|
| **Fase A** — WR de moneda_operando según tendencia fuerte vs. lateral de moneda_contexto al momento de la entrada (5 monedas × 4 contextos × 2 criterios = 40 pruebas) | 22/40 pasan filtro rápido (n≥30, ΔWR≥5pp) | — | — | — | 🔴 Ninguna significativa — IC99.875% (Bonferroni/40) cruza cero en las 22; BNB como operando aparece en 7/22, sin confirmar | `2026-08-25_correlacion-5-monedas-fase-ab.md` |
| **Fase B** — PnL/vela antes vs. después de que moneda_contexto entra en BAJISTA_FUERTE durante una posición ya abierta (40 combinaciones) | máx. 7 (de 40 combos) | — | — | — | ⚪ No evaluable — 0/40 combinaciones llegan a n≥30 casos de alerta válidos; limitación estructural (posiciones duran pocas velas frente a la escala diaria del criterio), no resultado nulo | `2026-08-25_correlacion-5-monedas-fase-ab.md` |
