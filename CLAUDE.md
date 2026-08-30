# Instrucciones permanentes — Z-Bot Padre v2

## Idioma
Responde siempre en español.

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
├── director_orquesta.py ← define fase por símbolo y llama SOLO a BTC/ETH/SOL (ver tabla arriba)
├── director_<activo>.py ← uno por activo, decide qué francotirador activar
│   └── francotirador_<fase>_<activo>.py ← genera señales de entrada
├── ejecutor.py          ← ÚNICO autorizado para abrir/cerrar posiciones
├── guardian_riesgo.py   ← DD máximo 10%, pérdida diaria máx 5%
├── centinela/           ← monitorea posiciones abiertas en tiempo real
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
Cada módulo corre en su propia sesión `screen`. Total esperado: 29 sesiones (verificado
2026-08-22: 29 activas, coincide).

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
- `z_executor` → `radar_executor.py`
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
