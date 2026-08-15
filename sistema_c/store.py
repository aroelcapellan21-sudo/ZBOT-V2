"""
store.py — Persistencia independiente para BTC Sistema C
Namespace: data/btc_system_c/

NO toca:
  auditoria.csv
  billetera.json
  config_cartera.py
  signals/billetera.json
  signals/modo.json

Cada trade tiene trade_id = BTC-C-NNNNNN.
"""
import os
import csv
import json
import fcntl
from datetime import datetime, timezone

DATA_DIR     = os.path.expanduser("~/bot-padre-v2/data/btc_system_c")
SIGNALS_CSV  = os.path.join(DATA_DIR, "signals.csv")
TRADES_CSV   = os.path.join(DATA_DIR, "trades.csv")
STATE_JSON   = os.path.join(DATA_DIR, "state.json")
METRICS_JSON = os.path.join(DATA_DIR, "metrics.json")
_LOCK_FILE   = os.path.join(DATA_DIR, "store.lock")

SIGNALS_FIELDS = [
    "signal_id", "timestamp", "symbol", "timeframe",
    "rsi", "close_price", "ema200_daily", "ema_date_used",
    "price_above_ema", "rsi_in_range", "sl_price", "tp_price", "generated",
]

TRADES_FIELDS = [
    "trade_id", "strategy_id", "symbol", "timeframe",
    "entry_timestamp", "rsi", "entry_price",
    "ema_period", "ema_value", "ema_date_used", "price_above_ema",
    "sl_price", "tp_price", "status",
    "exit_timestamp", "exit_price", "exit_reason",
    "entry_fee", "exit_fee", "gross_pnl", "net_pnl",
    "data_timestamp", "signal_timestamp", "execution_timestamp",
]

def ensure_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(SIGNALS_CSV):
        with open(SIGNALS_CSV, "w", newline="") as f:
            csv.DictWriter(f, fieldnames=SIGNALS_FIELDS).writeheader()
    if not os.path.exists(TRADES_CSV):
        with open(TRADES_CSV, "w", newline="") as f:
            csv.DictWriter(f, fieldnames=TRADES_FIELDS).writeheader()
    if not os.path.exists(STATE_JSON):
        _write_json(STATE_JSON, {"status": "IDLE"})
    if not os.path.exists(METRICS_JSON):
        _write_json(METRICS_JSON, {})

def _write_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)

def _with_lock(fn):
    """Envuelve fn() con un lock de archivo para evitar condiciones de carrera."""
    lk = open(_LOCK_FILE, "w")
    fcntl.flock(lk, fcntl.LOCK_EX)
    try:
        return fn()
    finally:
        fcntl.flock(lk, fcntl.LOCK_UN)
        lk.close()

# ── Contadores ────────────────────────────────────────────────────────────────

def _count_rows(path):
    try:
        with open(path) as f:
            return sum(1 for _ in f) - 1  # -1 por header
    except Exception:
        return 0

def next_signal_id():
    return f"SIG-{_count_rows(SIGNALS_CSV) + 1:06d}"

def next_trade_id():
    return f"BTC-C-{_count_rows(TRADES_CSV) + 1:06d}"

# ── Señales ───────────────────────────────────────────────────────────────────

def record_signal(ts, close, rsi, ema_val, ema_date, generated):
    """
    Registra cada evaluacion donde RSI entra en rango [55, 60).
    generated=True: paso el gate EMA → se abrio un trade.
    generated=False: RSI en rango pero bloqueado por EMA o por posicion existente.
    """
    ensure_dirs()
    sl = round(close * 0.95, 2)
    tp = round(close * 1.06, 2)
    rsi_in_range = rsi is not None and 55.0 <= rsi < 60.0
    price_ema = (str(close > ema_val) if ema_val else "NO_EMA")
    row = {
        "signal_id":      next_signal_id(),
        "timestamp":      ts,
        "symbol":         "BTCUSDT",
        "timeframe":      "4h",
        "rsi":            rsi if rsi is not None else "",
        "close_price":    close,
        "ema200_daily":   ema_val if ema_val is not None else "",
        "ema_date_used":  ema_date if ema_date else "",
        "price_above_ema": price_ema,
        "rsi_in_range":   str(rsi_in_range),
        "sl_price":       sl,
        "tp_price":       tp,
        "generated":      str(generated),
    }
    def _append():
        with open(SIGNALS_CSV, "a", newline="") as f:
            csv.DictWriter(f, fieldnames=SIGNALS_FIELDS).writerow(row)
    _with_lock(_append)
    return row["signal_id"]

# ── Trades ────────────────────────────────────────────────────────────────────

