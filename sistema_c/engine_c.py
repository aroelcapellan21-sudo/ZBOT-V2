"""
engine_c.py — BTC Sistema C: logica central de senales y salidas
INVESTIGACION PURA — NO toca produccion.

Parametros exactos del backtest:
  SYMBOL      = BTCUSDT
  RSI_PERIOD  = 14
  RSI_MIN     = 55.0  (inclusive)
  RSI_MAX     = 60.0  (exclusive: 55 <= RSI < 60)
  EMA_PERIOD  = 200 (diaria, anti-lookahead D-1)
  SL          = 5%
  TP          = 6%
  TRADE_AMT   = $5
  COMM        = 0.1% entrada + 0.1% salida

RSI: misma implementacion que btc_bootstrap_sistema_c_vs_produccion.py
     para garantizar reproducibilidad del backtest (ver NOTA DE DISCREPANCIA).

NOTA DE DISCREPANCIA detectada en rsi_system_c():
  El backtest usa range(1, 14) = 13 diferencias / 14
  Es internamente consistente — NO se corrige para mantener
  la reproducibilidad exacta con los 59 trades OOS.
  Produccion usa utils.calcular_rsi() (Wilder) que es distinto.
  Para Sistema C se usa rsi_system_c(), nunca calcular_rsi().
"""
import json
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta

SYMBOL     = "BTCUSDT"
RSI_MIN    = 55.0
RSI_MAX    = 60.0   # semiabierto: 55 <= RSI < 60
RSI_PERIOD = 14
EMA_PERIOD = 200
SL         = 0.05
TP         = 0.06
TRADE_AMT  = 5.0
COMM       = 0.001  # 0.1% por lado (taker VIP0)
STRATEGY   = "BTC_SYSTEM_C"

# ── Fetch ─────────────────────────────────────────────────────────────────────

def _fetch_raw(symbol, interval, limit, start_ms=None):
    """Descarga velas de Binance. Retorna lista de arrays crudos."""
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    if start_ms is not None:
        params["startTime"] = start_ms
    p = urllib.parse.urlencode(params)
    url = f"https://api.binance.com/api/v3/klines?{p}"
    with urllib.request.urlopen(url, timeout=15) as r:
        return json.loads(r.read().decode())

def _ts_ms(date_str):
    return int(datetime.strptime(date_str, "%Y-%m-%d")
               .replace(tzinfo=timezone.utc).timestamp() * 1000)

def fetch_4h_closed(limit=300):
    """
    Retorna lista de dicts {ts_ms, close} para las ultimas velas 4H CERRADAS.
    Una vela se considera cerrada cuando su close_time < ahora.
    """
    ahora = int(datetime.now(timezone.utc).timestamp() * 1000)
    raw = _fetch_raw(SYMBOL, "4h", limit)
    result = []
    for v in raw:
        if int(v[6]) < ahora:
            result.append({"ts_ms": int(v[0]), "close": float(v[4])})
    return result

def fetch_1d_since(since_date_str):
    """
    Descarga todas las velas diarias cerradas desde since_date_str.
    Retorna lista de dicts {ts_ms, close_time_ms, close, date_str}.
    """
    ahora = int(datetime.now(timezone.utc).timestamp() * 1000)
    velas = []; start = _ts_ms(since_date_str)
    while True:
        params = urllib.parse.urlencode({"symbol": SYMBOL, "interval": "1d",
                                         "startTime": start, "limit": 1000})
        with urllib.request.urlopen(
                f"https://api.binance.com/api/v3/klines?{params}", timeout=30) as r:
            batch = json.loads(r.read().decode())
        if not batch: break
        velas.extend(batch)
        if len(batch) < 1000: break
        start = batch[-1][0] + 1
    result = []
    for v in velas:
        if int(v[6]) < ahora:
            dt = datetime.fromtimestamp(int(v[0]) / 1000, tz=timezone.utc)
            result.append({
                "ts_ms":         int(v[0]),
                "close_time_ms": int(v[6]),
                "close":         float(v[4]),
                "date_str":      dt.strftime("%Y-%m-%d"),
            })
    return result

# ── EMA diaria ────────────────────────────────────────────────────────────────

def build_ema_map(velas_1d, n=EMA_PERIOD):
    """
    Construye {date_str: ema_value} con EMA de n periodos sobre cierres diarios.
    Solo incluye fechas donde la EMA ya esta disponible (>= n velas).
    """
    k = 2 / (n + 1)
    closes = [v["close"]    for v in velas_1d]
    dates  = [v["date_str"] for v in velas_1d]
    ema    = [None] * len(closes)
    if len(closes) >= n:
        ema[n - 1] = sum(closes[:n]) / n
        for i in range(n, len(closes)):
            ema[i] = closes[i] * k + ema[i - 1] * (1 - k)
    return {dates[i]: ema[i] for i in range(len(dates)) if ema[i] is not None}

