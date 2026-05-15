#!/usr/bin/env python3
# =========================================
# backtest_trailing_calibracion.py
# Punto 10: calibrar ACTIVACION y DISTANCIA
# del trailing stop por simbolo segun ATR.
# Sin librerias externas.
# =========================================

import csv
import os

DATA_DIR = os.path.expanduser("~/bot-padre-v2/data/historico_4h")
SIMBOLOS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "AVAXUSDT"]

CAPITAL_POR_OP = 20.0

# Parametros de entrada por simbolo (alcista, los mas comunes)
PARAMS_ENTRADA = {
    "BTCUSDT":  {"rsi_min": 55, "rsi_max": 75, "sl": 5.0, "tp": 6.0, "ec": 20, "el": 100},
    "ETHUSDT":  {"rsi_min": 60, "rsi_max": 75, "sl": 4.5, "tp": 5.0, "ec": 20, "el": 100},
    "SOLUSDT":  {"rsi_min": 50, "rsi_max": 70, "sl": 5.0, "tp": 6.0, "ec": 20, "el":  50},
    "BNBUSDT":  {"rsi_min": 60, "rsi_max": 75, "sl": 4.5, "tp": 5.0, "ec": 20, "el": 100},
    "AVAXUSDT": {"rsi_min": 60, "rsi_max": 75, "sl": 4.5, "tp": 5.0, "ec": 20, "el": 100},
}

# Grid de busqueda
ACTIVACIONES = [0.3, 0.5, 1.0, 1.5, 2.0]
DISTANCIAS   = [1.0, 1.5, 2.0, 2.5, 3.0]

def ema_serie(precios, periodo):
    if len(precios) < periodo:
        return [None] * len(precios)
    k  = 2.0 / (periodo + 1)
    r  = [None] * (periodo - 1)
    v  = sum(precios[:periodo]) / periodo
    r.append(v)
    for p in precios[periodo:]:
        v = p * k + v * (1 - k)
        r.append(v)
    return r

def rsi_serie(precios, periodo=14):
    n = len(precios)
    result = [None] * n
    if n < periodo + 1:
        return result
    cambios = [precios[i] - precios[i-1] for i in range(1, n)]
    avg_g = sum(max(0.0, c) for c in cambios[:periodo]) / periodo
    avg_l = sum(max(0.0, -c) for c in cambios[:periodo]) / periodo
    result[periodo] = 100.0 if avg_l == 0 else round(100 - 100 / (1 + avg_g / avg_l), 2)
    for i in range(periodo, n - 1):
        g = max(0.0, cambios[i])
        l = max(0.0, -cambios[i])
        avg_g = (avg_g * (periodo - 1) + g) / periodo
        avg_l = (avg_l * (periodo - 1) + l) / periodo
        result[i + 1] = 100.0 if avg_l == 0 else round(100 - 100 / (1 + avg_g / avg_l), 2)
    return result

def atr_serie(velas, periodo=14):
    """ATR como % del precio de cierre."""
    n = len(velas)
    trs = [None]
    for i in range(1, n):
        h, l, c_prev = velas[i][0], velas[i][1], velas[i-1][2]
        tr = max(h - l, abs(h - c_prev), abs(l - c_prev))
        trs.append(tr / velas[i][2] * 100)  # como % del precio
    result = [None] * n
    if n < periodo + 1:
        return result
    seed = sum(t for t in trs[1:periodo+1] if t is not None) / periodo
    result[periodo] = round(seed, 4)
    val = seed
    for i in range(periodo + 1, n):
        val = (val * (periodo - 1) + trs[i]) / periodo
        result[i] = round(val, 4)
    return result

def simular_con_trailing(precio_entrada, velas_futuras, sl_fijo_pct, tp_pct,
                          activacion_pct, distancia_pct, max_v=20):
    """
    Simula una posicion alcista con trailing stop.
    Retorna (resultado, pnl_pct).
    """
    sl_inicial  = precio_entrada * (1 - sl_fijo_pct / 100)
    tp_precio   = precio_entrada * (1 + tp_pct / 100)
    trailing_sl = sl_inicial
    maximo      = precio_entrada
    trailing_on = False

    for v in velas_futuras[:max_v]:
        high, low, close = v[0], v[1], v[2]

        # Actualizar maximo
        if high > maximo:
            maximo = high

        cambio_pct = (maximo - precio_entrada) / precio_entrada * 100

        # Actualizar trailing SL si hay ganancia
        if cambio_pct > 0:
            nuevo_sl = maximo * (1 - distancia_pct / 100)
            if nuevo_sl > trailing_sl:
                trailing_sl = nuevo_sl

        # Activar trailing
        if not trailing_on and cambio_pct >= activacion_pct:
            trailing_on = True

        # TP fijo
        if high >= tp_precio:
            pnl = ((tp_precio - precio_entrada) / precio_entrada) * 100
            return "TP", round(pnl, 3)

        # SL (fijo o trailing)
        if low <= trailing_sl:
            pnl = ((trailing_sl - precio_entrada) / precio_entrada) * 100
            return "TRAILING_SL" if trailing_on else "SL", round(pnl, 3)

    # Timeout
    if velas_futuras:
        cierre = velas_futuras[min(max_v-1, len(velas_futuras)-1)][2]
        pnl    = ((cierre - precio_entrada) / precio_entrada) * 100
        return "TIMEOUT", round(pnl, 3)
    return "TIMEOUT", 0.0

