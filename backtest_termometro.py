#!/usr/bin/env python3
# =========================================
# backtest_termometro.py
# Punto 9: evalua dos cambios al termometro
#   A) ventana 20 -> 50 velas (menos ruido)
#   B) VOLATILIDAD_EXTREMA: pausar vs operar con TP/SL reducidos
# Usa historico 4H. Sin librerias externas.
# =========================================

import csv
import os

DATA_DIR = os.path.expanduser("~/bot-padre-v2/data/historico_4h")
SIMBOLOS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "AVAXUSDT"]

PARAMETROS = {
    "BTCUSDT": {"sl": 5.0, "tp": 6.0, "ec": 20, "el": 100, "rsi_min": 55, "rsi_max": 75},
    "ETHUSDT": {"sl": 4.5, "tp": 5.0, "ec": 20, "el": 100, "rsi_min": 60, "rsi_max": 75},
    "SOLUSDT": {"sl": 5.0, "tp": 6.0, "ec": 20, "el":  50, "rsi_min": 50, "rsi_max": 70},
    "BNBUSDT": {"sl": 4.5, "tp": 5.0, "ec": 20, "el": 100, "rsi_min": 60, "rsi_max": 75},
    "AVAXUSDT":{"sl": 4.5, "tp": 5.0, "ec": 20, "el": 100, "rsi_min": 60, "rsi_max": 75},
}

CAPITAL_POR_OP = 20.0

# -------------------------------------------------------
# Utilidades
# -------------------------------------------------------
def ema_serie(precios, periodo):
    if len(precios) < periodo:
        return [None] * len(precios)
    k      = 2.0 / (periodo + 1)
    result = [None] * (periodo - 1)
    val    = sum(precios[:periodo]) / periodo
    result.append(val)
    for p in precios[periodo:]:
        val = p * k + val * (1 - k)
        result.append(val)
    return result

def rsi_serie(precios, periodo=14):
    n = len(precios)
    result = [None] * n
    if n < periodo + 1:
        return result
    cambios = [precios[i] - precios[i-1] for i in range(1, n)]
    gains   = [max(0.0, c) for c in cambios[:periodo]]
    losses  = [max(0.0, -c) for c in cambios[:periodo]]
    avg_g   = sum(gains) / periodo
    avg_l   = sum(losses) / periodo
    if avg_l == 0:
        result[periodo] = 100.0
    else:
        result[periodo] = round(100 - 100 / (1 + avg_g / avg_l), 2)
    for i in range(periodo, n - 1):
        g = max(0.0, cambios[i])
        l = max(0.0, -cambios[i])
        avg_g = (avg_g * (periodo - 1) + g) / periodo
        avg_l = (avg_l * (periodo - 1) + l) / periodo
        if avg_l == 0:
            result[i + 1] = 100.0
        else:
            result[i + 1] = round(100 - 100 / (1 + avg_g / avg_l), 2)
    return result

def calcular_volatilidad_ventana(cierres):
    if len(cierres) < 2:
        return 0.0
    cambios = [abs((cierres[j] - cierres[j-1]) / cierres[j-1]) * 100 for j in range(1, len(cierres))]
    return sum(cambios) / len(cambios)

def clasificar_estado(vol):
    # Usando solo volatilidad (simplificado para backtest)
    if vol > 2.0:
        return "VOLATILIDAD_EXTREMA"
    elif vol > 1.0:
        return "TENDENCIA_FUERTE"
    elif vol > 0.3:
        return "TENDENCIA_DEBIL"
    else:
        return "MERCADO_MUERTO"

def simular_trade_alcista(precio, velas_futuras, sl_pct, tp_pct, max_v=10):
    sl_p = precio * (1 - sl_pct / 100)
    tp_p = precio * (1 + tp_pct / 100)
    for v in velas_futuras[:max_v]:
        if v[1] <= sl_p: return "SL", -sl_pct
        if v[0] >= tp_p: return "TP",  tp_pct
    if velas_futuras:
        pnl = ((velas_futuras[min(max_v-1, len(velas_futuras)-1)][2] - precio) / precio) * 100
        return "TIMEOUT", round(pnl, 3)
    return "TIMEOUT", 0.0

