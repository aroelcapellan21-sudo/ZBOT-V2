# =========================================
# backtest_gate_salida.py  (HARNESS DE SIMULACION - no toca produccion)
# Mide el impacto del bug: revisar_cierres() se ejecuta DESPUES de los gates
# de entrada, asi que el SL/TP de posiciones abiertas NO se evalua cuando el
# gate de HORARIO bloquea (fuera de 4-21h UTC-4).
#
# Compara dos modos con IDENTICA logica de entrada y salida; la UNICA
# diferencia es si las salidas se evaluan fuera de horario:
#   BUGGY = comportamiento actual (salida solo dentro de 4-21h)
#   FIXED = revisar_cierres movido antes de los gates (salida siempre)
#
# Entrada (regla lateral, igual en ambos modos y SOLO en horario, como el
# codigo real): RSI in [rsi_min,rsi_max] y EMA_corta>EMA_larga. 1 pos a la vez.
# Salida: SL/TP fijos close-based. PnL realizado = % al close de la vela de
# cierre (captura el slippage por cerrar tarde). Net en puntos porcentuales.
#
# NOTA METODOLOGICA: solo modela el gate de HORARIO. Los otros 5 gates
# (guardian, termometro, spread, limite diario, eventos) tambien bloquean
# salidas en el codigo real, asi que el dano REAL del bug es >= al medido.
# Esta es una COTA INFERIOR conservadora.
# Sin librerias externas. No modifica ningun archivo del proyecto.
# =========================================

import urllib.request
import urllib.parse
import json
import time
from datetime import datetime, timezone, timedelta

import sys, os
sys.path.insert(0, os.path.expanduser("~/bot-padre-v2"))
from config_cartera import get_params

