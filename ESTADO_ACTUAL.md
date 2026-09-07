# Estado actual — Z-Bot Padre v2

Índice central de estado del proyecto. Complementa a `INDICE_RESULTADOS.md` (tabla de todos los
backtests) y a `CLAUDE.md`/`INVESTIGACION.md` (contrato técnico e historial completo). Este
archivo responde "¿dónde estamos hoy?" en un vistazo — no reemplaza a los otros tres, los resume.

**Protocolo de actualización — la regla vive en `CLAUDE.md` desde 2026-09-02.** Ninguna
investigación se cierra sin actualizar este archivo (sección "CERRADO RECIENTEMENTE", y
"COLA DE INVESTIGACIÓN" si corresponde), sin su fila en `INDICE_RESULTADOS.md`, y sin cargar
sus números en `data/resultados.db`.

---

## EN PRODUCCIÓN AHORA

- **Modo:** REAL, `BOT_REAL_CONFIRMADO=true` activo (llave persistente en
  `~/.bot_real_confirmado`, sobrevive reinicios — verificado en vivo 2 veces, corte real incluido).
- **Capital nominal:** $20.00 USDT. USDT libre: $10.78 (al 2026-08-24).
- **Combo O activado en producción — 24-ago.** `director_orquesta.py` ahora llama 4
  francotiradores (antes 3): SOL pasó de LATERAL-solo a ALCISTA+LATERAL (según fase local, mismo
  patrón que BTC/ETH), y se sumó AVAX (ALCISTA+LATERAL+BAJISTA, este último inerte por el gate
  global de bajistas). Backtesteado como "Combo O" en el torneo (Sharpe 4.060 vs 2.62 de la config
  anterior). Diagnóstico completo, diff y verificación en vivo:
  `2026-08-25_diagnostico-cambio-produccion-avax-sol.md`, `2026-08-25_diff-final-combo-o.patch`.
  - **BTC ALCISTA** — RSI 50-70, SL 3.5%, TP 6.0%, EMA 20/50, `MAX_OP_TOTAL=1`, `MONTO_FIJO=$5`.
  - **ETH ALCISTA** — RSI 60-75, SL 4.5%, TP 5.0%, EMA 20/100, `MONTO_FIJO=$5` hardcodeado.
  - **SOL ALCISTA/LATERAL** — RSI 50-70/43-57. **Cambio de sizing 24-ago**: pasó de
    `CAPITAL_MAX_POR_OP=2%` a `MONTO_FIJO=$5` (mismo patrón que BTC), con chequeo previo contra
    `MONTO_MINIMO_BINANCE` antes de reservar fila — ver siguiente punto, era un bloqueador real.
  - **AVAX ALCISTA/LATERAL** — RSI 50-70/43-57. Mismo fix de sizing que SOL (idéntico código salvo
    símbolo). Primera vez conectado a producción.
  - Posiciones abiertas: BTC ALCISTA ($5, desde 2026-08-23) y ETH ALCISTA ($5, desde 2026-08-22) —
    sin cambios por este despliegue, verificado con snapshots antes/después en
    `reports/snapshots_combo_o/` (no versionados, gitignored).
- **⚠️ Bloqueador de capital corregido, no solo detectado.** SOL/AVAX ALCISTA calculaban el monto
  como 2% del capital libre — con capital real (~$10-20) eso daba ~$0.20-0.40/trade, por debajo del
  mínimo de Binance ($5) que exige `ejecutor.py` (`MONTO_MINIMO_BINANCE=5.0`), así que toda señal
  quedaba rechazada en silencio (fila `ANULADA`). El torneo no lo detectó porque backtesteó con
  capital simulado de $100,000 (`sistema_c/torneo_generico.py`), donde 2% = $2,000. Corregido a
  `MONTO_FIJO=5.0` en ambos francotiradores, mismo patrón que BTC/ETH.
