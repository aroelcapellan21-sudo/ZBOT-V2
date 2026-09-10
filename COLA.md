# Cola de trabajo — Z-Bot Padre v2

**Última actualización: 2026-09-09 (Claude Code)**

> ⚠️ **FUENTE DE VERDAD ÚNICA.** Este archivo vive en el repo (`~/bot-padre-v2/COLA.md`), se
> versiona en git y se sincroniza solo a Drive junto con `reports/`.
>
> **Hasta el 09-sep había DOS colas con numeraciones distintas y sin un solo ítem en común:**
> `~/zbot-drive/cola/zbot-cola.md` (ítems 2-14) y la sección "COLA DE INVESTIGACIÓN" de
> `ESTADO_ACTUAL.md` (ítems 1-10). Sumaban 20 ítems abiertos que nadie veía juntos, y el trabajo
> de "revisar los hallazgos anteriores" estaba escrito **dos veces**. Decisión de Ariel el 09-sep:
> unificar acá. Las dos colas viejas quedan apuntando a este archivo; el original de Drive se
> conserva en `~/zbot-drive/cola/zbot-cola.md.bak_pre_unificacion`.
>
> **La numeración vieja se conserva entre paréntesis** (`ex Ítem 13`) porque los reportes ya
> escritos la citan.

**Regla fija:** una investigación a la vez, veredicto cerrado antes de pasar a la siguiente. Nada se
inserta antes de lo que ya está en curso, ni siquiera si Ariel lo propone en el momento.
✅ **Reafirmada el 09-sep**, cuando el ítem 2 podría haberse colado delante del 1 que está a un
tercio: se respetó el orden.

---

## En curso

**Nada.** La investigación de `cerrar_huerfanas()` —lo único que figuraba acá— se cerró y se
**aplicó** el 09-sep (commit `ade1ae0`). Ver "Ya cerrado".

Lo siguiente que se toma es el **ítem 1**.

## Orden confirmado por Ariel (09-sep)

> **1 (terminar Pruebas 2 y 3) → 2 → 3 (resolver la causa raíz, no sólo el síntoma) → 4 →
> 5, 6, 7, 8, 9, 10, 11, 12**, respetando la regla de no insertar nada delante de lo que está a
> mitad de camino.

## Cola de investigación, en orden

- [x] **1 · L11 — evaluación del laboratorio** *(ex Ítem 13)* — ✅ **CERRADO el 09-sep. 🔴 el
  laboratorio mide bien y elige mal.** Las tres pruebas están en "Ya cerrado".

- [x] **2 · Revisión de los hallazgos anteriores con las herramientas nuevas** — ✅ **CERRADO
  el 09-sep. 🟢 ninguno es candidato a reabrir.** Detalle en "Ya cerrado".

- [x] **3 · Auditoría de conexiones y sincronizaciones** *(ex Ítem 14)* — ✅ **CERRADO el
  09-sep. 7 de 8 conexiones sanas; el problema no era el estado sino la detección.**
  Detalle en "Ya cerrado".

- [ ] **0 · 🔴 ALTA PRIORIDAD — auditar los estudios pre-07-sep que usan `filtro_horario` con
  reloj inyectado** *(nuevo, 09-sep, sale de la reapertura del ítem 4)*

  **El canal de contaminación está confirmado, el alcance NO está medido.** Cualquier estudio
  anterior al fix de L1 (07-sep) que inyecte un reloj falso a `filtro_horario` evaluó la ventana
  **0-17 h en vez de 4-21 h**, porque los timestamps del backup 4h estaban corridos −4 h. Con velas
  de 4 h eso es **una vela exacta** de corrimiento, y el gate bloquea 1 de cada 6: **no bloqueaba de
  más ni de menos, bloqueaba la vela equivocada**.

  **Qué hay que hacer:**
  1. Listar **todos** los `.py` que hagan `filtro_horario.datetime = <reloj falso>` o equivalente.
     Se sabe de `torneo_generico.py` y los `resim_evaluar_literal_*`; **cuántos más hay, no está
     medido**.
  2. Cruzar con `data/resultados.db` por fecha: **toda prueba anterior al 2026-09-07** generada por
     esos scripts queda bajo sospecha.
  3. Decidir por bloque, no de a una: cuáles se rehacen y cuáles no dependen del gate horario.

  **Lo que ya se sabe y acota el problema:** un desfase uniforme **no altera el OHLC ni su orden**,
  así que RSI, EMAs y la mecánica de TP/SL son idénticos. `filtro_eventos` estaba anulado en el
  torneo. **El único canal verificado es el gate horario** — pero alcanza para mover el 16,7 % de
  las oportunidades.

  ⚠️ **Esto toca la credibilidad de una parte del índice, así que va antes que cualquier
  investigación nueva.** `reports/2026-09-09_item4-reabierto-desfase-4h.md`

- [x] **4 · Francotiradores para fase LATERAL** *(ex Ítem 2c)* — ✅ **CERRADO el 09-sep, ahora
  con datos limpios.** Rehechos 2 de los 4 estudios con el CSV corregido: el desfase mueve el
  PF **0,01-0,03** y **no cambia ningún veredicto**. Los otros 2 **no son reproducibles** (sus
  francotiradores se pausaron después, commit `5713c0a`) y se sostienen por margen: les faltan
  +0,599 y +0,557 para el umbral, o sea **16-18× el mayor efecto medido**.
  `reports/2026-09-09_item4-rehecho-con-datos-limpios.md`

