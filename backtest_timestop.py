# =========================================
# backtest_timestop.py
# Test B — Time Stop segun recomendacion Opus
# Cierra trades dormidos despues de X velas sin moverse Y%
# Compara: BASE vs CON TIME STOP
# Sin librerias externas. Constitucion RESPETADA
# =========================================

import csv
import os
from datetime import datetime

BASE_DIR    = os.path.expanduser("~/bot-padre-v2/data/historico_4h")
REPORTE_DIR = os.path.expanduser("~/bot-padre-v2/data/historico/backtesting")
os.makedirs(REPORTE_DIR, exist_ok=True)

COMISION = 0.001
SLIPPAGE = 0.0005
QUINTETO = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "AVAXUSDT"]

# Parametros base
SL_PCT = 3.5
TP_PCT = 6.0

# Parametros time stop — segun Opus
TIME_STOP_VELAS   = 6      # 24h en 4H
TIME_STOP_UMBRAL  = 1.0    # % minimo de movimiento esperado

# Parametros breakeven simple
VELAS_ESPERA = 2
UMBRAL_BE    = 0.8
COMISION_BE  = 0.2

PARAMS = {
    "BTCUSDT":  {"alcista": {"rsi": 55, "sl": SL_PCT, "tp": TP_PCT, "ec": 20, "el": 50},
                 "bajista": {"rsi": 35, "sl": SL_PCT, "tp": TP_PCT, "ec": 20, "el": 50}},
    "ETHUSDT":  {"alcista": {"rsi": 55, "sl": SL_PCT, "tp": TP_PCT, "ec": 20, "el": 50},
                 "bajista": {"rsi": 35, "sl": SL_PCT, "tp": TP_PCT, "ec": 20, "el": 50}},
    "SOLUSDT":  {"alcista": {"rsi": 55, "sl": 4.0,    "tp": 7.0,    "ec": 20, "el": 50},
                 "bajista": {"rsi": 35, "sl": 4.0,    "tp": 7.0,    "ec": 20, "el": 50}},
    "BNBUSDT":  {"alcista": {"rsi": 55, "sl": 4.0,    "tp": 7.0,    "ec": 20, "el": 50},
                 "bajista": {"rsi": 35, "sl": 4.0,    "tp": 7.0,    "ec": 20, "el": 50}},
    "AVAXUSDT": {"alcista": {"rsi": 55, "sl": 4.0,    "tp": 7.0,    "ec": 20, "el": 50},
                 "bajista": {"rsi": 35, "sl": 4.0,    "tp": 7.0,    "ec": 20, "el": 50}},
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
                    "open":      float(row["open"]),
                    "high":      float(row["high"]),
                    "low":       float(row["low"]),
                    "close":     float(row["close"]),
                    "volume":    float(row["volume"]),
                })
    except Exception as e:
        print(f"[ERROR] {symbol}: {e}")
    return velas

def calcular_rsi(cierres, periodo=14):
    if len(cierres) < periodo + 1:
        return None
    ganancias = [max(cierres[i]-cierres[i-1], 0) for i in range(1, len(cierres))]
    perdidas  = [max(cierres[i-1]-cierres[i], 0) for i in range(1, len(cierres))]
    avg_g = sum(ganancias[:periodo]) / periodo
    avg_p = sum(perdidas[:periodo]) / periodo
    for i in range(periodo, len(ganancias)):
        avg_g = (avg_g * (periodo-1) + ganancias[i]) / periodo
        avg_p = (avg_p * (periodo-1) + perdidas[i]) / periodo
    if avg_p == 0:
        return 100.0
    return round(100 - (100 / (1 + avg_g/avg_p)), 2)

def calcular_ema(cierres, periodo):
    if len(cierres) < periodo:
        return None
    k   = 2 / (periodo + 1)
    ema = sum(cierres[:periodo]) / periodo
    for precio in cierres[periodo:]:
        ema = precio * k + ema * (1 - k)
    return round(ema, 4)

