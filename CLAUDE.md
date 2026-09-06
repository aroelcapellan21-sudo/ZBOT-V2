# Instrucciones permanentes — Z-Bot Padre v2

## Idioma
Responde siempre en español.

## 🛑 REGLA PERMANENTE — mostrar el diff y esperar confirmación (desde 2026-08-31)

**REGLA PERMANENTE: Antes de aplicar CUALQUIER cambio a un archivo real del proyecto (código `.py`,
o documentación como `CLAUDE.md`), mostrar siempre el diff completo a Ariel y esperar su
confirmación explícita antes de escribirlo. Esto aplica sin excepción, incluso si una instrucción
anterior en la misma tarea dice "implementa directamente" o algo similar — esa instrucción nunca
reemplaza este paso. Aplica también a cambios pequeños o solo de documentación, no solo a cambios
grandes de código de producción.**

Notas de aplicación:
- El diff se muestra **antes de escribir el archivo**, no después. Primero el diff, después la
  confirmación de Ariel, y recién entonces la escritura.
- No aplica a archivos que no son del proyecto: reportes en `reports/`, scripts de investigación en
  el scratchpad de la sesión, ni consultas de solo lectura.
- Si en una misma tarea Ariel dice "hazlo directamente", esta regla **sigue vigente**: se prepara el
  diff, se muestra, y se espera. La instrucción de velocidad no cancela el paso de revisión.

## 🛑 REGLA PERMANENTE — investigación y evidencia antes de proponer (desde 2026-09-01)

**Cualquier posible modificación de Z-Bot V2 debe pasar primero por investigación, pruebas y
evidencia. Si se encuentra una mejora viable, se entrega primero la propuesta/diff concreta para
revisión y aprobación explícita. No se aplican cambios directamente.**

Orden obligatorio: **investigar → medir → proponer con diff → esperar aprobación explícita →
recién entonces aplicar.** No se salta ningún paso.

Notas de aplicación:
- Un hallazgo interesante **no es** una propuesta de cambio. Se registra como hipótesis y se
  investiga aparte antes de proponer nada.
- La propuesta incluye: evidencia, impacto esperado (en RD$/mes cuando aplique), riesgos y el diff
  exacto.
- El silencio no es aprobación.
- Los proyectos de investigación separados (`~/simfi/`, `~/estudio_mfemae_v2/`,
  `~/estudio_estrategia_agresiva/`) no están sujetos a esto: no tocan V2.

## 🛑 REGLA PERMANENTE — ninguna investigación se cierra sin registrarla (desde 2026-09-02)

**Ninguna investigación, backtest, prueba o auditoría con veredicto se da por terminada hasta que
su fila esté agregada en `INDICE_RESULTADOS.md`, `ESTADO_ACTUAL.md` esté actualizado, y sus números
estén cargados en `data/resultados.db`. Los tres, no dos de tres. No es un extra ni un "después lo
indexo": es parte del cierre. Si no está registrado, la investigación no está terminada.**

La fila lleva como mínimo: **fecha · qué se probó · resultado resumido · veredicto · ruta al
reporte**, más `n`/WR/PF/Sharpe cuando existan.

Notas de aplicación:
- Se hace **sin que Ariel lo pida**, igual que la regla de guardar reportes en `reports/`.
- Aplica también a resultados negativos y a los "no concluyentes". El valor del índice es no
  repetir una prueba ya hecha, y eso incluye sobre todo las que salieron mal.
- **Si un dato no existe, va `—` (o no se inserta la fila en la DB). Nunca se rellena con un
  número inventado ni con un 0 que se lea como medición.**
- No aplica a diagnósticos de infraestructura sin veredicto cuantitativo (chequeo de screens, fix
  de arranque, reconciliación): ésos van sólo a `reports/`.
- **`data/resultados.db` es la fuente consultable de los números; `INDICE_RESULTADOS.md` y
  `ESTADO_ACTUAL.md` son los espejos legibles y son los que se commitean.** Si un número discrepa,
  manda la DB.
- ⚠️ **Los dos `.md` se completan agregando filas, NO se regeneran borrando y reescribiendo.**
  Verificado el 2026-09-02: `INDICE_RESULTADOS.md` tiene prosa y agrupación por moneda que la DB
  no modela, y `ESTADO_ACTUAL.md` es mayormente narrativo (producción, cola de investigación) más
  filas de proyectos separados (`~/experimento_director_adaptativo/`) que nunca estuvieron en la
  DB. Regenerarlos desde cero **borraría** ese contenido. Por eso `exportar_indice()` se niega a
  sobrescribir `INDICE_RESULTADOS.md`.
- La DB de resultados es un archivo **separado de `signals/bot.db`** a propósito: `bot.db` es
  estado vivo de producción. Ningún módulo de producción importa nada de la DB de resultados.
- ⚠️ La DB registra **lo que se probó, no lo que se ejecutó**. El historial de operaciones reales
  sigue siendo `auditoria.csv`. No confundir una pérdida simulada con una pérdida de la cuenta.

**Por qué esta regla existe.** El mismo protocolo ya se había fijado el 2026-08-24 — pero escrito
**dentro de `INDICE_RESULTADOS.md`**, el archivo que él mismo mandaba actualizar. Nadie lee el
índice antes de cerrar una investigación. Resultado medido: el índice quedó congelado ese día y
**63 reportes posteriores nunca se indexaron**. Por eso ahora la regla vive acá.

## Reportes de análisis
Toda respuesta (análisis, investigación, conclusión — no código) que ocupe más de **15 líneas** se guarda
automáticamente como archivo en `~/bot-padre-v2/reports/`, sin pedir permiso, y en la terminal se muestra
**solo**: el resultado en 1 línea + la ruta del archivo. Nada más se imprime en la conversación.
- Nombre: `YYYY-MM-DD_tema-descriptivo.md` (fecha del día, slug corto en minúsculas con guiones).
- Contenido del archivo: el análisis completo (números, tablas, conclusiones), en Markdown.
- Aplica siempre, sin que Ariel lo pida cada vez — incluida esta misma regla y cualquier respuesta futura.
- `reports/` no se commitea a git (ver `.gitignore`) — son notas de trabajo, no código ni datos operativos.
- **Regla reforzada (2026-08-13):** siempre terminar la respuesta mostrando la ruta exacta y el comando
  `less` listo para copiar, incluso si el resultado ya se mostró parcialmente en pantalla:
  ```
  Resultado en: ~/bot-padre-v2/reports/YYYY-MM-DD_tema.md
  less ~/bot-padre-v2/reports/YYYY-MM-DD_tema.md
  ```

## Proyecto
**Z-Bot Padre v2** — bot de trading algorítmico sobre Binance.
- Dueño: Ariel
- Activos con código propio: BTC, ETH, SOL, BNB, AVAX (ver tabla de estado real abajo — hoy
  BTC/ETH/SOL/AVAX están conectados al ciclo de producción, BNB sigue huérfano)
