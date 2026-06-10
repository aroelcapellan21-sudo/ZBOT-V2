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
Cada módulo corre en su propia sesión `screen`. Los principales:
- `v2_main` → `main.py`
- `z_asistente` → `asistente.py` (Flask en :5050)
- `z_tunnel` → cloudflared (túnel público)
- `z_precision`, `z_volumen`, `z_fugas`, `z_fuerza`, `z_liquidez`, `z_velas`, `z_heatmap`, `z_correlation`

## Modo de operación
- Modo actual: `signals/modo.json` → `{"modo":"SIMULADOR","intervalo_velas":"1h","sleep_segundos":60}`
- Para cambiar a REAL: editar `modo.json` y `config/modo.txt`
- **No cambiar a REAL sin autorización explícita de Ariel**

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
