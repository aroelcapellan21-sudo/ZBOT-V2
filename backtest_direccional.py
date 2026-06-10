# =========================================
# backtest_direccional.py
# Aisla el cohorte ALCISTA vs BAJISTA por activo para medir el impacto
# de operar (o no) cada direccion en WR, PF y PnL.
#
# Replica las reglas de entrada/salida de los francotiradores en vivo:
#   ALCISTA: RSI in [50,70] y EMA20>EMA50, salida TP/SL (close-based)
#   BAJISTA: RSI in [30,50] y EMA20<EMA50, salida TP/SL (close-based)
# Una posicion a la vez. Net en puntos porcentuales (pp).
#
# Reporta BRUTO y NETO (con fee round-trip ~0.2%). Validado contra
# backtest_resultados.txt (BTC alcista ~195/42%, bajista ~214/36%).
# Genera reports_historicos/backtest_direccional.json
# Sin librerias externas. Constitucion RESPETADA
# =========================================

import urllib.request
import urllib.parse
import json
import os
import time
from datetime import datetime

ACTIVOS = {
    "BTCUSDT": {"sl": 3.5, "tp": 6.0},   # validacion vs referencia
    "ETHUSDT": {"sl": 3.5, "tp": 6.0},
    "SOLUSDT": {"sl": 4.0, "tp": 7.0},
    "BNBUSDT": {"sl": 4.0, "tp": 7.0},
    "AVAXUSDT": {"sl": 4.0, "tp": 7.0},
}
START_MS    = 1609459200000  # 2021-01-01
FEE_RT_PP   = 0.2            # fee round-trip aproximado en puntos porcentuales
SALIDA_JSON = os.path.expanduser("~/bot-padre-v2/reports_historicos/backtest_direccional.json")


def fetch_closes(symbol):
    closes, cur = [], START_MS
    now_ms = int(time.time() * 1000)
    base   = "https://api.binance.com/api/v3/klines"
    while cur < now_ms:
        p = urllib.parse.urlencode({"symbol": symbol, "interval": "4h",
                                    "startTime": cur, "endTime": now_ms, "limit": 1000})
        try:
            with urllib.request.urlopen(f"{base}?{p}", timeout=20) as r:
                data = json.loads(r.read().decode())
        except Exception as e:
            print(f"  fetch error {symbol}: {e}")
            break
        if not data:
            break
        closes.extend(float(k[4]) for k in data)
        cur = data[-1][0] + 1
        if len(data) < 1000:
            break
    return closes


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


def simular(closes, rsi, e20, e50, direccion, sl, tp):
    n = len(closes)
    i = 50
    wins = loss = 0
    while i < n:
        r, c, l = rsi[i], e20[i], e50[i]
        if r is None or c is None or l is None:
            i += 1
            continue
        entro = (direccion == "ALCISTA" and 50 <= r <= 70 and c > l) or \
                (direccion == "BAJISTA" and 30 <= r <= 50 and c < l)
        if not entro:
            i += 1
            continue
        entry = closes[i]
        j = i + 1
        cerrado = False
        while j < n:
            cambio = ((closes[j] - entry) / entry * 100) if direccion == "ALCISTA" \
                     else ((entry - closes[j]) / entry * 100)
            if cambio >= tp:
                wins += 1
                cerrado = True
                break
            if cambio <= -sl:
                loss += 1
                cerrado = True
                break
            j += 1
        if not cerrado:
            break              # posicion sin resolver al final del historial
        i = j + 1              # reanuda tras la salida
    return wins, loss


def metricas(wins, loss, sl, tp):
    tot = wins + loss
    if tot == 0:
        return None
    wr      = round(wins / tot * 100, 1)
    pf      = round((wins * tp) / (loss * sl), 2) if loss > 0 else None  # None = inf
    net     = round(wins * tp - loss * sl, 1)
    net_fee = round(net - tot * FEE_RT_PP, 1)
    return {"trades": tot, "wins": wins, "losses": loss, "wr": wr,
            "pf": pf, "net_pp": net, "net_pp_con_fees": net_fee}