- **`gestor_correlacion.py` — `MAX_TRADES_MISMA_DIR=2`, sin tocar (decisión explícita de Ariel).**
  Con los 4 francotiradores ahora ALCISTA, nunca va a haber más de 2 posiciones ALCISTA abiertas a
  la vez en todo el sistema — el 3er/4to intento se bloquea ahí, no por falta de señal. Verificado
  en vivo el primer ciclo post-activación (AVAX bloqueado por este gate con BTC+ETH ya abiertos).
- **Telegram — 2 mejoras chicas, 24-ago:** `/consejero` ahora muestra una línea inicial
  "🎯 Francotiradores activos: BTC-ALC, ETH-ALC, SOL-ALC/LAT, AVAX-ALC/LAT" (constante hardcodeada,
  actualizar a mano si cambia el wiring); `/disparos` ahora muestra "⏱️ Última operación: hace Xd Xh"
  por moneda (última fila `ABIERTA/TP/SL/TRAILING_SL/BE` en `auditoria.csv`, agrupado por symbol),
  para detectar francotiradores inactivos demasiado tiempo. Diseño y diff:
  `2026-08-25_diseno-tiempo-sin-operar.md`, `2026-08-25_diff-tiempo-sin-operar.patch`.
- **Bajistas:** los 5 desactivados por gate global (`gestor_bajistas.py`, falta de capital en
  Futuros — no por mal resultado, ver Fase 3 del torneo: el grupo BAJISTA combinado da PF 1.074,
  positivo, con AVAX BAJISTA como 2° mejor francotirador de los 15).
- **BNB:** sigue huérfano — código completo (3 fases sin pausa interna) pero
  `director_orquesta.py` no lo llama. Nota nueva: sus 11 filas históricas en `auditoria.csv` son
  todas `ANULADA` — nunca ejecutó un trade real ni siquiera cuando estuvo conectado (mismo
  bloqueador de sizing que SOL/AVAX tenían, nunca corregido para BNB porque sigue desconectado).
- **`config_cartera.py` no es fuente de verdad universal** — BTC ALCISTA lo ignora por completo
  (RSI/SL/EMA hardcodeados, distintos de lo que dice ese diccionario). ETH, SOL y AVAX ALCISTA sí
  leen RSI/EMA de ahí en vivo (el monto ya no, ver fix de sizing arriba).

## 🔬 laboratorio/ — los chequeos permanentes del simulador (desde 07-sep)

Dos scripts que **se vuelven a correr cuando haga falta** y **fallan con exit code** si algo se
rompió, así que sirven para CI:

- **`laboratorio/verificar_datos.py`** (L1) — huecos, duplicados, OHLC imposible, cruce entre las dos
  fuentes, muestra contra Binance, e impacto de los huecos sobre las ventanas ya registradas.
  Correrlo tras actualizar `data_1m/` o el backup 4h.
- **`laboratorio/verificar_reproducibilidad.py`** (L2) — el mismo tramo cambiando una cosa por vez.
  Correrlo tras tocar el simulador.

**L2 · Reproducibilidad: los 4 tests pasan** (misma corrida ×2 · distinto `PYTHONHASHSEED` ·
distinto `--tmpdir` · bandera obsoleta no-op). El test B era el que valía: el orden de `SYMS` **sí**
cambia con la semilla de hash, pero **el resultado no depende de eso** — medido, no razonado.

⚠️ **El asterisco, y no es menor:** eso prueba reproducibilidad *el mismo día, en la misma máquina,
con los mismos datos*. **No a lo largo del tiempo.** `FECHA_FIN = datetime.now()` y las velas de 4 h
se bajan frescas en cada arranque: la Tarea 1A y `CONTROL4H` corrieron con **19.823 vs 19.826 velas**
por unas horas de diferencia.

**Resuelto con una huella de datos** en cada resultado (`_huella_datos`): velas y rango por moneda +
**md5 de los 5 `.npy`**, calculada una vez al arranque (~2,7 s para 1,45 GB). Ahora dos corridas que
difieren se pueden distinguir entre **"cambió el simulador"** y **"cambiaron los datos"** — que hasta
hoy era indistinguible.

## 🔧 L1 · Integridad de datos — el backup 4h estaba corrido 4 h, ya está corregido (07-sep)

