"""
btc_system_c.py — Monitor SHADOW de BTC Sistema C

Modo por defecto: SHADOW
  - Calcula señales reales sobre datos Binance
  - Registra entradas/salidas hipoteticas con P/L exacto
  - NO envia ordenes a Binance
  - NO modifica auditoria.csv, billetera.json ni config_cartera.py

Para iniciar en screen:
  screen -dmS z_btc_system_c bash -c 'cd ~/bot-padre-v2 && python3 -m sistema_c.btc_system_c'

Para ver logs:
  screen -r z_btc_system_c

Para detener:
  screen -S z_btc_system_c -X quit

Para ver metricas:
  cat ~/bot-padre-v2/data/btc_system_c/metrics.json
  less ~/bot-padre-v2/reports/btc-system-c-live-monitoring.md
"""
import os
import sys
import time
import json
import traceback
from datetime import datetime, timezone

# ── Modo operativo ────────────────────────────────────────────────────────────
# SHADOW: solo registra, NO ejecuta ordenes
# PAPER:  reservado para futuras pruebas en testnet
# LIVE:   DESHABILITADO — requiere BTC_SYSTEM_C_LIVE=true en entorno
ALLOWED_MODES = ("SHADOW", "PAPER")
BTC_SYSTEM_C_MODE = "SHADOW"

def _check_live_guard():
    """
    Si alguien pone BTC_SYSTEM_C_MODE = "LIVE", el monitor se niega
    a arrancar a menos que exista la variable de entorno BTC_SYSTEM_C_LIVE=true.
    Esto evita activar LIVE por una variable accidental.
    """
    if BTC_SYSTEM_C_MODE == "LIVE":
        confirmado = os.environ.get("BTC_SYSTEM_C_LIVE", "").strip().lower()
        if confirmado != "true":
            print("[BTC-C] ❌ LIVE rechazado — requiere BTC_SYSTEM_C_LIVE=true en el entorno.")
            print("[BTC-C]    Esta sesion permanece como SHADOW sin enviar ordenes.")
            return "SHADOW"
        print("[BTC-C] ⚠️ LIVE CONFIRMADO via BTC_SYSTEM_C_LIVE=true — NO implementado todavia.")
        print("[BTC-C]    Saliendo. Implementar ejecutor para LIVE antes de activar.")
        sys.exit(1)
    return BTC_SYSTEM_C_MODE

# Verificar modo antes de cualquier importacion de logica
MODO_ACTIVO = _check_live_guard()

# ── Importaciones internas ────────────────────────────────────────────────────
# Se importa engine y store AQUI para que el guard de LIVE corra primero
sys.path.insert(0, os.path.expanduser("~/bot-padre-v2"))

from sistema_c.engine_c import (
    fetch_4h_closed, fetch_1d_since,
    build_ema_map, get_ema_anti_lookahead,
    rsi_system_c, check_signal, compute_levels,
    compute_pnl, check_exit, classify_regime,
    STRATEGY, SYMBOL,
)
from sistema_c.store import (
    ensure_dirs, load_state, is_open,
    record_signal, open_trade, close_trade,
    compute_and_save_metrics, generate_report,
)

# engine.py vive en el raiz del proyecto — se usa SOLO para Telegram alerts
try:
    from engine import enviar_aviso as _enviar_aviso
except ImportError:
    def _enviar_aviso(msg):
        print(f"[AVISO] {msg}")

# ── Configuracion de loop ─────────────────────────────────────────────────────
SLEEP_SEGUNDOS      = 240     # 4 minutos — alineado con velas 4H
EMA_WU_DATE         = "2019-06-01"   # warmup para EMA200 diaria
REPORT_INTERVAL_S   = 3600    # regenerar reporte cada 1h
LAST_CANDLE_KEY     = "last_processed_candle_ts"

def _ts_str(ts_ms):
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")

# ── Alertas Telegram ──────────────────────────────────────────────────────────

