# =========================================
# backtest_radar.py
# Backtesting con y sin filtros de radares
# VERSION 2 — Umbrales recalibrados
# v2: CMF -0.25, MFI extremos, vol 0.15x
# Sin librerias externas. Constitucion RESPETADA
# =========================================

import csv
import os
import math
import random
from datetime import datetime

BASE_DIR    = os.path.expanduser("~/bot-padre-v2/data/historico_4h")
REPORTE_DIR = os.path.expanduser("~/bot-padre-v2/data/historico/backtesting")
os.makedirs(REPORTE_DIR, exist_ok=True)

COMISION  = 0.001
SLIPPAGE  = 0.0005
QUINTETO  = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "AVAXUSDT"]

PARAMS = {
    "BTCUSDT":  {"alcista": {"rsi": 55, "sl": 3.5, "tp": 6,   "ec": 20, "el": 50},
                 "bajista": {"rsi": 35, "sl": 3.5, "tp": 6,   "ec": 20, "el": 50},
                 "lateral": {"rsi": 50, "sl": 3.0, "tp": 3.0, "ec": 20, "el": 50}},
    "ETHUSDT":  {"alcista": {"rsi": 55, "sl": 3.5, "tp": 6,   "ec": 20, "el": 50},
                 "bajista": {"rsi": 35, "sl": 3.5, "tp": 6,   "ec": 20, "el": 50},
                 "lateral": {"rsi": 50, "sl": 3.0, "tp": 3.0, "ec": 20, "el": 50}},
    "SOLUSDT":  {"alcista": {"rsi": 55, "sl": 4.0, "tp": 7,   "ec": 20, "el": 50},
                 "bajista": {"rsi": 35, "sl": 4.0, "tp": 7,   "ec": 20, "el": 50},
                 "lateral": {"rsi": 50, "sl": 3.0, "tp": 3.0, "ec": 20, "el": 50}},
    "BNBUSDT":  {"alcista": {"rsi": 55, "sl": 4.0, "tp": 7,   "ec": 20, "el": 50},
                 "bajista": {"rsi": 35, "sl": 4.0, "tp": 7,   "ec": 20, "el": 50},
                 "lateral": {"rsi": 50, "sl": 3.0, "tp": 3.0, "ec": 20, "el": 50}},
    "AVAXUSDT": {"alcista": {"rsi": 55, "sl": 4.0, "tp": 7,   "ec": 20, "el": 50},
                 "bajista": {"rsi": 35, "sl": 4.0, "tp": 7,   "ec": 20, "el": 50},
                 "lateral": {"rsi": 50, "sl": 3.0, "tp": 3.0, "ec": 20, "el": 50}},
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
                    "mes":       row["timestamp"][:7],
                    "año":       row["timestamp"][:4],
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

def calcular_cmf(velas, periodo=20):
    if len(velas) < periodo:
        return None
    suma_mfv = 0.0
    suma_vol = 0.0
    for v in velas[-periodo:]:
        alto   = v["high"]
        bajo   = v["low"]
        cierre = v["close"]
        vol    = v["volume"]
        rango  = alto - bajo
        if rango == 0:
            continue
        mfv = ((cierre - bajo) - (alto - cierre)) / rango * vol
        suma_mfv += mfv
        suma_vol += vol
    if suma_vol == 0:
        return None
    return round(suma_mfv / suma_vol, 4)

def calcular_mfi(velas, periodo=14):
    if len(velas) < periodo + 1:
        return None
    pts    = [((v["high"] + v["low"] + v["close"]) / 3, v["volume"]) for v in velas]
    mf_pos = 0.0
    mf_neg = 0.0
    for i in range(len(pts) - periodo, len(pts)):
        pt_act = pts[i][0]
        pt_ant = pts[i-1][0]
        vol    = pts[i][1]
        if pt_act > pt_ant:
            mf_pos += pt_act * vol
        elif pt_act < pt_ant:
            mf_neg += pt_act * vol
    if mf_neg == 0:
        return 100.0
    if mf_pos == 0:
        return 0.0
    return round(100 - (100 / (1 + mf_pos/mf_neg)), 2)

def calcular_correlacion_btc(velas_symbol, velas_btc, ventana=20):
    if len(velas_symbol) < ventana or len(velas_btc) < ventana:
        return None
    ret_s = [((velas_symbol[i]["close"] - velas_symbol[i-1]["close"]) / velas_symbol[i-1]["close"]) * 100
             for i in range(1, ventana)]
    ret_b = [((velas_btc[i]["close"] - velas_btc[i-1]["close"]) / velas_btc[i-1]["close"]) * 100
             for i in range(1, ventana)]
    n     = min(len(ret_s), len(ret_b))
    med_s = sum(ret_s[:n]) / n
    med_b = sum(ret_b[:n]) / n
    num   = sum((ret_s[i] - med_s) * (ret_b[i] - med_b) for i in range(n))
    den_s = math.sqrt(sum((x - med_s)**2 for x in ret_s[:n]))
    den_b = math.sqrt(sum((x - med_b)**2 for x in ret_b[:n]))
    if den_s == 0 or den_b == 0:
        return None
    return round(num / (den_s * den_b), 4)

def filtro_radares(velas_ventana, velas_btc_ventana, fase):
    """
    VERSION 2 — Umbrales recalibrados post-backtesting inicial.
    CMF: -0.25 (antes -0.15)
    MFI: solo extremos 90/10 (antes 85/15)
    Correlacion: solo bloquea alcista con corr < -0.50
    Volumen: 0.15x (antes 0.30x)
    """
    # 1. CMF — distribucion muy fuerte
    cmf = calcular_cmf(velas_ventana)
    if cmf is not None and cmf < -0.25:
        return False, f"cmf_distribucion_{cmf}"

    # 2. MFI — solo extremos reales
    mfi = calcular_mfi(velas_ventana)
    if mfi is not None:
        if fase == "ALCISTA" and mfi >= 90:
            return False, f"mfi_sobrecompra_extrema_{mfi}"
        if fase == "BAJISTA" and mfi <= 10:
            return False, f"mfi_sobreventa_extrema_{mfi}"

    # 3. Correlacion — solo bloquea alcista con correlacion negativa fuerte
    if fase == "ALCISTA" and velas_btc_ventana:
        corr = calcular_correlacion_btc(velas_ventana, velas_btc_ventana)
        if corr is not None and corr < -0.50:
            return False, f"correlacion_negativa_fuerte_{corr}"

    # 4. Volumen — solo volumen extremadamente bajo
    if len(velas_ventana) >= 5:
        vol_actual   = velas_ventana[-1]["volume"]
        vol_promedio = sum(v["volume"] for v in velas_ventana[-20:]) / min(20, len(velas_ventana))
        if vol_promedio > 0 and (vol_actual / vol_promedio) < 0.15:
            return False, f"volumen_muy_bajo_{round(vol_actual/vol_promedio,2)}x"

    return True, "radares_ok"

def simular(velas, velas_btc, params, fase, usar_radares=False):
    rsi_entrada = params["rsi"]
    stop_loss   = params["sl"]
    take_profit = params["tp"]
    ema_corta   = params["ec"]
    ema_larga   = params["el"]

    capital         = 1000.0
    capital_inicial = 1000.0
    capital_maximo  = 1000.0
    drawdown_max    = 0.0
    en_posicion     = False
    precio_entrada  = 0.0
    unidades        = 0.0
    operaciones     = []
    rechazos_radar  = 0
    vela_entrada    = 0

    for i in range(max(ema_larga, 20), len(velas)):
        ventana     = velas[max(0, i-ema_larga):i+1]
        ventana_btc = velas_btc[max(0, i-ema_larga):i+1] if velas_btc else []
        cierres_v   = [v["close"] for v in ventana]

        rsi   = calcular_rsi(cierres_v)
        ema_c = calcular_ema(cierres_v, ema_corta)
        ema_l = calcular_ema(cierres_v, ema_larga)

        if rsi is None or ema_c is None or ema_l is None:
            continue

        precio_actual = velas[i]["close"]

        if not en_posicion:
            señal = False
            if fase == "ALCISTA" and rsi >= rsi_entrada and ema_c > ema_l:
                señal = True
            elif fase == "BAJISTA" and rsi <= rsi_entrada and ema_c < ema_l:
                señal = True
            elif fase == "LATERAL" and 45 <= rsi <= 55:
                señal = True

            if señal:
                if usar_radares:
                    ok, motivo = filtro_radares(ventana, ventana_btc, fase)
                    if not ok:
                        rechazos_radar += 1
                        continue

                en_posicion    = True
                precio_entrada = precio_actual * (1 + SLIPPAGE) if fase != "BAJISTA" else precio_actual * (1 - SLIPPAGE)
                vela_entrada   = i
                monto          = capital * 0.02
                unidades       = monto / precio_entrada
                capital       -= monto * COMISION

        else:
            if fase == "BAJISTA":
                cambio = ((precio_entrada - precio_actual) / precio_entrada) * 100
            else:
                cambio = ((precio_actual - precio_entrada) / precio_entrada) * 100

            if cambio >= take_profit:
                precio_salida = precio_actual * (1 - SLIPPAGE) if fase != "BAJISTA" else precio_actual * (1 + SLIPPAGE)
                ganancia      = abs(unidades * precio_salida - unidades * precio_entrada)
                capital      += ganancia - ganancia * COMISION
                operaciones.append({"tipo": "TP", "cambio": cambio, "pnl": ganancia, "velas": i - vela_entrada})
                en_posicion   = False

            elif cambio <= -stop_loss:
                precio_salida = precio_actual * (1 - SLIPPAGE) if fase != "BAJISTA" else precio_actual * (1 + SLIPPAGE)
                perdida       = abs(unidades * precio_salida - unidades * precio_entrada)
                capital      -= perdida + perdida * COMISION
                operaciones.append({"tipo": "SL", "cambio": cambio, "pnl": -perdida, "velas": i - vela_entrada})
                en_posicion   = False

            if capital > capital_maximo:
                capital_maximo = capital
            else:
                dd = ((capital_maximo - capital) / capital_maximo) * 100
                if dd > drawdown_max:
                    drawdown_max = dd

    if not operaciones:
        return None

    total     = len(operaciones)
    ganancias = [o for o in operaciones if o["tipo"] == "TP"]
    perdidas  = [o for o in operaciones if o["tipo"] == "SL"]
    wr        = round(len(ganancias) / total * 100, 2)
    pnl_total = round(sum(o["pnl"] for o in operaciones), 2)
    sum_g     = sum(o["pnl"] for o in ganancias)
    sum_p     = abs(sum(o["pnl"] for o in perdidas))
    pf        = round(sum_g / sum_p, 2) if sum_p > 0 else 99.0
    t_medio   = round(sum(o["velas"] for o in operaciones) / total, 1)

    return {
        "total":          total,
        "ganancias":      len(ganancias),
        "perdidas":       len(perdidas),
        "wr":             wr,
        "pnl":            pnl_total,
        "drawdown_max":   round(drawdown_max, 2),
        "profit_factor":  pf,
        "tiempo_medio":   t_medio,
        "rechazos_radar": rechazos_radar,
        "capital_final":  round(capital, 2)
    }

def comparar(symbol, velas, velas_btc):
    params_symbol = PARAMS.get(symbol, PARAMS["BTCUSDT"])
    resultados    = {"SIN_RADAR": {}, "CON_RADAR": {}}
    for fase in ["alcista", "bajista", "lateral"]:
        params = params_symbol[fase]
        resultados["SIN_RADAR"][fase] = simular(velas, velas_btc, params, fase.upper(), usar_radares=False)
        resultados["CON_RADAR"][fase] = simular(velas, velas_btc, params, fase.upper(), usar_radares=True)
    return resultados

def imprimir_comparacion(symbol, resultados):
    print(f"\n{'='*60}")
    print(f"  {symbol} — SIN vs CON RADARES v2")
    print(f"{'='*60}")
    print(f"  {'Fase':<10} {'':>3} {'Ops':>4} {'WR':>6} {'PF':>5} {'DD':>6} {'PNL':>8} {'Rechazos':>9}")
    print(f"  {'─'*58}")

    totales = {"SIN": {"ops":0,"g":0,"pnl":0.0}, "CON": {"ops":0,"g":0,"pnl":0.0}}

    for fase in ["alcista", "bajista", "lateral"]:
        r_sin = resultados["SIN_RADAR"][fase]
        r_con = resultados["CON_RADAR"][fase]

        if r_sin:
            print(f"  {fase.upper():<10} SIN | Ops:{r_sin['total']:>3} WR:{r_sin['wr']:>5}% PF:{r_sin['profit_factor']:>4} DD:{r_sin['drawdown_max']:>5}% PNL:${r_sin['pnl']:>7}")
            totales["SIN"]["ops"] += r_sin["total"]
            totales["SIN"]["g"]   += r_sin["ganancias"]
            totales["SIN"]["pnl"] += r_sin["pnl"]

        if r_con:
            mejora_wr = round(r_con["wr"] - (r_sin["wr"] if r_sin else 0), 2)
            mejora_pf = round(r_con["profit_factor"] - (r_sin["profit_factor"] if r_sin else 0), 2)
            emoji_wr  = "✅" if mejora_wr >= 0 else "❌"
            emoji_pf  = "✅" if mejora_pf >= 0 else "❌"
            print(f"  {fase.upper():<10} CON | Ops:{r_con['total']:>3} WR:{r_con['wr']:>5}% PF:{r_con['profit_factor']:>4} DD:{r_con['drawdown_max']:>5}% PNL:${r_con['pnl']:>7} Rechazos:{r_con['rechazos_radar']:>4} | WR{emoji_wr}{mejora_wr:+.1f}% PF{emoji_pf}{mejora_pf:+.2f}")
            totales["CON"]["ops"] += r_con["total"]
            totales["CON"]["g"]   += r_con["ganancias"]
            totales["CON"]["pnl"] += r_con["pnl"]

        print(f"  {'─'*58}")

    for modo in ["SIN", "CON"]:
        t  = totales[modo]
        wr = round(t["g"] / t["ops"] * 100, 2) if t["ops"] > 0 else 0
        print(f"  TOTAL {modo:>3} | Ops:{t['ops']:>4} WR:{wr:>5}% PNL:${round(t['pnl'],2):>8}")

    wr_sin  = round(totales["SIN"]["g"] / totales["SIN"]["ops"] * 100, 2) if totales["SIN"]["ops"] > 0 else 0
    wr_con  = round(totales["CON"]["g"] / totales["CON"]["ops"] * 100, 2) if totales["CON"]["ops"] > 0 else 0
    pnl_sin = totales["SIN"]["pnl"]
    pnl_con = totales["CON"]["pnl"]

    print(f"\n  VEREDICTO {symbol}:")
    if wr_con >= wr_sin and pnl_con >= pnl_sin * 0.90:
        print(f"  ✅ RADARES MEJORAN ({wr_sin}% → {wr_con}% WR | ${round(pnl_sin,2)} → ${round(pnl_con,2)} PNL)")
    elif wr_con >= wr_sin:
        print(f"  ⚠️ RADARES mejoran WR pero reducen PNL (menos trades)")
    else:
        print(f"  ❌ RADARES NO MEJORAN — revisar umbrales")

if __name__ == "__main__":
    print("=" * 60)
    print("  BACKTESTING RADARES v2 — UMBRALES RECALIBRADOS")
    print(f"  Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    velas_btc = leer_csv("BTCUSDT")
    resumen_global = {"SIN": {"ops":0,"g":0,"pnl":0.0}, "CON": {"ops":0,"g":0,"pnl":0.0}}

    for symbol in QUINTETO:
        print(f"\n  Procesando {symbol}...")
        velas = leer_csv(symbol)
        if not velas:
            print(f"  [SKIP] Sin datos para {symbol}")
            continue

        btc_ref    = velas_btc if symbol != "BTCUSDT" else []
        resultados = comparar(symbol, velas, btc_ref)
        imprimir_comparacion(symbol, resultados)

        for fase in ["alcista", "bajista", "lateral"]:
            r_sin = resultados["SIN_RADAR"][fase]
            r_con = resultados["CON_RADAR"][fase]
            if r_sin:
                resumen_global["SIN"]["ops"] += r_sin["total"]
                resumen_global["SIN"]["g"]   += r_sin["ganancias"]
                resumen_global["SIN"]["pnl"] += r_sin["pnl"]
            if r_con:
                resumen_global["CON"]["ops"] += r_con["total"]
                resumen_global["CON"]["g"]   += r_con["ganancias"]
                resumen_global["CON"]["pnl"] += r_con["pnl"]

    print(f"\n{'='*60}")
    print(f"  RESUMEN GLOBAL — TODOS LOS ACTIVOS")
    print(f"{'='*60}")
    for modo in ["SIN", "CON"]:
        t  = resumen_global[modo]
        wr = round(t["g"] / t["ops"] * 100, 2) if t["ops"] > 0 else 0
        print(f"  {modo} RADARES | Ops:{t['ops']:>5} | WR:{wr:>5}% | PNL Total:${round(t['pnl'],2):>10}")

    wr_sin  = round(resumen_global["SIN"]["g"] / resumen_global["SIN"]["ops"] * 100, 2) if resumen_global["SIN"]["ops"] > 0 else 0
    wr_con  = round(resumen_global["CON"]["g"] / resumen_global["CON"]["ops"] * 100, 2) if resumen_global["CON"]["ops"] > 0 else 0
    pnl_sin = resumen_global["SIN"]["pnl"]
    pnl_con = resumen_global["CON"]["pnl"]

    print(f"\n  VEREDICTO GLOBAL:")
    if wr_con >= 65 and pnl_con >= pnl_sin * 0.90:
        print(f"  ✅ RADARES APROBADOS — Integrar a francotiradores")
        print(f"     WR: {wr_sin}% → {wr_con}% | PNL: ${round(pnl_sin,2)} → ${round(pnl_con,2)}")
    elif wr_con >= wr_sin:
        print(f"  ⚠️ RADARES MEJORAN WR — revisar si sacrificio de trades vale")
        print(f"     WR: {wr_sin}% → {wr_con}% | Ops: {resumen_global['SIN']['ops']} → {resumen_global['CON']['ops']}")
    else:
        print(f"  ❌ RADARES NO APROBADOS — Ajustar umbrales")
        print(f"     WR: {wr_sin}% → {wr_con}%")

    print(f"{'='*60}")