**Los datos siempre estuvieron bien; las etiquetas de tiempo del backup, no.** Cada fila de los CSV
de `~/bot-padre-v3-backup/data/historico_4h/` decía ser **4 horas más temprano** de lo que era.

Detectado cruzando dos fuentes independientes: los `data_1m` agregados a 4 h contra el backup.
Diferían en el 98,5–99,2 % de las velas. Probando desplazamientos, `backup[t] == 1m[t+4h]` con
**mediana 0,000000 % y 100,0 % de velas iguales**.

**Corregido en la fuente el 07-sep** (los 13 CSV, +4 h por fila, precios intactos). Verificado
después: las dos fuentes coinciden al **100 %**. Respaldo en `historico_4h_pre_correccion_desfase/`
y una marca que impide aplicarlo dos veces — **una segunda pasada dejaría los datos +8 h**.

**Por qué se corrigió en la fuente y no con una bandera:** de los **58 `.py` que leen ese backup**,
**35 no corregían nada** y **9 sólo ajustaban el índice de inicio** (la ventana quedaba bien, las
horas seguían mal por dentro). **Ninguno de los 58 tenía los timestamps correctos.** Una bandera
opcional deja el error a un olvido de distancia.

- Se quitó la compensación de los **9** de `sistema_c/` (Uso A).
- **No se tocaron los 6** que usan `hours=4 * velas` para calcular duración (Uso B) — no tienen relación.
- La bandera `--corregir-desfase` del sandbox quedó como **no-op**, no eliminada: 4 lanzadores la
  pasan y los checkpoints reanudables la llevan en su firma. Verificado: con y sin ella, resultado idéntico.

⚠️ **Esto NO altera ningún resultado ya registrado** — los estudios viejos corrieron con los datos
como estaban. Lo que cambia es que **de acá en adelante todos leen la hora correcta**. Si se rehace
un estudio viejo dará distinto en lo que dependa de la hora, y eso es lo correcto.

### Lo demás que midió L1

**Los `data_1m` son exactos**: 48/48 velas de muestra idénticas a la API de Binance, y las **15,8 M
de velas** con OHLC coherente (cero duplicados, cero timestamps hacia atrás, ninguna con `high<low`).

**Huecos: 20.153 minutos = 0,097 %** del total. Caen dentro del torneo (0,43 % de la ventana), los 12
gates (0,43 %) y el ensanchado de TP/SL (0,41 %); **cero en los 8 escenarios del Ítem 2**. Decisión:
**no rellenarlos** — un precio interpolado puede disparar un TP que nunca existió.

## 🔴 El bot opera en la fase MÁS QUIETA del mercado y está ciego 73–85% del año (07-sep-2026)

Medido sobre 2026 completo: 89.516 ciclos de 4 min, 248,7 días, fase **LOCAL** de cada moneda —que
es la que despacha `director_orquesta.py:248`, no el voto global.

### Cobertura real: sólo hay francotiradores ALCISTA activos

| Moneda | ALCISTA | LATERAL | BAJISTA | Días operables (de 248,7) |
|---|---|---|---|---|
| ETH | **27,0 %** | 48,7 % | 24,3 % | 67,1 |
| BNB | 25,3 % | 51,3 % | 23,4 % | 62,8 · *no opera, huérfano* |
| BTC | 22,6 % | 56,3 % | 21,1 % | 56,2 |
| SOL | 17,9 % | 64,6 % | 17,5 % | 44,4 |
| AVAX | **14,9 %** | 60,1 % | 24,9 % | **37,2** |

**El bot no puede operar entre el 73 % y el 85 % del año.** AVAX, con dinero real, tiene fase
ALCISTA sólo 37 de 249 días.

### ✅ Confirmado con 2021–2025: la cobertura NUNCA supera el 41 %

| Año | ALCISTA promedio de las 4 que operan |
|---|---|
| 2021 | **41,0 %** ← el mejor |
| 2022 | **14,5 %** ← el peor |
| 2023 | 33,9 % |
| 2024 | 30,1 % |
| 2025 | 20,4 % |
| 2026 | 20,6 % |