def simular(velas, params, fase, usar_timestop=False):
    rsi_entrada = params["rsi"]
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

    for i in range(max(ema_larga, 20), len(velas)):
        ventana = velas[max(0, i-ema_larga):i+1]
        cierres = [v["close"] for v in ventana]
        rsi     = calcular_rsi(cierres)
        ema_c   = calcular_ema(cierres, ema_corta)
        ema_l   = calcular_ema(cierres, ema_larga)

        if rsi is None or ema_c is None or ema_l is None:
            continue

        precio_actual = velas[i]["close"]

        if not en_posicion:
            señal = False
            if fase == "ALCISTA" and rsi >= rsi_entrada and ema_c > ema_l:
                señal = True
            elif fase == "BAJISTA" and rsi <= rsi_entrada and ema_c < ema_l:
                señal = True

            if señal:
                en_posicion    = True
                precio_entrada = precio_actual * (1 + SLIPPAGE) if fase != "BAJISTA" else precio_actual * (1 - SLIPPAGE)
                sl_actual      = precio_entrada * (1 - stop_loss/100) if fase != "BAJISTA" else precio_entrada * (1 + stop_loss/100)
                be_price_op    = precio_entrada * (1 + COMISION_BE/100) if fase != "BAJISTA" else precio_entrada * (1 - COMISION_BE/100)
                be_activado    = False
                vela_entrada   = i
                monto          = capital * 0.02
                unidades       = monto / precio_entrada
                capital       -= monto * COMISION

        else:
            if fase == "BAJISTA":
                cambio = ((precio_entrada - precio_actual) / precio_entrada) * 100
            else:
                cambio = ((precio_actual - precio_entrada) / precio_entrada) * 100

            velas_en_trade = i - vela_entrada

            # BREAKEVEN
            if not be_activado:
                if velas_en_trade >= VELAS_ESPERA and cambio >= UMBRAL_BE:
                    be_mejor = (be_price_op > sl_actual) if fase != "BAJISTA" else (be_price_op < sl_actual)
                    if be_mejor:
                        sl_actual   = be_price_op
                        be_activado = True

            # TRAILING
            if cambio > 0:
                sl_trail  = precio_actual * (1 - stop_loss/100) if fase != "BAJISTA" else precio_actual * (1 + stop_loss/100)
                sl_actual = max(sl_actual, sl_trail) if fase != "BAJISTA" else min(sl_actual, sl_trail)

            # TIME STOP — cierra trade dormido
            if usar_timestop and velas_en_trade >= TIME_STOP_VELAS:
                if abs(cambio) < TIME_STOP_UMBRAL:
                    pnl_real = abs(unidades * precio_actual - unidades * precio_entrada)
                    if cambio > 0:
                        capital += pnl_real - pnl_real * COMISION
                        operaciones.append({"tipo": "TIME_TP", "pnl": pnl_real, "velas": velas_en_trade})
                    else:
                        capital -= pnl_real + pnl_real * COMISION
                        operaciones.append({"tipo": "TIME_SL", "pnl": -pnl_real, "velas": velas_en_trade})
                    en_posicion = False
                    be_activado = False
                    continue

            # TP
            if cambio >= take_profit:
                ganancia  = abs(unidades * precio_actual - unidades * precio_entrada)
                capital  += ganancia - ganancia * COMISION
                operaciones.append({"tipo": "TP", "pnl": ganancia, "velas": velas_en_trade})
                en_posicion = False
                be_activado = False

            # SL / BE / TRAILING
            elif (fase != "BAJISTA" and precio_actual <= sl_actual) or \
                 (fase == "BAJISTA" and precio_actual >= sl_actual):
                pnl_real    = abs(unidades * sl_actual - unidades * precio_entrada)
                es_ganancia = (sl_actual >= precio_entrada) if fase != "BAJISTA" else (sl_actual <= precio_entrada)
                if es_ganancia:
                    capital += pnl_real - pnl_real * COMISION
                    tipo = "BE" if be_activado and abs(sl_actual - be_price_op) < 0.0001 else "TRAILING_SL"
                    operaciones.append({"tipo": tipo, "pnl": pnl_real, "velas": velas_en_trade})
                else:
                    capital -= pnl_real + pnl_real * COMISION
                    operaciones.append({"tipo": "SL", "pnl": -pnl_real, "velas": velas_en_trade})
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

    total    = len(operaciones)
    tps      = [o for o in operaciones if o["tipo"] in ("TP", "BE", "TRAILING_SL", "TIME_TP")]
    sls      = [o for o in operaciones if o["tipo"] in ("SL", "TIME_SL")]
    wins     = [o for o in operaciones if o["tipo"] in ("TP", "BE", "TIME_TP")]
    wr       = round(len(wins) / total * 100, 2)
    pnl      = round(sum(o["pnl"] for o in operaciones), 2)
    sum_g    = sum(o["pnl"] for o in tps)
    sum_p    = abs(sum(o["pnl"] for o in sls))
    pf       = round(sum_g / sum_p, 2) if sum_p > 0 else 99.0

    time_tp_count = len([o for o in operaciones if o["tipo"] == "TIME_TP"])
    time_sl_count = len([o for o in operaciones if o["tipo"] == "TIME_SL"])

    return {
        "total": total,
        "tp": len([o for o in operaciones if o["tipo"] == "TP"]),
        "be": len([o for o in operaciones if o["tipo"] == "BE"]),
        "sl": len(sls),
        "time_tp": time_tp_count,
        "time_sl": time_sl_count,
        "wr": wr,
        "pnl": pnl,
        "drawdown_max": round(drawdown_max, 2),
        "profit_factor": pf,
        "capital_final": round(capital, 2)
    }

