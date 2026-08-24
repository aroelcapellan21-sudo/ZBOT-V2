# Estado actual — Z-Bot Padre v2

Índice central de estado del proyecto. Complementa a `INDICE_RESULTADOS.md` (tabla de todos los
backtests) y a `CLAUDE.md`/`INVESTIGACION.md` (contrato técnico e historial completo). Este
archivo responde "¿dónde estamos hoy?" en un vistazo — no reemplaza a los otros tres, los resume.

**Protocolo de actualización — permanente desde 2026-08-24**: al cerrar cualquier investigación
nueva, este archivo (sección "CERRADO RECIENTEMENTE", y "COLA DE INVESTIGACIÓN" si corresponde) se
actualiza como parte del cierre, junto con `INDICE_RESULTADOS.md`, sin que haga falta pedirlo cada
vez.

---

## EN PRODUCCIÓN AHORA

- **Modo:** REAL, `BOT_REAL_CONFIRMADO=true` activo (llave persistente en
  `~/.bot_real_confirmado`, sobrevive reinicios — verificado en vivo 2 veces, corte real incluido).
- **Capital nominal:** $20.00 USDT. USDT libre: $15.34 (al 2026-08-22).
- **Francotiradores activos** (los únicos 3 que `director_orquesta.py` llama):
  - **BTC ALCISTA** — RSI 50-70, SL 3.5%, TP 6.0%, EMA 20/50, `MAX_OP_TOTAL=1`. Puesto 4/15 en el
    torneo (PF 1.369, Sharpe 2.346).
  - **ETH ALCISTA** — RSI 60-75, SL 4.5%, TP 5.0%, EMA 20/100. **Mejor francotirador de los 15**
    (PF 1.437, Sharpe 2.953).
  - **SOL LATERAL** — RSI 43-57, SL 3.5%, TP 4.0%. **Puesto 12/15** — el más débil de los 3
    activos hoy (PF 0.928, Sharpe −0.697 sobre 5.9 años) — ver "Cola de investigación".
  - Posición abierta actual: ETH ALCISTA, $5, desde 2026-08-22.
- **Bajistas:** los 5 desactivados por gate global (`gestor_bajistas.py`, falta de capital en
  Futuros — no por mal resultado, ver Fase 3 del torneo: el grupo BAJISTA combinado da PF 1.074,
  positivo, con AVAX BAJISTA como 2° mejor francotirador de los 15).
- **BNB y AVAX:** huérfanos en las 3 fases — código completo, sin ninguna pausa interna, pero
  `director_orquesta.py` nunca los llama. AVAX ALCISTA (PF 1.231) y BNB LATERAL (PF 1.130) tienen
  mejor evidencia que SOL LATERAL, el 3er activo actual.
- **`config_cartera.py` no es fuente de verdad universal** — BTC ALCISTA lo ignora por completo
  (RSI/SL/EMA hardcodeados, distintos de lo que dice ese diccionario). ETH ALCISTA y SOL LATERAL sí
  lo leen en vivo.

## COLA DE INVESTIGACIÓN

Ordenada por prioridad/impacto potencial, no por fecha.

1. **Decisión pendiente — ¿reemplazar SOL LATERAL en producción?** El torneo (24-ago) muestra que
   swapear SOL LATERAL por SOL ALCISTA (mismas 3 monedas, mismo capital) sube el Sharpe de la
   config actual de 2.62 a 3.86 y es mucho más estable en walk-forward (nunca cae de PF 1.13 en 3
   ventanas, contra PF 1.011 de la config actual en la ventana más reciente). AVAX ALCISTA es una
   alternativa casi empatada. Ningún cambio se activó — decisión de Ariel. Ver
   `2026-08-24_torneo-francotiradores-fase1.md`.
2. **SOL LATERAL — filtro de volatilidad k=2.0, "prometedor no confirmado".** Mejor resultado de
   toda la línea de investigación de volatilidad (PF 1.768, Sharpe 1.704, +$3.53 vs. baseline) pero
   depende de una sola ventana de 6 meses (PF 5.88). Si se junta más historia de SOL con el tiempo,
   vale la pena re-testear. Ver `2026-08-24_sol-filtro-volatilidad-k-alto.md`.