**En seis años el bot nunca pudo operar más del 41 % del tiempo.** Incluso en el mejor año estuvo
ciego el 59 %; en el peor, el 85,5 %. Promedio de los seis: 26,8 %.

⚠️ 2026 (20,6 %) está **por debajo** del promedio: el rango real es **14,5 %–41,0 %**, no el
"15 %–27 %" que sugería medir sólo 2026.

### ⚠️ CORREGIDO — lo de BAJISTA era un dato de 2026, no un patrón

Se registró el 07-sep que *"BAJISTA tiene 40 % más rango y 46 % más volumen que ALCISTA"*. **Con
2021–2025 eso no se sostiene:**

| Año | rango BAJISTA / ALCISTA | |
|---|---|---|
| 2021 | 0,94× | ← se invierte |
| 2022 | 1,27× | |
| 2023 | **0,65×** | ← se invierte fuerte |
| 2024 | 1,10× | |
| 2025 | 1,22× | |
| 2026 | 1,40× | ← el año que se había medido |

**Sólo 4 de 6 años.** En volumen es peor: 0,52× en 2021 y 0,44× en 2023. **No usar ese dato como
argumento para investigar BAJISTA.**

### ✅ Lo que SÍ se sostiene: LATERAL es la mayor parte del año

**5 de 6 años** LATERAL tiene más velas que ALCISTA (hasta **2,93×** en 2022), con rango entre
**0,62× y 0,93×** (mediana 0,89×). La mayor parte del año, con movimiento apenas menor. **Éste es
el hallazgo robusto de los tres**, y es el que sostiene el Ítem 2c.

### ⚠️ ALCANCE de todo el trabajo anterior sobre francotiradores ALCISTA

**El torneo de francotiradores, la auditoría de los 12 gates y el ensanchado de TP/SL midieron una
estrategia que sólo puede actuar ~1/5 del año.**

**No quedan invalidados** —las comparaciones entre configuraciones ALCISTA siguen valiendo entre
sí— pero **su alcance está acotado a esa ventana**. Cualquier proyección de rendimiento anual a
partir de ellos hereda ese techo.

### Qué dispara los cambios de fase (para saber dónde aplicar histéresis)

`cambio_7d` **55,1 %** de los cruces que cambian la fase · `cambio_30d` **31,6 %** ·
`precio vs EMA200` **13,3 %**. Una histéresis sobre 7 días cubre la mitad del problema; para llegar
al 87 % hay que aplicarla también al de 30 días.

Detalle: `reports/2026-09-07_item2bc-condiciones-y-cobertura.md`.

**Nota de negocio, NO tarea de código:** activar BAJISTA en real exige reescribir `ejecutor.py` para
Futuros (hoy `cerrar_posicion` cierra shorts con BUY spot) **y** abrir esa cuenta. Es decisión de
Ariel, independiente de investigar el valor potencial. **LATERAL, en cambio, es operable en SPOT hoy
mismo** y es el 48–65 % del año.

## 🔴 El bot casi no está operando su estrategia (medido 07-sep-2026)

**En 2026, el 89% de los cierres del bot son por cambio de fase global, no por TP ni por SL.**
Simulación de 2026 completo a 4 minutos, con el simulador ya corregido: **210 de 237 cierres** son
`FASE_CAMBIO`. Sólo 27 llegan a TP o SL.

El voto de `detectar_fase_global()` —5 monedas, y basta que 2 dejen de estar ALCISTA para que caiga
a LATERAL— barre las posiciones antes de que la lógica de TP/SL tenga ocasión de actuar. Causa
mecánica: el umbral duro sin histéresis de `detectar_fase()` (`utils.py:92`, `cambio > 1.0`),
evaluado cada 240 s.

> **Los 8 escenarios probados dan EXACTAMENTE 12 TP.** Apagar el churn de 210 cierres a 24 (−89%)
> no hace que **ni una sola** operación más llegue al take profit. Los trades que el mecanismo
> cierra no son trades que iban a ganar.