def cargar_velas(symbol):
    ruta  = os.path.join(DATA_DIR, f"{symbol}_4h.csv")
    velas = []
    with open(ruta, "r") as f:
        for row in csv.DictReader(f):
            velas.append((float(row["high"]), float(row["low"]), float(row["close"])))
    return velas

def backtest_symbol(symbol, velas):
    p       = PARAMS_ENTRADA[symbol]
    sl_pct  = p["sl"]
    tp_pct  = p["tp"]
    ec      = p["ec"]
    el      = p["el"]
    rsi_min = p["rsi_min"]
    rsi_max = p["rsi_max"]

    cierres  = [v[2] for v in velas]
    n        = len(cierres)
    ema_ec_s = ema_serie(cierres, ec)
    ema_el_s = ema_serie(cierres, el)
    rsi_s    = rsi_serie(cierres, 14)
    atr_s    = atr_serie(velas, 14)

    min_idx = max(el, 14) + 5

    # Recopilar puntos de entrada
    entradas = []
    for i in range(min_idx, n - 20):
        rsi_val = rsi_s[i]
        ema_c   = ema_ec_s[i]
        ema_l   = ema_el_s[i]
        precio  = cierres[i]
        if rsi_val is None or ema_c is None or ema_l is None:
            continue
        if (rsi_min <= rsi_val <= rsi_max) and (precio > ema_c > ema_l):
            atr_val = atr_s[i] if atr_s[i] else 0.0
            futuras = [(velas[j][0], velas[j][1], velas[j][2]) for j in range(i+1, min(i+21, n))]
            entradas.append((precio, futuras, atr_val))

    if not entradas:
        return {}, 0.0

    # ATR promedio del simbolo
    atr_vals = [a for _, _, a in entradas if a > 0]
    atr_prom = round(sum(atr_vals) / len(atr_vals), 3) if atr_vals else 0.0

    # Grid search
    resultados = {}
    for act in ACTIVACIONES:
        for dist in DISTANCIAS:
            trades = []
            for precio, futuras, _ in entradas:
                r, pnl = simular_con_trailing(precio, futuras, sl_pct, tp_pct, act, dist)
                trades.append((r, pnl))
            wins   = sum(1 for r, _ in trades if r in ("TP", "TRAILING_SL") and _ > 0)
            total  = len(trades)
            wr     = round(wins / total * 100, 1) if total else 0
            pnl    = round(CAPITAL_POR_OP * sum(p for _, p in trades) / 100, 2)
            resultados[(act, dist)] = (total, wr, pnl)

    return resultados, atr_prom

def main():
    print("=" * 72)
    print("BACKTEST TRAILING STOP — calibracion por simbolo")
    print("=" * 72)

    recomendaciones = {}

    for symbol in SIMBOLOS:
        print(f"\n  {symbol}")
        velas = cargar_velas(symbol)
        res, atr_prom = backtest_symbol(symbol, velas)
        print(f"  ATR promedio 4H: {atr_prom}%")

        if not res:
            print("  Sin entradas suficientes.")
            continue

        # Mejor combinacion por PNL
        mejor_key = max(res, key=lambda k: res[k][2])
        mejor     = res[mejor_key]
        act_opt, dist_opt = mejor_key

        # Actual (0.5, 1.5)
        actual = res.get((0.5, 1.5), (0, 0, 0))

        print(f"  {'Act%':>5} {'Dist%':>6} {'Trades':>7} {'WR%':>6} {'PNL':>9}")
        print(f"  {'-'*40}")

        # Mostrar combinaciones relevantes
        subset_acts  = [0.5, act_opt]
        subset_dists = [1.5, dist_opt]
        mostrados = set()
        for act in ACTIVACIONES:
            for dist in DISTANCIAS:
                if act not in subset_acts and dist not in subset_dists:
                    continue
                k = (act, dist)
                if k in mostrados:
                    continue
                mostrados.add(k)
                t, wr, pnl = res[k]
                marker = " ← ACTUAL" if k == (0.5, 1.5) else (" ← OPTIMO" if k == mejor_key else "")
                print(f"  {act:>5.1f} {dist:>6.1f} {t:>7d} {wr:>6.1f}% ${pnl:>8.2f}{marker}")

        mejora = round(mejor[2] - actual[2], 2)
        print(f"\n  Recomendacion: ACTIVACION={act_opt}%  DISTANCIA={dist_opt}%")
        print(f"  Mejora vs actual: ${mejora:+.2f} PNL")
        recomendaciones[symbol] = {"activacion": act_opt, "distancia": dist_opt,
                                    "atr": atr_prom, "mejora_pnl": mejora}

    print(f"\n{'=' * 72}")
    print("RESUMEN — Valores recomendados para config_cartera.py")
    print(f"{'=' * 72}")
    print(f"  {'Symbol':12s} {'ATR 4H':>8} {'Act actual':>11} {'Dist actual':>12} {'Act optima':>11} {'Dist optima':>12} {'Mejora PNL':>11}")
    print(f"  {'-'*72}")
    for symbol, r in recomendaciones.items():
        print(f"  {symbol:12s} {r['atr']:>7.3f}% {'0.5%':>11} {'1.5%':>12} {r['activacion']:>10.1f}% {r['distancia']:>11.1f}% ${r['mejora_pnl']:>+.2f}")
    print(f"{'=' * 72}")

if __name__ == "__main__":
    main()