- Stack: Python puro, Binance REST API, Telegram Bot API, Flask (asistente web)
- **Estado actual (verificado 2026-08-29): modo REAL**, `BOT_REAL_CONFIRMADO=true` activo.
  Capital nominal: $20.00 USDT (`capital_inicial`/`capital_real` en `billetera.json`). USDT libre:
  $14.541 (post-reconciliación de la posición fantasma de ETH, ver
  `reports/2026-08-29_reconciliacion-posicion-fantasma-eth.md`). Francotiradores con dinero real
  operando: BTC ALCISTA, ETH ALCISTA, SOL ALCISTA, AVAX ALCISTA (los 4 conectados hoy a
  `director_orquesta.py` — ver tabla abajo para el detalle completo por fase) — posición ABIERTA
  actual: SOL ALCISTA, $5 desde 2026-08-29.
- Objetivo: mantener REAL con evidencia continua; escalar capital cuando la rentabilidad real lo
  justifique (ver `INVESTIGACION.md` para el historial completo de validación).

## Estado real de francotiradores por moneda × fase (verificado leyendo el código, 2026-08-29)

⚠️ Esta tabla se arma leyendo `dirigir()` completo de cada `director_<moneda>.py` y confirmando
qué llama `director_orquesta.py` — no se copia de documentación anterior. Reverificar del mismo
modo antes de asumir que sigue vigente si pasó mucho tiempo. Detalle completo de esta actualización:
`reports/2026-08-29_francotiradores-activos-bot-real.md`.

| Moneda | Fase | Estado | Motivo / mecanismo verificado |
|--------|------|--------|-------------------------------|
| **BTC** | ALCISTA | ✅ Activo | RSI 50–70, SL 3.5%, TP 6.0%, EMA 20/50, $5/trade, `MAX_OP_TOTAL=1`, trailing 0.5%/1.0%, BE 2 velas +0.8% |
| BTC | BAJISTA | ⏸️ Inerte | El director sí llama `evaluar_bajista()`, pero el gate global `gestor_bajistas.bajistas_activos()` está en `False` (`signals/estado_bajistas.json`: `sin_autorizacion_manual`, actualizado 2026-08-27) y lo corta |
| BTC | LATERAL | ⏸️ Pausado en el director | Comentario literal: *"sin backtest de gates completos esta semana"* — `director_btc.py` ni siquiera llama a `evaluar_lateral` |
| **ETH** | ALCISTA | ✅ Activo | RSI 60–75, SL 4.5%, TP 5.0%, EMA 20/100, $5/trade hardcodeado |
| ETH | BAJISTA | ⏸️ Ni se llama | `director_eth.py` no importa ni llama `evaluar_bajista` — solo imprime *"BAJISTA desactivado — solo ALCISTA y LATERAL"* |
| ETH | LATERAL | ⏸️ Desactivado por código propio | El director sí llama `evaluar_lateral()`, pero la función hace `return` incondicional desde 2026-08-13 (backtest forense PF 0.90). `revisar_cierres` sigue activo para proteger posiciones ya abiertas |
| **SOL** | ALCISTA | ✅ Activo (reactivado 24-ago) | `director_sol.py` llama `evaluar_alcista()` sin condición. Reactivado en commit `4dd1ba5` ("activar combo O en produccion SOL+AVAX ALCISTA") |
| SOL | BAJISTA | ⏸️ Inerte | Mismo gate global `gestor_bajistas` que BTC |
| SOL | LATERAL | ⏸️ Pausado por código propio (29-ago) | Commit `5713c0a`: `francotirador_lateral_sol.py` hace `revisar_cierres(precio_actual, evaluar_tp=True); return` incondicional al entrar a `evaluar()` — torneo del 24-ago lo marcó débil (PF 0.928) |
| **BNB** | las 3 | ⏸️ Director huérfano | `director_bnb.py` tiene las 3 fases codificadas **sin ninguna pausa interna** (ALCISTA y BAJISTA sin condición, LATERAL desactivado por código propio), pero `director_orquesta.py` no lo importa ni lo llama — nunca se ejecuta en producción |
| **AVAX** | ALCISTA | ✅ Activo (conectado 24-ago) | `director_avax.py` ahora está importado y llamado por `director_orquesta.py` (antes huérfano). Llama `evaluar_alcista()` sin condición, mismo commit `4dd1ba5` |
| AVAX | BAJISTA | ⏸️ Inerte | Mismo gate global `gestor_bajistas` |
| AVAX | LATERAL | ⏸️ Pausado por código propio (29-ago) | Mismo commit `5713c0a` que SOL lateral, mismo patrón (`revisar_cierres` + `return` incondicional), torneo del 24-ago lo marcó débil (PF 0.985) |

## Arquitectura
```
main.py                  ← orquestador principal (NO ejecuta órdenes, NO toca capital)
├── director_orquesta.py ← fase LOCAL por moneda → BTC/ETH/SOL/AVAX. Ojo: cerrar_huerfanas()
│                          usa la fase GLOBAL, ver sección al final
├── director_<activo>.py ← uno por activo, decide qué francotirador activar
│   └── francotirador_<fase>_<activo>.py ← genera señales de entrada
├── ejecutor.py          ← ÚNICO autorizado para abrir/cerrar posiciones
├── guardian_riesgo.py   ← DD máximo 10%, pérdida diaria máx 5%
├── centinela/           ← ⚠️ NO vigila nada. Observador aislado, ver sección al final
├── brain/
│   ├── telegram_engine.py  ← polling de comandos + envío de alertas
│   ├── data_engine.py      ← fetch de velas desde Binance
│   └── core.py
├── signals/             ← archivos de estado compartidos entre módulos (JSON)
├── memoria/             ← logs por categoría (eventos, corecro, matrix, centinela)
├── constitution/        ← leyes supremas del bot (nunca violar)
└── config/              ← billetera.json
```

## Procesos en pantalla (screen)
Cada módulo corre en su propia sesión `screen`. Total esperado: **29 sesiones** desde el
2026-09-06, cuando `z_executor` se apagó a propósito (eran 30; verificado 2026-09-01: 30 activas,
coincidía).

⚠️ El conteo anterior decía 29 pero la lista de abajo solo enumeraba 28 nombres: faltaban
`motor_confluencia` (que ya existía) y la sesión de Claude Code. Ambas están listadas ahora, y
el total (30) coincide con la lista.

**bot-padre-v2:**
- `v2_main` → `main.py`
- `z_asistente` → `asistente.py` (Flask en :5050)
- `z_tunnel` → `tunnel_asistente.py` (cloudflared)
- `z_dashboard_v2` → `z_webserver_v2.py`
- `z_diagnostico` → `auto_diagnostico.py`
- `z_precision`, `z_volumen`, `z_fugas`, `z_fuerza`, `z_liquidez`, `z_velas`, `z_heatmap`, `z_correlation`
- `z_radar` → `radar_noticias.py`
- `z_intel` → `servidor_intel.py`

**zbot/radar:**
- `z_auditor` → `auditor_supremo.py`
- `z_webserver` → `z_webserver.py`
- ~~`z_executor` → `radar_executor.py`~~ — **APAGADO el 2026-09-06 por decisión de Ariel.** El
  score del radar no tiene valor predictivo (control pareado lo iguala, correlación negativa sobre
  n=432k) y el proceso consumía 1.016 MB de RAM sin aportar nada. La línea sigue en
  `iniciar_bots.sh` pero comentada; para reactivarlo hay que descomentarla **y** volver a agregar
  `z_executor` a `SCREENS_ESPERADOS` en `monitor_screens.py`.