def open_trade(ts, close, rsi, ema_val, ema_date):
    """
    Persiste un trade en estado OPEN y actualiza state.json.
    entry_fee = 5.0 * 0.001 = $0.005
    """
    ensure_dirs()
    sl = round(close * 0.95, 2)
    tp = round(close * 1.06, 2)
    now = datetime.now(timezone.utc).isoformat()
    tid = next_trade_id()
    row = {
        "trade_id":            tid,
        "strategy_id":         "BTC_SYSTEM_C",
        "symbol":              "BTCUSDT",
        "timeframe":           "4h",
        "entry_timestamp":     ts,
        "rsi":                 rsi,
        "entry_price":         close,
        "ema_period":          200,
        "ema_value":           ema_val,
        "ema_date_used":       ema_date,
        "price_above_ema":     str(close > ema_val),
        "sl_price":            sl,
        "tp_price":            tp,
        "status":              "OPEN",
        "exit_timestamp":      "",
        "exit_price":          "",
        "exit_reason":         "",
        "entry_fee":           round(5.0 * 0.001, 4),
        "exit_fee":            "",
        "gross_pnl":           "",
        "net_pnl":             "",
        "data_timestamp":      now,
        "signal_timestamp":    ts,
        "execution_timestamp": now,
    }
    state = {
        "status":      "OPEN",
        "trade_id":    tid,
        "entry_price": close,
        "entry_ts":    ts,
        "sl_price":    sl,
        "tp_price":    tp,
        "rsi":         rsi,
        "ema_val":     ema_val,
        "ema_date":    ema_date,
    }

    def _write():
        with open(TRADES_CSV, "a", newline="") as f:
            csv.DictWriter(f, fieldnames=TRADES_FIELDS).writerow(row)
        _write_json(STATE_JSON, state)

    _with_lock(_write)
    return tid

def close_trade(trade_id, exit_ts, exit_price, reason, entry_price):
    """
    Cierra el trade: reescribe la fila en trades.csv con estado y P/L,
    luego limpia state.json.
    Retorna net_pnl.
    """
    ensure_dirs()
    fees  = round(5.0 * 0.001 * 2, 4)
    gross = round(5.0 * (exit_price - entry_price) / entry_price, 4)
    net   = round(gross - fees, 4)

    def _rewrite():
        rows = []
        with open(TRADES_CSV) as f:
            rows = list(csv.DictReader(f))
        updated = False
        for r in rows:
            if r["trade_id"] == trade_id and r["status"] == "OPEN":
                r["status"]          = reason
                r["exit_timestamp"]  = exit_ts
                r["exit_price"]      = exit_price
                r["exit_reason"]     = reason
                r["exit_fee"]        = round(5.0 * 0.001, 4)
                r["gross_pnl"]       = gross
                r["net_pnl"]         = net
                updated = True
                break
        if not updated:
            print(f"[STORE] ⚠️ No se encontro trade_id={trade_id} en estado OPEN")
        tmp = TRADES_CSV + ".tmp"
        with open(tmp, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=TRADES_FIELDS)
            w.writeheader()
            w.writerows(rows)
        os.replace(tmp, TRADES_CSV)
        _write_json(STATE_JSON, {"status": "IDLE"})

    _with_lock(_rewrite)
    return net

# ── Estado ───────────────────────────────────────────────────────────────────

def load_state():
    ensure_dirs()
    try:
        with open(STATE_JSON) as f:
            return json.load(f)
    except Exception:
        return {"status": "IDLE"}

def is_open():
    return load_state().get("status") == "OPEN"

# ── Metricas ─────────────────────────────────────────────────────────────────

def compute_and_save_metrics():
    """Calcula metricas desde trades.csv y persiste metrics.json."""
    ensure_dirs()
    try:
        with open(TRADES_CSV) as f:
            rows = list(csv.DictReader(f))
    except Exception:
        rows = []

    closed = [r for r in rows if r["status"] in ("TP", "SL")]
    n     = len(closed)
    tps   = [r for r in closed if r["status"] == "TP"]
    sls   = [r for r in closed if r["status"] == "SL"]
    pls   = []
    for r in closed:
        try:
            pls.append(float(r["net_pnl"]))
        except Exception:
            pass

    wr  = round(len(tps) / n * 100, 1) if n > 0 else 0.0
    tg  = sum(float(r["net_pnl"]) for r in tps  if r["net_pnl"])
    tl  = abs(sum(float(r["net_pnl"]) for r in sls if r["net_pnl"]))
    pf  = round(tg / tl, 3) if tl > 0 else 0.0
    pl  = round(sum(pls), 4)
    exp = round(pl / n, 4) if n > 0 else 0.0

    cap = 20.0; mxc = cap; mxdd = 0.0
    for r in closed:
        try:
            cap += float(r["net_pnl"]); mxc = max(mxc, cap)
            mxdd = max(mxdd, (mxc - cap) / mxc * 100)
        except Exception:
            pass

    mrsl = 0; crsl = 0
    for r in closed:
        if r["status"] == "SL":
            crsl += 1; mrsl = max(mrsl, crsl)
        else:
            crsl = 0
    mrtp = 0; crtp = 0
    for r in closed:
        if r["status"] == "TP":
            crtp += 1; mrtp = max(mrtp, crtp)
        else:
            crtp = 0

    total_signals = _count_rows(SIGNALS_CSV)

    metrics = {
        "strategy_id":     "BTC_SYSTEM_C",
        "symbol":          "BTCUSDT",
        "mode":            "SHADOW",
        "progress":        f"{n}/30",
        "trades":          n,
        "open":            1 if is_open() else 0,
        "tp":              len(tps),
        "sl":              len(sls),
        "win_rate":        wr,
        "profit_factor":   pf,
        "expectancy":      exp,
        "total_pnl":       pl,
        "drawdown_max":    round(mxdd, 1),
        "racha_max_sl":    mrsl,
        "racha_max_tp":    mrtp,
        "total_signals":   total_signals,
        "benchmark_oos": {
            "period": "2024-2025",
            "trades": 59, "pf": 1.322, "wr": 54.2,
            "exp": 0.0383, "dd": 5.3,
            "note": "OOS backtest btc_bootstrap_sistema_c_vs_produccion.py"
        },
    }
    _write_json(METRICS_JSON, metrics)
    return metrics

