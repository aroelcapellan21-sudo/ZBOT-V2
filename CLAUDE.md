# Instrucciones permanentes — Z-Bot Padre v2

## Idioma
Responde siempre en español.

## Proyecto
**Z-Bot Padre v2** — bot de trading algorítmico sobre Binance.
- Dueño: Ariel
- Activos: BTC, ETH, SOL, BNB, AVAX
- Stack: Python puro, Binance REST API, Telegram Bot API, Flask (asistente web)
- Estado actual: **paper trading / SIMULADOR** — capital simulado $1,000 USDT
- Objetivo: pasar a real cuando se cumplan 3 meses consecutivos en positivo, o cuando todo funcione perfecto

## Arquitectura
```
main.py                  ← orquestador principal (NO ejecuta órdenes, NO toca capital)
├── director_orquesta.py ← define fase global del mercado (ALCISTA / BAJISTA / LATERAL)
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
└── config/              ← billetera.json, modo.txt
```

## Procesos en pantalla (screen)
Cada módulo corre en su propia sesión `screen`. Total esperado: 29 sesiones.

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

## Modo de operación
- Modo actual: `signals/modo.json` → `{"modo":"SIMULADOR","intervalo_velas":"1h","sleep_segundos":60}`
- Para cambiar a REAL: editar `modo.json` y `config/modo.txt`
- **No cambiar a REAL sin autorización explícita de Ariel**

## Dirección de operación — SPOT solo-LONG (desde jun 2026)
- El bot opera **solo ALCISTA y LATERAL**. Los 5 francotiradores bajistas están desactivados.
- Razón: hacer SHORT es imposible en cuenta SPOT. En SIMULADOR generaba balances de cripto negativos (causa raíz de los negativos en billetera).
- Gate central: `gestor_bajistas.py` → `bajistas_activos()`. Cada `evaluar()` bajista lo consulta y retorna temprano si está desactivado.
- **Reactivación automática:** el gate lee el saldo de Futuros USDT-M de Binance (`/fapi/v2/balance`). Si `availableBalance` USDT ≥ 5.0, los bajistas vuelven solos. Cachea 5 min; ante error de API → desactivado (seguro). Estado en `signals/estado_bajistas.json`.
- **Pendiente:** `ejecutor.py:cerrar_posicion` cierra shorts con BUY spot. Para shorts reales en futuros hay que reescribir el ejecutor — reactivar el gate no basta.
- **Evidencia (backtest 5.4 años, 4h):** `backtest_direccional.py` → `reports_historicos/backtest_direccional.json`. Desactivar bajistas sube WR +2.1 pp (40.7%→42.8%) y cuesta ~28 pp de PnL en 5.4 años descontando fees (≈cero). El PnL bajista bruto (+342 pp) descansa casi entero en AVAX; BTC/ETH/BNB bajistas son negativos tras fees. Si se reactivan en futuros, hacerlo **selectivo por activo**, no los 5 en bloque.

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
- Los 15 francotiradores tienen parámetros validados por backtest — no cambiar sin evidencia

## Gestión de salidas vs gates de entrada (hallazgo jun 2026 — NO cambiar sin re-decidir)
- En `evaluar()` de los 15 francotiradores, `revisar_cierres()` (que evalúa SL/TP de
  posiciones abiertas) se llama **después** de los 6 gates de entrada (guardian, termómetro,
  spread, horario, límite diario, eventos). Si cualquiera hace `return`, el SL/TP **no se
  evalúa** ese ciclo. En concreto, fuera de la ventana 4-21h (UTC-4) las posiciones quedan
  **hasta 7h sin stop activo**.