- `z_squeeze` → `squeeze_detector.py`
- `z_macd` → `macd_engine.py`
- `z_rsi_adv` → `rsi_advanced.py`
- `z_vol_engine` → `volumen_engine.py`
- `z_sentiment` → `z_sentiment.py`
- `z_orderblocks` → `orderblock_engine.py`
- `z_timeframes` → `timeframe_engine.py`
- `z_ignition` → `ignition.py`
- `z_heatmap_radar` → `heatmap.py`
- `z_wicks` → `wick_analyzer.py`

**Otros proyectos levantados por el mismo script:**
- `motor_confluencia` → `main.py` de `~/motor-confluencia` (rescatado jun 2026, no es del bot v2)

**Claude Code (desde 2026-09-01):**
- `z_code` → `claude --remote-control z_code` en `~/bot-padre-v2`

  Sesión de Claude Code que arranca sola tras un corte de luz, para poder entrar desde el celular
  sin estar frente a la Dell. Reemplaza a la vieja `claude_code`, que entró de arrastre en jun 2026
  y estaba rota en dos formas (ver `reports/2026-09-01_arranque-automatico-claude-code.md`).

  **No usa `iniciar()` como el resto — tiene su propio bloque en `iniciar_bots.sh`.** Motivo:
  `proceso_activo()` identifica el proceso extrayendo un nombre de archivo `.py` del comando; con
  `claude` sale vacío, siempre da "no está corriendo", y la rama de limpieza **mataba la sesión
  viva** (quedó registrado como `[WIPE] claude_code` en `memoria/arranque.log`). El guard propio
  (`claude_en_screen_activo()`) mira `/proc`: busca un proceso `claude` con cwd en el proyecto y
  cuyo padre sea un `screen`.

  ⚠️ Dos detalles que hay que respetar si algún día se toca esa parte:
  - **El binario se resuelve por ruta absoluta, no por PATH.** Bajo `@reboot` el PATH de cron es
    `/usr/bin:/bin` y `claude` no está ahí (vive en `~/.nvm/versions/node/<version>/bin/`). Sin
    esto la screen arranca y muere al instante con `command not found`.
  - **`TERM` se exporta a mano** (`xterm-256color`): bajo cron viene vacío y Claude Code es una TUI.

Para verificar caídas: `python3 monitor_screens.py`

Para iniciar/reiniciar todos los procesos: `bash iniciar_bots.sh`
- Si el screen no existe → lo crea
- Si el screen existe y está vivo → lo saltea (`[SKIP]`)
- Si el screen existe pero está Dead → hace `screen -wipe` y lo reinicia (`[DEAD]` → `[OK]`)

**IMPORTANTE al reiniciar un screen manualmente:**
`screen -S nombre -X quit` mata la sesión pero NO el proceso Python hijo.
Siempre matar el proceso también: `kill $(pgrep -f archivo.py)`
De lo contrario queda un zombie haciendo polling doble → error 409 en Telegram.

⚠️ **`pgrep -f` matchea por substring y cruza proyectos.** `pgrep -f main.py` también
devuelve el `main.py` de `~/motor-confluencia`, así que `kill $(pgrep -f main.py)` mata un
bot ajeno. Para `v2_main` **usar siempre PIDs explícitos**, verificados antes con
`pgrep -af main.py` y `readlink /proc/<pid>/cwd`.

## Modo de operación
- Modo actual: `signals/modo.json` → `{"modo":"REAL","intervalo_velas":"4h","sleep_segundos":240}`
- Para cambiar de modo: editar `signals/modo.json`. **`config/modo.txt` fue eliminado el
  2026-08-15** (auditoría C-03): decía `SIMULACION` sin que ningún módulo lo leyera —
  contradecía `modo.json` en silencio y funcionaba como un falso interruptor de emergencia.
- **No cambiar el modo sin autorización explícita de Ariel**
- **Segunda confirmación técnica (desde 2026-07-29, commit `0278d48`):** `modo.json` diciendo
  `"REAL"` no alcanza por sí solo. `ejecutor.py` (`ejecutar_operacion`, `cerrar_posicion`)
  también exige la variable de entorno `BOT_REAL_CONFIRMADO=true` en el proceso de `v2_main`
  — si falta, opera en SIMULADOR aunque el JSON diga REAL.
- **Fallback seguro (desde 2026-08-12, commit `0aee782`):** `_leer_modo()` en `ejecutor.py` y
  `director_orquesta.py` devuelve `"SIMULADOR"` (y loguea el motivo) si `modo.json` falta, se
  corrompe o se lee a medio escribir — nunca asume `"REAL"` por defecto.
- **Llave persistente para `BOT_REAL_CONFIRMADO` (desde 2026-08-15, commit `b547d81`).** La
  variable sobrevive a un reinicio del servidor mediante un archivo fuera del repo que Ariel crea
  a mano una sola vez: `~/.bot_real_confirmado` (vacío, solo su existencia importa). Dos lectores
  independientes de ese archivo, misma lógica:
  - `iniciar_bots.sh` (disparado por `@reboot` en crontab, `sleep 30 && iniciar_bots.sh`): si el
    archivo existe, arranca `v2_main` con `export BOT_REAL_CONFIRMADO=true && python3 main.py`.
    Si no existe, arranca sin la variable → SIMULADOR aunque `modo.json` diga REAL.
  - `watchdog.py` (cron cada 5 min, solo actúa si `main.py` no está vivo): mismo chequeo, respaldo
    si el que revive `v2_main` es el watchdog en vez de `iniciar_bots.sh`.
  - `modo.json` y `~/.bot_real_confirmado` son dos archivos distintos en ubicaciones distintas
    (uno dentro del repo, el otro fuera de `$HOME` y fuera de git) — la segunda confirmación
    técnica sigue siendo real, no se acopló todo a un único archivo.
  - **Verificado en vivo dos veces** (2026-08-18 simulando corte de luz, y 2026-08-22 con un corte
    real): `v2_main` relanza solo con `BOT_REAL_CONFIRMADO=true`, `modo.json` intacto, posiciones
    sin alterar, sin tracebacks.
  - **Runbook — si volvés y el bot está en SIMULADOR sin que lo hayas cambiado vos:**
    1. `screen -r v2_main` y mirar el log: si dice `[SIMULADOR]` en vez de `[REAL]` en las
       aperturas/cierres, o no aparece `[CENTINELA] Capital real leido desde billetera.json`,
       confirma el diagnóstico.
    2. Verificar `signals/modo.json` — si sigue en `"REAL"`, el problema es la variable de
       entorno, no el modo configurado.
    3. Verificar que `~/.bot_real_confirmado` exista (`ls -la ~/.bot_real_confirmado`). Si no
       existe, ese es el motivo — créalo (`touch ~/.bot_real_confirmado`) para que el próximo
       arranque automático lo tome. Si existe pero igual arrancó en SIMULADOR, revisar
       `memoria/arranque.log` por si `iniciar_bots.sh` falló antes de llegar a `v2_main`.
    4. **Exportar la variable en una shell nueva no alcanza para el proceso ya corriendo**:
       `os.environ` de un proceso vivo no cambia por un `export` posterior en la terminal. Hay
       que matar el proceso real (`pgrep -af main.py` + verificar `readlink /proc/<pid>/cwd`
       antes de matar — no usar `kill $(pgrep -f main.py)` a ciegas, cruza con otros bots) y
       volver a lanzarlo desde una shell donde la variable ya esté exportada:
       ```
       screen -S v2_main -X quit
       kill <PID_verificado>
       screen -dmS v2_main bash -c "cd ~/bot-padre-v2 && export BOT_REAL_CONFIRMADO=true && python3 main.py"
       ```
    5. Confirmar en el log del screen que ahora sí opera en modo REAL antes de dar por resuelto.

