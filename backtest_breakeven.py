# =========================================
# backtest_breakeven.py
# FIX: Bug BE inflaba WR - solo marca BE cuando sl_actual == be_price
# FIX: PNL del BE consistente con capital
# FIX: be_activo no se confunde con trailing
# Validado por Opus + consenso aprobado
# Sin librerias externas. Constitucion RESPETADA
# =========================================

import csv
import os
import math
from datetime import datetime

BASE_DIR    = os.path.expanduser("~/bot-padre-v2/data/historico_4h")
REPORTE_DIR = os.path.expanduser("~/bot-padre-v2/data/historico/backtesting")
os.makedirs(REPORTE_DIR, exist_ok=True)

COMISION  = 0.001
SLIPPAGE  = 0.0005
QUINTETO  = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "AVAXUSDT"]

# Parametros breakeven
VELAS_ESPERA    = 2
UMBRAL_BE       = 0.8
COMISION_BE     = 0.2

# Parametros de entrada por fase
PARAMS = {
    "BTCUSDT":  {"alcista": {"rsi": 55, "sl": 3.5, "tp": 6.0, "ec": 20, "el": 50},
                 "bajista": {"rsi": 35, "sl": 3.5, "tp": 6.0, "ec": 20, "el": 50}},
    "ETHUSDT":  {"alcista": {"rsi": 55, "sl": 3.5, "tp": 6.0, "ec": 20, "el": 50},
                 "bajista": {"rsi": 35, "sl": 3.5, "tp": 6.0, "ec": 20, "el": 50}},
    "SOLUSDT":  {"alcista": {"rsi": 55, "sl": 4.0, "tp": 7.0, "ec": 20, "el": 50},
                 "bajista": {"rsi": 35, "sl": 4.0, "tp": 7.0, "ec": 20, "el": 50}},
    "BNBUSDT":  {"alcista": {"rsi": 55, "sl": 4.0, "tp": 7.0, "ec": 20, "el": 50},
                 "bajista": {"rsi": 35, "sl": 4.0, "tp": 7.0, "ec": 20, "el": 50}},
    "AVAXUSDT": {"alcista": {"rsi": 55, "sl": 4.0, "tp": 7.0, "ec": 20, "el": 50},
                 "bajista": {"rsi": 35, "sl": 4.0, "tp": 7.0, "ec": 20, "el": 50}},
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

def calcular_correlacion(velas_symbol, velas_btc, ventana=20):
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

def radar_aprueba_breakeven(ventana, ventana_btc):
    cmf = calcular_cmf(ventana)
    if cmf is not None and cmf < -0.10:
        return False, f"cmf_negativo_{cmf}"
    if ventana_btc:
        corr = calcular_correlacion(ventana, ventana_btc)
        if corr is not None and corr < 0.20:
            return False, f"correlacion_suelta_{corr}"
    if len(ventana) >= 5:
        vol_actual   = ventana[-1]["volume"]
        vol_promedio = sum(v["volume"] for v in ventana[-20:]) / min(20, len(ventana))
        if vol_promedio > 0 and (vol_actual / vol_promedio) < 0.20:
            return False, "volumen_muy_bajo"
    return True, "radar_ok"

def simular(velas, velas_btc, params, fase, usar_breakeven=False, usar_radar_be=False):
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
    be_price_op    = 0.0   # precio exacto de breakeven para esta operacion
    be_activado    = False  # FIX: flag correcto por operacion
    unidades       = 0.0
    operaciones    = []
    be_activados   = 0
    be_rechazados  = 0
    vela_entrada   = 0

    for i in range(max(ema_larga, 20), len(velas)):
        ventana     = velas[max(0, i-ema_larga):i+1]
        ventana_btc = velas_btc[max(0, i-ema_larga):i+1] if velas_btc else []
        cierres     = [v["close"] for v in ventana]

        rsi   = calcular_rsi(cierres)
        ema_c = calcular_ema(cierres, ema_corta)
        ema_l = calcular_ema(cierres, ema_larga)

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

            # BREAKEVEN — solo activa si no esta ya activado
            if usar_breakeven and not be_activado:
                condicion_tiempo   = velas_en_trade >= VELAS_ESPERA
                condicion_ganancia = cambio >= UMBRAL_BE

                # FIX: solo mover SL a be_price si be_price es mejor que sl_actual
                if condicion_tiempo and condicion_ganancia:
                    be_mejor = (be_price_op > sl_actual) if fase != "BAJISTA" else (be_price_op < sl_actual)
                    if be_mejor:
                        if usar_radar_be:
                            ok_radar, _ = radar_aprueba_breakeven(ventana, ventana_btc)
                            if ok_radar:
                                sl_actual   = be_price_op
                                be_activado = True
                                be_activados += 1
                            else:
                                be_rechazados += 1
                        else:
                            sl_actual   = be_price_op
                            be_activado = True
                            be_activados += 1

            # Trailing dinamico — puede superar be_price pero be_activado no cambia
            if cambio > 0:
                sl_trail = precio_actual * (1 - stop_loss/100) if fase != "BAJISTA" else precio_actual * (1 + stop_loss/100)
                if fase != "BAJISTA":
                    sl_actual = max(sl_actual, sl_trail)
                else:
                    sl_actual = min(sl_actual, sl_trail)

            # TP
            if cambio >= take_profit:
                ganancia  = abs(unidades * precio_actual - unidades * precio_entrada)
                capital  += ganancia - ganancia * COMISION
                operaciones.append({"tipo": "TP", "pnl": ganancia, "cambio": cambio, "velas": velas_en_trade})
                en_posicion = False
                be_activado = False

            # SL / BE / TRAILING_SL
            elif (fase != "BAJISTA" and precio_actual <= sl_actual) or \
                 (fase == "BAJISTA" and precio_actual >= sl_actual):

                pnl_real = abs(unidades * sl_actual - unidades * precio_entrada)

                if fase != "BAJISTA":
                    es_ganancia = sl_actual >= precio_entrada
                else:
                    es_ganancia = sl_actual <= precio_entrada

                if es_ganancia:
                    capital += pnl_real - pnl_real * COMISION
                    # FIX: BE solo si sl_actual es exactamente be_price_op
                    # Si trailing supero be_price, es TRAILING_SL no BE
                    if be_activado and abs(sl_actual - be_price_op) < 0.0001:
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

    total       = len(operaciones)
    tps         = [o for o in operaciones if o["tipo"] == "TP"]
    bes         = [o for o in operaciones if o["tipo"] == "BE"]
    trails      = [o for o in operaciones if o["tipo"] == "TRAILING_SL"]
    sls         = [o for o in operaciones if o["tipo"] == "SL"]

    # FIX: WR = solo TP + BE (trailing no cuenta como win, es neutro/positivo pero no fue objetivo)
    wr        = round((len(tps) + len(bes)) / total * 100, 2)
    pnl       = round(sum(o["pnl"] for o in operaciones), 2)
    sum_g     = sum(o["pnl"] for o in tps + bes + trails)
    sum_p     = abs(sum(o["pnl"] for o in sls))
    pf        = round(sum_g / sum_p, 2) if sum_p > 0 else 99.0

    return {
        "total":         total,
        "tp":            len(tps),
        "be":            len(bes),
        "trailing":      len(trails),
        "sl":            len(sls),
        "wr":            wr,
        "pnl":           pnl,
        "drawdown_max":  round(drawdown_max, 2),
        "profit_factor": pf,
        "be_activados":  be_activados,
        "be_rechazados": be_rechazados,
        "capital_final": round(capital, 2)
    }

def imprimir_comparacion(symbol, resultados):
    print(f"\n{'='*65}")
    print(f"  {symbol} — SIN BE vs CON BE vs CON BE+RADAR")
    print(f"{'='*65}")
    print(f"  {'Fase':<10} {'Modo':<12} {'Ops':>4} {'WR':>6} {'PF':>5} {'DD':>6} {'PNL':>8} {'BE_act':>7}")
    print(f"  {'─'*63}")

    totales = {
        "SIN":      {"ops":0,"tp":0,"be":0,"sl":0,"pnl":0.0},
        "CON_BE":   {"ops":0,"tp":0,"be":0,"sl":0,"pnl":0.0},
        "CON_RADAR":{"ops":0,"tp":0,"be":0,"sl":0,"pnl":0.0},
    }

    for fase in ["alcista", "bajista"]:
        r_sin   = resultados["SIN"][fase]
        r_be    = resultados["CON_BE"][fase]
        r_radar = resultados["CON_RADAR"][fase]

        for modo, r in [("SIN", r_sin), ("CON_BE", r_be), ("CON_RADAR", r_radar)]:
            if not r:
                continue
            be_str = str(r.get("be_activados", 0))
            print(f"  {fase.upper():<10} {modo:<12} Ops:{r['total']:>3} WR:{r['wr']:>5}% PF:{r['profit_factor']:>4} DD:{r['drawdown_max']:>5}% PNL:${r['pnl']:>7} BE:{be_str:>4}")
            totales[modo]["ops"] += r["total"]
            totales[modo]["tp"]  += r["tp"]
            totales[modo]["be"]  += r["be"]
            totales[modo]["sl"]  += r["sl"]
            totales[modo]["pnl"] += r["pnl"]

        print(f"  {'─'*63}")

    print(f"\n  TOTALES {symbol}:")
    for modo in ["SIN", "CON_BE", "CON_RADAR"]:
        t  = totales[modo]
        wr = round((t["tp"] + t["be"]) / t["ops"] * 100, 2) if t["ops"] > 0 else 0
        print(f"  {modo:<12} | Ops:{t['ops']:>4} WR:{wr:>5}% PNL:${round(t['pnl'],2):>8} BE_salvados:{t['be']:>3}")

    wr_sin    = round((totales["SIN"]["tp"] + totales["SIN"]["be"]) / totales["SIN"]["ops"] * 100, 2) if totales["SIN"]["ops"] > 0 else 0
    wr_be     = round((totales["CON_BE"]["tp"] + totales["CON_BE"]["be"]) / totales["CON_BE"]["ops"] * 100, 2) if totales["CON_BE"]["ops"] > 0 else 0
    wr_radar  = round((totales["CON_RADAR"]["tp"] + totales["CON_RADAR"]["be"]) / totales["CON_RADAR"]["ops"] * 100, 2) if totales["CON_RADAR"]["ops"] > 0 else 0
    pnl_sin   = totales["SIN"]["pnl"]
    pnl_be    = totales["CON_BE"]["pnl"]
    pnl_radar = totales["CON_RADAR"]["pnl"]

    print(f"\n  VEREDICTO {symbol}:")
    if wr_radar >= wr_be and pnl_radar >= pnl_be * 0.95:
        print(f"  ✅ BE+RADAR es mejor — WR {wr_sin}% → {wr_radar}% | PNL ${round(pnl_sin,2)} → ${round(pnl_radar,2)}")
    elif wr_be > wr_sin and pnl_be >= pnl_sin * 0.95:
        print(f"  ✅ BE sin radar es mejor — WR {wr_sin}% → {wr_be}% | PNL ${round(pnl_sin,2)} → ${round(pnl_be,2)}")
    elif wr_be > wr_sin:
        print(f"  ⚠️ BE mejora WR pero reduce PNL — evaluar")
    else:
        print(f"  ❌ Breakeven NO mejora — mantener sistema actual")

if __name__ == "__main__":
    print("=" * 65)
    print("  BACKTESTING BREAKEVEN — SIN vs CON vs CON+RADAR (CORREGIDO)")
    print(f"  Parametros: {VELAS_ESPERA} velas ({VELAS_ESPERA*4}h), umbral +{UMBRAL_BE}%")
    print(f"  Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 65)

    velas_btc = leer_csv("BTCUSDT")
    resumen_global = {
        "SIN":       {"ops":0,"tp":0,"be":0,"sl":0,"pnl":0.0},
        "CON_BE":    {"ops":0,"tp":0,"be":0,"sl":0,"pnl":0.0},
        "CON_RADAR": {"ops":0,"tp":0,"be":0,"sl":0,"pnl":0.0},
    }

    for symbol in QUINTETO:
        print(f"\n  Procesando {symbol}...")
        velas = leer_csv(symbol)
        if not velas:
            continue

        btc_ref    = velas_btc if symbol != "BTCUSDT" else []
        resultados = {"SIN": {}, "CON_BE": {}, "CON_RADAR": {}}

        for fase in ["alcista", "bajista"]:
            params = PARAMS.get(symbol, PARAMS["BTCUSDT"])[fase]
            resultados["SIN"][fase]       = simular(velas, btc_ref, params, fase.upper(), usar_breakeven=False)
            resultados["CON_BE"][fase]    = simular(velas, btc_ref, params, fase.upper(), usar_breakeven=True,  usar_radar_be=False)
            resultados["CON_RADAR"][fase] = simular(velas, btc_ref, params, fase.upper(), usar_breakeven=True,  usar_radar_be=True)

        imprimir_comparacion(symbol, resultados)

        for modo in ["SIN", "CON_BE", "CON_RADAR"]:
            for fase in ["alcista", "bajista"]:
                r = resultados[modo][fase]
                if r:
                    resumen_global[modo]["ops"] += r["total"]
                    resumen_global[modo]["tp"]  += r["tp"]
                    resumen_global[modo]["be"]  += r["be"]
                    resumen_global[modo]["sl"]  += r["sl"]
                    resumen_global[modo]["pnl"] += r["pnl"]

    print(f"\n{'='*65}")
    print(f"  RESUMEN GLOBAL — TODOS LOS ACTIVOS")
    print(f"{'='*65}")
    for modo in ["SIN", "CON_BE", "CON_RADAR"]:
        t  = resumen_global[modo]
        wr = round((t["tp"] + t["be"]) / t["ops"] * 100, 2) if t["ops"] > 0 else 0
        print(f"  {modo:<12} | Ops:{t['ops']:>5} WR:{wr:>5}% PNL:${round(t['pnl'],2):>10} BE_salvados:{t['be']:>4}")

    wr_sin    = round((resumen_global["SIN"]["tp"] + resumen_global["SIN"]["be"]) / resumen_global["SIN"]["ops"] * 100, 2) if resumen_global["SIN"]["ops"] > 0 else 0
    wr_be     = round((resumen_global["CON_BE"]["tp"] + resumen_global["CON_BE"]["be"]) / resumen_global["CON_BE"]["ops"] * 100, 2) if resumen_global["CON_BE"]["ops"] > 0 else 0
    wr_radar  = round((resumen_global["CON_RADAR"]["tp"] + resumen_global["CON_RADAR"]["be"]) / resumen_global["CON_RADAR"]["ops"] * 100, 2) if resumen_global["CON_RADAR"]["ops"] > 0 else 0
    pnl_sin   = resumen_global["SIN"]["pnl"]
    pnl_be    = resumen_global["CON_BE"]["pnl"]
    pnl_radar = resumen_global["CON_RADAR"]["pnl"]

    print(f"\n  VEREDICTO GLOBAL:")
    if wr_radar >= wr_be and pnl_radar >= pnl_sin * 0.95:
        print(f"  ✅ APROBADO BE+RADAR — WR {wr_sin}% → {wr_radar}% | PNL ${round(pnl_sin,2)} → ${round(pnl_radar,2)}")
    elif wr_be > wr_sin and pnl_be >= pnl_sin * 0.95:
        print(f"  ✅ APROBADO BE SIN RADAR — WR {wr_sin}% → {wr_be}% | PNL ${round(pnl_sin,2)} → ${round(pnl_be,2)}")
    elif wr_be > wr_sin:
        print(f"  ⚠️ BE mejora WR pero reduce PNL — revisar parametros")
    else:
        print(f"  ❌ NO APROBADO — mantener sistema actual")
    print(f"{'='*65}")