### Estado: 🟡 NO CONCLUYENTE — decisión abierta, NO archivada

Las 3 soluciones se midieron juntas (8 combinaciones) y **ninguna es significativa**: los 7 IC 95%
cruzan el cero. La mejor (zona muerta 0,25) da +$2,83 con P(mejor)=80,1%. Los 8 pierden plata
(PF 0,603–0,774): la mejor reduce la pérdida de −$12,22 a −$9,38.

**Esto NO se archiva como "no sirve".** No es una apuesta de rendimiento que falló: es un **defecto
de diseño real** — hoy el bot cierra posiciones que su propia lógica de entrada considera válidas.
Lo que falta no es voluntad, es evidencia.

**⚠️ QUÉ FALTA PARA DECIDIR DE VERDAD:**

> **Medir el impacto del cambio de duración por trade sobre el perfil de riesgo.** Las soluciones
> alargan mucho el trade medio: **14,9 h** en el baseline → **32,3 h** con la zona muerta →
> **83,0 h** con las tres. Eso cambia el drawdown máximo y la exposición simultánea, y **este
> estudio no lo midió**. Sin ese número no se puede aprobar ni rechazar: se estaría cambiando el
> perfil de riesgo del bot a ciegas.

Detalle: `reports/2026-09-07_item2-paso2-ocho-escenarios.md`.

**Y más grande que el ítem:** con PF 0,774 en el mejor caso, el problema no es sólo el director.
Antes de seguir parcheando `cerrar_huerfanas()` corresponde preguntarse por qué la fase global
cambia 200+ veces en 8 meses.

## 🛑 LEER ANTES DE CITAR CUALQUIER BACKTEST DE ESTE ARCHIVO (06-sep-2026)

**El simulador tenía tres fallos de fidelidad. Todo resultado anterior al 06-sep-2026 los arrastra.**
Esto no invalida el historial, pero cambia cómo hay que leerlo. Si venís de otra sesión o de otra
herramienta y no tenés el contexto: esto es lo que necesitás saber, no hace falta reconstruir nada.

**La causa raíz es una sola, y ya estaba documentada el 03-sep para el RSI:** el bot real evalúa cada
240 s y ve la **vela de 4h EN CURSO**; el simulador miraba **velas cerradas**. Apareció en tres
lugares distintos:

| # | Fallo | Efecto medido | Estado |
|---|---|---|---|
| 1 | La fase de despacho (`_pop_gate` → `_fase_actual`) usaba velas cerradas | El simulador abría **5 veces** donde producción intentó **190** en la misma ventana | ✅ corregido 06-sep |
| 2 | `_f_urlopen` **ignoraba el parámetro `interval`**: servía velas de 4h aunque le pidieran 1h o 1d | `detector_multitimeframe` comparaba **tres veces la misma serie**. Era el bloqueo dominante: **2.380 → 644** tras el fix | ✅ corregido 06-sep |
| 3 | `data_1m/` desactualizado (terminaba el 04-sep) y **sin BNB**, que entra en el voto de fase global | Recortaba la ventana de simulación **en silencio**; el voto se calculaba sobre 4 monedas en vez de 5 | ✅ corregido 06-sep |

**Qué significa en la práctica:**

- **Las comparaciones RELATIVAS entre estrategias siguen valiendo**: todas se midieron con el mismo
  simulador y el mismo sesgo.
- **Los niveles ABSOLUTOS están sesgados a la baja en frecuencia.** El simulador subestimaba cuántas
  veces se opera. Cualquier cifra de "trades por semana" o "operaciones al mes" anterior al 06-sep
  es un piso, no una medición.
- **Los fallos 1 y 2 sólo afectan al modo `--paso 4m`.** A 4 horas cada paso ES una vela cerrada, así
  que no hay "vela en curso" que perder. Los backtests a 4h no los sufren — pero sí sufren lo del
  hallazgo de abajo (sobreestiman el resultado).
- **Correcciones aplicadas en `~/tarea1a_4m/sandbox_director.py`.** `sandbox_multi_fix.py`, el que
  midió la Tarea 1A, **todavía las tiene**: rehacer esa prueba con el simulador corregido.