def main():
    print("=" * 78)
    print("BACKTEST DIRECCIONAL 4H | 2021-01-01 -> hoy | reglas de francotiradores")
    print("=" * 78)

    por_activo = {}
    agg = {"ALCISTA": {"trades": 0, "wins": 0, "net": 0.0, "net_fee": 0.0},
           "BAJISTA": {"trades": 0, "wins": 0, "net": 0.0, "net_fee": 0.0}}

    for sym, p in ACTIVOS.items():
        closes = fetch_closes(sym)
        rsi = rsi_array(closes)
        e20 = ema_array(closes, 20)
        e50 = ema_array(closes, 50)
        print(f"\n{sym}  ({len(closes)} velas 4h)  SL {p['sl']}% TP {p['tp']}%")
        por_activo[sym] = {"velas": len(closes), "sl": p["sl"], "tp": p["tp"]}
        for d in ("ALCISTA", "BAJISTA"):
            w, l = simular(closes, rsi, e20, e50, d, p["sl"], p["tp"])
            m = metricas(w, l, p["sl"], p["tp"])
            if not m:
                print(f"  {d:8} sin trades")
                continue
            por_activo[sym][d] = m
            pfs = "inf" if m["pf"] is None else f"{m['pf']:.2f}"
            print(f"  {d:8} trades {m['trades']:4} | WR {m['wr']:5.1f}% | PF {pfs:>5} "
                  f"| Net {m['net_pp']:+8.1f} pp | NetFee {m['net_pp_con_fees']:+8.1f} pp")
            agg[d]["trades"]  += m["trades"]
            agg[d]["wins"]    += m["wins"]
            agg[d]["net"]     += m["net_pp"]
            agg[d]["net_fee"] += m["net_pp_con_fees"]

    agregado = {}
    for d in ("ALCISTA", "BAJISTA"):
        a = agg[d]
        agregado[d] = {
            "trades":          a["trades"],
            "wr":              round(a["wins"] / a["trades"] * 100, 1) if a["trades"] else 0,
            "net_pp":          round(a["net"], 1),
            "net_pp_con_fees": round(a["net_fee"], 1),
        }

    ta = agg["ALCISTA"]["trades"]; wa = agg["ALCISTA"]["wins"]
    tb = agg["BAJISTA"]["trades"]; wb = agg["BAJISTA"]["wins"]
    wr_antes = round((wa + wb) / (ta + tb) * 100, 1)
    wr_desp  = round(wa / ta * 100, 1)
    antes_despues = {
        "antes_alc_y_baj": {
            "trades": ta + tb, "wr": wr_antes,
            "net_pp_bruto": round(agg["ALCISTA"]["net"] + agg["BAJISTA"]["net"], 1),
            "net_pp_con_fees": round(agg["ALCISTA"]["net_fee"] + agg["BAJISTA"]["net_fee"], 1),
        },
        "despues_solo_alc": {
            "trades": ta, "wr": wr_desp,
            "net_pp_bruto": round(agg["ALCISTA"]["net"], 1),
            "net_pp_con_fees": round(agg["ALCISTA"]["net_fee"], 1),
        },
        "delta": {
            "wr_pp": round(wr_desp - wr_antes, 1),
            "net_pp_bruto": round(-agg["BAJISTA"]["net"], 1),
            "net_pp_con_fees": round(-agg["BAJISTA"]["net_fee"], 1),
        },
    }

    print("\n" + "=" * 78)
    print("ANTES (alc+baj) vs DESPUES (solo alc)")
    print("=" * 78)
    ad = antes_despues
    print(f"  ANTES  : trades {ad['antes_alc_y_baj']['trades']:4} | WR {ad['antes_alc_y_baj']['wr']:5.1f}% "
          f"| Bruto {ad['antes_alc_y_baj']['net_pp_bruto']:+8.1f} pp | Fees {ad['antes_alc_y_baj']['net_pp_con_fees']:+8.1f} pp")
    print(f"  DESPUES: trades {ad['despues_solo_alc']['trades']:4} | WR {ad['despues_solo_alc']['wr']:5.1f}% "
          f"| Bruto {ad['despues_solo_alc']['net_pp_bruto']:+8.1f} pp | Fees {ad['despues_solo_alc']['net_pp_con_fees']:+8.1f} pp")
    print(f"  DELTA  : WR {ad['delta']['wr_pp']:+.1f} pp | Bruto {ad['delta']['net_pp_bruto']:+.1f} pp "
          f"| Fees {ad['delta']['net_pp_con_fees']:+.1f} pp")

    salida = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "metodologia": ("4h 2021->hoy, reglas francotiradores (RSI+EMA20/50, salida TP/SL "
                        "close-based, 1 posicion a la vez). Net en puntos porcentuales (pp). "
                        f"Fee round-trip {FEE_RT_PP}pp/trade."),
        "nota": ("Los SHORT (bajista) son INEJECUTABLES en cuenta SPOT. El net bajista solo "
                 "seria realizable con Futuros USDT-M. Ver gestor_bajistas.py."),
        "por_activo": por_activo,
        "agregado": agregado,
        "antes_despues": antes_despues,
    }
    try:
        tmp = SALIDA_JSON + ".tmp"
        with open(tmp, "w") as f:
            json.dump(salida, f, indent=2, ensure_ascii=False)
        os.replace(tmp, SALIDA_JSON)
        print(f"\n✅ Guardado: {SALIDA_JSON}")
    except Exception as e:
        print(f"\n❌ Error guardando JSON: {e}")


if __name__ == "__main__":
    main()