TZ_SD       = timezone(timedelta(hours=-4))
HORA_INICIO = 4
HORA_FIN    = 21
START_MS    = int(datetime(2023, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
FEE_RT_PP   = 0.2
SYMBOLS     = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "AVAXUSDT"]
SALIDA_JSON = os.path.expanduser("~/bot-padre-v2/reports_historicos/backtest_gate_salida.json")


def fetch_klines_1h(symbol):
    """Devuelve [(openTime_ms, close), ...] en 1h desde START hasta hoy."""
    out, cur = [], START_MS
    now_ms = int(time.time() * 1000)
    base = "https://api.binance.com/api/v3/klines"
    while cur < now_ms:
        p = urllib.parse.urlencode({"symbol": symbol, "interval": "1h",
                                    "startTime": cur, "endTime": now_ms, "limit": 1000})
        try:
            with urllib.request.urlopen(f"{base}?{p}", timeout=25) as r:
                data = json.loads(r.read().decode())
        except Exception as e:
            print(f"  fetch error {symbol}: {e}")
            break
        if not data:
            break
        out.extend((int(k[0]), float(k[4])) for k in data)
        cur = data[-1][0] + 1
        if len(data) < 1000:
            break
    return out


def ema_array(closes, period):
    out = [None] * len(closes)
    if len(closes) < period:
        return out
    k = 2 / (period + 1)
    e = sum(closes[:period]) / period
    out[period - 1] = e
    for i in range(period, len(closes)):
        e = closes[i] * k + e * (1 - k)
        out[i] = e
    return out


def rsi_array(closes, period=14):
    out = [None] * len(closes)
    if len(closes) < period + 1:
        return out
    gains  = [max(closes[i] - closes[i - 1], 0) for i in range(1, len(closes))]
    losses = [max(closes[i - 1] - closes[i], 0) for i in range(1, len(closes))]
    ag = sum(gains[:period]) / period
    al = sum(losses[:period]) / period
    out[period] = 100.0 if al == 0 else round(100 - 100 / (1 + ag / al), 2)
    for i in range(period, len(gains)):
        ag = (ag * (period - 1) + gains[i]) / period
        al = (al * (period - 1) + losses[i]) / period
        out[i + 1] = 100.0 if al == 0 else round(100 - 100 / (1 + ag / al), 2)
    return out


def en_horario(open_ms):
    h = datetime.fromtimestamp(open_ms / 1000, TZ_SD).hour
    return HORA_INICIO <= h < HORA_FIN


def simular(times, closes, rsi, ec, el, rsi_min, rsi_max, sl, tp, modo):
    """modo:
        'BUGGY'   = ni SL ni TP fuera de horario (comportamiento actual)
        'FIXED'   = SL y TP fuera de horario (revisar_cierres antes de los gates)
        'SOLO_SL' = SL siempre (hard-stop), TP solo en horario
    Entrada identica en los tres: solo dentro de horario (como el codigo real)."""
    n = len(closes)
    i = 50
    wins = loss = trades = 0
    pnl = 0.0
    peor_slip = 0.0   # cierre mas alla de -sl por gestionar tarde (solo informativo)
    while i < n:
        r, c, l = rsi[i], ec[i], el[i]
        if r is None or c is None or l is None:
            i += 1
            continue
        if not (rsi_min <= r <= rsi_max and c > l and en_horario(times[i])):
            i += 1
            continue
        entry = closes[i]
        j = i + 1
        cerrado = False
        while j < n:
            dentro  = en_horario(times[j])
            eval_tp = dentro or (modo == "FIXED")
            eval_sl = dentro or (modo in ("FIXED", "SOLO_SL"))
            cambio  = (closes[j] - entry) / entry * 100
            if eval_tp and cambio >= tp:
                pnl += cambio
                trades += 1
                wins += 1
                cerrado = True
                break
            if eval_sl and cambio <= -sl:
                pnl += cambio
                trades += 1
                loss += 1
                if cambio < -sl:
                    peor_slip = min(peor_slip, cambio + sl)
                cerrado = True
                break
            j += 1
        if not cerrado:
            break
        i = j + 1
    return {"trades": trades, "wins": wins, "losses": loss,
            "wr": round(wins / trades * 100, 1) if trades else 0,
            "pnl_pp": round(pnl, 1),
            "pnl_pp_fee": round(pnl - trades * FEE_RT_PP, 1),
            "peor_slippage_pp": round(peor_slip, 2)}


def main():
    MODOS = ("BUGGY", "FIXED", "SOLO_SL")
    print("=" * 84)
    print("BACKTEST GATE DE SALIDA | 1h | 2023-01-01 -> hoy | laterales (5 activos)")
    print("BUGGY (actual) | FIXED (salida siempre) | SOLO_SL (SL siempre, TP solo en horario)")
    print("=" * 84)

    por_activo = {}
    agg = {m: {"trades": 0, "wins": 0, "pnl": 0.0, "pnl_fee": 0.0}
           for m in MODOS}

    for sym in SYMBOLS:
        p = get_params(sym, "lateral")
        kl = fetch_klines_1h(sym)
        if len(kl) < 200:
            print(f"\n{sym}: datos insuficientes ({len(kl)})")
            continue
        times  = [t for t, _ in kl]
        closes = [c for _, c in kl]
        rsi = rsi_array(closes)
        ec  = ema_array(closes, p["ec"])
        el  = ema_array(closes, p["el"])
        print(f"\n{sym}  ({len(closes)} velas 1h)  SL {p['sl']}% TP {p['tp']}% "
              f"RSI[{p['rsi_min']}-{p['rsi_max']}] EMA{p['ec']}/{p['el']}")
        por_activo[sym] = {"velas": len(closes), "sl": p["sl"], "tp": p["tp"]}
        for modo in MODOS:
            m = simular(times, closes, rsi, ec, el,
                        p["rsi_min"], p["rsi_max"], p["sl"], p["tp"], modo)
            por_activo[sym][modo] = m
            print(f"  {modo:5} trades {m['trades']:4} | WR {m['wr']:5.1f}% "
                  f"| PnL {m['pnl_pp']:+8.1f} pp | PnLfee {m['pnl_pp_fee']:+8.1f} pp "
                  f"| peor slip {m['peor_slippage_pp']:+.2f} pp")
            agg[modo]["trades"]   += m["trades"]
            agg[modo]["wins"]     += m["wins"]
            agg[modo]["pnl"]      += m["pnl_pp"]
            agg[modo]["pnl_fee"]  += m["pnl_pp_fee"]

    print("\n" + "=" * 84)
    print("AGREGADO (5 activos)")
    print("=" * 84)
    resumen = {}
    for modo in MODOS:
        a = agg[modo]
        wr = round(a["wins"] / a["trades"] * 100, 1) if a["trades"] else 0
        resumen[modo] = {"trades": a["trades"], "wr": wr,
                         "pnl_pp": round(a["pnl"], 1),
                         "pnl_pp_fee": round(a["pnl_fee"], 1)}
        print(f"  {modo:7} trades {a['trades']:4} | WR {wr:5.1f}% "
              f"| PnL {a['pnl']:+8.1f} pp | PnLfee {a['pnl_fee']:+8.1f} pp")

    deltas = {}
    print()
    for modo in ("FIXED", "SOLO_SL"):
        d_pnl = round(resumen[modo]["pnl_pp"]     - resumen["BUGGY"]["pnl_pp"], 1)
        d_fee = round(resumen[modo]["pnl_pp_fee"] - resumen["BUGGY"]["pnl_pp_fee"], 1)
        d_wr  = round(resumen[modo]["wr"]         - resumen["BUGGY"]["wr"], 1)
        deltas[modo] = {"wr_pp": d_wr, "pnl_pp": d_pnl, "pnl_pp_fee": d_fee}
        print(f"  DELTA ({modo} - BUGGY): WR {d_wr:+.1f} pp | "
              f"PnL {d_pnl:+.1f} pp | PnLfee {d_fee:+.1f} pp")
    print("  (DELTA positivo en PnL = mejora frente al comportamiento actual)")
    print("\n  Cota INFERIOR: solo modela el gate de horario; guardian/termometro/")
    print("  spread/limite-diario/eventos tambien bloquean salidas en produccion.")

    salida = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "metodologia": ("1h 2023->hoy, regla lateral RSI+EMA, 1 pos a la vez, "
                        "salida SL/TP close-based. BUGGY=salida solo 4-21h UTC-4, "
                        "FIXED=salida siempre. Solo modela gate de horario => cota inferior."),
        "por_activo": por_activo,
        "agregado": resumen,
        "deltas_vs_buggy": deltas,
    }
    try:
        with open(SALIDA_JSON, "w") as f:
            json.dump(salida, f, indent=2, ensure_ascii=False)
        print(f"\nGuardado: {SALIDA_JSON}")
    except Exception as e:
        print(f"\nError guardando JSON: {e}")


if __name__ == "__main__":
    main()