3. **`resumen_capital.py` con rutas rotas** tras la reorganización de archivos del home
   (`~/bot-padre-v4/v5/v6` movidos a `~/_archivo_bots_anteriores/`) — usado por `/consejero` en
   Telegram, no se cae (tiene fallback) pero muestra capital/trades por defecto para esas filas en
   vez de los reales. Pendiente decisión: corregir las 3 rutas o dejarlo así. Ver
   `~/RESUMEN_ORGANIZACION_2026-08-24.md`.
4. **5 archivos en "zona gris"** de la reorganización del home, sin clasificar (`backup_sd.sh`,
   `package-lock.json`, `intel_noticias/`, `respuesta22.txt`, `setup-dell.sh`/`backup_dell/`) —
   pendientes de que Ariel confirme qué son. Ver `~/PROPUESTA_ORGANIZACION_2026-08-24.md`, sección 5.
5. **Corrección de texto pendiente en `INVESTIGACION.md`**: el hallazgo "horario×calidad" quedó
   invalidado tras corregir el bug de timestamps (2026-08-23) — el texto publicado no se actualizó
   todavía, solo existe un reporte nuevo con la corrección. Ver
   `2026-08-23_reverificacion-filtro-eventos-calidad-horario-corregido.md`.
6. **Bug estructural sin corregir**: 0 cierres `BE`/`TRAILING_SL` reales en 9 años — la fórmula de
   trailing de producción es auto-referencial y nunca dispara (`sl_trail` siempre < `precio_actual`
   en la misma evaluación). Documentado, no tocado — fuera de alcance de las investigaciones de
   backtest. Ver `2026-08-19_trailing-stop-desconectado-investigacion.md`.
7. **Polvo inmovilizado** — punto abierto de siempre, sin resolver (ver `CLAUDE.md`, sección
   "Camino de dinero").
8. **`memoria_propia.json` no se actualiza** — causa raíz ligada a `FASE_CAMBIO`, sin corregir (ver
   `INVESTIGACION.md`).
9. **Bajistas en Futuros** — el torneo confirma señal real (grupo BAJISTA PF 1.074, AVAX BAJISTA
   2° mejor de los 15), pero activarlos requiere cuenta de Futuros y reescribir
   `ejecutor.py:cerrar_posicion` — no iniciado, no es tarea de backtest.

## CERRADO RECIENTEMENTE

Más reciente primero. Ver `INDICE_RESULTADOS.md` para el detalle de métricas de cada uno.