def get_ema_anti_lookahead(ts_4h_ms, ema_map):
    """
    Para la vela 4H con apertura en ts_4h_ms, retorna (ema_value, ema_date_used).
    Busca hacia atras D-1 ... D-5. Nunca usa la vela diaria actual (D).

    Assertion obligatoria: ema_date < dia de la vela 4H.
    Si no encuentra EMA → (None, None) y la señal se rechaza.

    Raises AssertionError si se detecta lookahead (nunca deberia ocurrir
    con busqueda D-1..D-5 sobre velas cerradas).
    """
    dt_4h = datetime.fromtimestamp(ts_4h_ms / 1000, tz=timezone.utc)
    for d in range(1, 6):
        fecha = (dt_4h - timedelta(days=d)).strftime("%Y-%m-%d")
        if fecha in ema_map:
            ema_dt = datetime.strptime(fecha, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            assert ema_dt < dt_4h, (
                f"LOOKAHEAD DETECTADO: ema_date={fecha} >= signal_4h={dt_4h.date()}. "
                f"Senal RECHAZADA."
            )
            return ema_map[fecha], fecha
    return None, None

# ── RSI ───────────────────────────────────────────────────────────────────────

def rsi_system_c(closes):
    """
    RSI(14) usando ventana de 15 cierres con promedio simple.
    Replica EXACTAMENTE btc_bootstrap_sistema_c_vs_produccion.rsi_calc().

    DISCREPANCIA documentada: range(1,14) = 13 diferencias / 14 (no 14/14).
    Esto es correcto para el backtest pero no el RSI Wilder clasico.
    NO cambiar sin re-correr el backtest de regresion.

    NO usar utils.calcular_rsi(): produce valores distintos (Wilder sobre
    toda la historia) que dan un numero diferente de trades en OOS.
    """
    if len(closes) < 15:
        return None
    v = closes[-15:]
    gains  = [max(v[i] - v[i - 1], 0.0) for i in range(1, 14)]  # 13 items
    losses = [max(v[i - 1] - v[i], 0.0) for i in range(1, 14)]  # 13 items
    ag = sum(gains)  / 14  # divide por 14, igual que backtest
    al = sum(losses) / 14
    if al == 0:
        return 100.0
    return round(100 - 100 / (1 + ag / al), 2)

# ── Señal y salida ────────────────────────────────────────────────────────────

def check_signal(close_4h, rsi, ema_val):
    """
    Condicion de entrada completa:
      55 <= RSI < 60   (rango semiabierto — 60.00 NO genera señal)
      close_4h > ema200_daily   (strictly greater, == NO genera señal)

    Retorna True si se genera señal, False si no.
    """
    if rsi is None or ema_val is None:
        return False
    rsi_ok = RSI_MIN <= rsi < RSI_MAX
    ema_ok = close_4h > ema_val
    return rsi_ok and ema_ok

def compute_levels(entry_price):
    """
    sl_price = entry * 0.95
    tp_price = entry * 1.06
    Sin trailing. Sin modificacion posterior.
    """
    return round(entry_price * (1 - SL), 2), round(entry_price * (1 + TP), 2)

def compute_pnl(entry_price, exit_price):
    """
    P/L neto = (exit/entry - 1) * TRADE_AMT - fees
    TP tipico: +$0.2900  (5*0.06 - 5*0.002 = 0.30 - 0.01)
    SL tipico: -$0.2600  (5*0.05 + 5*0.002 = 0.25 + 0.01)
    """
    fees  = round(TRADE_AMT * COMM * 2, 4)
    gross = round(TRADE_AMT * (exit_price - entry_price) / entry_price, 4)
    net   = round(gross - fees, 4)
    return fees, gross, net

def check_exit(state, current_price):
    """
    Comprueba SL/TP sobre la posicion abierta.
    Sin trailing. Sin breakeven. Sin modificacion de SL.
    Retorna ("SL"|"TP"|None, exit_price|None).
    """
    if state is None or state.get("status") != "OPEN":
        return None, None
    if current_price <= state["sl_price"]:
        return "SL", current_price
    if current_price >= state["tp_price"]:
        return "TP", current_price
    return None, None

# ── Regimen ───────────────────────────────────────────────────────────────────

def classify_regime(close_4h, ema_val):
    """SOBRE / BAJO EMA200d para logging de regimen forward."""
    if ema_val is None:
        return "SIN_EMA"
    return "SOBRE" if close_4h > ema_val else "BAJO"