- [ ] **0b · 🆕 Estudios irreproducibles por cambios de código posteriores** *(09-sep, sale del ítem 4)*
  `torneo_avax_lateral` y `sol_lateral_evaluar_literal_2020_2026` **ya no se pueden rehacer**: sus
  francotiradores se pausaron por código el 29-ago (commit `5713c0a`) y los estudios son del 22-23,
  así que hoy el torneo importa la función desactivada y devuelve **n = 0**.
  **No es un problema de datos** —eso es el ítem 0— **sino de que el código que medían cambió
  después.** Es el asterisco que L2 había dejado anotado (*"prueba reproducibilidad el mismo día, no
  a lo largo del tiempo"*) apareciendo en la práctica. **Cuántos estudios más están en esta
  situación, no está medido.** Salida posible: correrlos contra una copia parcheada del
  francotirador, sin tocar producción.

- [ ] **4b · Survivorship bias — identificado el 09-sep, NO medido** *(sale de la Prueba 3)*
  Las 5 monedas del bot se eligieron entre las que **hoy** están arriba, y nunca se testeó
  sobre monedas que se hundieron o salieron del top. La "segunda lista" (XRP, LINK, UNI,
  NEAR, ADA) arrastra el mismo sesgo. Es una de las **dos sins graves** que quedaron abiertas.
  Sin número todavía: nadie sabe cuánto infla los resultados registrados.

- [ ] **5 · ¿El cupo `MAX_OP_TOTAL` 1→2 depende de un año bueno?** *(ex Ítem 3)* — verificar por año
  antes de aplicarlo. ⚠️ Ojo con lo ya medido: `MAX_TRADES_MISMA_DIR=2` topa el bot en 2 posiciones
  totales, así que subir `MAX_OP_TOTAL` solo no alcanza.

- [ ] **6 · Sensibilidad del RSI en subidas fuertes** *(ex Ítem 4)* — entradas tardías tras enfriarse
  desde arriba contra entradas normales desde abajo.

- [ ] **7 · ¿El guardián de riesgo se acercó alguna vez al 10 % de drawdown?** *(ex Ítem 5)*
  ⚠️ **Dato nuevo del 09-sep:** en simulación de 6 años lo **supera** en las dos ramas —40,5 % con
  `cerrar_huerfanas()` y 17,7 % sin ella—. Falta la pregunta original: si el **real** se acercó.

- [ ] **8 · Evaluar "Confluencia 3-Filtros"** *(ex Ítem 6, propuesta externa)* — el filtro 1
  (volumen+calidad) es testeable en paralelo; los filtros 2 (multi-timeframe) y 3 (capital dinámico)
  dependen del resto. Las proyecciones del documento original (65-70 % WR, +25-35 % mensual)
  **no son referencia real**.

- [ ] **9 · Por qué BNB quedó huérfano** *(ex Ítem 7)* — francotirador programado y nunca llamado,
  mientras AVAX sí está activo. Ariel considera el patrón alcista de BNB más fiel que el de AVAX; no
  hay veredicto de que AVAX le haya ganado: BNB simplemente nunca se conectó.

- [ ] **10 · Exposición conjunta y candado de montos** *(ex Ítem 8)* — (a) medir la exposición de
  BTC/ETH/SOL/AVAX al **mismo** movimiento de mercado, en vez de tratarlas como 4 apuestas
  independientes (enlaza con la hipótesis de correlación 0,544 y con que caen juntas el 30 % de los
  meses); (b) verificar que **ningún componente pueda modificar montos sin autorización**.

- [ ] **11 · Cuántos movimientos fuertes hay por año y cuántos captura la estrategia** *(ex Ítem 10)*
  — por moneda, con umbral a definir, medido con el simulador honesto, para calcular expectativa
  real (no promesa) con capital chico y grande. Conecta con la cobertura del 15-41 % del año: la
  ganancia probablemente se concentra en pocos eventos fuertes, no en operar seguido.

- [ ] **12 · Evaluar motor-confluencia sobre su historial completo** *(ex Ítem 11)* — proyecto
  separado, capital simulado, multi-mercado. No sólo el dashboard reciente de 11 operaciones (9 % de
  win rate): calcular WR y PnL acumulado reales, y revisar si su "score de confluencia" comparte el
  problema ya confirmado en el radar de zbot (puntaje combinado sin valor predictivo, n=432.156).

## Mantenimiento y deuda técnica

*(Migrados el 09-sep desde la sección "COLA DE INVESTIGACIÓN" de `ESTADO_ACTUAL.md`, que tenía
numeración propia. **No bloquean la cola de investigación** y no compiten por su orden: se toman en
huecos.)*

- [ ] **M1 · Polvo inmovilizado** — 🟡 **corregido el 09-sep 17:40: en la cuenta NO hay polvo.**
  `/api/v3/account` da BTC = 0,0 real contra 6,916e-05 en `billetera.json`. El mecanismo es real
  (~$0,79 por vuelta = 8,2 % del ticket) pero **el saldo atrapado sólo existe en el archivo**.
  Dato útil: **cuando la comisión se paga en BNB el polvo deja de generarse** (se compra y se
  vende la cantidad redonda) y además abarata la comisión un 28 %. Hoy el BNB de la cuenta es 0.
  Ver `reports/2026-09-09_billetera-vs-binance-y-correccion-del-polvo.md`.
- [x] **M11 · `billetera.json` — ✅ CERRADO el 09-sep, las 3 decisiones resueltas** (prueba **301**)
  1. ✅ **Resincronizado.** USDT 23,3342 → **29,00757172** · BTC 6,916e-05 → **0,0** (el fantasma) ·
     AVAX 0,94176 → **0,86913**. `capital_inicial`, `capital_real` y `moneda_activa` preservados.
     Hecho bajo el **mismo `flock`** que usan `ejecutor.py` y `gestor_billetera.py`, con respaldo
     previo y escritura atómica; aborta si hay saldo bloqueado. ⚠️ Se corrigió un fallo de diseño
     propio antes de aplicar: la consulta a Binance iba **antes** del lock, dejando una ventana para
     que el bot operara en el medio. Verificado: el guardián calcula **$36,18** (antes $36,59
     inflado), DD 3,62 %, sin bloqueo. El saldo real de AVAX coincide **exacto** con la `qty` de la
     posición abierta.
  2. ✅ **BNB comprado** (autorizado por Ariel). `MARKET BUY 0.007 BNBUSDT` → **FILLED, $5,0501**,
     dos fills a $721,44, comisión 0,00000525 BNB **ya con el descuento aplicado**. ⚠️ No fueron $5
     exactos: el `stepSize` es 0,001 y el `NOTIONAL` exige $5,00 con `applyMinToMarket`, así que $5
     truncados dan 0,006 BNB = **$4,33** y la orden habría sido rechazada con `-1013`; 0,007 es el
     múltiplo inmediato superior que pasa. Hecho **bajo el `flock` de billetera** y **sin escribir
     en `auditoria.csv`** (no es una posición). USDT 29,0076 → **23,9575** · BNB 0 → **0,00699475**.
     El descuento ya estaba activado en la cuenta (`spotBNBBurn: True`): sólo faltaba el saldo.
  3. ✅ **Verificación automática.** `~/comparar_billetera.py` integrado al chequeo diario de las
     08:00; deja `ALERTA_billetera_*.md` en `reports/` si no coincide. Umbrales: USDT > $0,50,
     cripto > 2 % con mínimo absoluto. Probado en los dos sentidos (OK con la billetera actual,
     detecta las 3 diferencias con el respaldo previo). Un fallo de red no cuenta como
     desincronización.

  Reporte: `reports/2026-09-09_m11-billetera-resincronizada-y-verificacion.md`

- [ ] **M2 · `memoria_propia.json` no se actualiza** — causa ligada a `FASE_CAMBIO`, sin corregir.
- [ ] **M3 · SOL LATERAL, filtro de volatilidad k=2,0** — "prometedor no confirmado": el mejor
  resultado de la línea de volatilidad (PF 1,768, Sharpe 1,704, +$3,53) pero depende de **una sola
  ventana de 6 meses**. ⚠️ **Corregido el 09-sep (ítem 2): "re-testear cuando haya más historia
  de SOL" no alcanza.** Su baseline tiene SR +0,0096 por trade y necesitaría **29.281 trades**
  contra los 397 que tiene — 74× la muestra. Más historia no lo va a salvar.
- [ ] **M4 · Combo N** (BTC+ETH+AVAX-BAJISTA, Sharpe 3,96) — mejor que el combo O en backtest, pero
  **requiere Futuros**. No descartado: fuera de alcance sin esa cuenta.
- [ ] **M5 · Bajistas en Futuros** — el torneo confirma señal real (grupo BAJISTA PF 1,074), pero
  activarlos exige cuenta de Futuros **y reescribir `ejecutor.py:cerrar_posicion`**. No es tarea de
  backtest.
- [ ] **M6 · `resumen_capital.py` con rutas rotas** — tras mover `~/bot-padre-v4/v5/v6` a
  `~/_archivo_bots_anteriores/`. Usado por `/consejero`; no se cae (tiene fallback) pero muestra
  valores por defecto. Decidir: corregir las 3 rutas o dejarlo.
- [ ] **M7 · 5 archivos en "zona gris"** del home sin clasificar (`backup_sd.sh`,
  `package-lock.json`, `intel_noticias/`, `respuesta22.txt`, `setup-dell.sh`/`backup_dell/`) —
  esperan que Ariel confirme qué son.
- [ ] **M8 · Corrección de texto en `INVESTIGACION.md`** — el hallazgo "horario×calidad" quedó
  invalidado al corregir el bug de timestamps (23-ago) y el texto publicado no se actualizó.
- [ ] **M9 · Trailing/BE: 0 cierres reales en 9 años** — documentado y **decidido no tocar** (dos
  mediciones independientes dicen que arreglarlo empeora). Queda como deuda conocida, no como TODO.
- [ ] **M10 · Fase B de correlación — rediseño** — con la ventana pedida, 0/40 combinaciones llegan
  a n≥30 (máx. 7). Un diseño distinto podría generar muestra, pero es otra pregunta.

- [ ] **M12 · Regla de proceso "buscar antes de investigar" — redactada, sin aplicar** *(09-sep,
  corregida el mismo día)*
  Va en `CLAUDE.md`, junto a la regla del 01-sep. Antes de arrancar cualquier investigación nueva
  hay que consultar **dos** lugares: `INDICE_RESULTADOS.md` + `resultados.db` (*"¿esto ya se
  midió?"*) **y** las secciones "NO TOCAR" / "DECISIÓN TOMADA" de `CLAUDE.md` (*"¿esto ya se
  decidió, y con qué argumento?"*). El motivo: hay decisiones sostenidas por evidencia que **no es
  una fila de la DB** —el trailing, el termómetro, el centinela viven en prosa—, y un backtest nuevo
  puede contradecirlas sin que nadie lo note.

  🔴 **CORRECCIÓN del 09-sep, aprendida en el mismo día por las malas:** **no alcanza con encontrar
  que algo ya se midió.** Hay que verificar **la fecha de esa medición contra la fecha de cada fix
  del laboratorio** (L1 en adelante) antes de darla por válida. El ítem 4 se cerró apoyándose en 7
  estudios sin mirar con qué datos habían corrido: eran todos anteriores al fix de L1 y el gate
  horario había evaluado la hora corrida 4 h. **Buscar los resultados no es buscar las condiciones
  en que se produjeron.**

  Fechas de fix contra las que hay que contrastar, por ahora: **2026-09-07 (L1**, desfase de −4 h
  del backup 4h**)**. Cada fix nuevo del laboratorio suma una fecha a esta lista.
  **Diff completo y listo:** `reports/2026-09-09_diffs-cierre-del-dia.txt`, bloque B
  ⚠️ **ese diff quedó desactualizado con esta corrección — hay que regenerarlo al aplicarlo.**

- [ ] **M13 · Marcar 4 archivos viejos como históricos — redactado, sin aplicar** *(09-sep)*
  `CONTEXTO_SESION.md` (volcado de código de junio), `CIERRE_FINAL.md` (los 3 puntos de julio),
  `reporte_evaluacion_real.md` (evaluación de mayo, con números del simulador a 4 h que
  **sobreestima**) y `CLAUDE_BACKUP_2026-08-22.md` (copia vieja de `CLAUDE.md`). Cada encabezado
  dice qué es, por qué quedó superado y dónde vive hoy esa información.
  **Diff completo y listo:** `reports/2026-09-09_diffs-cierre-del-dia.txt`, bloque C.

- [x] **M14 · ~~Respaldo de `reports/` fuera de la Dell~~ — ⛔ DESCARTADO por decisión de Ariel
  (09-sep).** No se toca nada.
  **Lo que se midió antes de descartarlo, para no volver a abrirlo sin datos nuevos:** `reports/`
  está en `.gitignore` y nunca va a GitHub. Drive **sí** lo respalda, con verificación diaria por
  checksum (292/292 el 09-sep, 0 diferencias), **pero sólo los `.md`**: el vigía y el verificador
  filtran con `--include "*.md"`. De los 16 MB, **13 MB en 157 archivos quedan fuera** — los JSON de
  backtests, los diffs, `raw/`, `snapshots_combo_o/` —, y ésos dependen de un solo respaldo: el
  rsync al disco USB, que copia todo `/home/ariel/` (verificado: 446 entradas de `reports/` en la
  corrida del 09-sep 02:03) pero **no tiene verificación que alguien lea**.
  La propuesta era quitar el filtro `*.md` de los dos scripts (bloque D del mismo archivo de diffs).
  **Decisión: no se aplica.** Reabrir sólo con evidencia nueva y decisión explícita de Ariel.

## ✅ BLOQUE DE LABORATORIO — COMPLETO (L1–L10, cerrado el 07-sep)

Fue **antes** que todo lo demás. Motivo: 5 artefactos de ventana corta en una jornada; el
laboratorio no era lo bastante sólido para sostener conclusiones nuevas.

- [x] **L1 · Integridad de datos históricos** — ✅ 07-sep (ver "Ya cerrado")
- [x] **L2 · Reproducibilidad** — ✅ 07-sep: 4/4 tests + huella de datos
- [x] **L3 · Validación fuera de muestra** — ✅ 07-sep (3 niveles)
- [x] **L4 · Monte Carlo** — ✅ 07-sep (el barajado ingenuo miente)
- [x] **L5 · Benchmark tonto** — ✅ 07-sep (la entrada SÍ le gana al azar). **Reconstruido como
  script re-ejecutable el 09-sep**: `~/lab_eval/benchmark_tonto.py`
- [x] **L6 · pytest** — ✅ 07-sep: 31 tests (43 con los de L10), todos pasan
- [x] **L7 · GitHub Actions** — ✅ 07-sep: CI de 2 niveles, verde
- [x] **L8 · ruff** — ✅ 07-sep: encontró 3 bugs reales, los 3 corregidos
- [x] **L9 · mypy** — ✅ 07-sep: acotado a los 16 módulos de producción
- [x] **L10 · hypothesis** — ✅ 07-sep: 12 property-based sobre el camino del dinero.
  ⚠️ Se había marcado cerrado con la librería sólo **instalada** y sin un test escrito; se corrigió.
- [x] **L11 · ¿es fuerte el laboratorio?** — ✅ **CERRADO 09-sep, 3 de 3 pruebas.** 🔴 mide bien y elige mal.

## Ya cerrado

- [~] **4 · Francotiradores LATERAL (09-sep) — ⚠️ ESTE CIERRE QUEDO REVERTIDO EL MISMO DIA.**
  Ver el ítem 4 arriba: los 7 estudios que lo sostenían son anteriores al fix de L1 y el gate
  horario corría con la hora corrida 4 h. Lo de abajo se conserva como el análisis que se hizo,
  **no como veredicto vigente.** (prueba **302**, hoy `NO_CONCLUYENTE`)
  **Primer ítem cerrado con la regla "buscar antes de investigar", y la justifica: lo que iba a
  medir ya estaba medido siete veces.** No se corrió un solo backtest nuevo.
  - **La premisa sigue en pie:** LATERAL es la mayor parte del año (5 de 6, hasta 2,93× más velas
    que ALCISTA) y el bot está ciego el **73-85 %** del año. El hueco existe.
  - **Ninguna implementación lo aprovecha.** Los 7 estudios registrados dan **PF 0,963-1,208**
    contra el umbral de **1,6**; la mediana es **1,020** — empatar descontando comisiones. El
    "PF 1,183 de SOL" son 38 trades de 2026 aislado, ya registrado como artefacto: el mismo estudio
    sobre 5,9 años da **1,001**.
  - **Y hoy se sabe más:** el mejor (`bnb_lateral`, PF 1,208) tiene SR +0,0918 contra un SR₀ de
    **+0,2178**, y su **DSR es 0,016**. `avax_lateral` quedó "sin señal" en el ítem 2. `btc_lateral`
    y `avax_lateral` están entre los 20 que el jackknife da vuelta al excluir un año.
  - **Los cinco están pausados con un número delante:** ETH PF 0,90 · SOL 0,928 · AVAX 0,985 · BTC
    sin backtest de gates · BNB huérfano. Reactivar sería reabrir una decisión sin evidencia nueva.
  - ⚠️ **Anotado con cautela, no como hallazgo:** el mejor LATERAL es BNB, la moneda que no opera, y
    3 de los 5 "recuperables" del ítem 2 también eran de BNB. **No se presenta como hallazgo**
    porque es la forma exacta del *storytelling bias* que el L11 marcó con 4 reincidencias, y los
    números no lo sostienen. Para mirar en el **ítem 9**.
  - 🎯 **La premisa cambia de forma:** explotar el año ciego **no se logra reactivando lo que hay**.
    Hay que **diseñar** algo distinto, con las dos condiciones que puso el L11 (no probar N
    variantes y quedarse con la mejor; apuntar a un efecto grande o traer mucha más muestra). Eso
    es un **proyecto de diseño de estrategia**, no un ítem de cola de verificación.
    Reporte: `reports/2026-09-09_item4-francotiradores-lateral.md`

- [x] **3 · Auditoría de conexiones y sincronizaciones (09-sep) — ✅ 7 de 8 sanas; lo que faltaba
  era la detección.** (prueba **300**)
  - **Estado:** GitHub `4f7d040` sin pendientes · Drive reportes 292/292 por checksum · Drive cola
    automática · túnel `:5050` HTTP 200 · Telegram `getMe` OK · Binance 273-348 ms · 30 screens.
  - 🎯 **Causa raíz medida:** Drive tenía **tres** mecanismos de detección —verificación
    programada, archivo de estado y alerta— y el backup **ninguno**. `backup_externo.sh` no tiene
    una sola línea que notifique: escribe en un log de 78 MB que nadie abre. Por eso el 08-sep pasó
    inadvertido y por eso en julio una caída duró 32 días.
  - **Los dos fallos, explicados:** 06-sep `código rsync 24` (archivos que desaparecieron durante
    la copia — benigno) y **08-sep abortó por disco sin montar** tras el reinicio de las 00:29: esa
    noche no hubo backup. ⚠️ **Corrige el reporte del 08-sep**, que decía que la del 06 "nunca
    escribió `Backup OK`, sin explicación": sí escribió — escribió `FALLO`.
  - **El disco con sufijo `2`:** hay 3 directorios del mismo UUID en `/media/ariel`, los otros dos
    **vacíos y no son puntos de montaje**. No afecta nada: el script resuelve por `findmnt UUID`.
    298 G libres de 457 G. El backup incluye `reports/` completo con `raw/` y `snapshots_combo_o/`
    — los 13 MB que Drive no cubre **sí** están ahí (refuerza M14).
  - 🔴 **Problema de fondo:** Telegram es el **único** canal de alerta del sistema y el más frágil
    — 11 fallos en 7 días, siempre por red, o sea **correlacionados con lo que tienen que avisar**.
  - **APLICADO:** `~/verificar_conexiones.sh` + timer diario 08:00, que le da al backup los tres
    mecanismos y consolida backup + Drive + screens + git en un archivo. Si el último `Backup OK`
    pasa de **48 h**, deja un `ALERTA_backup_*.md` dentro de `reports/`, que ya se sincroniza solo
    a Drive. **No avisa por Telegram a propósito**, para no construir sobre el punto único de falla
    que este mismo ítem midió. Probado en real (exit 0, estado en Drive) y la rama de alerta
    probada en aislamiento: detecta 139 h sin backup y escribe el detalle correcto.
    Además se quitó el `except Exception: pass` de `tunnel_asistente.py`.
  - **No se probó** el failover real (cortar la red) ni la URL pública del túnel desde afuera.
    Reporte: `reports/2026-09-09_item3-auditoria-de-conexiones.md`

- [x] **2 · Revisión de los `NO_CONCLUYENTE` con las herramientas del L11 (09-sep) — 🟢 ninguno es
  candidato a reabrir, y el reparto es el hallazgo.** (prueba **299**)
  - De los **123** `NO_CONCLUYENTE`: **77 no tienen serie** (auditorías, diagnósticos,
    proyecciones). De los **46 con trades**: **21 MEDIDO** (muestra suficiente y aun así no
    alcanza — el nulo *es* un resultado), **11 INEVALUABLE** (n < 30) y **14 NO VISIBLE**.
  - 🔴 **25 de 46 (54 %) nunca tuvieron capacidad de detectar nada** y estaban archivados igual que
    los medidos.
  - **Los 14 "no visibles" son dos cosas distintas.** 🟡 **5 recuperables** (falta muestra
    alcanzable): `torneo_bnb_lateral` +29 trades, `btc_volatilidad k_1.31` +45,
    `sol_volatilidad_khigh k_1.75` +53, y los dos de BNB con +508 y +638. **Tres de los cinco son
    de BNB**, la moneda huérfana — coherente, porque no opera y por eso tiene menos trades.
    ⚪ **9 sin señal:** `torneo_eth_bajista` necesitaría **6.181.199 trades** (SR +0,0007).
  - 🎯 **El dato que ordena todo:** con los 298 ensayos de la casa, el Sharpe máximo esperado **por
    azar** es **SR₀ = +0,2178 por trade**, y **ninguno de los 46 lo supera** (el mejor recuperable
    llega a +0,1526). Los 5 son recuperables **contra cero**, la vara que la Prueba 1 mostró que
    aprueba 100 de 100 estrategias de ruido puro.
  - **Norma que deja:** `NO_CONCLUYENTE` debería distinguir "medido y nulo" de "no evaluable";
    antes de archivar un nulo hay que calcular el **MinTRL**; y un MinTRL astronómico es un
    resultado **positivo** que cierra el tema, no un pendiente esperando datos.
  - Sin backtests nuevos: todo salió de los trades ya guardados.
    Reporte: `reports/2026-09-09_item2-revision-de-los-no-concluyentes.md`

- [x] **12 · Carrera entre `watchdog.py` e `iniciar_bots.sh` + watchdog ciego** *(ex Ítem 12)*
  — ✅ **RESUELTO el 08-sep 01:11, commit `3592e89`, pusheado y verificado en vivo.**
  *(Migrado a esta sección el 09-sep: en la unificación de la cola había quedado en el
  bloque de ítems abiertos, con su `[x]` pero fuera de "Ya cerrado". Texto original
  completo, tal como estaba en `~/zbot-drive/cola/zbot-cola.md.bak_pre_unificacion`:)*

  - [x] **Ítem 12 · INFRAESTRUCTURA — ✅ RESUELTO 08-sep 01:11 (era 🔴 URGENTE)** —
    Arreglar la carrera entre `watchdog.py` (cron `*/5`) e `iniciar_bots.sh` (`@reboot sleep 30`) al
    levantar `v2_main`. **No es urgente y no bloquea nada**: se resuelve en cualquier hueco, sin
    esperar al cierre de `cerrar_huerfanas()` ni al resto de la cola.

    **Qué pasó el 08-sep** (corte de luz, arranque del sistema 00:29):
    - `00:30:02` el watchdog ve el bot caído y lo relanza **suelto, sin screen**.
    - `00:30:07` `iniciar_bots.sh` llega a `v2_main`, encuentra el proceso vivo y lo saltea:
      `[SKIP] v2_main ya está corriendo (proceso vivo)` — la screen nunca se crea.
    - Resultado: bot vivo y en REAL, pero **huérfano** (`ppid=1`), `screen -r v2_main` no existe y
      `monitor_screens.py` lo daba por caído (`❌ Caídos: ['v2_main']`). Corregido a mano a las 00:40
      con 0 posiciones abiertas.

    **Por qué no es urgente:** la garantía de modo REAL **no se perdió** — el watchdog también lee
    `~/.bot_real_confirmado` y exporta `BOT_REAL_CONFIRMADO=true` (verificado en
    `/proc/<pid>/environ` del proceso que él levantó). El daño es de observabilidad, no de dinero.

    **Lo que sí se pierde mientras dura:** `reiniciar_bot()` lanza con
    `stdout=DEVNULL, stderr=DEVNULL` (`watchdog.py:69-74`), así que el log del bot **no queda en
    ningún lado** — ni en una screen ni en un archivo. Si algo falla en ese período, no hay rastro.

    **Opciones a evaluar cuando llegue el turno** (medir antes de elegir, ninguna aplicada):
    1. Que el watchdog espere unos segundos tras un reinicio antes de actuar (p. ej. no hacer nada si
       el `uptime` es menor a ~90 s, dejando que `iniciar_bots.sh` haga su trabajo primero).
    2. Que los dos se coordinen con un archivo compartido de "ya está levantando el bot"
       (`flock`, como ya hace `subir_drive.sh`) antes de intentar levantarlo.
    3. Que el watchdog levante **dentro de screen**, igual que `iniciar_bots.sh`. No resuelve la
       carrera, pero la vuelve inofensiva: gane quien gane, el bot queda observable.

    ### 🔴 CONFIRMADO el 08-sep 01:00 — el watchdog está ciego (esto es lo urgente del ítem)

    Lo que estaba anotado como hipótesis **se verificó y es cierto**. `bot_esta_vivo()`
    (`watchdog.py:52-60`) usa `pgrep -f main.py`, que matchea por substring y cruza proyectos:
    el `main.py` de `~/motor-confluencia` cuenta como "el bot".

    Verificación sin tocar producción (el namespace de PIDs sin privilegios está bloqueado):
    se emuló `pgrep -f "main.py"` sobre `/proc`, se **validó la emulación contra el `pgrep` real**
    en el mismo instante (`emulacion == pgrep real: True`, mismos 4 PIDs) y recién entonces se
    aplicó el contrafactual quitando los PIDs de `v2_main`:

    ```
    Lo que SEGUIRÍA matcheando:  3452 (screen motor_confluencia) · 3454 (~/motor-confluencia)
    => pgrep returncode 0  =>  bot_esta_vivo() devolvería True  con v2_main MUERTO
    ```

    **Por qué es urgente:**
    - Es la **única recuperación automática** que existe. `monitor_screens.py` corre cada 60 s pero
      sólo escribe `estado_screens.json`: no manda Telegram ni reinicia nada.
    - El **SL del bot es lógico, no una orden en Binance**: si `v2_main` muere con una posición
      abierta, queda **sin stop** hasta que alguien lo note a ojo.
    - El fallo es **silencioso por construcción**: el log escribe `Bot vivo. Todo OK.` igual.
    - `motor_confluencia` entró a `iniciar_bots.sh` el **18-ago** (`4305772`), así que está vivo
      siempre que lo esté la máquina.

    **Lo que NO se afirma:** no hay evidencia de que ya haya fallado en silencio — ese caso no deja
    rastro. Las 18 detecciones de `memoria/watchdog.log` prueban que detecta *cuando no hay otro
    `main.py` vivo*, no que detecte siempre.

    **No se tocó código.** El arreglo (acotar el patrón a este proyecto verificando el `cwd` del PID,
    o usar un pidfile) es un cambio a un módulo de producción: va con diff a aprobación de Ariel,
    junto con las 3 opciones de la carrera de arriba, en una sola pasada por `watchdog.py`.

    Reporte: `reports/2026-09-08_watchdog-ciego-pgrep-cruzado.md`
    **APLICADO el 08-sep 01:11** (commit `3592e89`, pusheado) tras aprobación de Ariel: fix del
    `pgrep` por `cwd` verificado contra `/proc` (no pidfile) + opciones 1 y 3 de la carrera;
    la opción 2 (`flock`) descartada con motivo. **Verificado en vivo, no en emulación:** con
    0 posiciones abiertas, `motor_confluencia` vivo y `v2_main` matado a propósito, el `pgrep`
    viejo seguía devolviendo returncode 0 ("bot vivo") mientras el bot estaba muerto; el código
    nuevo dio `bot_esta_vivo(): False`, lo reinició **dentro de la screen** `v2_main` (PID 5530,
    `ppid` = la screen), con `BOT_REAL_CONFIRMADO=true`, y `monitor_screens.py` quedó en
    `27 activos / 0 caídos`.
    Queda abierto, anotado y sin tocar: `proceso_activo()` de `iniciar_bots.sh` compara `cwd`
    pero no exige que el proceso sea un python (mismo agujero, otro archivo), y los `except:`
    desnudos de `cargar_token()`/`enviar_telegram()`.
    `reports/2026-09-08_propuesta-fix-watchdog.md`


- [x] **L11 · Pruebas 2 y 3 — el laboratorio queda CERRADO (09-sep) — 🔴 mide bien y elige mal.**
  - **Prueba 2 · cobertura de errores** (prueba 297). Los tres huecos existen, ninguno da vuelta la
    decisión de hoy. **La comisión no es fija:** 0,0822 % efectiva real sobre 162 trades de la
    cuenta contra el 0,1 % del sandbox — sobreestima **18 %**, y la ventaja de quitar
    `cerrar_huerfanas()` baja de +$31,02 a **+$26,51** sin darse vuelta. **El sandbox siempre llena
    la orden:** en producción falla el **92 %** de los intentos de apertura (473 de 514 filas
    `ANULADA`) **y el motivo no queda registrado en ningún lado**. **Jackknife:** 20 de 126 estudios
    (15,9 %) cambian de signo al quitar un año; 2021 los da vuelta en 12 de 20.
  - **Prueba 3 · estándares externos** (prueba 298). **DSR: 0 de 121 estudios** superan la
    corrección por prueba múltiple (93 de 121 pasan el PSR contra cero; el SR máximo esperado por
    azar con 297 ensayos es +0,2188 por trade y el mejor DSR del proyecto es 0,726). **PBO por
    CSCV: 48,6 %** sobre 108 meses × 11 configuraciones — elegir la mejor del torneo es casi una
    moneda al aire, y **coincide con el ρ +0,010 de L3 por otra vía**. **MinTRL:** 19,1 % de los
    estudios no tienen largo suficiente ni contra cero. **Siete sins:** 3 ✅, 2 🟡, 2 🔴 — quedan
    abiertas *survivorship* (ver ítem 4b) y *overfitting*, ya cuantificada.
  - ⚠️ **Las fórmulas se verificaron contra las fuentes al ejecutar, y hizo falta:** el extractor
    del PDF devolvió el signo de la asimetría cambiado y sin el cuadrado en el término de curtosis.
  - **Por qué la decisión de hoy sigue en pie:** `cerrar_huerfanas()` no fue elegir entre 297
    candidatos, fue una comparación **pareada** entre dos ramas con la misma lógica y los mismos
    datos. Lo que estas pruebas invalidan es la **selección** del mejor entre muchos.
  - Reportes: `reports/2026-09-09_L11-prueba2-cobertura-de-errores.md`,
    `reports/2026-09-09_L11-prueba3-estandares-externos.md`

- [x] **`cerrar_huerfanas()` · etapa 2 y decisión final (09-sep) — 🟢 APLICADO, commit `ade1ae0`.**
  Sobre **2020-09-22 → 2026-09-08** (783.358 pasos de 4 min, las dos ramas completas):
  **CON** 2.675 trades, WR 35,3 %, PF 1,015, PnL **+$3,77**, maxDD $14,91 (40,5 %) ·
  **SIN** 1.106 trades, WR 44,1 %, PF 1,164, PnL **+$34,79**, maxDD $6,52 (17,7 %).
  - **Quitarla gana +$31,02** y es el **primer candidato de la serie que no se cae al sacudirlo**:
    **7 de 7 años** calendario y **4 de 4 monedas** (BTC cambia de signo, −$7,03 → +$9,32).
    Bootstrap por bloque mensual (65 meses): **IC 95 % [+17,06 · +45,13], no cruza cero**;
    test de signo **42/61, p = 0,0044**; sin los 5 mejores meses sigue **+$19,94**.
  - **Descomposición exacta:** +$17,07 de **1.801 reaperturas que sólo existen en CON**, +$14,31 de
    307 trades con la misma entrada y salida distinta, −$0,36 de 232 que sólo existen en SIN.
  - **Las posiciones no quedaron sin guardián:** `_proteger_otras_fases()` (commit `f9d6c2c`, 30-ago)
    ya cubría eso en los 4 directores, y por fase **LOCAL**, 5,2× más frecuente que la global.
  - ⚠️ Asteriscos registrados: el bot opera **menos de la mitad** (1.108 aperturas contra 2.677) ·
    a escala actual son **~$0,43/mes** · **ambas ramas superan el 10 % del guardián** · las huellas
    de datos difieren en 4 velas al final de 6 años.
  - `INDICE_RESULTADOS.md`, `ESTADO_ACTUAL.md`, `CLAUDE.md`, `data/resultados.db` (pruebas **293** y
    **294**). Reporte: `reports/2026-09-09_huerfanas-etapa2-6anos.md` · celular:
    https://claude.ai/code/artifact/1b6ac240-8b94-4e0d-966e-7d57b76c28f1

- [x] **Impacto REALIZADO de `cerrar_huerfanas()` — las primeras 31 filas `FASE_CAMBIO` (09-sep).**
  `CLAUDE.md` decía "0 filas, nunca llegó a dispararse": **quedó desactualizado**. Se disparó **31
  veces entre el 3 y el 7-sep** (16 AVAX, 8 BTC, 7 SOL), justo lo que ese archivo anticipaba al
  pasar `MONTO_FIJO` a $7/$10.
  - **El costo real no era el que parecía:** efecto sobre la caja −$5,0973, pero **+$4,9754 es polvo
    inmovilizado** y sólo **−$0,1219 pérdida efectiva por precio**. Un primer cálculo las mezclaba y
    daba −$0,81 por trade de BTC en 12 minutos, **imposible por precio**.
  - **BTC concentra el polvo:** ~$0,79 por vuelta = **8,2 % del ticket** (compra 0,00011988 y el
    `stepSize` de 0,00001 deja 0,00000988 sin vender). Su polvo pasó de 0 a ~$5,5 en cuatro días:
    **~13 % del capital**. El mecanismo no crea el polvo —todo cierre trunca— pero **multiplicaba
    los cierres**: 31 en 5 días, mediana de 20 minutos.
  - 7 filas no tienen `COMPRA` con ese timestamp y **no se estimaron**. Prueba **295**.
    Reporte: `reports/2026-09-09_impacto-realizado-cerrar-huerfanas.md`

- [x] **L11 · Prueba 1 — engaño controlado (09-sep) — 🔴 dos puntos ciegos medidos.**
  600 estrategias sintéticas con ventaja conocida por diseño (6 valores de `p` × 100 semillas, ~240
  trades cada una, BTC 2020-2026), con criterios **pre-registrados el 08-sep**.
  - 🔴 **INDULGENCIA:** el criterio *"IC 95 % del total no cruza cero"* —el bootstrap citado en todo
    `INDICE_RESULTADOS.md`— **aprobó 100 de 100 estrategias de ruido puro**. Causa: entrar al azar
    rinde **+1,5517 % por trade** por deriva del mercado, así que toda vara contra **cero** aprueba
    al ruido. **No invalida** su uso comparativo (A vs B); **sí** invalida leer "IC 95 % > 0" como
    "la estrategia sirve".
  - 🔴 **FALTA DE POTENCIA:** con la vara correcta los falsos positivos son **0/100 = 0,0 %** ✅,
    pero la detección es 1 % (p=0,505), 2 % (0,51), 5 % (0,52), **17 % (0,55)** y **40 % (0,60)**.
    **Ninguna** se detecta en ≥50 % de las semillas. **Umbral: con ~240 trades no distingue del azar
    una ventaja de +0,485 pp por trade** (~$0,034 en un ticket de $7).
  - 📌 **Cómo cambia la lectura de todo el índice:** la mayoría de los `NO_CONCLUYENTE` no dicen "no
    hay ventaja", dicen **"el instrumento no la ve a esta escala"**. De ahí sale el **ítem 2**.
  - Contraste del mismo día: la etapa 2 de `cerrar_huerfanas()` está **muy por encima** del umbral,
    y por eso resiste.
  - **Control:** `monte_carlo.py` marcó "el drawdown depende del orden" en estrategias de ruido puro
    (falsos positivos también ahí); `validar_fuera_muestra.py` dio ρ 0,063 y P(>0) 81,4 %, correcto.
  - Arnés nuevo y re-ejecutable en `~/lab_eval/`. Prueba **296**.
    Reporte: `reports/2026-09-09_L11-evaluacion-del-laboratorio.md`

- [x] **L7–L10 · CI, ruff, mypy, hypothesis (07-sep) — ✅ y encontraron 3 bugs reales.**
  - **CI de dos niveles.** *Bloquea:* `pytest` (31/31) y `ruff --select E9,F821,F811`. *Avisa sin
    frenar:* ruff completo (342 hallazgos, **277 son f-strings cosméticos**) y mypy (36 errores).
    La filosofía está escrita en el propio workflow: **un CI que nace en rojo se aprende a ignorar.**
  - 🐛 **`ejecutor.py:35`, en el camino del dinero** — el fallback de avisos referenciaba `_e`, la
    variable del `except`, que **Python 3 borra al salir del bloque**. Crasheaba con `NameError` la
    primera vez que se usaba, justo cuando fallaba Telegram. **Reproducido antes de corregir.**
  - 🐛 `periodista_independiente.py` importaba `os` dos veces.
  - 🐛 `sistema_c/tests_sistema_c.py:329` usaba `ets_ms` sin inicializar — falso positivo en la
    práctica (se asigna antes de leerse), hecho explícito igual.
  - **Tras los 3 fixes el CI queda verde.** `mypy` acotado a los **16 módulos de producción**: los
    298 archivos chocan con nombres de módulo duplicados y tipar scripts de un solo uso no aporta.
  - `INDICE_RESULTADOS.md`, `ESTADO_ACTUAL.md`, `data/resultados.db` (prueba id 290).

- [x] **L6 · pytest (07-sep) — ✅ 31 tests, 31 pasan.**
  - **21 sobre `ejecutor.py`**, y cada uno tiene detrás un incidente real: `_truncar_cantidad` (si
    redondea hacia arriba → rechazo −2010 y posición ABIERTA sin stop; incluye el caso
    `0.29*100 = 28.999999999999996` que motivó usar `Decimal`), `_formatear_qty` (notación científica
    → error −1100, **pasa siempre con BTC**: $5 a ~$80.000 da qty 6,25e-05), `_extraer_fill` (restar
    la comisión en el activo correcto según compra o venta).
  - **10 invariantes de `auditoria.csv` sobre el archivo REAL de producción**: cabecera exacta, ≥7
    columnas, estados y acciones de conjunto cerrado, timestamps ordenados, ABIERTA con qty, ANULADA
    sin qty, sin duplicados de symbol+timestamp. **Todos pasan hoy** — los datos de producción
    cumplen los invariantes.
  - Entorno: venv `.venv-lab` (el pip del sistema está bloqueado por PEP 668). Config en
    `pyproject.toml`, con `ruff` y `mypy` ya configurados en modo permisivo para L8/L9.

- [x] **L5 · Benchmark tonto (07-sep) — 🟢 la entrada SÍ aporta. Primera buena noticia del bloque.**
  - **Entradas al azar**, mismo TP/SL y misma cantidad de trades que el bot: **supera al azar en 4 de
    4 monedas** — BTC +199,1 % vs +36,6 % (**P 95,0 %**), ETH +269,3 % vs −43,2 % (**100 %**), SOL
    +80,9 % vs −108,9 % (**97,5 %**), AVAX +146,5 % vs −117,2 % (**100 %**). Los 12 gates, el RSI y
    las EMAs **seleccionan algo real**.
  - **La referencia 3 (moneda al aire) es la misma prueba que la 2** — tirar una moneda con la
    frecuencia observada *es* elegir al azar. Se reportan juntas.
  - **Buy & hold:** retornos enormes (BTC +1.426 %, BNB +36.535 %) pero con **caídas del 84 al 97 %**
    y entre 5 y 8 años acumulados bajo el −20 %.
  - **Comprado sólo en ALCISTA, sin ningún filtro: le gana a buy & hold en 4 de 5 monedas con la
    mitad del drawdown.** BTC +2.837 % vs +1.426 % (DD −46,5 % vs −83,9 %); **AVAX +10.826 % vs
    +89 %**.
  - ⚠️ La primera versión daba **+22.900.366 %** por un **look-ahead** (decidía la fase con el cierre
    de la vela *i* y cobraba el retorno de esa misma vela). Corregido a decidir con velas cerradas
    hasta *i−1*. **Segundo error propio atrapado hoy antes de registrarlo** (el otro fue el Monte
    Carlo ingenuo de L4).
  - 📌 **El cuadro que arman L3+L4+L5:** la entrada aporta (L5) · su magnitud está bien medida (L4) ·
    **cuál variante es la mejor, no se puede saber** (L3) · sólo opera el 15–41 % del año (2b/2c) ·
    y **la fase sola ya le gana a buy & hold** (L5). Lectura sugerida, no veredicto: el valor parece
    estar más en **estar dentro en el régimen correcto** que en afinar los gates.
  - `INDICE_RESULTADOS.md`, `ESTADO_ACTUAL.md`, `data/resultados.db` (prueba id 288).
    Reporte: `reports/2026-09-07_L5-benchmark-tonto.md`

- [x] **L4 · Monte Carlo (07-sep) — 🟡 el hallazgo es metodológico: el barajado ingenuo miente.**
  - **Casi queda registrada una falsa alarma.** Barajando **trade a trade**, 41 de 108 estudios daban
    el drawdown observado bajo el percentil 5 — "el riesgo real es 1,70× mayor de lo medido", y 2,56×
    en el peor 5 %.
  - **Barajando por bloques de 20 trades quedan 14.** El barajado libre destruye la estructura
    temporal y genera secuencias de pérdidas que la estrategia real nunca produjo. **Dos tercios de
    la alarma eran artefacto del método.** El script quedó con bloques de 20 por defecto.
  - **También se descartó una explicación propia:** se propuso que ganadoras y perdedoras alternan
    más que el azar (autocorrelación −0,084 en un BTC), pero medida en los 108 la mediana es
    **+0,009** y es negativa en sólo el 46 %. Cierta en el caso mirado primero, **falsa en general**.
  - **Lo que queda:** 14 de 108 (13 %) con DD bajo el percentil 5 usando bloques — más que el ~5 %
    esperable, pero acotado y con estimación gruesa.
  - **Bootstrap:** en los estudios grandes el **signo del resultado es robusto** (P(>0) ≈ 100 %,
    IC 95 % enteramente positivos, cero cruzando el cero entre los 10 mayores).
  - 📌 **Contraste con L3, y es el punto: cuánto rinde una configuración está bien medido; cuál es la
    mejor, no.** L4 confirma la primera mitad; L3 había demolido la segunda.
  - ⚠️ **Unidades:** los DD están en puntos porcentuales sumados por trade, **no** en % de la cuenta.
    30 puntos con $7 por trade son **$2,10 ≈ 5,7 %** de $36,86.
  - Entregable: `laboratorio/monte_carlo.py` (shuffle por bloques + bootstrap, exit code).
    `INDICE_RESULTADOS.md`, `ESTADO_ACTUAL.md`, `data/resultados.db` (prueba id 287).
    Reporte: `reports/2026-09-07_L4-monte-carlo.md`

- [x] **L3 (parte 2) · El walk-forward confirma: elegir el mejor NO le gana al azar (07-sep) — 🔴.**
  Diseño: elegir la mejor combinación **con los datos hasta el mes N**, medir el mes **N+1**, correr
  la ventana y repetir. Contra elegir **al azar** y contra el **techo** (elegir con el futuro).
  - Con 24 meses de historia: ventaja **+64,64 %**, pero **IC 95 % [−101,07, +247,09]** y
    **P(>0) = 77,4 %** — bajo la vara con que este proyecto rechazó un cambio el 02-sep (P = 83 %).
  - **La sensibilidad lo da vuelta:** cuanta **más** historia se exige, **menos** ventaja hay
    (+67,41 % con 12 m → +26,72 % con 48 m). Y **excluyendo los meses en que la elegida no operó**
    —la comparación justa— cae de **+30,37 %** a **−24,78 %**, con **P(>0) = 36,4 %**.
  - **Techo:** elegir con el futuro daría **+1.334,77 %**. El método captura **10,7 %**.
  - 🔴 **TERCERA VÍA INDEPENDIENTE con la misma conclusión:** bootstrap del Ítem 2 (7 IC 95 %
    cruzando el cero) · estabilidad del ranking entre años (ρ +0,010) · este walk-forward.
    **Ya es un patrón sobre el método de selección, no una coincidencia.**
  - **Regla que queda:** toda configuración que se proponga aplicar debe demostrar que **gana fuera
    de la ventana donde se la eligió** y que **le gana al azar**. Se verifica con
    `laboratorio/validar_fuera_muestra.py` (3 niveles, exit code para CI).
  - `INDICE_RESULTADOS.md`, `ESTADO_ACTUAL.md`, `data/resultados.db` (prueba id 286).
- [x] **L3 (parte 1) · El ranking del torneo NO se sostiene entre años (07-sep) — 🔴.**
  Partiendo los **2.790 trades** del torneo ya guardados en `resultados.db` por año, **sin correr
  nada nuevo**:
  - **ρ medio del orden entre años = +0,010** (21 pares) — indistinguible del azar.
  - El mejor global (`avax_alcista`) **gana 1 de 7 años**; queda 8º, 8º y 9º en tres de ellos.
  - **Controlado por moneda** (comparando sólo fases dentro de la misma, para descartar que sea "qué
    moneda se movió ese año"): **ρ −0,058** (103 pares). **La objeción no salva el resultado.** Sólo
    AVAX muestra algo de señal (ρ +0,233, gana 4/6).
  - **Consecuencia:** correr todas las combinaciones sobre toda la historia y quedarse con la mejor
    **selecciona ruido**. Las mediciones siguen valiendo; **la conclusión de que una sea "la mejor",
    no**.
  - Coincide con el bootstrap del Ítem 2 (7 IC 95 % cruzando el cero): **dos métodos independientes,
    la misma conclusión**.
  - ⚠️ **El torneo dejó de estar etiquetado como "REFERENCIA PRINCIPAL"** en `INDICE_RESULTADOS.md`.
  - El mismo test sobre los 8 escenarios del Ítem 2 da ρ +0,008, pero **no se usa como evidencia**:
    la mediana es de 12 trades por mes y escenario, muestra demasiado chica.
  - `INDICE_RESULTADOS.md`, `ESTADO_ACTUAL.md`, `data/resultados.db` (prueba id 285).
    Reporte: `reports/2026-09-07_L3-validacion-fuera-de-muestra.md`

- [x] **L1 · Integridad de datos históricos (07-sep) — 🔧 APLICADO.** Los datos estaban bien; las
  etiquetas del backup 4h, no: **toda su columna de tiempo estaba corrida −4 h**. Detectado cruzando
  dos fuentes independientes (los `data_1m` agregados contra el backup): diferían en el 98,5–99,2 %
  de las velas, y `backup[t] == 1m[t+4h]` con **mediana 0,000000 % y 100 % de velas iguales**.
  - **Corregido en la fuente**: 13 CSV +4 h por fila, respaldo y marca anti-doble-aplicación.
    Verificado después: las dos fuentes coinciden al **100 %**.
  - **Por qué en la fuente y no con una bandera:** de los **58 `.py`** que leen ese backup, **35 no
    corregían nada** y **9 sólo ajustaban el índice de inicio** (ventana bien, horas mal por dentro).
    **Ninguno tenía los timestamps correctos.**
  - Los `data_1m` son **exactos** (48/48 velas de muestra idénticas a Binance; 15,8 M de velas con
    OHLC coherente). Huecos: **20.153 min = 0,097 %**, con 0,41–0,43 % de las ventanas del torneo,
    los 12 gates y TP/SL, y **cero** en los 8 escenarios del Ítem 2. **No se rellenan**, por decisión.
  - Decisiones ejecutadas: BNB 1m crudo descargado · desfase corregido en la fuente · huecos intactos.
  - `INDICE_RESULTADOS.md`, `ESTADO_ACTUAL.md`, `data/resultados.db` (prueba id 283), commit `e97233a`.
    Reporte: `reports/2026-09-07_L1-integridad-datos-historicos.md`
- [x] **L2 · Reproducibilidad — CERRADO 07-sep: 4/4 tests + huella de datos.**
  `verificar_reproducibilidad.py` (reutilizable) corre el mismo tramo cambiando una cosa por vez:
  **A** misma corrida dos veces · **B** distinto `PYTHONHASHSEED` · **C** distinto `--tmpdir` ·
  **D** la bandera obsoleta sigue siendo no-op. **Los cuatro pasan.**
  - El test B era el que valía: el orden de `SYMS` **sí** cambia con la semilla de hash
    (`set(MONEDAS) | set(MONEDAS_VOTO)`), pero **el resultado no depende de eso**. Medido, no razonado.
  - ⚠️ **El asterisco, ya resuelto:** los tests prueban reproducibilidad *el mismo día con los
    mismos datos*, no a lo largo del tiempo. Se cerró agregando una **huella de datos** a cada
    resultado (velas y rango por moneda + **md5 de los 5 `.npy`**, ~2,7 s una vez al arranque). Ahora
    dos corridas que difieren se distinguen entre "cambió el simulador" y "cambiaron los datos".
  - Entregables en el repo: `laboratorio/verificar_datos.py` y
    `laboratorio/verificar_reproducibilidad.py`, ambos con exit code para CI.

- [x] **Ítem 2b — por qué la fase cambia cada 8h + cobertura real (07-sep) — 🟡 PROMETEDOR.**
  - **Disparadores de fase:** `cambio_7d` **55,1%** de los cruces que cambian la fase, `cambio_30d`
    **31,6%**, `precio vs EMA200` **13,3%**. Una histéresis sobre 7 días cubre la mitad; para el 87%
    hay que aplicarla también al de 30 días.
  - **Las 5 monedas oscilan cada 6–10 h** (AVAX 6,0h · BNB 7,2h · BTC 8,6h · ETH 9,5h · SOL 10,6h).
    El voto global no crea el ruido: agrega cinco señales que ya son ruido. **672 cambios de fase
    global en 2026**, uno cada 8,9 h.
  - **Cobertura real:** el bot no puede operar entre el **73% y el 85% del año**. AVAX opera con
    dinero real y tiene sólo **37 días alcistas de 249**.
  - **El bot opera en la fase más quieta de las tres.** BAJISTA tiene 40% más rango y 46% más
    volumen; LATERAL 2,6× más velas con 7% menos de rango.
  - ⚠️ **ALCANCE de lo anterior:** el torneo de francotiradores, los 12 gates y el ensanchado de
    TP/SL **midieron una estrategia que sólo actúa ~1/5 del año**. No se invalidan —las
    comparaciones entre configuraciones ALCISTA valen entre sí— pero su alcance queda acotado.
  - **Dos artefactos de ventana corta corregidos sobre la marcha:** con 12 días `c7` parecía el
    98,5% (real 55,1%) y ALCISTA local parecía 37–67% (real 14,9–27,0%). Tercer y cuarto caso de la
    serie en que una ventana corta engaña.
  - Registrado en `INDICE_RESULTADOS.md`, `ESTADO_ACTUAL.md` y `data/resultados.db` (prueba id 282).
    Reportes: `reports/2026-09-07_item2bc-condiciones-y-cobertura.md`,
    `reports/2026-09-07_item2b-por-que-oscila-la-fase.md`

- [x] **Ítem 2 — churn de fase GLOBAL vs LOCAL (07-sep) — 🟡 NO CONCLUYENTE, decisión ABIERTA.**
  **No se archiva como "no sirve": es un defecto de diseño real** — hoy el bot cierra posiciones que
  su propia lógica de entrada considera válidas. Lo que falta es evidencia, no voluntad.
  - **Hallazgo principal, no buscado:** en 2026 **210 de 237 cierres (89%) son por cambio de fase**,
    no por TP ni SL. El bot no está operando su estrategia: lo barre el voto de fase.
  - **Los 8 escenarios dan EXACTAMENTE 12 TP.** Apagar el churn de 210 a 24 (−89%) **no hace que ni
    una sola operación más llegue al take profit**. Los trades que el mecanismo cierra no iban a ganar.
  - **Ninguna de las 3 soluciones es significativa**: los 7 IC95% cruzan el cero. La mejor (A · zona
    muerta 0,25) da +$2,83 con P(mejor)=80,1%. Sumar B y C a A aporta **+$0,021** con P(mejor)=**49,8%**
    — una moneda al aire.
  - **Contradice el instinto de partida:** la fase local corta *más* churn (−74% vs −57%) pero su
    **PF empeora** (0,603 vs 0,619 del baseline). Cortar más no es cortar mejor.
  - Los 8 pierden plata (PF 0,603–0,774): la mejor reduce la pérdida de −$12,22 a −$9,38.
  - ⚠️ **QUÉ FALTA PARA DECIDIR:** medir el impacto del **cambio de duración por trade** (14,9 h
    baseline → 32,3 h con A → 83,0 h con A+B+C) sobre el **perfil de riesgo: drawdown máximo y
    exposición simultánea**. Este estudio no lo midió. Sin eso se estaría cambiando el perfil de
    riesgo del bot a ciegas.
  - Registrado en `INDICE_RESULTADOS.md`, `ESTADO_ACTUAL.md` y `data/resultados.db` (prueba id 281).
    Reporte: `reports/2026-09-07_item2-paso2-ocho-escenarios.md`
- [x] **Simulador: capa del director + 3 fallos de fidelidad corregidos (06/07-sep)** —
  `sandbox_director.py` reproduce el voto de las 5 monedas y `cerrar_huerfanas()`, que el simulador
  anterior se salteaba por completo. Fidelidad validada contra `eventos.log`: **87,3% de coincidencia
  de fase ciclo a ciclo** y **31 transiciones simuladas contra 33 reales**. Los 3 fallos (fase de
  despacho con velas cerradas, `_f_urlopen` ignorando `interval`, `data_1m` desactualizado y sin BNB)
  afectan a **todo el historial de backtests** — registrado en los dos .md y en la DB (prueba id 280).

- [x] **Tarea 1A — 4 minutos vs 4 horas (06-sep) — 🟡 LA RESOLUCIÓN IMPORTA, Y EN CONTRA.** El bot
  real evalúa cada 240 s, o sea cada 4 min; todos los backtests anteriores se corrieron a 4 h.
  Simular a la resolución real da **PF 1.202 vs 1.384** y **WR 45,7% vs 49,7%**, con **81,5% más
  trades** (1.419 vs 782). Consistente en **4/4 monedas, sin una sola excepción**. Mecanismo medido:
  los 1.204 trades que sólo existen a 4m rinden PF 1.142, contra PF 1.606 de los 215 que ambas
  resoluciones ven — mirar más seguido no encuentra mejores oportunidades, encuentra más
  oportunidades mediocres. **Consecuencia: todo backtest a 4h sobreestima el nivel absoluto**; las
  comparaciones relativas entre estrategias siguen valiendo. Antes de aplicar cualquier cambio que
  dependa de cruzar PF ≥ 1,6, revalidarlo a 4 minutos.
  *Queda abierto sin verificar:* los rechazos por `SL inejecutable` pasan de 3 a 312 (18% de los
  intentos). Hipótesis, no conclusión.
  Registrado en `INDICE_RESULTADOS.md`, `ESTADO_ACTUAL.md` y `data/resultados.db` (prueba id 279).
  Reporte: `reports/2026-09-06_tarea1a-4m-vs-4h-comparacion.md`
- [x] **Reanudación desde checkpoint del simulador (05/06-sep)** — corrida completa vs. cortada-y-reanudada
  da resultado **idéntico** (13/13 campos, `usdt_final` hasta el último decimal, `auditoria.csv` bit
  a bit), incluido el caso difícil con 2 posiciones abiertas cruzando el corte. La 1A se terminó
  reanudando desde el 65,8% tras el apagón, en vez de repetir 11,5 h de cómputo.
- [x] Auditoría económica completa (31-ago) — trailing/breakeven, termómetro, centinela documentados
- [x] Bugs históricos de ejecución (-1100, reapertura inmediata, TP fantasma, NOTIONAL, billetera.json) — resueltos y verificados en vivo
- [x] Infraestructura de datos: `data/resultados.db` construida y poblada (235 pruebas / 32.339 trades)
- [x] Simulador mejorado a granularidad de 4 minutos, control de consistencia confirmado (784 trades idénticos a la versión anterior)
- [x] Conexión Google Drive (`zbotv2.ariel@gmail.com` → carpeta `zbot-reportes`) verificada y funcionando
- [x] Subida automática de reportes y auditoria.csv a Drive (disparada por evento, sin temporizador) — instalada y probada
- [x] Verificación diaria de sincronización Dell↔Drive (07:00 AM, por contenido) — instalada y probada, encontró y ayudó a cerrar un hueco real de concurrencia

## Protocolo pre-vuelo (aplica a toda prueba pesada nueva)

Antes de lanzar cualquier prueba/simulación larga: memoria RAM+swap disponible vs. pico esperado, protección de sesión en screen/tmux, checkpoints probados, espacio en disco, estimación de tiempo honesta, revisión de fugas de memoria conocidas. Code da veredicto GO/NO-GO explícito antes de arrancar.

---
**Instrucciones para Code:** marcá `[x]` el ítem que cierres, con fecha y veredicto (🟢/🟡/🔴) al lado. No reordenes ni saltes ítems. Este archivo es la fuente de verdad compartida entre Ariel, Claude y vos — actualizalo cada vez que cambie el estado de algo.