| Fecha | Investigación | Veredicto |
|---|---|---|
| 24-ago | Torneo de francotiradores (15 combinaciones, Fase 1) | ALCISTA significativamente mejor que LATERAL; config actual no es la óptima (ver cola #1) |
| 24-ago | Volatilidad como filtro de entrada (BTC/ETH/SOL) | BTC/ETH empeoran, SOL prometedor no confirmado (ver cola #2) |
| 24-ago | Volatilidad como aviso de salida (postergación) | 🔴 Descartado — mediana 0.00pp pese a n≥30 |
| 24-ago | Antecedentes de movimientos grandes (Fase 1 exploratoria, múltiples umbrales) | Umbral 5% da n≥30 en las 3 monedas; ATR elevado previo es la única variable con patrón consistente |
| 24-ago | Ajuste por mecha en el TP | 🔴 Descartado — máx. 17 eventos de calendario independientes |
| 24-ago | Análisis de outliers del trailing k×ATR | Exploratorio — origina la hipótesis de "ajuste por mecha" (descartada arriba) |
| 23-ago | TP postergado con trailing k×ATR | 🔴 Descartado — 94-100% del efecto en 1-2 trades por moneda |
| 24-ago | Combinación RSI 55-75 + MAX_OP_TOTAL=2 (BTC) | 🔴 Descartado — no significativo, trade-off desproporcionado |
| 24-ago | Fase 2-B — gates restantes (Parte 1: 6 gates × umbral; Parte 2: EMA50-BASE20, compresión, Sistema C) | Ninguno significativo; Sistema C BTC pasa de 🟡 a 🔴 |
| 24-ago | Auditoría de gates inertes (remoción completa) | Sin efecto medible en ninguno de los 3 |
| 23-ago | Fase 2 — aporte individual de gates (RSI/EMA/MAX_OP_TOTAL/multitimeframe) | Ninguno significativo; MAX_OP_TOTAL=2 no implementado (decisión Ariel) |
| 23-ago | Bug de offset de timestamps (UTC-4) en backups de 4h | Corregido en disco (sin commit, `.gitignore`d) en v2 y v3-backup |
| 23-ago | Experimento Dennis/Turtle + Prueba D/E (gestión de riesgo y salida alternativa) | 🔴 Archivado en ambas monedas tras estrés-test completo (granularidad real 4min) |
| 22-ago | Reorganización `CLAUDE.md`/`INVESTIGACION.md` (82.9k → 21.2k + 76.9k chars) | Commit `51d46c4` |
| 22-ago | Fix `gestor_billetera.py` — `ultima_actualizacion` no se actualizaba | Commit `3825d50` |
| 22-ago | Fix `reconciliar.py` — polvo bajo 1 tick descartado en silencio | Commit `3760b6b` |
| 24-ago | Reorganización de archivos sueltos del home (fuera de `bot-padre-v2/`) | 46 ítems movidos, nada borrado — ver cola #3, #4 |

## REGLAS PERMANENTES

Metodología acumulada de toda la serie de investigaciones — aplicar sin que haga falta repetirla.

1. **Evaluar mecanismos de salida con precisión de 1h (o más fina), nunca solo con el cierre de
   4h.** La evaluación gruesa infla sistemáticamente los resultados — visto en detector de vela
   fuerte (+67pp a 4h → ~0 a 1h), Prueba D (PF 2.1 a 4h → 1.5 o negativo a 4min real), TP
   postergado.
2. **No concluir de una ventana con n<30** (n<10 para descartar de plano). Muestras chicas generan
   "hallazgos" que se revierten con más datos — pasó 4 veces esta sesión (mtf SOL LATERAL, eventos
   SOL LATERAL, horario×calidad, fix memoria por símbolo).
3. **Un mecanismo con "piso"** (nunca puede cerrar peor que el baseline) **hace que el bootstrap
   "no cruce cero" de forma mecánica, no como evidencia real** — el criterio que decide en esos
   casos es la dependencia de outliers (top-3/top-5 como % del efecto total), no el IC.
4. **Contar eventos de calendario únicos, no solo trades**, cuando varias monedas pueden compartir
   la misma vela/fecha de disparo (ej. 2026-08-19 en BTC/ETH/SOL a la vez) — son el mismo evento de
   mercado, no observaciones independientes.
5. **Verificar el bug de offset de timestamps (UTC-4)** antes de confiar en cualquier hallazgo
   basado en la hora del día — ya invalidó 1 hallazgo (horario×calidad) y afectó la confianza en
   otros 2.
6. **Antes de asumir el valor de un parámetro de producción, comprobar con grep si el francotirador
   importa `config_cartera.py` o lo tiene hardcodeado** — confirmado que difieren para BTC.
7. **Mirar siempre mediana y % del top-5, no solo media/PF** — una media/PF positivos empujados por
   una cola de outliers no son un candidato.
8. **Walk-forward de mínimo 3 ventanas, y out-of-sample real (forward) cuando exista** — el
   candidato BNB mostró que un backtest 🟡 prometedor puede volverse negativo en forward real 2026.
9. **Reusar datasets `evaluar()`/`revisar_cierres()` literal ya validados en vez de recalcular** —
   criterio aplicado en toda la serie de gates de esta sesión.
10. **Bootstrap no pareado cuando los conjuntos de entrada difieren entre variantes; pareado cuando
    comparten timestamps exactos** — usar el que corresponda según el solapamiento real, no asumir
    uno fijo.
11. **α ajustado por Bonferroni cuando se prueban múltiples variantes/comparaciones a la vez**, no
    un α fijo para toda la sesión.
12. **Cerrar todo reporte con "qué no se hizo"** (no se tocó producción, no se activó nada, no se
    hizo commit).
