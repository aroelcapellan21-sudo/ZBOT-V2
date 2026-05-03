# =========================================
# backtest_filtros_vela.py
# Test C Ronda 1 — Solo filtro cuerpo decisivo
# Cuerpo/rango >= 0.3 (relajado de 0.5)
# Sin filtro distancia EMA20
# Sin filtro volumen
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

SL_PCT = 3.5
TP_PCT = 6.0

# Filtro ronda 1 — solo cuerpo decisivo relajado
BODY_RATIO_MIN = 0.3

# Parametros breakeven
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

def filtro_cuerpo(vela, ratio_min=BODY_RATIO_MIN):
    rango = vela["high"] - vela["low"]
    if rango == 0:
        return False
    body = abs(vela["close"] - vela["open"])
    return (body / rango) >= ratio_min

def simular(velas, params, fase, usar_filtro=False):
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
    rechazados     = 0

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
                if usar_filtro and not filtro_cuerpo(velas[i]):
                    rechazados += 1
                    continue

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

            if not be_activado:
                if velas_en_trade >= VELAS_ESPERA and cambio >= UMBRAL_BE:
                    be_mejor = (be_price_op > sl_actual) if fase != "BAJISTA" else (be_price_op < sl_actual)
                    if be_mejor:
                        sl_actual   = be_price_op
                        be_activado = True

            if cambio > 0:
                sl_trail  = precio_actual * (1 - stop_loss/100) if fase != "BAJISTA" else precio_actual * (1 + stop_loss/100)
                sl_actual = max(sl_actual, sl_trail) if fase != "BAJISTA" else min(sl_actual, sl_trail)

            if cambio >= take_profit:
                ganancia  = abs(unidades * precio_actual - unidades * precio_entrada)
                capital  += ganancia - ganancia * COMISION
                operaciones.append({"tipo": "TP", "pnl": ganancia, "velas": velas_en_trade})
                en_posicion = False
                be_activado = False

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

    total  = len(operaciones)
    wins   = [o for o in operaciones if o["tipo"] in ("TP", "BE")]
    sls    = [o for o in operaciones if o["tipo"] == "SL"]
    wr     = round(len(wins) / total * 100, 2)
    pnl    = round(sum(o["pnl"] for o in operaciones), 2)
    sum_g  = sum(o["pnl"] for o in [x for x in operaciones if x["pnl"] > 0])
    sum_p  = abs(sum(o["pnl"] for o in sls))
    pf     = round(sum_g / sum_p, 2) if sum_p > 0 else 99.0

    return {
        "total":        total,
        "tp":           len([o for o in operaciones if o["tipo"] == "TP"]),
        "be":           len([o for o in operaciones if o["tipo"] == "BE"]),
        "sl":           len(sls),
        "rechazados":   rechazados,
        "wr":           wr,
        "pnl":          pnl,
        "drawdown_max": round(drawdown_max, 2),
        "profit_factor": pf,
        "capital_final": round(capital, 2)
    }

if __name__ == "__main__":
    print("=" * 65)
    print("  TEST C RONDA 1 — FILTRO CUERPO DECISIVO")
    print(f"  Cuerpo/rango >= {BODY_RATIO_MIN} (relajado)")
    print(f"  Sin filtro distancia EMA20 | Sin filtro volumen")
    print(f"  Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 65)

    resumen = {
        "BASE":    {"ops":0, "wins":0, "pnl":0.0},
        "FILTRO":  {"ops":0, "wins":0, "pnl":0.0},
    }

    for symbol in QUINTETO:
        print(f"\n  Procesando {symbol}...")
        velas = leer_csv(symbol)
        if not velas:
            continue

        print(f"\n{'='*65}")
        print(f"  {symbol} — BASE vs FILTRO CUERPO")
        print(f"{'='*65}")
        print(f"  {'Fase':<10} {'Modo':<10} {'Ops':>4} {'WR':>6} {'PF':>5} {'DD':>6} {'PNL':>8} {'Rech':>5}")
        print(f"  {'─'*63}")

        for fase in ["alcista", "bajista"]:
            params   = PARAMS.get(symbol, PARAMS["BTCUSDT"])[fase]
            r_base   = simular(velas, params, fase.upper(), usar_filtro=False)
            r_filtro = simular(velas, params, fase.upper(), usar_filtro=True)

            for modo, r in [("BASE", r_base), ("FILTRO", r_filtro)]:
                if not r:
                    continue
                rech = r.get("rechazados", 0)
                print(f"  {fase.upper():<10} {modo:<10} Ops:{r['total']:>3} WR:{r['wr']:>5}% PF:{r['profit_factor']:>4} DD:{r['drawdown_max']:>5}% PNL:${r['pnl']:>7} Rech:{rech:>4}")
                wins = r.get("tp", 0) + r.get("be", 0)
                resumen[modo]["ops"]  += r["total"]
                resumen[modo]["wins"] += wins
                resumen[modo]["pnl"]  += r["pnl"]

        print(f"  {'─'*63}")

    print(f"\n{'='*65}")
    print(f"  RESUMEN GLOBAL")
    print(f"{'='*65}")
    for modo in ["BASE", "FILTRO"]:
        t  = resumen[modo]
        wr = round(t["wins"] / t["ops"] * 100, 2) if t["ops"] > 0 else 0
        print(f"  {modo:<10} | Ops:{t['ops']:>5} WR:{wr:>5}% PNL:${round(t['pnl'],2):>10}")

    wr_base   = round(resumen["BASE"]["wins"]   / resumen["BASE"]["ops"]   * 100, 2) if resumen["BASE"]["ops"]   > 0 else 0
    wr_filtro = round(resumen["FILTRO"]["wins"] / resumen["FILTRO"]["ops"] * 100, 2) if resumen["FILTRO"]["ops"] > 0 else 0
    pnl_base   = resumen["BASE"]["pnl"]
    pnl_filtro = resumen["FILTRO"]["pnl"]

    print(f"\n  VEREDICTO:")
    if wr_filtro >= 65 and pnl_filtro >= pnl_base * 0.95:
        print(f"  ✅ APROBADO — WR {wr_base}% → {wr_filtro}% | PNL ${round(pnl_base,2)} → ${round(pnl_filtro,2)}")
        print(f"  🎯 META BLUE GUARDIAN ALCANZADA")
    elif wr_filtro > wr_base and pnl_filtro >= pnl_base * 0.90:
        print(f"  ✅ MEJORA — WR {wr_base}% → {wr_filtro}% | PNL ${round(pnl_base,2)} → ${round(pnl_filtro,2)}")
        print(f"  ⚠️  Meta 65% no alcanzada — pasar a Ronda 2")
    else:
        print(f"  ❌ NO MEJORA — WR {wr_base}% → {wr_filtro}% | Pasar a Ronda 2")
    print(f"{'='*65}")
