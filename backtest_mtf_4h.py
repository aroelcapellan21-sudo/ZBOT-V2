#!/usr/bin/env python3
# =========================================
# backtest_mtf_4h.py
# Compara logica MTF ACTUAL vs OPCION B (4H gate duro)
# EMA incremental — O(n) por serie. Sin librerias externas.
# =========================================

import csv
import os

DATA_DIR = os.path.expanduser("~/bot-padre-v2/data/historico_4h")
SIMBOLOS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "AVAXUSDT"]
FASES    = ["alcista", "bajista", "lateral"]

PARAMETROS = {
    "BTCUSDT": {
        "alcista": {"rsi_min": 55, "rsi_max": 75, "sl": 5.0, "tp": 6.0, "ec": 20, "el": 100},
        "bajista": {"rsi_min": 20, "rsi_max": 30, "sl": 3.5, "tp": 4.0, "ec": 10, "el": 50},
        "lateral": {"rsi_min": 43, "rsi_max": 57, "sl": 3.5, "tp": 4.0, "ec": 10, "el": 30},
    },
    "ETHUSDT": {
        "alcista": {"rsi_min": 60, "rsi_max": 75, "sl": 4.5, "tp": 5.0, "ec": 20, "el": 100},
        "bajista": {"rsi_min": 20, "rsi_max": 30, "sl": 3.0, "tp": 4.0, "ec": 20, "el": 50},
        "lateral": {"rsi_min": 43, "rsi_max": 57, "sl": 4.5, "tp": 6.0, "ec": 20, "el": 100},
    },
    "SOLUSDT": {
        "alcista": {"rsi_min": 50, "rsi_max": 70, "sl": 5.0, "tp": 6.0, "ec": 20, "el": 50},
        "bajista": {"rsi_min": 20, "rsi_max": 33, "sl": 3.5, "tp": 5.0, "ec": 20, "el": 100},
        "lateral": {"rsi_min": 43, "rsi_max": 57, "sl": 3.5, "tp": 4.0, "ec": 20, "el": 100},
    },
    "BNBUSDT": {
        "alcista": {"rsi_min": 60, "rsi_max": 75, "sl": 4.5, "tp": 5.0, "ec": 20, "el": 100},
        "bajista": {"rsi_min": 20, "rsi_max": 35, "sl": 3.5, "tp": 4.0, "ec": 20, "el": 100},
        "lateral": {"rsi_min": 43, "rsi_max": 57, "sl": 4.5, "tp": 5.0, "ec": 20, "el": 100},
    },
    "AVAXUSDT": {
        "alcista": {"rsi_min": 60, "rsi_max": 75, "sl": 4.5, "tp": 5.0, "ec": 20, "el": 100},
        "bajista": {"rsi_min": 20, "rsi_max": 33, "sl": 3.5, "tp": 4.0, "ec": 20, "el": 50},
        "lateral": {"rsi_min": 43, "rsi_max": 57, "sl": 5.0, "tp": 6.0, "ec": 20, "el": 100},
    },
}

CAPITAL_POR_OP = 20.0  # 2% de $1000

def ema_serie(precios, periodo):
    """Calcula la serie completa de EMA en O(n). Retorna lista del mismo largo."""
    if len(precios) < periodo:
        return [None] * len(precios)
    k      = 2.0 / (periodo + 1)
    result = [None] * (periodo - 1)
    seed   = sum(precios[:periodo]) / periodo
    result.append(seed)
    val = seed
    for p in precios[periodo:]:
        val = p * k + val * (1 - k)
        result.append(val)
    return result

def rsi_serie(precios, periodo=14):
    """Calcula la serie RSI en O(n) con media movil exponencial."""
    n = len(precios)
    result = [None] * n
    if n < periodo + 1:
        return result
    cambios  = [precios[i] - precios[i-1] for i in range(1, n)]
    gains = [max(0.0, c) for c in cambios[:periodo]]
    losses = [max(0.0, -c) for c in cambios[:periodo]]
    avg_g = sum(gains)  / periodo
    avg_l = sum(losses) / periodo
    if avg_l == 0:
        result[periodo] = 100.0
    else:
        rs = avg_g / avg_l
        result[periodo] = 100.0 - 100.0 / (1 + rs)
    for i in range(periodo, n - 1):
        g = max(0.0, cambios[i])
        l = max(0.0, -cambios[i])
        avg_g = (avg_g * (periodo - 1) + g) / periodo
        avg_l = (avg_l * (periodo - 1) + l) / periodo
        if avg_l == 0:
            result[i + 1] = 100.0
        else:
            rs = avg_g / avg_l
            result[i + 1] = round(100.0 - 100.0 / (1 + rs), 2)
    return result