Detalle completo: `reports/2026-09-06_item2-paso1-fidelidad.md` y la auditoría que ya había
señalado la causa raíz, `reports/2026-09-03_tarea1-auditoria-confiabilidad-simulador.md`.

**Fidelidad tras corregir**, contra las 2.316 líneas `ORQUESTA` que el bot dejó en `eventos.log`:
fase global coincide en el **87,3%** de los ciclos (510/584) y produce **31 transiciones contra 33
reales**. El modelo sirve para comparar soluciones entre sí; **sobreestima los cierres forzados un
14%**, así que no se le pueden pedir números absolutos.

## ⚠️ Hallazgo transversal 06-sep — los backtests a 4h sobreestiman

**Tarea 1A cerrada.** El bot real evalúa cada 240 s (`sleep_segundos`), o sea cada 4 minutos; todos
los backtests de este índice se corrieron a 4 horas. Simular a la resolución real da **PF 1.202
contra 1.384**, y WR **45.7% contra 49.7%**, con 81.5% más trades. Consistente en las 4 monedas, sin
una sola excepción.

Mecanismo medido: los 1.204 trades que **sólo** aparecen a 4m rinden PF 1.142, contra PF 1.606 de los
215 que ambas resoluciones ven. Mirar más seguido no encuentra mejores oportunidades: encuentra más
oportunidades mediocres.

**Cómo leer el resto de este archivo a partir de ahora:** las comparaciones *relativas* entre
estrategias siguen valiendo (todas se midieron igual), pero el **nivel absoluto está inflado**. Antes
de aplicar cualquier cambio que dependa de cruzar el umbral PF ≥ 1.6, revalidarlo a 4 minutos.

Detalle: `reports/2026-09-06_tarea1a-4m-vs-4h-comparacion.md`.

## COLA DE INVESTIGACIÓN

Ordenada por prioridad/impacto potencial, no por fecha.

1. ~~Decisión pendiente — ¿reemplazar/ampliar la config de producción?~~ **Resuelto 24-ago: Combo O
   activado en producción** (ver "En producción ahora"). Nota viva: el peor caso teórico de $20
   simultáneos (4×$5) en la práctica queda capado en $10 por `MAX_TRADES_MISMA_DIR=2`, que sigue sin
   tocarse — así que la exposición real hoy es menor a la backtesteada como "worst case".
   Pendiente de observación: **N** (BTC+ETH+AVAX-BAJISTA, Sharpe 3.96) seguía siendo mejor que O,
   pero requiere Futuros — no descartado, solo fuera de alcance sin esa cuenta.
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
10. **Fase B de correlación entre monedas — rediseño pendiente.** Con la ventana de 3 velas
    antes/después pedida, 0/40 combinaciones llegan a n≥30 casos de alerta (máx. observado 7) — las
    posiciones duran muy pocas velas frente a la escala diaria del criterio de tendencia. Un diseño
    distinto (sin el requisito de margen, o con ventana fija post-entrada en vez de vela a vela
    hasta el cierre) podría generar más muestra, pero es una pregunta distinta a la ya cerrada. Ver
    `2026-08-25_correlacion-5-monedas-fase-ab.md`.

## CERRADO RECIENTEMENTE

Más reciente primero. Ver `INDICE_RESULTADOS.md` para el detalle de métricas de cada uno.