def cargar_velas(symbol):
    ruta  = os.path.join(DATA_DIR, f"{symbol}_4h.csv")
    velas = []
    with open(ruta, "r") as f:
        for row in csv.DictReader(f):
            velas.append((float(row["high"]), float(row["low"]), float(row["close"])))
    return velas

# -------------------------------------------------------
# Backtest principal
# -------------------------------------------------------
def backtest_symbol(symbol, velas, ventana_termometro):
    p = PARAMETROS[symbol]
    sl_pct  = p["sl"]
    tp_pct  = p["tp"]
    ec      = p["ec"]
    el      = p["el"]
    rsi_min = p["rsi_min"]
    rsi_max = p["rsi_max"]

    cierres = [v[2] for v in velas]
    n       = len(cierres)

    ema_ec_s = ema_serie(cierres, ec)
    ema_el_s = ema_serie(cierres, el)
    rsi_s    = rsi_serie(cierres, 14)

    min_idx = max(el, ventana_termometro) + 15

    # Resultados por escenario
    # A: sin termometro (baseline)
    # B: actual — VOLATILIDAD_EXTREMA opera con TP/SL*0.7
    # C: propuesto — VOLATILIDAD_EXTREMA pausa completamente
    res = {"sin_filtro": [], "actual_07": [], "pausa_extrema": []}

    for i in range(min_idx, n - 10):
        rsi_val = rsi_s[i]
        ema_c   = ema_ec_s[i]
        ema_l   = ema_el_s[i]
        precio  = cierres[i]

        if rsi_val is None or ema_c is None or ema_l is None:
            continue

        entrada_ok = (rsi_min <= rsi_val <= rsi_max) and (precio > ema_c > ema_l)
        if not entrada_ok:
            continue

        # Calcular estado del termometro en este punto
        ventana  = cierres[max(0, i - ventana_termometro + 1): i + 1]
        vol      = calcular_volatilidad_ventana(ventana)
        estado   = clasificar_estado(vol)

        velas_fut = [(velas[j][0], velas[j][1], velas[j][2]) for j in range(i+1, min(i+11, n))]

        # A) Sin filtro termometro
        r, pnl = simular_trade_alcista(precio, velas_fut, sl_pct, tp_pct)
        res["sin_filtro"].append((estado, r, pnl))

        # B) Actual: VOLATILIDAD_EXTREMA → TP/SL * 0.7, MERCADO_MUERTO → pausa
        if estado == "MERCADO_MUERTO":
            pass  # no entra
        elif estado == "VOLATILIDAD_EXTREMA":
            r, pnl = simular_trade_alcista(precio, velas_fut, sl_pct * 0.7, tp_pct * 0.7)
            res["actual_07"].append((estado, r, pnl))
        else:
            r, pnl = simular_trade_alcista(precio, velas_fut, sl_pct, tp_pct)
            res["actual_07"].append((estado, r, pnl))

        # C) Propuesto: VOLATILIDAD_EXTREMA → pausa total, MERCADO_MUERTO → pausa
        if estado in ("MERCADO_MUERTO", "VOLATILIDAD_EXTREMA"):
            pass  # no entra
        else:
            r, pnl = simular_trade_alcista(precio, velas_fut, sl_pct, tp_pct)
            res["pausa_extrema"].append((estado, r, pnl))

    return res

def stats(trades):
    if not trades:
        return 0, 0.0, 0.0
    wins   = sum(1 for _, r, _ in trades if r == "TP")
    total  = len(trades)
    wr     = round(wins / total * 100, 1)
    pnl    = round(CAPITAL_POR_OP * sum(pnl for _, _, pnl in trades) / 100, 2)
    return total, wr, pnl

def stats_por_estado(trades):
    from collections import defaultdict
    grupos = defaultdict(list)
    for estado, r, pnl in trades:
        grupos[estado].append((r, pnl))
    resultado = {}
    for estado, ts in grupos.items():
        wins  = sum(1 for r, _ in ts if r == "TP")
        total = len(ts)
        pnl   = round(CAPITAL_POR_OP * sum(p for _, p in ts) / 100, 2)
        resultado[estado] = (total, round(wins / total * 100, 1) if total else 0, pnl)
    return resultado

