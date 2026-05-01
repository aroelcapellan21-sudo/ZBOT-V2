# =========================================
# optimizador_completo.py
# Optimiza parametros para las 5 monedas
# Meta: WR >= 65%, PF >= 1.8 (Blue Guardian)
# Prueba combinaciones de RSI, SL, TP, EMA
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

# Meta Blue Guardian
META_WR = 65.0
META_PF = 1.8

# Espacios de busqueda
RSI_ALCISTA  = [50, 52, 55, 57, 60]
RSI_BAJISTA  = [30, 33, 35, 38, 40]
RSI_LATERAL  = [(43,57), (45,55), (47,53)]
SL_OPCIONES  = [2.5, 3.0, 3.5, 4.0, 4.5, 5.0]
TP_OPCIONES  = [4.0, 5.0, 6.0, 7.0, 8.0, 9.0]
EMA_PARES    = [(10,30), (20,50), (20,100), (10,50)]

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

def calcular_sharpe(retornos):
    if len(retornos) < 2:
        return 0
    media = sum(retornos) / len(retornos)
    var   = sum((r - media)**2 for r in retornos) / len(retornos)
    std   = math.sqrt(var)
    if std == 0:
        return 0
    return round((media / std) * math.sqrt(252), 2)

def simular(velas, modo, rsi_param, sl, tp, ec, el, rsi_lat_min=45, rsi_lat_max=55):
    """
    Simula operaciones para un conjunto de parametros.
    modo: ALCISTA | BAJISTA | LATERAL
    """
    capital        = 1000.0
    capital_max    = 1000.0
    drawdown_max   = 0.0
    en_posicion    = False
    precio_entrada = 0.0
    unidades       = 0.0
    operaciones    = []
    vela_entrada   = 0
    retornos       = []

    for i in range(max(el, 20), len(velas)):
        ventana  = velas[max(0, i-el):i+1]
        cierres  = [v["close"] for v in ventana]

        rsi   = calcular_rsi(cierres)
        ema_c = calcular_ema(cierres, ec)
        ema_l = calcular_ema(cierres, el)

        if rsi is None or ema_c is None or ema_l is None:
            continue

        precio_actual = velas[i]["close"]

        if not en_posicion:
            señal = False
            if modo == "ALCISTA" and rsi >= rsi_param and ema_c > ema_l:
                señal = True
            elif modo == "BAJISTA" and rsi <= rsi_param and ema_c < ema_l:
                señal = True
            elif modo == "LATERAL" and rsi_lat_min <= rsi <= rsi_lat_max and abs(ema_c - ema_l) / ema_l * 100 < 2.0:
                señal = True

            if señal:
                en_posicion    = True
                precio_entrada = precio_actual * (1 + SLIPPAGE) if modo != "BAJISTA" else precio_actual * (1 - SLIPPAGE)
                vela_entrada   = i
                monto          = capital * 0.02
                unidades       = monto / precio_entrada
                capital       -= monto * COMISION

        else:
            if modo == "BAJISTA":
                cambio = ((precio_entrada - precio_actual) / precio_entrada) * 100
            else:
                cambio = ((precio_actual - precio_entrada) / precio_entrada) * 100

            # Trailing stop integrado
            if cambio > 0:
                sl_trail    = precio_actual * (1 - sl / 100) if modo != "BAJISTA" else precio_actual * (1 + sl / 100)
                sl_fijo     = precio_entrada * (1 - sl / 100) if modo != "BAJISTA" else precio_entrada * (1 + sl / 100)
                sl_efectivo = max(sl_trail, sl_fijo) if modo != "BAJISTA" else min(sl_trail, sl_fijo)
            else:
                sl_efectivo = precio_entrada * (1 - sl / 100) if modo != "BAJISTA" else precio_entrada * (1 + sl / 100)

            if cambio >= tp:
                precio_salida = precio_actual * (1 - SLIPPAGE) if modo != "BAJISTA" else precio_actual * (1 + SLIPPAGE)
                ganancia      = abs(unidades * precio_salida - unidades * precio_entrada)
                capital      += ganancia - ganancia * COMISION
                operaciones.append({"tipo": "TP", "pnl": ganancia, "velas": i - vela_entrada})
                retornos.append(ganancia)
                en_posicion   = False

            elif (modo != "BAJISTA" and precio_actual <= sl_efectivo) or \
                 (modo == "BAJISTA" and precio_actual >= sl_efectivo):
                precio_salida = precio_actual * (1 - SLIPPAGE) if modo != "BAJISTA" else precio_actual * (1 + SLIPPAGE)
                perdida       = abs(unidades * precio_salida - unidades * precio_entrada)
                capital      -= perdida + perdida * COMISION
                operaciones.append({"tipo": "SL", "pnl": -perdida, "velas": i - vela_entrada})
                retornos.append(-perdida)
                en_posicion   = False

            if capital > capital_max:
                capital_max = capital
            else:
                dd = ((capital_max - capital) / capital_max) * 100
                if dd > drawdown_max:
                    drawdown_max = dd

    if not operaciones:
        return None

    total     = len(operaciones)
    ganancias = [o for o in operaciones if o["tipo"] == "TP"]
    perdidas  = [o for o in operaciones if o["tipo"] == "SL"]
    wr        = round(len(ganancias) / total * 100, 2)
    pnl       = round(sum(o["pnl"] for o in operaciones), 2)
    sum_g     = sum(o["pnl"] for o in ganancias)
    sum_p     = abs(sum(o["pnl"] for o in perdidas))
    pf        = round(sum_g / sum_p, 2) if sum_p > 0 else 99.0
    t_medio   = round(sum(o["velas"] for o in operaciones) / total, 1)
    sharpe    = calcular_sharpe(retornos)

    return {
        "modo":         modo,
        "rsi":          rsi_param,
        "sl":           sl,
        "tp":           tp,
        "ec":           ec,
        "el":           el,
        "total":        total,
        "ganancias":    len(ganancias),
        "perdidas":     len(perdidas),
        "wr":           wr,
        "pnl":          pnl,
        "drawdown_max": round(drawdown_max, 2),
        "profit_factor": pf,
        "tiempo_medio": t_medio,
        "sharpe":       sharpe,
        "capital_final": round(capital, 2)
    }