| Fecha | Investigación | Veredicto |
|---|---|---|
| 02-sep | Ensanchar TP/SL de los 4 francotiradores activos (1.5× y 2×, más variantes asimétricas) | 🟡 Prometedor, **no aplicar todavía** — mejora en las 4 monedas y en las 3 ventanas del walk-forward, pero el bootstrap cruza cero (P(mejor) 83%) y el máximo PF es 1.444, bajo el umbral 1.6. Falta repetirlo con los 12 gates. Ver `2026-09-02_backtest-sl-tp-ensanchado-y-montos.md` |
| 02-sep | Combinaciones de monto por moneda con $36.86 de capital | 🔴 Dejar 10/7/7/7 — desbalancear por ratio ganancia/pérdida es el peor de 5 combos (el ratio no predice: ETH con 1.02 rinde el doble por dólar que BTC con 1.57), y usar ~$36 deja una zona muerta silenciosa entre $33.79 y $36 donde la 4ª moneda no abre |
| 02-sep | **[INFRAESTRUCTURA]** Base de datos consultable de resultados (`data/resultados.db`) + regla permanente de indexado en `CLAUDE.md` | Aplicado. 94 pruebas cargadas: 74 del índice histórico + 20 del backfill 25-ago→02-sep. Consultas con `python3 consultar.py`. Ver `2026-09-02_diseno-db-resultados-y-regla-indice.md` |
| 01-sep | Riesgo real por operación y margen para subir el monto | Informativo — arriesga **0.79% del capital** por operación ($0.29 de un ticket de $7). El límite para subir el monto es el capital, no el riesgo. Ratio ganancia/pérdida: BTC 1.57, **ETH 1.02**, SOL 1.62, AVAX 1.62 |
| 31-ago | **[PRODUCCIÓN]** Puntos ciegos del camino del dinero | Aplicado: BTC `MONTO_FIJO` $7→$10 y validación de `status` en `ejecutor.py` (rechazo definitivo vs `OrdenIncierta`), 14/14 escenarios simulados correctos |
| 31-ago | Auditoría económica del trailing — conectar `trailing_stop.py` | 🔴 Descartado — PF 0.583 vs 0.919 actual, mata 152 de 168 TP, WR 42.1%→29.4% |
| 31-ago | Fix B — breakeven y trailing anclados al máximo (12 combinaciones) | 🔴 Descartado — la mejor da PF 1.00 vs 0.98 actual; ninguna llega al umbral 1.6 |
| 31-ago | Termómetro — impacto económico de reconectarlo | 🔴 Descartado — bloquearía 31.9% del tiempo (66.2% en agosto) y habría cortado 4 de las 8 operaciones reales (costo $0.34) |
| 31-ago | `cerrar_huerfanas()` — fase GLOBAL vs LOCAL (222 divergencias + las 8 ops reales) | 🔴 No se corrige (decisión de Ariel, 31-ago) — impacto realizado $0.00, IC95% cruza cero, drawdown 5.8× mayor |
| 31-ago | Auditoría de arquitectura y conexiones — 4 conexiones rotas | Documentadas, **no reparadas**: efecto económico cero o negativo en las 4 (termómetro, centinela, trailing huérfano, fase global/local) |
| 30-ago | Aporte individual del combo O (5 escenarios) + walk-forward de 3 ventanas | Las 4 monedas aportan: sacar cualquiera baja el PnL total. "Sin BTC" gana en las 3 ventanas pero no se aplicó |
| 30-ago | **[PRODUCCIÓN]** Subir `MONTO_FIJO` $5 → $7 | Aplicado — con $5 el `minNotional` de Binance bloqueaba los cierres; 0 bloqueos del guardián de entrada en 1,648 señales reales |
| 24-ago | **[PRODUCCIÓN]** Activación Combo O — SOL ALCISTA+LATERAL, AVAX conectado por primera vez | Aplicado y verificado en vivo. Diagnóstico previo detectó bloqueador crítico (sizing SOL/AVAX por debajo del mínimo Binance) antes de tocar nada; corregido a `MONTO_FIJO=$5` en ambos. Posiciones BTC/ETH abiertas intactas (snapshots antes/después). Ver `2026-08-25_diagnostico-cambio-produccion-avax-sol.md`, `2026-08-25_diff-final-combo-o.patch` |
| 24-ago | **[PRODUCCIÓN]** Telegram — línea de francotiradores activos (`/consejero`) y tiempo sin operar (`/disparos`) | 2 cambios chicos aplicados y verificados. `/disparos` reusa infraestructura existente (no comando nuevo) — extiende el loop por moneda ya presente. Ver `2026-08-25_diseno-tiempo-sin-operar.md`, `2026-08-25_diff-tiempo-sin-operar.patch`, `2026-08-25_diff-linea-francotiradores-telegram.patch` |
| 25-ago | *(proyecto separado, `~/experimento_director_adaptativo/`)* BNB — ¿caída de BTC como señal de ENTRADA? (3 variantes: inmediata, 1 vela después, gate adicional) | 🔴 Descartado, las 3 variantes. Entrada inmediata peor que la real (WR 42.3% vs 45.3%, PF 0.982); con 1 vela de espera queda empatada (no significativo, Δ−0.06% IC95%[−1.13,0.99]); como gate adicional mejora en el punto central (+0.98% vs −0.03%/trade) pero no significativo (IC95%[−1.30,3.25]) y sin consistencia año a año (n=1-3 en varios años). El rebote de 24h es real pero chico (mediana +0.88%) frente al TP real (6.5%) — no sobrevive a un trade completo. Ver `experimento_director_adaptativo/reports/2026-08-25_bnb-entrada-tras-caida-btc.md` |
| 25-ago | *(proyecto separado, `~/experimento_director_adaptativo/`)* Profundización BTC→BNB (par más consistente del ranking de correlación) | Hallazgo contrario a la hipótesis: BTC cae ≥3%/24h → BNB tiende a **rebotar** (mediana +0.88%, bootstrap significativo IC95% [0.21,1.33], consistente 9/10 años), no a caer con él. BTC sube fuerte no muestra reacción significativa. No sirve como señal de aviso para cerrar BNB — sugiere lo opuesto. Profundizado en la fila de arriba (como señal de entrada, también descartado). Ver `experimento_director_adaptativo/reports/2026-08-25_btc-lidera-bnb.md` |
| 25-ago | *(proyecto separado, `~/experimento_director_adaptativo/`)* Director adaptativo Fase 1+1B — cambiar dinámicamente entre A y O según fase global de mercado, 9 combinaciones de ventana/líder/frecuencia | Descartado en 8 de 9 combinaciones — pero **ventana 150 + voto 5 monedas + revisión diaria SÍ supera a O fijo** (Sharpe 4.336 vs 4.060, PnL $50.40 vs $47.84, mejor racha), con el trade-off de peor drawdown (−14.62% vs −12.92%). No es una tendencia general de "detectar más rápido = mejor" — es una combinación específica frágil. Ver `experimento_director_adaptativo/reports/2026-08-25_fase1-viabilidad.md` y `-fase1b-deteccion-rapida.md` |
| 25-ago | Perfil de perdedoras + circuit breaker (A y O, $20 real) | Sin señal de aviso previo clara (RSI/volumen/ATR de entrada casi iguales ganadoras/perdedoras); circuit breaker (3 pérdidas→pausa 7 días) mejora DD en ambas pero es mixto (cuesta $ en A, empeora la racha máxima en O); mayor parte del costo viene de rachas cortas (1-3), no largas |
| 25-ago | Recálculo A vs. O con capital real ($20) | Ganancia en $ idéntica en cualquier capital base ($24.03/$47.84, `MONTO_FIJO` fijo); WR/PF/Sharpe/racha invariantes; DD%/retorno%/peor30d% sí cambian (DD de O sube a −12.92% con $20); O requiere hasta $20 simultáneos (4 francotiradores × $5), sin margen libre hoy |
| 25-ago | Torneo de francotiradores — Fase 2 (10 combinaciones nuevas, 3 y 4 francotiradores) | O (4 francotiradores, 100% SPOT) supera a B en Sharpe y retorno; N (con AVAX bajista) sigue siendo el mejor de 3 pero requiere Futuros; ninguna significativa vs A/B (ver cola #1) |
| 25-ago | Correlación 5 monedas — Fase A (entradas) y Fase B (posiciones abiertas) | Fase A: ninguna de 40 combinaciones significativa (IC cruza cero en las 22 que pasan el filtro); Fase B: no evaluable, 0/40 combos llegan a n≥30 (máx. observado 7) — limitación estructural, no resultado nulo (ver cola #10) |
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