def main():
    for ventana in [20, 50]:
        print(f"\n{'=' * 68}")
        print(f"VENTANA TERMOMETRO: {ventana} velas 4H (~{ventana*4}h / ~{ventana//6}d)")
        print(f"{'=' * 68}")

        all_sin   = []
        all_act   = []
        all_prop  = []

        for symbol in SIMBOLOS:
            velas = cargar_velas(symbol)
            res   = backtest_symbol(symbol, velas, ventana)
            all_sin.extend(res["sin_filtro"])
            all_act.extend(res["actual_07"])
            all_prop.extend(res["pausa_extrema"])

            n_s, wr_s, pnl_s = stats(res["sin_filtro"])
            n_a, wr_a, pnl_a = stats(res["actual_07"])
            n_p, wr_p, pnl_p = stats(res["pausa_extrema"])
            print(f"  {symbol:10s}  SIN: {n_s:5d} t WR{wr_s:5.1f}% PNL${pnl_s:8.2f}"
                  f"  |  ACT: {n_a:5d} t WR{wr_a:5.1f}% PNL${pnl_a:8.2f}"
                  f"  |  PAUSA: {n_p:5d} t WR{wr_p:5.1f}% PNL${pnl_p:8.2f}")

        print(f"\n  {'GLOBAL':10s}  SIN: {stats(all_sin)[0]:5d} t WR{stats(all_sin)[1]:5.1f}% PNL${stats(all_sin)[2]:8.2f}"
              f"  |  ACT: {stats(all_act)[0]:5d} t WR{stats(all_act)[1]:5.1f}% PNL${stats(all_act)[2]:8.2f}"
              f"  |  PAUSA: {stats(all_prop)[0]:5d} t WR{stats(all_prop)[1]:5.1f}% PNL${stats(all_prop)[2]:8.2f}")

        # Desglose por estado del mercado (con ventana=20 original)
        if ventana == 20:
            print(f"\n  Desglose por estado (ventana=20, escenario SIN filtro):")
            gx = stats_por_estado(all_sin)
            for estado in ["MERCADO_MUERTO", "TENDENCIA_DEBIL", "TENDENCIA_FUERTE", "VOLATILIDAD_EXTREMA"]:
                if estado in gx:
                    t, wr, pnl = gx[estado]
                    print(f"    {estado:22s}: {t:6d} trades  WR {wr:5.1f}%  PNL ${pnl:9.2f}")

    print(f"\n{'=' * 68}")
    print("CONCLUSION")
    print(f"{'=' * 68}")

    # Recalcular para ventana=50 (propuesta)
    all_sin50  = []
    all_act50  = []
    all_prop50 = []
    for symbol in SIMBOLOS:
        velas = cargar_velas(symbol)
        res   = backtest_symbol(symbol, velas, 50)
        all_sin50.extend(res["sin_filtro"])
        all_act50.extend(res["actual_07"])
        all_prop50.extend(res["pausa_extrema"])

    # Ventana 20 (actual)
    all_sin20  = []
    all_act20  = []
    all_prop20 = []
    for symbol in SIMBOLOS:
        velas = cargar_velas(symbol)
        res   = backtest_symbol(symbol, velas, 20)
        all_sin20.extend(res["sin_filtro"])
        all_act20.extend(res["actual_07"])
        all_prop20.extend(res["pausa_extrema"])

    _, wr_a20, pnl_a20 = stats(all_act20)
    _, wr_p20, pnl_p20 = stats(all_prop20)
    _, wr_a50, pnl_a50 = stats(all_act50)
    _, wr_p50, pnl_p50 = stats(all_prop50)

    print(f"  Ventana 20 actual  + TP/SL*0.7 : WR {wr_a20:5.1f}%  PNL ${pnl_a20:9.2f}")
    print(f"  Ventana 20 actual  + PAUSA ext : WR {wr_p20:5.1f}%  PNL ${pnl_p20:9.2f}  (Δ PNL ${pnl_p20-pnl_a20:+.2f})")
    print(f"  Ventana 50 propues + TP/SL*0.7 : WR {wr_a50:5.1f}%  PNL ${pnl_a50:9.2f}")
    print(f"  Ventana 50 propues + PAUSA ext : WR {wr_p50:5.1f}%  PNL ${pnl_p50:9.2f}  (Δ PNL ${pnl_p50-pnl_a50:+.2f})")
    print(f"{'=' * 68}")

if __name__ == "__main__":
    main()