def optimizar_symbol(symbol, velas):
    print(f"\n  Optimizando {symbol}...")
    mejores = {"ALCISTA": None, "BAJISTA": None, "LATERAL": None}
    conteo  = {"ALCISTA": 0, "BAJISTA": 0, "LATERAL": 0}

    # ALCISTA
    print(f"    [{symbol}] Modo ALCISTA...")
    for rsi in RSI_ALCISTA:
        for sl in SL_OPCIONES:
            for tp in TP_OPCIONES:
                if tp <= sl:
                    continue
                for ec, el in EMA_PARES:
                    r = simular(velas, "ALCISTA", rsi, sl, tp, ec, el)
                    if r and r["total"] >= 20:
                        conteo["ALCISTA"] += 1
                        actual = mejores["ALCISTA"]
                        if actual is None or (r["wr"] > actual["wr"] and r["profit_factor"] >= actual["profit_factor"]):
                            mejores["ALCISTA"] = r

    # BAJISTA
    print(f"    [{symbol}] Modo BAJISTA...")
    for rsi in RSI_BAJISTA:
        for sl in SL_OPCIONES:
            for tp in TP_OPCIONES:
                if tp <= sl:
                    continue
                for ec, el in EMA_PARES:
                    r = simular(velas, "BAJISTA", rsi, sl, tp, ec, el)
                    if r and r["total"] >= 20:
                        conteo["BAJISTA"] += 1
                        actual = mejores["BAJISTA"]
                        if actual is None or (r["wr"] > actual["wr"] and r["profit_factor"] >= actual["profit_factor"]):
                            mejores["BAJISTA"] = r

    # LATERAL
    print(f"    [{symbol}] Modo LATERAL...")
    for rsi_min, rsi_max in RSI_LATERAL:
        for sl in SL_OPCIONES:
            for tp in TP_OPCIONES:
                if tp <= sl:
                    continue
                for ec, el in EMA_PARES:
                    r = simular(velas, "LATERAL", 50, sl, tp, ec, el, rsi_min, rsi_max)
                    if r and r["total"] >= 20:
                        conteo["LATERAL"] += 1
                        actual = mejores["LATERAL"]
                        if actual is None or (r["wr"] > actual["wr"] and r["profit_factor"] >= actual["profit_factor"]):
                            mejores["LATERAL"] = r

    return mejores, conteo