- Se evaluó moverlo antes de los gates. **Backtest (`backtest_gate_salida.py`, 1h 2023→hoy,
  5 laterales, ~30k velas, → `reports_historicos/backtest_gate_salida.json`):**
  - **FIXED** (gestionar salidas siempre): **−44.3 pp** con fees en 3.4 años vs el actual.
  - **SOLO_SL** (SL siempre 24h, TP solo en horario): **−10.6 pp** con fees (≈−3 pp/año).
  - Causa: no mirar de noche deja que trades que tocan SL reboten (mercado mean-reverting);
    corregirlo realiza más pérdidas y añade fees.
- **Decisión (Ariel, jun 2026): NO cambiar el código** — el backtest histórico no muestra
  mejora de PnL. El matiz pendiente: el backtest 1h **no captura** la protección de cola que
  SOLO_SL daría en vivo (el bot evalúa cada 60s; ante crash nocturno cortaría en ~1 min en
  vez de esperar a las 4am). Si en el futuro pesa más el riesgo de cola que los ~3 pp/año,
  reconsiderar SOLO_SL. Documentado, sin implementar.

## Asimetría TP/SL en el registro de cierres (hallazgo jun 2026 — relevante para paso a real)
- En `revisar_cierres()` de los **15 francotiradores** (alcista/bajista/lateral × 5 activos), el
  cierre por **SL se registra al precio teórico `sl_efectivo`, NO al `precio_actual` real**:
  `registrar_sl(precio_entrada, sl_efectivo, ...)` en las 3 ramas (BE, trailing, SL normal) y el
  aviso siempre reporta `-STOP_LOSS%` nominal. En cambio el **TP sí usa `precio_actual`**:
  `registrar_tp(precio_entrada, precio_actual, ...)`.
- **Consecuencia:** el PnL contable está sesgado **al alza** por ambos lados — ganancias reales
  (o mayores) en TP, pérdidas **topadas** al nominal en SL. En **SIMULADOR** es inocuo: el peor
  caso de un SL queda topado en `-STOP_LOSS%` aunque el precio real haya caído mucho más (ej. un
  gap nocturno con el monitoreo congelado fuera de la ventana 4-21h se contabiliza como -3.5% en
  BTC, no como la caída real). En **REAL** el registro a `sl_efectivo` es contabilidad ficticia:
  `cerrar_posicion` ejecutaría orden de mercado al precio real del gap (sin tope) pero los libros
  anotarían -SL% → riesgo de cola sin tope **y** PnL sobreestimado.
- **Decisión: documentado, sin implementar.** Si se implementa la mitigación SOLO_SL (ver sección
  anterior), corregir **también** que el SL registre `precio_actual` en vez de `sl_efectivo`. No
  tocar antes del paso a real sin re-decidir con Ariel.

## Telegram
- Admins: ADMIN_YAYO (6578945006), ADMIN_SOCIA (6533031969)
- Token en `keys.env` como `TELEGRAM_BOT_TOKEN` — **ese es el nombre exacto de la clave, todos los módulos deben leerlo así**.
- El bot responde comandos vía polling en `brain/telegram_engine.py`.
- **Dos rutas de salida a Telegram, no confundir:**
  - `brain/telegram_engine.py` → polling de comandos y respuestas (`/status`, etc.).
  - `engine.py:enviar_aviso()` → **avisos de trades** (entradas, TP, SL, errores de cierre). Lo usan los 15 francotiradores y `director_orquesta`.
- **Bug histórico (jun 2026):** `engine.cargar_token()` buscaba `TELEGRAM_TOKEN=` (clave inexistente) en vez de `TELEGRAM_BOT_TOKEN=`, así que los avisos de trades nunca salían — se abrían posiciones sin notificación. El polling sí funcionaba porque leía la clave correcta. Corregido.
- **Log de fallos:** `engine.enviar_aviso()` registra cualquier fallo de envío en `memoria/telegram.log` (token ausente, rechazo de la API con `ok:false`, o excepción de red). Antes solo se imprimían al stdout del screen y se perdían. Si no llega un aviso, revisar **primero** ese archivo. Si está vacío, el envío salió bien y el problema es del lado de Telegram/cliente.