def detectar_tendencia_ventana(ema20_val, ema50_val, precio, cierre_inicio, umbral):
    if ema20_val is None or ema50_val is None:
        return "DESCONOCIDA"
    cambio = ((precio - cierre_inicio) / cierre_inicio) * 100
    if precio > ema20_val > ema50_val and cambio > umbral:
        return "ALCISTA"
    elif precio < ema20_val < ema50_val and cambio < -umbral:
        return "BAJISTA"
    return "LATERAL"

def mtf_actual_pasa(fase, tf4h, tf1d):
    f = fase.upper()
    if f == "ALCISTA":
        return not (tf4h == "BAJISTA" and tf1d == "BAJISTA")
    if f == "BAJISTA":
        return not (tf4h == "ALCISTA" and tf1d == "ALCISTA")
    if f == "LATERAL":
        if tf4h == "ALCISTA" and tf1d == "ALCISTA":
            return False
        if tf4h == "BAJISTA" and tf1d == "BAJISTA":
            return False
        return True
    return True

def mtf_opcion_b_pasa(fase, tf4h):
    f = fase.upper()
    if f == "ALCISTA":
        return tf4h != "BAJISTA"
    if f == "BAJISTA":
        return tf4h != "ALCISTA"
    if f == "LATERAL":
        return tf4h == "LATERAL"
    return True

def simular_trade(fase, precio_entrada, velas_futuras, sl_pct, tp_pct, max_velas=10):
    if fase in ("alcista", "lateral_long"):
        sl_p = precio_entrada * (1 - sl_pct / 100)
        tp_p = precio_entrada * (1 + tp_pct / 100)
    else:  # bajista
        sl_p = precio_entrada * (1 + sl_pct / 100)
        tp_p = precio_entrada * (1 - tp_pct / 100)

    for vela in velas_futuras[:max_velas]:
        high, low = vela[0], vela[1]
        if fase == "alcista":
            if low  <= sl_p: return "SL", -sl_pct
            if high >= tp_p: return "TP",  tp_pct
        elif fase == "bajista":
            if high >= sl_p: return "SL", -sl_pct
            if low  <= tp_p: return "TP",  tp_pct
        elif fase == "lateral":
            up   = precio_entrada * (1 + sl_pct / 100)
            down = precio_entrada * (1 - sl_pct / 100)
            tp_up   = precio_entrada * (1 + tp_pct / 100)
            tp_down = precio_entrada * (1 - tp_pct / 100)
            if high >= up or low <= down:
                return "SL", -sl_pct
            if high >= tp_up or low <= tp_down:
                return "TP",  tp_pct

    if velas_futuras:
        cierre_final = velas_futuras[min(max_velas - 1, len(velas_futuras) - 1)][2]
        pnl = ((cierre_final - precio_entrada) / precio_entrada) * 100
        if fase == "bajista":
            pnl = -pnl
        return "TIMEOUT", round(pnl, 3)
    return "TIMEOUT", 0.0