def imprimir_resultado(symbol, mejores):
    print(f"\n{'='*60}")
    print(f"  {symbol} — PARAMETROS OPTIMOS")
    print(f"{'='*60}")

    for modo in ["ALCISTA", "BAJISTA", "LATERAL"]:
        r = mejores[modo]
        if not r:
            print(f"  {modo}: Sin resultados suficientes")
            continue

        alcanza_wr = r["wr"] >= META_WR
        alcanza_pf = r["profit_factor"] >= META_PF
        emoji      = "✅" if alcanza_wr and alcanza_pf else "⚠️" if alcanza_wr or alcanza_pf else "❌"

        print(f"\n  {emoji} {modo}:")
        print(f"     RSI    : {r['rsi']}")
        print(f"     SL     : {r['sl']}%")
        print(f"     TP     : {r['tp']}%")
        print(f"     EMA    : {r['ec']}/{r['el']}")
        print(f"     Ops    : {r['total']}")
        print(f"     WR     : {r['wr']}% {'✅' if alcanza_wr else f'(meta {META_WR}%)'}")
        print(f"     PF     : {r['profit_factor']} {'✅' if alcanza_pf else f'(meta {META_PF})'}")
        print(f"     DD Max : {r['drawdown_max']}%")
        print(f"     PNL    : ${r['pnl']}")
        print(f"     Sharpe : {r['sharpe']}")

def guardar_reporte(resultados_todos):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ruta      = os.path.join(REPORTE_DIR, f"OPTIMIZACION_{timestamp}.txt")

    with open(ruta, "w") as f:
        f.write(f"OPTIMIZACION COMPLETA — Blue Guardian\n")
        f.write(f"Meta: WR >= {META_WR}% | PF >= {META_PF}\n")
        f.write(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"{'='*60}\n\n")

        for symbol, mejores in resultados_todos.items():
            f.write(f"\n{symbol}\n{'─'*40}\n")
            for modo in ["ALCISTA", "BAJISTA", "LATERAL"]:
                r = mejores[modo]
                if not r:
                    f.write(f"  {modo}: Sin resultados\n")
                    continue
                alcanza = r["wr"] >= META_WR and r["profit_factor"] >= META_PF
                estado  = "APROBADO" if alcanza else "PENDIENTE"
                f.write(f"  {modo} [{estado}]: RSI:{r['rsi']} SL:{r['sl']}% TP:{r['tp']}% EMA:{r['ec']}/{r['el']} | WR:{r['wr']}% PF:{r['profit_factor']} DD:{r['drawdown_max']}% PNL:${r['pnl']}\n")

        f.write(f"\n{'='*60}\n")
        f.write(f"PARAMETROS RECOMENDADOS PARA FRANCOTIRADORES\n")
        f.write(f"{'='*60}\n")
        for symbol, mejores in resultados_todos.items():
            f.write(f"\n{symbol} = {{\n")
            for modo in ["ALCISTA", "BAJISTA", "LATERAL"]:
                r = mejores[modo]
                if r:
                    f.write(f"    '{modo.lower()}': {{'rsi': {r['rsi']}, 'sl': {r['sl']}, 'tp': {r['tp']}, 'ec': {r['ec']}, 'el': {r['el']}}},\n")
            f.write(f"}}\n")

    print(f"\n[OK] Reporte guardado: {ruta}")
    return ruta

if __name__ == "__main__":
    print("=" * 60)
    print("  OPTIMIZADOR COMPLETO — Blue Guardian")
    print(f"  Meta: WR >= {META_WR}% | PF >= {META_PF}")
    print(f"  Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    resultados_todos = {}

    for symbol in QUINTETO:
        velas = leer_csv(symbol)
        if not velas:
            print(f"  [SKIP] Sin datos para {symbol}")
            continue

        mejores, conteo = optimizar_symbol(symbol, velas)
        imprimir_resultado(symbol, mejores)
        resultados_todos[symbol] = mejores

        print(f"\n  Combinaciones probadas — {symbol}:")
        for modo, n in conteo.items():
            print(f"    {modo}: {n} combinaciones")

    ruta = guardar_reporte(resultados_todos)

    print(f"\n{'='*60}")
    print(f"  RESUMEN GLOBAL")
    print(f"{'='*60}")
    aprobados = 0
    total     = 0
    for symbol, mejores in resultados_todos.items():
        for modo, r in mejores.items():
            if r:
                total += 1
                if r["wr"] >= META_WR and r["profit_factor"] >= META_PF:
                    aprobados += 1
                    print(f"  ✅ {symbol} {modo}: WR {r['wr']}% PF {r['profit_factor']}")
                else:
                    print(f"  ⚠️  {symbol} {modo}: WR {r['wr']}% PF {r['profit_factor']}")

    print(f"\n  Aprobados: {aprobados}/{total} modos")
    print(f"  Reporte  : {ruta}")
    print(f"{'='*60}")