## Dirección de operación — SPOT solo-LONG (desde jun 2026)
- El bot opera **solo ALCISTA y LATERAL**. Los 5 francotiradores bajistas están desactivados.
- Razón: hacer SHORT es imposible en cuenta SPOT. En SIMULADOR generaba balances de cripto
  negativos (causa raíz de los negativos en billetera).
- Gate central: `gestor_bajistas.py` → `bajistas_activos()`. Cada `evaluar()` bajista lo consulta
  y retorna temprano si está desactivado. Estado actual (verificado 2026-08-22,
  `signals/estado_bajistas.json`): `activos: false`, `motivo: sin_autorizacion_manual`.
- **Reactivación MANUAL.** Exige **dos** condiciones: `BOT_BAJISTAS_CONFIRMADO=true` en el
  entorno del proceso **y** `availableBalance` USDT ≥ 5.0 en Futuros USDT-M. Sin la variable
  corta antes de consultar la API. Cachea 5 min; ante error de API → desactivado. La variable
  sigue el patrón de `BOT_REAL_CONFIRMADO`: no vive en ningún archivo del repo, se exporta a mano
  el día que se decida — **después** de reescribir el ejecutor para futuros.
- **Fondear futuros por cualquier motivo no reactiva shorts reales** — la ruta de ejecución sigue
  siendo spot. `ejecutor.py:cerrar_posicion` cierra shorts con BUY spot; para shorts reales en
  futuros hay que reescribir el ejecutor, reactivar el gate no basta.
- Ver `INVESTIGACION.md` para el backtest de 5.4 años que sustenta desactivar bajistas y el
  detalle del incidente que dejó el gate en `false` por accidente en su momento.

## Camino de dinero — reglas de oro y qué no tocar

### `auditoria.csv` — estructura (8 columnas)
```
timestamp,accion,symbol,precio,rsi,estado,monto,qty
```
- `precio` es el fill real de Binance (no el cierre de vela). `qty` es `executedQty` **neto de
  comisión** del fill de entrada — es la cantidad con la que se cierra. Filas viejas sin esa
  columna caen a un cálculo teórico.
- Retrocompatible: los módulos que leen el archivo usan `len(partes) >= N` e indexan 0..6.
  Agregar columnas al final no rompe nada. **No insertar columnas en el medio.**
- **Estados:** además de `ABIERTA`/`TP`/`SL`/`TRAILING_SL`/`BE`/`FASE_CAMBIO`, existen
  `RESERVADA` (fila escrita ANTES de mandar la orden, bajo `AUDITORIA_LOCK`) y `ANULADA` (la
  orden falló o fue rechazada, se conserva como rastro). `contar_operaciones_abiertas()` cuenta
  `RESERVADA` además de `ABIERTA` — si el proceso muere entre la reserva y la orden, la fila
  huérfana frena compras nuevas en vez de habilitarlas.

### Reglas de oro
1. **Escribir la fila ANTES de mandar la orden.** El bot decide leyendo `auditoria.csv`; si opera
   primero y anota después, un fallo al anotar hace que repita la operación.
2. **Todo append a `auditoria.csv` va bajo `AUDITORIA_LOCK`.** `revisar_cierres()` y
   `cerrar_huerfanas()` leen el archivo entero y lo reescriben con `os.replace`; una fila
   appendeada sin lock en medio de esa reescritura **se pierde**.
3. **Marcar el cierre ANTES de contabilizar, nunca al revés.** Si la contabilidad falla y la fila
   vuelve a `ABIERTA`, el ciclo siguiente re-vende una posición que ya no existe. `_contabilizar()`
   envuelve `registrar_tp/sl` y nunca propaga la excepción: avisa por Telegram del descuadre y
   sigue.
4. **Nunca salir en silencio después de haber operado.** Cualquier early return post-venta que no
   toque la billetera debe avisar por Telegram del descuadre.
5. **`ejecutar_operacion()` y `cerrar_posicion()` devuelven `(mensaje, fill)`, no un string
   suelto.** Hay que desempaquetar la tupla (`fill = {"qty", "usdt", "precio"}`, o `None` si la
   orden falló/fue rechazada).
6. **Truncar cantidades al `LOT_SIZE`, nunca `round()` ni `floor()` sobre float.** `round()` hacia
   arriba pide más de lo que hay en cuenta → rechazo `-2010` → el cierre falla y la posición queda
   `ABIERTA` sin stop. `floor()` sobre float se come un tick entero por error binario
   (`0.29 * 100 = 28.999999999999996`). Usar `Decimal`/`ROUND_DOWN`.
7. **`guardian_riesgo.py` nunca decide con datos incompletos.** `_obtener_precio()` devuelve
   `None`, nunca `0.0` (un `0.0` hundiría el capital calculado y dispararía un drawdown
   inexistente). `cargar_billetera()` levanta `DatosIncompletos` si alguna moneda con saldo se
   quedó sin precio — `esta_bloqueado()` lo captura, pausa el ciclo, y **no persiste nada en la
   DB** (transitorio: cuando vuelve la red, el guardián autoriza solo). Ante cualquier duda sobre
   los datos, pausar sin escribir estado — un bloqueo persistido solo puede venir de un drawdown
   calculado con todos los precios disponibles.
8. **`reconciliar.py` (barrido de polvo) vende de verdad, vía `cerrar_posicion(qty=...)`** — nunca
   tocar `billetera.json` directamente sin mandar la orden real. Respeta los mismos locks
   (`billetera.json.lock`, `AUDITORIA_LOCK`). Solo corre manual desde Telegram
   (`/reconciliar confirmar`) — vende dinero real, no debe correr sin supervisión.

### Cambios aplicados el 2026-08-31 (puntos ciegos del camino del dinero)

Ambos salen del análisis `reports/2026-08-31_puntos-ciegos-camino-del-dinero.md`, que buscó lugares
donde el bot puede fallar **en silencio** con dinero real, como pasó con el bug de NOTIONAL.

**1. `MONTO_FIJO` de BTC: $7 → $10** (`francotirador_alcista_btc.py:37`). Solo BTC; ETH, SOL y AVAX
siguen en $7.
- **Qué reemplaza:** con $7, el truncamiento al `stepSize` (0.00001) **después** de la comisión
  dejaba la cantidad cerrable en **0.00007 BTC = $5,49** de un ticket de $7.