# ── Reporte ──────────────────────────────────────────────────────────────────

def generate_report():
    """Genera reports/btc-system-c-live-monitoring.md."""
    ensure_dirs()
    m = compute_and_save_metrics()
    state = load_state()

    lines = []
    lines.append("# BTC Sistema C — Monitor SHADOW")
    lines.append(f"\n**Actualizado:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"**Modo:** {m['mode']} | **strategy_id:** {m['strategy_id']}")
    lines.append(f"**Progreso hacia 30 trades:** {m['progress']}")
    lines.append("\n---\n")

    lines.append("## Metricas prospectivas")
    lines.append("\n| Metrica | Valor |")
    lines.append("|---------|-------|")
    lines.append(f"| Trades cerrados | {m['trades']} |")
    lines.append(f"| TP | {m['tp']} |")
    lines.append(f"| SL | {m['sl']} |")
    lines.append(f"| Win Rate | {m['win_rate']:.1f}% |")
    lines.append(f"| Profit Factor | {m['profit_factor']:.3f} |")
    lines.append(f"| Expectancy | ${m['expectancy']:.4f} |")
    lines.append(f"| P/L acumulado | ${m['total_pnl']:.4f} |")
    lines.append(f"| Drawdown max | {m['drawdown_max']:.1f}% |")
    lines.append(f"| Racha SL | {m['racha_max_sl']} |")
    lines.append(f"| Racha TP | {m['racha_max_tp']} |")
    lines.append(f"| Señales totales | {m['total_signals']} |")

    if state.get("status") == "OPEN":
        lines.append("\n## Posicion abierta")
        lines.append(f"\n**Trade ID:** {state.get('trade_id')}")
        lines.append(f"**Entrada:** ${state.get('entry_price')} @ {state.get('entry_ts')}")
        lines.append(f"**SL:** ${state.get('sl_price')} | **TP:** ${state.get('tp_price')}")
        lines.append(f"**RSI entrada:** {state.get('rsi')}")
        lines.append(f"**EMA200d:** {state.get('ema_val')} ({state.get('ema_date')})")
    else:
        lines.append("\n**Posicion:** IDLE — sin posicion abierta.")

    bm = m["benchmark_oos"]
    lines.append("\n## Benchmark historico (OOS 2024–2025)")
    lines.append("\n| Metrica | OOS Backtest | Prospectivo |")
    lines.append("|---------|-------------|------------|")
    lines.append(f"| Trades | {bm['trades']} | {m['trades']} |")
    lines.append(f"| Win Rate | {bm['wr']:.1f}% | {m['win_rate']:.1f}% |")
    lines.append(f"| PF | {bm['pf']:.3f} | {m['profit_factor']:.3f} |")
    lines.append(f"| Expectancy | ${bm['exp']:.4f} | ${m['expectancy']:.4f} |")
    lines.append(f"| DD max | {bm['dd']:.1f}% | {m['drawdown_max']:.1f}% |")
    lines.append(f"\n⚠️ *Comparacion valida solo con n >= 30 trades.*")

    lines.append("\n## Parametros exactos")
    lines.append("\n```")
    lines.append("SYMBOL     = BTCUSDT")
    lines.append("TIMEFRAME  = 4H")
    lines.append("RSI        = 14 periodos, 55 <= RSI < 60 (semiabierto)")
    lines.append("EMA        = 200 diaria, precio cierre D-1 (anti-lookahead)")
    lines.append("SL         = 5%")
    lines.append("TP         = 6%")
    lines.append("MONTO      = $5 por trade")
    lines.append("TRAILING   = NO")
    lines.append("FILTROS    = NINGUNO adicional")
    lines.append("MODO       = SHADOW (LIVE = DISABLED)")
    lines.append("```")

    lines.append("\n## Prohibiciones activas")
    lines.append("- NO enviar ordenes a Binance")
    lines.append("- NO modificar auditoria.csv, billetera.json, config_cartera.py")
    lines.append("- NO cambiar RSI/EMA/SL/TP hasta >= 30 trades")
    lines.append("- NO activar para ETH/SOL/AVAX (descartados)")

    lines.append("\n---")
    lines.append("\n**PRODUCCION NO MODIFICADA. SISTEMA C NO ACTIVADO EN LIVE.**")

    ruta = os.path.expanduser("~/bot-padre-v2/reports/btc-system-c-live-monitoring.md")
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w") as f:
        f.write("\n".join(lines))
    return ruta