def cargar_cierres(symbol):
    ruta  = os.path.join(DATA_DIR, f"{symbol}_4h.csv")
    velas = []
    with open(ruta, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            velas.append((float(row["close"]), float(row["high"]), float(row["low"])))
    return velas

def backtest_symbol_fase(symbol, fase, velas):
    p       = PARAMETROS[symbol][fase]
    rsi_min = p["rsi_min"]
    rsi_max = p["rsi_max"]
    sl_pct  = p["sl"]
    tp_pct  = p["tp"]
    ec      = p["ec"]
    el      = p["el"]

    cierres = [v[0] for v in velas]
    n       = len(cierres)

    # Precompute series en O(n)
    ema_ec_s  = ema_serie(cierres, ec)
    ema_el_s  = ema_serie(cierres, el)
    ema20_s   = ema_serie(cierres, 20)
    ema50_s   = ema_serie(cierres, 50)
    rsi_s     = rsi_serie(cierres, 14)

    # Para MTF 1D: EMA20/50 sobre ventana de 60 velas 4H
    # Lo aproximamos con EMAs de periodo largo sobre la serie completa
    # y usamos el cambio porcentual en ventana de 60
    ema20_1d_s = ema_serie(cierres, 20)
    ema50_1d_s = ema_serie(cierres, 50)

    min_idx = max(el, 60) + 15

    trades_actual   = []
    trades_opcion_b = []

    for i in range(min_idx, n - 10):
        rsi_val  = rsi_s[i]
        ema_c    = ema_ec_s[i]
        ema_l    = ema_el_s[i]
        precio   = cierres[i]

        if rsi_val is None or ema_c is None or ema_l is None:
            continue

        if fase == "alcista":
            entrada_ok = (rsi_min <= rsi_val <= rsi_max) and (precio > ema_c > ema_l)
        elif fase == "bajista":
            entrada_ok = (rsi_min <= rsi_val <= rsi_max) and (precio < ema_c < ema_l)
        else:
            entrada_ok = (rsi_min <= rsi_val <= rsi_max)

        if not entrada_ok:
            continue

        # MTF 4H: ventana de 50 velas
        inicio_4h = max(0, i - 49)
        tf4h = detectar_tendencia_ventana(
            ema20_s[i], ema50_s[i], precio, cierres[inicio_4h], umbral=2.0
        )

        # MTF 1D aprox: ventana de 60 velas
        inicio_1d = max(0, i - 59)
        tf1d = detectar_tendencia_ventana(
            ema20_1d_s[i], ema50_1d_s[i], precio, cierres[inicio_1d], umbral=3.0
        )

        velas_futuras = [(velas[j][1], velas[j][2], velas[j][0]) for j in range(i+1, min(i+11, n))]

        if mtf_actual_pasa(fase, tf4h, tf1d):
            res, pnl = simular_trade(fase, precio, velas_futuras, sl_pct, tp_pct)
            trades_actual.append((res, pnl))

        if mtf_opcion_b_pasa(fase, tf4h):
            res, pnl = simular_trade(fase, precio, velas_futuras, sl_pct, tp_pct)
            trades_opcion_b.append((res, pnl))

    return trades_actual, trades_opcion_b

def stats(trades):
    if not trades:
        return 0, 0.0, 0.0
    wins   = sum(1 for r, _ in trades if r == "TP")
    total  = len(trades)
    wr     = round(wins / total * 100, 1)
    pnl_pct = sum(pnl for _, pnl in trades)
    pnl_usd = round(CAPITAL_POR_OP * pnl_pct / 100, 2)
    return total, wr, pnl_usd

def main():
    print("=" * 70)
    print("BACKTEST MTF: ACTUAL vs OPCION B (4H como gate duro)")
    print("=" * 70)

    all_actual   = []
    all_opcion_b = []
    fases_actual   = {f: [] for f in FASES}
    fases_opcion_b = {f: [] for f in FASES}

    for symbol in SIMBOLOS:
        print(f"\n  {symbol} ({DATA_DIR}/{symbol}_4h.csv)")
        velas = cargar_cierres(symbol)

        for fase in FASES:
            ta, tb = backtest_symbol_fase(symbol, fase, velas)
            all_actual.extend(ta)
            all_opcion_b.extend(tb)
            fases_actual[fase].extend(ta)
            fases_opcion_b[fase].extend(tb)

            n_a, wr_a, pnl_a = stats(ta)
            n_b, wr_b, pnl_b = stats(tb)
            diff_trades = n_b - n_a
            print(f"    {fase:8s}  ACTUAL: {n_a:5d} tr WR {wr_a:5.1f}% PNL ${pnl_a:8.2f}"
                  f"  |  OPT-B: {n_b:5d} tr WR {wr_b:5.1f}% PNL ${pnl_b:8.2f}"
                  f"  ({diff_trades:+d} trades)")

    print("\n" + "=" * 70)
    print("RESUMEN POR FASE (5 simbolos)")
    print("=" * 70)
    for fase in FASES:
        n_a, wr_a, pnl_a = stats(fases_actual[fase])
        n_b, wr_b, pnl_b = stats(fases_opcion_b[fase])
        print(f"  {fase.upper():8s}  ACTUAL: {n_a:5d} tr WR {wr_a:5.1f}% PNL ${pnl_a:8.2f}"
              f"  |  OPT-B: {n_b:5d} tr WR {wr_b:5.1f}% PNL ${pnl_b:8.2f}"
              f"  ({n_b - n_a:+d} trades)")

    print("\n" + "=" * 70)
    print("RESUMEN GLOBAL")
    print("=" * 70)
    n_a, wr_a, pnl_a = stats(all_actual)
    n_b, wr_b, pnl_b = stats(all_opcion_b)
    print(f"  ACTUAL  : {n_a:6d} trades  WR {wr_a:5.1f}%  PNL ${pnl_a:9.2f}")
    print(f"  OPCION B: {n_b:6d} trades  WR {wr_b:5.1f}%  PNL ${pnl_b:9.2f}")
    print(f"  Trades  : {n_b - n_a:+d} ({round((n_b/n_a - 1)*100, 1) if n_a else 0:+.1f}%)")
    print(f"  PNL     : ${round(pnl_b - pnl_a, 2):+.2f}")
    print(f"  WR      : {round(wr_b - wr_a, 1):+.1f}pp")

    print()
    if wr_b > wr_a and pnl_b > pnl_a:
        print("  → OPCION B GANA en WR y PNL. Recomendado aplicar.")
    elif wr_b > wr_a:
        print("  → OPCION B tiene mejor WR. PNL similar o menor (menos trades).")
    elif pnl_b > pnl_a:
        print("  → OPCION B genera mas PNL con igual o menor WR.")
    else:
        print("  → ACTUAL es superior. El gate duro 4H perjudica el sistema.")
    print("=" * 70)

if __name__ == "__main__":
    main()