- **Evidencia:** margen sobre el minNotional de solo **5,7%** (bastaba una caída del 8,74% para que
  el cierre quedara bloqueado, con un SL de 3,5%), y **12,4% de la posición inmovilizada como polvo
  en cada trade**. Barriendo el precio de BTC entre $40k y $150k, con $7 el margen mínimo es
  **−18,9%**: a ~$140.000 el guardián de entrada habría rechazado toda operación de BTC. Con $10 el
  margen mínimo sube a **+37,9%** y el de hoy a 66%.
- **Efectos secundarios revisados** (`reports/2026-08-31_analisis-efectos-secundarios-btc-10.md`):
  siguen cabiendo las 4 monedas a la vez ($31 de $37,21); el umbral en que dejarían de caber ($31)
  queda **por debajo** del bloqueo del guardián ($33,79), así que no se puede alcanzar; el único
  efecto confirmado es más concentración en BTC (25% → 32%).

**2. `ejecutor.py`: validación de `status` y distinción de orden incierta.**
- **Qué reemplaza:** antes se daba por buena **cualquier** respuesta HTTP 200 (`status` nunca se
  miraba), y el `except` de la orden **no distinguía** "no se envió" de "se envió y no supe el
  resultado". Ese segundo caso marcaba la fila `ANULADA` y el bot se olvidaba de una posición que
  podía existir de verdad — es exactamente la posición fantasma de ETH
  (`reports/2026-08-29_reconciliacion-posicion-fantasma-eth.md`).
- **Qué hace ahora:**
  - **Rechazo definitivo** (`RuntimeError`, la orden no existe): `status` `REJECTED`/`EXPIRED`/
    `CANCELED`, `executedQty = 0`, HTTP 4xx, y **fallo de DNS** (la petición nunca salió).
  - **`OrdenIncierta`** (pudo ejecutarse): timeout, HTTP **5xx** —estado desconocido según la propia
    doc de Binance—, conexión cortada a mitad, JSON ilegible, y `status` ausente o desconocido.
    Ante esto **nunca** se asume que no hay posición: se escribe un marcador
    `signals/ORDEN_INCIERTA_<symbol>_<side>_<ts>.json` y se avisa por Telegram para reconciliar a
    mano.
  - **`PARTIALLY_FILLED`** se acepta (la `executedQty` real manda) pero **avisa**, porque queda saldo
    sin operar en Binance.
- **Verificación:** 14 escenarios probados con respuestas simuladas (sin tocar Binance ni dinero),
  14/14 clasificados como corresponde.
- **No cambia** ninguna estrategia, TP, SL, entrada ni sizing: solo cómo se interpreta la respuesta.

⚠️ **Los cambios en `ejecutor.py` no tienen efecto hasta reiniciar `v2_main`**: el proceso tiene el
módulo cargado en memoria desde su arranque.

### Qué no tocar
> ⚠️ **No restaurar el simulador sobre `auditoria.csv` real.** El backup completo de 386
> operaciones de paper trading vive en
> `NUNCA_RESTAURAR_auditoria_simulador_386trades_2026-08-15.csv.bak` (raíz del proyecto). Si se
> sobrescribe `auditoria.csv` con ese archivo, el bot en REAL vería 386 operaciones históricas que
> nunca ocurrieron en Binance.

**Polvo inmovilizado — punto abierto, no resuelto.** Al cerrar hay que truncar al `stepSize` y el
resto queda como cripto suelta, sin respaldar ninguna posición. No se pierde (sigue en
`billetera.json` y el guardián lo valoriza) pero distorsiona el PnL reportado por trade hasta
varios puntos porcentuales. **No barrer el saldo completo dentro de `cerrar_posicion`** — eso
realizaría el polvo viejo como ganancia del trade en curso, reubicando la distorsión en vez de
eliminarla. El mecanismo correcto es `reconciliar.py` (manual, ver regla de oro 8), fuera del
ciclo de trades.