def _alerta_entrada(trade_id, ts, close, rsi, ema_val, ema_date, sl, tp):
    msg = (
        f"[{MODO_ACTIVO}] BTC SYSTEM C — SEÑAL\n"
        f"Trade ID: {trade_id}\n"
        f"Timestamp: {ts}\n"
        f"RSI: {rsi}\n"
        f"Price: ${close:,.2f}\n"
        f"EMA200d ({ema_date}): ${ema_val:,.2f}\n"
        f"Price > EMA200: SI\n"
        f"SL: ${sl:,.2f} (-5%)\n"
        f"TP: ${tp:,.2f} (+6%)\n"
        f"Monto: $5 | Modo: {MODO_ACTIVO} — sin orden real"
    )
    print(f"[BTC-C] {msg}")
    _enviar_aviso(msg)

def _alerta_salida(trade_id, reason, entry_price, exit_price, fees, gross, net):
    signo = "+" if net >= 0 else ""
    msg = (
        f"[{MODO_ACTIVO}] BTC SYSTEM C — CIERRE\n"
        f"Trade ID: {trade_id}\n"
        f"Razon: {reason}\n"
        f"Entrada: ${entry_price:,.2f}\n"
        f"Salida: ${exit_price:,.2f}\n"
        f"Gross P/L: ${gross:+.4f}\n"
        f"Fees: -${fees:.4f}\n"
        f"Net P/L: {signo}${net:.4f}\n"
        f"Modo: {MODO_ACTIVO} — sin orden real"
    )
    print(f"[BTC-C] {msg}")
    _enviar_aviso(msg)

# ── Logica de un ciclo ────────────────────────────────────────────────────────

def _ciclo(ema_map, state_cache):
    """
    Ejecuta un ciclo completo:
    1. Obtiene la ultima vela 4H cerrada
    2. Comprueba si ya la procesamos (evita señal duplicada en el mismo ciclo)
    3. RSI sobre las ultimas 15 cierres
    4. EMA anti-lookahead
    5. Si posicion abierta: comprobar SL/TP
    6. Si no hay posicion: comprobar señal de entrada
    7. Registrar señal en signals.csv si RSI entra en rango
    Retorna el timestamp de la ultima vela procesada.
    """
    # 1. Fetch 4H
    velas_4h = fetch_4h_closed(limit=300)
    if len(velas_4h) < 20:
        print("[BTC-C] ⚠️ Datos 4H insuficientes")
        return state_cache.get(LAST_CANDLE_KEY)

    ultima = velas_4h[-1]
    ts_ms  = ultima["ts_ms"]
    close  = ultima["close"]
    ts_str = _ts_str(ts_ms)

    # 2. Evitar reprocesar la misma vela
    if ts_ms == state_cache.get(LAST_CANDLE_KEY):
        print(f"[BTC-C] Vela {ts_str} ya procesada. Esperando nueva.")
        return ts_ms

    closes = [v["close"] for v in velas_4h]
    rsi    = rsi_system_c(closes)

    # 3. EMA anti-lookahead
    from datetime import datetime, timezone
    dt_4h = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
    ema_val, ema_date = get_ema_anti_lookahead(ts_ms, ema_map)
    regime = classify_regime(close, ema_val)

    print(f"[BTC-C] {ts_str} | Close: ${close:,.2f} | RSI: {rsi} "
          f"| EMA200d: {f'${ema_val:,.2f}' if ema_val else 'N/A'} ({ema_date}) "
          f"| Regimen: {regime}")

    # 4. Estado actual
    state = load_state()
    pos_open = state.get("status") == "OPEN"

    # 5. Verificar salida si hay posicion abierta
    if pos_open:
        reason, exit_price = check_exit(state, close)
        if reason:
            trade_id    = state["trade_id"]
            entry_price = state["entry_price"]
            net = close_trade(trade_id, ts_str, exit_price, reason, entry_price)
            fees, gross, _ = compute_pnl(entry_price, exit_price)
            _alerta_salida(trade_id, reason, entry_price, exit_price, fees, gross, net)
            print(f"[BTC-C] {reason}: entry=${entry_price} exit=${exit_price} net=${net:+.4f}")
            pos_open = False
        else:
            entry = state["entry_price"]
            pct   = (close - entry) / entry * 100
            print(f"[BTC-C] Posicion OPEN {state['trade_id']} | "
                  f"Entry: ${entry} | SL: ${state['sl_price']} | TP: ${state['tp_price']} "
                  f"| PnL latente: {pct:+.2f}%")

    # 6. Señal de entrada (solo si RSI en rango; registrar siempre para auditoria)
    rsi_en_rango = rsi is not None and 55.0 <= rsi < 60.0
    if rsi_en_rango:
        signal_ok = check_signal(close, rsi, ema_val)
        if signal_ok and not pos_open:
            sl, tp = compute_levels(close)
            trade_id = open_trade(ts_str, close, rsi, ema_val, ema_date)
            record_signal(ts_str, close, rsi, ema_val, ema_date, generated=True)
            _alerta_entrada(trade_id, ts_str, close, rsi, ema_val, ema_date, sl, tp)
            print(f"[BTC-C] SEÑAL ABIERTA {trade_id}: RSI={rsi} EMA={ema_val} → SL=${sl} TP=${tp}")
        elif signal_ok and pos_open:
            record_signal(ts_str, close, rsi, ema_val, ema_date, generated=False)
            print(f"[BTC-C] Señal RSI+EMA pero posicion ya OPEN — ignorada")
        else:
            # RSI en rango pero bloqueado por EMA o sin EMA
            record_signal(ts_str, close, rsi, ema_val, ema_date, generated=False)
            motivo = "sin EMA disponible" if ema_val is None else f"close ${close:,.2f} <= EMA ${ema_val:,.2f}"
            print(f"[BTC-C] RSI en rango pero bloqueado: {motivo}")

    return ts_ms

