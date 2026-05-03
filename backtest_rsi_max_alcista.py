# =========================================
# backtest_rsi_max_alcista.py
# Compara RSI_MAX=70 (actual) vs RSI_MAX=63 (propuesto)
# Solo señales ALCISTAS — 5 monedas, resultado GLOBAL
# Incluye: breakeven, trailing, comision, slippage
# =========================================

import csv
import os
from datetime import datetime

BASE_DIR = os.path.expanduser("~/bot-padre-v2/data/historico_4h")

COMISION  = 0.001
SLIPPAGE  = 0.0005

# Parametros reales de cada francotirador alcista
PARAMS = {
    "BTCUSDT":  {"rsi_min": 50, "sl": 3.5, "tp": 6.0, "ec": 20, "el": 50},
    "ETHUSDT":  {"rsi_min": 50, "sl": 3.5, "tp": 6.0, "ec": 20, "el": 50},
    "SOLUSDT":  {"rsi_min": 50, "sl": 4.0, "tp": 7.0, "ec": 20, "el": 50},
    "BNBUSDT":  {"rsi_min": 50, "sl": 4.0, "tp": 7.0, "ec": 20, "el": 50},
    "AVAXUSDT": {"rsi_min": 50, "sl": 4.0, "tp": 7.0, "ec": 20, "el": 50},
}

# Breakeven — igual que el sistema en produccion
BE_VELAS_ESPERA = 2
BE_UMBRAL       = 0.8
BE_COMISION     = 0.2

# Trailing — igual que el sistema en produccion
TRAILING_ACTIVACION = 0.5
TRAILING_DISTANCIA  = 1.5

ESCENARIOS = {
    "ACTUAL   (RSI_MAX=70)":   70,
    "PROPUESTO(RSI_MAX=63)":   63,
}

