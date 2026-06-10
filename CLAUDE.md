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

## Telegram
- Admins: ADMIN_YAYO (6578945006), ADMIN_SOCIA (6533031969)
- Token en `keys.env` como `TELEGRAM_BOT_TOKEN`
- El bot responde comandos vía polling en `brain/telegram_engine.py`