Historial completo de los fixes que llevaron a este contrato (ejecutor #3/#4, guardian #7,
reconciliar #9, auditoría pre-REAL): ver `INVESTIGACION.md`.

## Cambios que afectan capital, monto por trade o cantidad de monedas simultáneas
**Regla permanente (desde 2026-08-30).** Antes de aplicar cualquier cambio que toque capital,
`MONTO_FIJO`/monto por trade, o cuántas monedas pueden operar a la vez (`MAX_OP_TOTAL`, cantidad
de francotiradores conectados), es obligatorio presentar un **análisis de efectos secundarios**
ANTES de implementar — no alcanza con "esto resuelve el problema X".

El análisis tiene que decir explícitamente: *"esto también podría causar Y y Z en otras partes del
sistema — revisado y descartado/confirmado"*, con evidencia real (código, números, logs), no
opinión. Ejemplo del formato esperado: ver
`reports/2026-08-30_analisis-riesgo-subir-monto-por-trade.md` (subir el monto por trade resuelve
el NOTIONAL, pero reduce cuántas monedas pueden operar a la vez con el mismo capital — ambos
efectos, el buscado y el secundario, cuantificados antes de decidir).

**No se avanza a la implementación hasta que Ariel confirme explícitamente ese análisis.** Mismo
espíritu que la regla de "aprobar antes de cambios" para francotiradores (backtest antes de
aplicar), pero específico para cambios de capital/sizing: acá el backtest no alcanza porque el
riesgo no es de estrategia, es de mecánica de cuenta (NOTIONAL, concentración, margen del
guardián).

## Constitución (reglas irrompibles)
- El capital base nunca se retira — solo ganancias netas
- La inacción es victoria si el capital está en riesgo
- Ninguna orden puede violar la Constitución (`constitution/constitution.yaml`)

## Git
- Hacer commit y push después de cada cambio importante
- Remote SSH: `git@github.com:aroelcapellan21-sudo/ZBOT-V2.git`
- Nunca commitear `keys.env` ni archivos con credenciales

## Seguridad
- Las claves están en `keys.env` (Binance API, Telegram token, Anthropic API key)
- `keys.env` está en `.gitignore` — nunca modificar esa regla
- No loguear ni imprimir claves en ningún módulo

## Código
- Sin librerías externas salvo las ya usadas (no agregar dependencias sin consultar)
- No usar `except: pass` — siempre loguear errores
- Cambios en francotiradores requieren backtest previo con umbral PF ≥ 1.6
- Los parámetros de los francotiradores están validados por backtest — no cambiar sin evidencia
- **Patrón obligatorio de salidas vs. gates de entrada:** en `evaluar()` de cada francotirador,
  todo gate de entrada que hace `return` antes de llegar al chequeo final debe llamar primero
  `revisar_cierres(precio_actual, evaluar_tp=False)` (o `True` si el gate es de fase/dirección,
  como `gestor_bajistas`) — una posición ya abierta necesita seguir protegida por SL aunque el
  gate bloquee entradas nuevas ese ciclo. Historial completo del hallazgo, los backtests
  (`FIXED` −44.3pp, `SOLO_SL` −10.6pp) y la única excepción documentada
  (`francotirador_lateral_eth.py`, desactivado por código): ver `INVESTIGACION.md`.
- **`config_cartera.py` no es fuente de verdad universal — verificado 2026-08-22.**
  `francotirador_alcista_btc.py` no lo importa: RSI/SL/EMA_LARGA están hardcodeados y **difieren**
  del diccionario `BTCUSDT.alcista` de `config_cartera.py` (que queda muerto para BTC). ETH
  ALCISTA y SOL LATERAL sí llaman `get_params()` y lo leen en vivo (SOL con el trailing hardcodeado
  aparte, sin discrepancia numérica hoy). **Antes de asumir el valor de un parámetro, comprobar con
  `grep` si el francotirador en cuestión importa `config_cartera` o lo tiene hardcodeado** — no
  asumir por lo que dice este archivo. Detalle completo:
  `reports/2026-08-22_config_cartera-codigo-muerto-3-francotiradores-activos.md`.

## ⛔ El trailing stop y el breakeven están rotos A PROPÓSITO — NO LOS ARREGLES

**Si llegaste acá porque viste que el trailing no funciona: sí, está roto. Ya lo sabemos. Fue
medido dos veces y arreglarlo EMPEORA el resultado. No lo toques sin leer esto entero.**

### Qué está roto y por qué lo parece tanto

En `revisar_cierres()` de cada francotirador (p. ej. `francotirador_alcista_sol.py:221-235`),
`sl_efectivo` es una **variable local que se recalcula de cero en cada ciclo** y se ancla al
**precio actual**, no al máximo del trade:

```python
if cambio > 0:
    sl_trail    = round(precio_actual * (1 - TRAILING_DISTANCIA / 100), 4)
    sl_efectivo = max(sl_efectivo, sl_trail)     # <- desde el precio ACTUAL, no el maximo
```

Consecuencias, demostradas formalmente (no estimadas):
- **El stop retrocede** cuando el precio baja. Un trailing real sólo sube.
- Mientras el trailing manda, la condición de cierre es `precio_actual <= precio_actual × 0,99`,
  **falsa por construcción**: el trailing no puede dispararse nunca.
- El BE exige `cambio >= 0,8%` **en el ciclo actual**, así que nunca queda "armado".
- **`sl_efectivo` no se persiste en ningún archivo ni tabla** — por eso no hay estado que mantener.

**Resultado neto: el sistema opera con TP fijo + SL fijo.** Por eso hay **0 estados `TRAILING_SL` y
0 `BE`** en todo el historial (9 años de backtest y todas las filas de `auditoria.csv`). No son
estados raros: son **inalcanzables**. Si contás cierres por trailing y te da cero, no es un bug de
tu consulta.

### Por qué NO se arregla — dos mediciones independientes

| Intento | Resultado | Veredicto |
|---|---|---|
| **Arreglar la versión inline** (persistir el máximo y anclar ahí el trailing) | PF **0,94** vs **0,98** actual · **mata 73 TP** (194 → 121) | 🔴 No aplicar |
| **Barrido completo de parámetros** de ese mismo fix (varias distancias y activaciones) | Mejor combinación: PF **1,00** (trailing 3%) · **ninguna** pasa PF ≥ 1,6 | 🔴 No aplicar |
| **Conectar `trailing_stop.py`** (auditoría económica 2026-08-31, 401 operaciones, mar–ago 2026) | PF **0,583** vs **0,919** actual · PnL **−$11,33** · **mata 152 de 168 TP** · win rate 42,1% → 29,4% | 🔴 Descartado |

**Antes de proponer "probémoslo con otra distancia": ya se barrió el espacio de parámetros.** La
tendencia es monótona y va en contra: cuanto **más ancho** el trailing, mejor el PF y más TP
sobreviven — es decir, el óptimo tiende a *no tener trailing*. El techo del barrido (PF 1,00) queda
a 0,6 puntos del umbral de 1,6.

**El mecanismo es siempre el mismo:** un trailing que funciona cierra las operaciones antes de que
lleguen al TP. Con TP de 4–7% y distancias de trailing de 1–1,5%, cualquier retroceso normal del
mercado corta el trade. El trailing roto, al ser inoperante, **deja correr las operaciones hasta el
TP — y eso rinde más**.

Detalle por moneda del segundo estudio: donde el sistema pierde, el trailing amortigua; **donde
gana, lo destruye**. En BNB (PF 3,39) y ETH (PF 2,26) —las dos únicas monedas rentables del
período— `trailing_stop.py` se lleva el **98%** y el **84%** del beneficio.

Ninguna de las dos alternativas alcanza el umbral **PF ≥ 1,6** que este proyecto exige para tocar
francotiradores. Por eso no se aplican.

### `trailing_stop.py` — existe, está huérfano, y así se queda

Hay un módulo `trailing_stop.py` en la raíz con un trailing **técnicamente correcto** (persiste
`trailing_sl` en la DB y sólo lo sube, `línea 59`). Es tentador: parece "la versión buena que
alguien olvidó conectar". **No lo conectes.**

- **Nadie lo importa** (`grep -rn "trailing_stop" --include=*.py .` sobre imports → vacío) y no
  figura entre los módulos alcanzables desde producción.
- **La tabla `trailing_data` no existe en `signals/bot.db`** → nunca se ejecutó ni una vez.
- Su condición de cierre (`línea 70`) exige además `cambio > -(TRAILING_DISTANCIA + 0.5)`: por
  debajo de −2% **deja de cerrar**, así que tampoco sirve como protección de pérdida por sí solo.
- Fue medido: es la columna "conectar `trailing_stop.py`" de la tabla de arriba.

### Qué SÍ es cierto y conviene no confundir

- **No hay riesgo abierto.** El SL base funciona y protege la pérdida. Lo que no existe es la
  protección de ganancia.
- `TRAILING_ACTIVACION` y `TRAILING_DISTANCIA` en los francotiradores son, hoy, **cosméticos**:
  cambiarlos no altera ninguna salida.
- Si algún día se quiere trailing de verdad, no es una "reparación": es un **cambio de estrategia**
  que necesita backtest propio con PF ≥ 1,6 y OK explícito de Ariel, y probablemente una columna
  nueva **al final** de `auditoria.csv` (nunca en el medio).

Reportes con la evidencia completa:
`reports/2026-08-31_auditoria-economica-trailing.md` (el estudio de 401 operaciones),
`reports/2026-08-31_backtest-fix-breakeven-trailing.md` y
`reports/2026-08-31_chequeo-profundo-salud-bot.md` (causa raíz).

## ⛔ Termómetro y Centinela — también rotos, tampoco se arreglan (2026-08-31)

Mismo criterio que el trailing: **se midieron económicamente y ninguno demostró mejora**, así que
**no se tocó una línea de código de ninguno de los dos**. Lo que sigue documenta por qué, para que
nadie los "repare" creyendo que encontró un bug sin explorar.

### 🌡️ Termómetro — gate congelado desde el 4 de marzo

`puede_operar_termometro()` es uno de los 10 gates de entrada y lo llaman los 4 francotiradores
activos (`francotirador_alcista_btc.py:333`, `eth.py:608`, `sol.py:327`, `avax.py:327`). Lee su
estado de `db.json_get("estado_termometro")`.

**Quien actualiza ese estado es `clasificar_mercado()` (`termometro.py:44-75`), y sólo se invoca
desde su propio `if __name__ == "__main__"` (`línea 149`).** No hay screen, ni cron, ni import que
lo ejecute (verificado sobre `iniciar_bots.sh`, `arrancar_maestro.sh` y `crontab -l`). El estado en
la DB tiene una medición del **2026-03-04**: `TENDENCIA_DEBIL`, `operar: True`. **El gate deja pasar
el 100% de las señales: hoy es un no-op.**

**Evidencia económica de conectarlo (`reports/2026-08-31_termometro-impacto-economico.md`,
reconstrucción hora por hora con 5.495 velas 1h reales por moneda, ene–ago 2026):**

| | Resultado |
|---|---|
| Tiempo que bloquearía | **31,89%** (y **66,2% en agosto**) |
| Operaciones reales que habría bloqueado | **4 de 8 (50%)** |
| PnL de esas 4 (dinero real) | **+$0,3433** → conectarlo habría **costado $0,34** |
| Misma prueba sobre 393 ops simuladas | **−$0,38** → habría ahorrado $0,38 |
| Significancia | IC 95% **incluye el cero** en ambas |

**Los dos signos se contradicen y ninguno es significativo → sin mejora demostrada → 🔴 NO
CONECTAR.** El costo cierto, en cambio, sí es medible: perder la mitad de las operaciones en un bot
que ya opera poco. Si algún día se quiere el filtro, entra como **cambio de estrategia** con
backtest propio (PF ≥ 1,6), no como reparación.

**⚠️ ADVERTENCIA OPERATIVA — no ejecutes `python3 termometro.py`.** Correrlo a mano **escribe**
`estado_termometro` en la DB y ese valor queda congelado para siempre (nada vuelve a actualizarlo).
Reconstruyendo las últimas 24 h del análisis, **15 de 24 horas habrían dado `MERCADO_MUERTO`
(`operar: False`)**: si el congelamiento cae ahí, el gate pasa a **bloquear el 100% de las entradas
de las 4 monedas, de forma permanente y silenciosa** — sin log de la transición y sin aviso de
Telegram (el aviso de `guardar_estado()` sólo salta si el estado *cambia*, y no volvería a cambiar).
El síntoma sería "el bot dejó de abrir posiciones" sin ninguna otra pista. Las rachas de
`MERCADO_MUERTO` llegaron a **376 horas seguidas (15,7 días)** en el histórico.

**Por qué esto NO se arregló quitando el gate:** quitarlo daría exactamente **$0,00** de diferencia
(el gate no filtra nada hoy), así que no hay mejora económica que lo justifique — y este proyecto no
cambia código de producción por limpieza. La contramedida elegida es de costo cero: **esta
advertencia**. El disparador del fallo es una acción humana, así que documentarlo lo previene.

**Dos hallazgos del código que conviene no repetir:** la rama `VOLATILIDAD_EXTREMA` **nunca se
activó ni una hora** en 7,5 meses (volatilidad máxima observada 1,18% contra un umbral de 2,0%), así
que el gate **sólo detecta mercado quieto, no volatilidad**; y `obtener_multiplicadores()`
(`tp_mult`/`sl_mult`) **no la llama nadie**, así que conectarlo **no cambiaría ningún TP ni SL**.

### 🛡️ Centinela — no es una red de seguridad, es un observador aislado

`CLAUDE.md` lo describía como *"monitorea posiciones abiertas en tiempo real"*. **Era falso en los
tres niveles** y por eso se corrigió el diagrama de arquitectura. Consume un hilo permanente de
`main.py` (`main.py:104`) y **no puede afectar ninguna decisión de trading**:

1. **Su capital nunca se actualiza.** `drawdown.evaluar()` lee `estado.get("capital_actual")`, y
   `estado.actualizar_capital()` sólo se llama en el `if __name__ == "__main__"` de
   `centinela/modulos/drawdown.py:73-74`, con valores de prueba (1000.0 / 980.0). **El drawdown vale
   0 para siempre**: es estructuralmente incapaz de detectar la caída que dice vigilar.
2. **Nadie lee su veredicto.** `alertas.py:67` escribe `estado.set("sistema_pausado", True)`, pero
   `sistema_pausado` y `modo_panico` no se consultan desde ningún módulo fuera de `centinela/`. Su
   estado vive sólo en RAM y se pierde en cada reinicio.
3. **Su canal de alertas está vacío.** `TELEGRAM_TOKEN_ALERTAS = ""` en `centinela/config.py:47`,
   así que toda alerta termina en un `print` dentro de un screen que nadie mira.

Además, su módulo `operaciones` —el único que miraba posiciones— está comentado desde la auditoría
V2.12 (`centinela/centinela.py:20` y `66-73`), y `centinela/estado/estado_global.py:14` conserva un
`except:` desnudo con **fallback de $1.000** (el mismo patrón que `guardian_riesgo.py` eliminó a
propósito), leyendo además sólo `USDT` y no el capital total.

**Evidencia económica: su efecto sobre el dinero es exactamente CERO**, en ambas direcciones. No
abre, no cierra, no bloquea. Por lo tanto **ninguna reparación suya puede demostrar mejora
económica** — ni conectarlo, ni apagarlo, ni arreglar el fallback. **🔴 NO TOCAR el código.**

Conectarlo de verdad **no sería una reparación sino un rediseño**: agregaría una **segunda autoridad
de bloqueo** junto a `guardian_riesgo.py`, y habría que definir cuál manda. No se hace sin decisión
explícita de Ariel y evidencia propia.

**Lo único que importaba acá era la documentación:** quien lea el árbol de arquitectura no debe
creer que existe una protección que no existe. El guardián de riesgo (`guardian_riesgo.py`) **sí**
funciona y cubre drawdown máximo y pérdida diaria — esa es la red de seguridad real del sistema.

Evidencia completa: `reports/2026-08-31_termometro-impacto-economico.md` y
`reports/2026-08-31_auditoria-arquitectura-y-conexiones.md`.

## ⚠️ `cerrar_huerfanas()` usa fase GLOBAL mientras la apertura usa fase LOCAL (2026-08-31)

**Este caso NO es como los tres anteriores.** El trailing, el termómetro y el centinela son inercia
benigna: dejarlos rotos no hace daño. Éste es una **contradicción de diseño real y hoy ejecutable**,
pero **la evidencia económica no alcanza para justificar el cambio**. Se documenta con esa distinción
explícita para que quien lo mire decida con los números a la vista, no con la intuición.

### La contradicción

Los directores abren posiciones según la fase **LOCAL** de cada moneda
(`director_orquesta.py:248-257`, `dirigir_btc(fases['BTCUSDT'])`, etc.), pero
`cerrar_huerfanas()` decide el cierre forzado comparando contra la fase **GLOBAL** —el voto de las
5 monedas— en `director_orquesta.py:56`:

```python
if len(partes) < 7 or partes[5] != "ABIERTA" or partes[1] == fase_nueva:
    nuevas.append(linea); continue      # fase_nueva es la fase GLOBAL
```

**Consecuencia:** una posición abierta legítimamente (su moneda está en fase ALCISTA) puede cerrarse
en Binance porque el voto global cambió, y el director puede **reabrirla al ciclo siguiente**, ya que
la fase local no cambió. Comisión doble y una pérdida que ninguna lógica de trading pidió.

### Cuándo nació (importante para no medir mal)

| Commit | Fecha | Qué pasó |
|---|---|---|
| anterior a `bf414c0` | — | La apertura usaba **fase global**: abrir y cerrar por global era **coherente**. **No había bug** |
| **`bf414c0`** | **2026-08-17** | La apertura pasa a **fase local** → **acá nace la divergencia** |
| `4dd1ba5` | 2026-08-24 | Suma AVAX y cambia sizing. **No** introdujo la fase local (ya existía) |

**De los 415 cambios de fase global del histórico, 399 (96%) son anteriores al 17-ago**, es decir de
la época sin bug. **No los uses como evidencia de este problema.** La ventana real de exposición es
de 16 cambios.

### Evidencia económica — no alcanza

**Impacto realizado: $0,00.** Hay **0 filas `FASE_CAMBIO`** en `auditoria.csv` en toda la ventana:
el mecanismo **nunca llegó a dispararse**. La causa más consistente es que `cerrar_posicion()`
fallaba por el bug de NOTIONAL (`MONTO_FIJO` era $5 y el mínimo de Binance es $5), lo que explica
que las 4 posiciones del período terminaran cerradas **a mano** (`MANUAL_WIN`/`MANUAL_LOSS`). No está
probado al 100%: esos avisos van a Telegram y los `print` al screen, y ninguno se conserva.

**Simulación amplia** (`reports/2026-08-31_simulacion-historica-global-vs-local.md`): 222 posiciones
donde ambas lógicas deciden distinto, con precios reales de 15m y TP/SL reconstruidos por commit. El
modelo se validó reproduciendo **355 de los 376** cierres reales.

| | Resultado |
|---|---|
| PnL fase GLOBAL (actual) | −$0,92 |
| PnL fase LOCAL (propuesta) | +$5,50 |
| Diferencia | **+$6,42** (+0,64% del capital simulado) |
| **IC 95% (bootstrap)** | **−$3,10 … +$16,30 — el cero está dentro** |
| **Casos que favorecen a GLOBAL** | **54,5%** (test de signo **p = 0,0219**, significativo) |
| Sin SOL | **−$1,54** (se invierte) |
| Sin los 14 casos que llegaron a TP | **−$5,08** (se invierte) |
| Sin el mejor 5% | **−$3,66** (se invierte) |
| **Máximo drawdown** | GLOBAL $2,24 vs **LOCAL $12,92 (5,8× más)** |

**El dato que más pesa:** de las 222 posiciones que la lógica LOCAL mantendría abiertas, **206
(92,8%) terminan cerrándose igual** poco después, al cambiar la fase local de su propia moneda. Toda
la diferencia sale de **16 casos**. Y a escala actual ($7/op sobre $37) la ventaja equivaldría a
**~$2,14 en tres meses** — centavos por mes.

**Veredicto: 🔴 NO TOCAR por economía.** No hay mejora demostrada, se invierte ante cualquier
exclusión, y viene con casi 6× más drawdown.

### ✅ DECISIÓN TOMADA (Ariel, 2026-08-31)

**Decisión: no se corrige por ahora. Motivo: beneficio esperado indistinguible de cero y el
drawdown simulado sube ~6×.**

El arreglo de `director_orquesta.py:56` queda **cancelado**, no pendiente. Esto no es un TODO ni un
trabajo a medio hacer: es una decisión tomada con la evidencia a la vista. Queda **solo
documentado**. Si en el futuro se reabre, tiene que ser con evidencia nueva —no con el mismo
análisis— y con una decisión explícita de Ariel que reemplace a ésta.

### Lo que sí cambió, y hay que tener presente

**El bug pasó de latente a ejecutable el 31-ago.** Durante toda la ventana estuvo **inhabilitado por
otro bug** (el NOTIONAL con `MONTO_FIJO = $5`). Con **$7** desde el 31-ago los cierres automáticos
**vuelven a ser ejecutables**, así que el mecanismo ahora sí puede disparar. La frecuencia histórica
fue de ~1,14 cambios de fase global por día, con **63,2%** de los ciclos teniendo al menos una moneda
cuya fase local difiere de la global.

**Qué mirar si algún día aparece:** una fila con estado `FASE_CAMBIO` en `auditoria.csv` cuya moneda
seguía en su fase local original. Ese sería el primer caso real — hasta hoy no hubo ninguno.

### Si se decide corregirlo

No se hace por PnL (no lo hay) sino **por coherencia**: hoy el sistema puede cerrar una posición que
su propia lógica de entrada considera válida. Es un cambio de **una condición** en
`director_orquesta.py:56` —comparar contra la fase local de la moneda de esa fila en vez de contra
`fase_nueva`— y **no toca francotiradores ni parámetros**, así que no requiere backtest de PF. Sí
requiere OK explícito de Ariel, y asumir que el beneficio esperado es **indistinguible de cero** y
que el drawdown sube.

Evidencia completa: `reports/2026-08-31_simulacion-historica-global-vs-local.md` (222 divergencias)
y `reports/2026-08-31_evaluacion-economica-global-vs-local.md` (las 8 posiciones reales).

## Telegram
- Admins: ADMIN_YAYO (6578945006), ADMIN_SOCIA (6533031969)
- Token en `keys.env` como `TELEGRAM_BOT_TOKEN` — **ese es el nombre exacto de la clave, todos
  los módulos deben leerlo así**.
- **Dos rutas de salida a Telegram, no confundir:**
  - `brain/telegram_engine.py` → polling de comandos y respuestas (`/status`, etc.).
  - `engine.py:enviar_aviso()` → **avisos de trades** (entradas, TP, SL, errores de cierre). Lo
    usan los 15 francotiradores y `director_orquesta`.
- **Log de fallos:** `engine.enviar_aviso()` registra cualquier fallo de envío en
  `memoria/telegram.log`. Si no llega un aviso, revisar **primero** ese archivo.
- **Comandos que mueven dinero o estado, patrón de dos pasos:** sin argumento muestran un previo
  que **no toca nada**; solo con `confirmar` como segunda palabra ejecutan. Admin-gateados por el
  chequeo al tope de `procesar_comando`.
  - `/reconciliar` → previo del polvo vendible · `/reconciliar confirmar` → vende en Binance.
  - `/desbloquear` → estado del guardián · `/desbloquear confirmar` → levanta el bloqueo y
    **rebasea `capital_maximo_historico` al capital actual** (a propósito — si no, el guardián
    bloquearía de nuevo contra el mismo pico). Queda huella en `estado_riesgo.desbloqueo`.

---
Historial de investigación de parámetros y backtests: ver `INVESTIGACION.md`.