def leer_csv(symbol):
    ruta  = os.path.join(BASE_DIR, f"{symbol}_4h.csv")
    velas = []
    try:
        with open(ruta, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                velas.append({
                    "timestamp": row["timestamp"],
                    "close":     float(row["close"]),
                    "high":      float(row["high"]),
                    "low":       float(row["low"]),
                    "volume":    float(row["volume"]),
                    "open":      float(row["open"]),
                })
    except Exception as e:
        print(f"  [ERROR] {symbol}: {e}")
    return velas

def calcular_rsi(cierres, periodo=14):
    if len(cierres) < periodo + 1:
        return None
    ganancias = [max(cierres[i] - cierres[i-1], 0) for i in range(1, len(cierres))]
    perdidas  = [max(cierres[i-1] - cierres[i], 0) for i in range(1, len(cierres))]
    avg_g = sum(ganancias[:periodo]) / periodo
    avg_p = sum(perdidas[:periodo]) / periodo
    for i in range(periodo, len(ganancias)):
        avg_g = (avg_g * (periodo - 1) + ganancias[i]) / periodo
        avg_p = (avg_p * (periodo - 1) + perdidas[i]) / periodo
    if avg_p == 0:
        return 100.0
    return round(100 - (100 / (1 + avg_g / avg_p)), 2)

def calcular_ema(cierres, periodo):
    if len(cierres) < periodo:
        return None
    k   = 2 / (periodo + 1)
    ema = sum(cierres[:periodo]) / periodo
    for precio in cierres[periodo:]:
        ema = precio * k + ema * (1 - k)
    return round(ema, 4)

def simular_alcista(velas, params, rsi_max):
    rsi_min     = params["rsi_min"]
    stop_loss   = params["sl"]
    take_profit = params["tp"]
    ema_corta   = params["ec"]
    ema_larga   = params["el"]

    capital        = 1000.0
    capital_max    = 1000.0
    drawdown_max   = 0.0
    en_posicion    = False
    precio_entrada = 0.0
    sl_actual      = 0.0
    be_price_op    = 0.0
    be_activado    = False
    unidades       = 0.0
    operaciones    = []
    vela_entrada   = 0

    for i in range(ema_larga, len(velas)):
        ventana = velas[max(0, i - ema_larga): i + 1]
        cierres = [v["close"] for v in ventana]

        rsi   = calcular_rsi(cierres)
        ema_c = calcular_ema(cierres, ema_corta)
        ema_l = calcular_ema(cierres, ema_larga)

        if rsi is None or ema_c is None or ema_l is None:
            continue

        precio_actual = velas[i]["close"]

        if not en_posicion:
            if rsi_min <= rsi <= rsi_max and ema_c > ema_l:
                en_posicion    = True
                precio_entrada = precio_actual * (1 + SLIPPAGE)
                sl_actual      = precio_entrada * (1 - stop_loss / 100)
                be_price_op    = precio_entrada * (1 + BE_COMISION / 100)
                be_activado    = False
                vela_entrada   = i
                monto          = capital * 0.02
                unidades       = monto / precio_entrada
                capital       -= monto * COMISION
        else:
            cambio         = ((precio_actual - precio_entrada) / precio_entrada) * 100
            velas_en_trade = i - vela_entrada

            # Breakeven
            if not be_activado:
                if velas_en_trade >= BE_VELAS_ESPERA and cambio >= BE_UMBRAL:
                    if be_price_op > sl_actual:
                        sl_actual   = be_price_op
                        be_activado = True

            # Trailing
            if cambio >= TRAILING_ACTIVACION:
                sl_trail  = precio_actual * (1 - TRAILING_DISTANCIA / 100)
                sl_actual = max(sl_actual, sl_trail)

            # TP
            if cambio >= take_profit:
                ganancia = abs(unidades * precio_actual - unidades * precio_entrada)
                capital += ganancia - ganancia * COMISION
                operaciones.append({"tipo": "TP", "pnl": ganancia, "cambio": cambio, "velas": velas_en_trade})
                en_posicion = False
                be_activado = False

            # SL / BE / TRAILING_SL
            elif precio_actual <= sl_actual:
                pnl_real   = abs(unidades * sl_actual - unidades * precio_entrada)
                es_ganancia = sl_actual >= precio_entrada

                if es_ganancia:
                    capital += pnl_real - pnl_real * COMISION
                    if be_activado and abs(sl_actual - be_price_op) < 0.01:
                        tipo = "BE"
                    else:
                        tipo = "TRAILING_SL"
                    operaciones.append({"tipo": tipo, "pnl": pnl_real, "cambio": cambio, "velas": velas_en_trade})
                else:
                    capital -= pnl_real + pnl_real * COMISION
                    operaciones.append({"tipo": "SL", "pnl": -pnl_real, "cambio": cambio, "velas": velas_en_trade})

                en_posicion = False
                be_activado = False

            if capital > capital_max:
                capital_max = capital
            else:
                dd = ((capital_max - capital) / capital_max) * 100
                if dd > drawdown_max:
                    drawdown_max = dd

    if not operaciones:
        return None

    total  = len(operaciones)
    tps    = [o for o in operaciones if o["tipo"] == "TP"]
    bes    = [o for o in operaciones if o["tipo"] == "BE"]
    trails = [o for o in operaciones if o["tipo"] == "TRAILING_SL"]
    sls    = [o for o in operaciones if o["tipo"] == "SL"]

    wr     = round((len(tps) + len(bes)) / total * 100, 2)
    pnl    = round(sum(o["pnl"] for o in operaciones), 2)
    sum_g  = sum(o["pnl"] for o in tps + bes + trails)
    sum_p  = abs(sum(o["pnl"] for o in sls))
    pf     = round(sum_g / sum_p, 2) if sum_p > 0 else 99.0

    return {
        "total":        total,
        "tp":           len(tps),
        "be":           len(bes),
        "trailing":     len(trails),
        "sl":           len(sls),
        "wr":           wr,
        "pnl":          pnl,
        "sum_g":        sum_g,
        "sum_p":        sum_p,
        "drawdown_max": round(drawdown_max, 2),
        "pf":           pf,
        "capital_final": round(capital, 2),
    }

def acumular(global_acc, r):
    global_acc["ops"]   += r["total"]
    global_acc["tp"]    += r["tp"]
    global_acc["be"]    += r["be"]
    global_acc["trail"] += r["trailing"]
    global_acc["sl"]    += r["sl"]
    global_acc["pnl"]   += r["pnl"]
    global_acc["sum_g"] += r["sum_g"]
    global_acc["sum_p"] += r["sum_p"]

def wr_global(acc):
    if acc["ops"] == 0:
        return 0.0
    return round((acc["tp"] + acc["be"]) / acc["ops"] * 100, 2)

def pf_global(acc):
    if acc["sum_p"] == 0:
        return 99.0
    return round(acc["sum_g"] / acc["sum_p"], 2)

def nuevo_acc():
    return {"ops": 0, "tp": 0, "be": 0, "trail": 0, "sl": 0, "pnl": 0.0, "sum_g": 0.0, "sum_p": 0.0}

if __name__ == "__main__":
    print("=" * 72)
    print("  BACKTEST RSI_MAX ALCISTA — ACTUAL (70) vs PROPUESTO (63)")
    print(f"  5 monedas: BTC ETH SOL BNB AVAX | {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  Sistema: Breakeven {BE_VELAS_ESPERA}v/{BE_UMBRAL}% | Trailing {TRAILING_DISTANCIA}% | Com {COMISION*100}%")
    print("=" * 72)

    resultados_global = {nombre: nuevo_acc() for nombre in ESCENARIOS}
    detalle_por_sym   = {}

    for symbol in ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "AVAXUSDT"]:
        velas = leer_csv(symbol)
        if not velas:
            print(f"  [SKIP] {symbol} — sin datos")
            continue

        detalle_por_sym[symbol] = {}
        print(f"\n  {symbol} ({len(velas)} velas, desde {velas[0]['timestamp'][:10]} hasta {velas[-1]['timestamp'][:10]})")
        print(f"  {'Escenario':<28} {'Ops':>4} {'TP':>4} {'BE':>4} {'SL':>4} {'WR':>6} {'PF':>5} {'DD':>6} {'PNL':>9}")
        print(f"  {'─'*70}")

        for nombre, rsi_max in ESCENARIOS.items():
            r = simular_alcista(velas, PARAMS[symbol], rsi_max)
            if r is None:
                print(f"  {nombre:<28} Sin operaciones")
                detalle_por_sym[symbol][nombre] = None
                continue

            detalle_por_sym[symbol][nombre] = r
            acumular(resultados_global[nombre], r)

            print(f"  {nombre:<28} {r['total']:>4} {r['tp']:>4} {r['be']:>4} {r['sl']:>4} "
                  f"{r['wr']:>5}% {r['pf']:>5} {r['drawdown_max']:>5}% ${r['pnl']:>8.2f}")

    # ── RESUMEN GLOBAL ─────────────────────────────────────────────
    print("\n")
    print("=" * 72)
    print("  RESULTADO GLOBAL — 5 MONEDAS COMBINADAS")
    print("=" * 72)
    print(f"  {'Escenario':<28} {'Ops':>4} {'TP':>4} {'BE':>4} {'SL':>4} {'WR':>6} {'PF':>5} {'PNL':>10}")
    print(f"  {'─'*70}")

    lineas_global = []
    for nombre, acc in resultados_global.items():
        wr  = wr_global(acc)
        pf  = pf_global(acc)
        pnl = round(acc["pnl"], 2)
        lineas_global.append((nombre, acc, wr, pf, pnl))
        print(f"  {nombre:<28} {acc['ops']:>4} {acc['tp']:>4} {acc['be']:>4} {acc['sl']:>4} "
              f"{wr:>5}% {pf:>5} ${pnl:>9.2f}")

    print(f"  {'─'*70}")

    # Veredicto
    nombre_a, acc_a, wr_a, pf_a, pnl_a = lineas_global[0]
    nombre_b, acc_b, wr_b, pf_b, pnl_b = lineas_global[1]

    print(f"\n  IMPACTO DEL CAMBIO:")
    print(f"  WR:  {wr_a}% → {wr_b}%  (Δ {round(wr_b - wr_a, 2):+}%)")
    print(f"  PF:  {pf_a}  → {pf_b}   (Δ {round(pf_b - pf_a, 2):+})")
    print(f"  PNL: ${pnl_a} → ${pnl_b} (Δ ${round(pnl_b - pnl_a, 2):+.2f})")
    print(f"  Ops: {acc_a['ops']} → {acc_b['ops']} (Δ {acc_b['ops'] - acc_a['ops']:+d} operaciones filtradas)")

    print()
    if wr_b > wr_a and pf_b > pf_a:
        print("  ✅ VEREDICTO: RSI_MAX=63 mejora AMBOS — WR y PF. APROBADO para aplicar.")
    elif wr_b > wr_a and pf_b >= pf_a * 0.97:
        print("  ✅ VEREDICTO: RSI_MAX=63 mejora WR con PF casi igual. APROBADO.")
    elif wr_b > wr_a and pnl_b < pnl_a:
        print("  ⚠️  VEREDICTO: RSI_MAX=63 mejora WR pero reduce PNL por menos operaciones. Evaluar.")
    elif wr_b <= wr_a:
        print("  ❌ VEREDICTO: RSI_MAX=63 NO mejora WR. No aplicar el cambio.")
    else:
        print("  ⚠️  VEREDICTO: Resultados mixtos. Revisar manualmente.")
    print("=" * 72)