if __name__ == "__main__":
    print("=" * 65)
    print("  BACKTESTING TEST B — TIME STOP")
    print(f"  Cierra si despues de {TIME_STOP_VELAS} velas ({TIME_STOP_VELAS*4}h) movimiento < {TIME_STOP_UMBRAL}%")
    print(f"  Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 65)

    resumen = {
        "BASE":     {"ops":0, "wins":0, "pnl":0.0},
        "CON_TS":   {"ops":0, "wins":0, "pnl":0.0},
    }

    for symbol in QUINTETO:
        print(f"\n  Procesando {symbol}...")
        velas = leer_csv(symbol)
        if not velas:
            continue

        print(f"\n{'='*65}")
        print(f"  {symbol} — BASE vs CON TIME STOP")
        print(f"{'='*65}")
        print(f"  {'Fase':<10} {'Modo':<10} {'Ops':>4} {'WR':>6} {'PF':>5} {'DD':>6} {'PNL':>8} {'T_TP':>5} {'T_SL':>5}")
        print(f"  {'─'*63}")

        for fase in ["alcista", "bajista"]:
            params  = PARAMS.get(symbol, PARAMS["BTCUSDT"])[fase]
            r_base  = simular(velas, params, fase.upper(), usar_timestop=False)
            r_ts    = simular(velas, params, fase.upper(), usar_timestop=True)

            for modo, r in [("BASE", r_base), ("CON_TS", r_ts)]:
                if not r:
                    continue
                t_tp = r.get("time_tp", 0)
                t_sl = r.get("time_sl", 0)
                print(f"  {fase.upper():<10} {modo:<10} Ops:{r['total']:>3} WR:{r['wr']:>5}% PF:{r['profit_factor']:>4} DD:{r['drawdown_max']:>5}% PNL:${r['pnl']:>7} T_TP:{t_tp:>3} T_SL:{t_sl:>3}")
                wins = r.get("tp", 0) + r.get("be", 0) + r.get("time_tp", 0)
                resumen[modo]["ops"]  += r["total"]
                resumen[modo]["wins"] += wins
                resumen[modo]["pnl"]  += r["pnl"]

            print(f"  {'─'*63}")

    print(f"\n{'='*65}")
    print(f"  RESUMEN GLOBAL")
    print(f"{'='*65}")
    for modo in ["BASE", "CON_TS"]:
        t  = resumen[modo]
        wr = round(t["wins"] / t["ops"] * 100, 2) if t["ops"] > 0 else 0
        print(f"  {modo:<10} | Ops:{t['ops']:>5} WR:{wr:>5}% PNL:${round(t['pnl'],2):>10}")

    wr_base = round(resumen["BASE"]["wins"]   / resumen["BASE"]["ops"]   * 100, 2) if resumen["BASE"]["ops"]   > 0 else 0
    wr_ts   = round(resumen["CON_TS"]["wins"] / resumen["CON_TS"]["ops"] * 100, 2) if resumen["CON_TS"]["ops"] > 0 else 0
    pnl_base = resumen["BASE"]["pnl"]
    pnl_ts   = resumen["CON_TS"]["pnl"]

    print(f"\n  VEREDICTO:")
    if wr_ts >= 65 and pnl_ts >= pnl_base * 0.95:
        print(f"  ✅ APROBADO — WR {wr_base}% → {wr_ts}% | PNL ${round(pnl_base,2)} → ${round(pnl_ts,2)}")
        print(f"  🎯 META BLUE GUARDIAN ALCANZADA")
    elif wr_ts > wr_base and pnl_ts >= pnl_base * 0.90:
        print(f"  ✅ MEJORA — WR {wr_base}% → {wr_ts}% | PNL ${round(pnl_base,2)} → ${round(pnl_ts,2)}")
        print(f"  ⚠️  Meta 65% no alcanzada — considerar Test C")
    else:
        print(f"  ❌ NO APROBADO — WR {wr_base}% → {wr_ts}%")
    print(f"{'='*65}")