# ── Loop principal ────────────────────────────────────────────────────────────

def main():
    ensure_dirs()
    print("=" * 60)
    print(f"BTC Sistema C — Monitor {MODO_ACTIVO}")
    print(f"strategy_id = {STRATEGY}")
    print("NO envia ordenes. NO modifica produccion.")
    print("=" * 60)
    print(f"[BTC-C] Iniciando warmup EMA desde {EMA_WU_DATE}...")

    # Construir mapa EMA inicial (warmup completo)
    velas_1d = fetch_1d_since(EMA_WU_DATE)
    ema_map  = build_ema_map(velas_1d, n=200)
    print(f"[BTC-C] EMA200 diaria disponible: {len(ema_map)} fechas "
          f"({min(ema_map)} → {max(ema_map)})")

    state_cache = load_state()
    last_report = 0

    while True:
        try:
            ts_procesado = _ciclo(ema_map, state_cache)
            if ts_procesado:
                state_cache[LAST_CANDLE_KEY] = ts_procesado

            # Regenerar mapa EMA cada 25h (una vela diaria nueva)
            # Se hace al inicio del dia UTC para mantener EMA fresca
            hora_utc = datetime.now(timezone.utc).hour
            if hora_utc == 0 and len(ema_map) > 0:
                velas_1d = fetch_1d_since(EMA_WU_DATE)
                ema_map  = build_ema_map(velas_1d, n=200)

            # Reporte periodico
            ahora = time.time()
            if ahora - last_report > REPORT_INTERVAL_S:
                m = compute_and_save_metrics()
                ruta = generate_report()
                print(f"[BTC-C] Metricas: trades={m['trades']}/30 | "
                      f"PF={m['profit_factor']:.3f} | Exp=${m['expectancy']:.4f}")
                print(f"[BTC-C] Reporte: {ruta}")
                last_report = ahora

        except AssertionError as e:
            # Lookahead detectado: error critico, no silencioso
            print(f"[BTC-C] ❌ LOOKAHEAD ERROR: {e}")
            _enviar_aviso(f"❌ BTC Sistema C — LOOKAHEAD DETECTADO\n{e}\nCiclo abortado.")
        except Exception as e:
            print(f"[BTC-C] ⚠️ Error en ciclo: {e}")
            traceback.print_exc()

        print(f"[BTC-C] Durmiendo {SLEEP_SEGUNDOS}s...")
        time.sleep(SLEEP_SEGUNDOS)


if __name__ == "__main__":
    main()
