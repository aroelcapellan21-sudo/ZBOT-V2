# =========================================
# backtest_params_vs_config.py
# Compara parametros ACTUALES (hardcoded) vs PROPUESTOS (config_cartera.py)
# 5 monedas x 3 fases = 15 francotiradores
# Reporta WR global y PNL global por escenario
# Misma logica que el bot: breakeven, trailing, comision, slippage
# Sin librerias externas. Constitucion RESPETADA
# =========================================

import csv
import os

BASE_DIR = os.path.expanduser("~/bot-padre-v2/data/historico_4h")

COMISION            = 0.001
SLIPPAGE            = 0.0005
BE_VELAS_ESPERA     = 2
BE_UMBRAL           = 0.8
BE_COMISION         = 0.2
TRAILING_ACTIVACION = 0.5
TRAILING_DISTANCIA  = 1.5
CAPITAL_INICIAL     = 1000.0
RIESGO_POR_OP       = 0.02

SIMBOLOS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "AVAXUSDT"]
FASES    = ["alcista", "bajista", "lateral"]

# ---- PARAMETROS ACTUALES (hardcodeados en los francotiradores) ----
ACTUAL = {
    "BTCUSDT": {
        "alcista": {"rsi_min": 50, "rsi_max": 70, "sl": 3.5, "tp": 6.0, "ec": 20, "el": 50},
        "bajista": {"rsi_min": 30, "rsi_max": 50, "sl": 3.5, "tp": 6.0, "ec": 20, "el": 50},
        "lateral": {"rsi_min": 45, "rsi_max": 55, "sl": 3.0, "tp": 3.0, "ec": 20, "el": 50},
    },
    "ETHUSDT": {
        "alcista": {"rsi_min": 50, "rsi_max": 70, "sl": 3.5, "tp": 6.0, "ec": 20, "el": 50},
        "bajista": {"rsi_min": 30, "rsi_max": 50, "sl": 3.5, "tp": 6.0, "ec": 20, "el": 50},
        "lateral": {"rsi_min": 45, "rsi_max": 55, "sl": 3.0, "tp": 3.0, "ec": 20, "el": 50},
    },
    "SOLUSDT": {
        "alcista": {"rsi_min": 50, "rsi_max": 70, "sl": 4.0, "tp": 7.0, "ec": 20, "el": 50},
        "bajista": {"rsi_min": 30, "rsi_max": 50, "sl": 4.0, "tp": 7.0, "ec": 20, "el": 50},
        "lateral": {"rsi_min": 45, "rsi_max": 55, "sl": 3.0, "tp": 3.0, "ec": 20, "el": 50},
    },
    "BNBUSDT": {
        "alcista": {"rsi_min": 50, "rsi_max": 70, "sl": 4.0, "tp": 7.0, "ec": 20, "el": 50},
        "bajista": {"rsi_min": 30, "rsi_max": 50, "sl": 4.0, "tp": 7.0, "ec": 20, "el": 50},
        "lateral": {"rsi_min": 45, "rsi_max": 55, "sl": 3.0, "tp": 3.0, "ec": 20, "el": 50},
    },
    "AVAXUSDT": {
        "alcista": {"rsi_min": 50, "rsi_max": 70, "sl": 4.0, "tp": 7.0, "ec": 20, "el": 50},
        "bajista": {"rsi_min": 30, "rsi_max": 50, "sl": 4.0, "tp": 7.0, "ec": 20, "el": 50},
        "lateral": {"rsi_min": 45, "rsi_max": 55, "sl": 3.0, "tp": 3.0, "ec": 20, "el": 50},
    },
}

# ---- PARAMETROS PROPUESTOS (config_cartera.py — validados con 18,678 velas) ----
PROPUESTO = {
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

# -----------------------------------------------------------------------

def leer_csv(symbol):
    ruta  = os.path.join(BASE_DIR, f"{symbol}_4h.csv")
    velas = []
    try:
        with open(ruta) as f:
            reader = csv.DictReader(f)
            for row in reader:
                velas.append({
                    "close":  float(row["close"]),
                    "high":   float(row["high"]),
                    "low":    float(row["low"]),
                })
    except Exception as e:
        print(f"  [ERROR] No se pudo leer {symbol}: {e}")
    return velas

def calcular_rsi(cierres, periodo=14):
    if len(cierres) < periodo + 1:
        return None
    avg_g = avg_p = 0.0
    for i in range(1, periodo + 1):
        d = cierres[i] - cierres[i - 1]
        if d >= 0:
            avg_g += d
        else:
            avg_p += abs(d)
    avg_g /= periodo
    avg_p /= periodo
    for i in range(periodo + 1, len(cierres)):
        d = cierres[i] - cierres[i - 1]
        g = max(d, 0)
        p = max(-d, 0)
        avg_g = (avg_g * (periodo - 1) + g) / periodo
        avg_p = (avg_p * (periodo - 1) + p) / periodo
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
    return round(ema, 6)

# -----------------------------------------------------------------------
# Simuladores por fase
# -----------------------------------------------------------------------

def simular_alcista(velas, p):
    rsi_min = p["rsi_min"]; rsi_max = p["rsi_max"]
    sl_pct  = p["sl"];      tp_pct  = p["tp"]
    ec      = p["ec"];      el      = p["el"]
    ventana = max(el, 14) + 2

    capital = CAPITAL_INICIAL
    en_pos  = False
    ops     = []
    precio_entrada = sl_actual = be_price = 0.0
    be_on = False; unidades = 0.0; vela_entrada = 0

    for i in range(ventana, len(velas)):
        c = [velas[j]["close"] for j in range(i - ventana, i + 1)]
        rsi   = calcular_rsi(c)
        ema_c = calcular_ema(c, ec)
        ema_l = calcular_ema(c, el)
        if rsi is None or ema_c is None or ema_l is None:
            continue
        precio = velas[i]["close"]

        if not en_pos:
            if rsi_min <= rsi <= rsi_max and ema_c > ema_l:
                precio_entrada = precio * (1 + SLIPPAGE)
                sl_actual      = precio_entrada * (1 - sl_pct / 100)
                be_price       = precio_entrada * (1 + BE_COMISION / 100)
                be_on          = False
                monto          = capital * RIESGO_POR_OP
                unidades       = monto / precio_entrada
                capital       -= monto * COMISION
                en_pos         = True
                vela_entrada   = i
        else:
            cambio = (precio - precio_entrada) / precio_entrada * 100
            velas_en = i - vela_entrada

            if not be_on and velas_en >= BE_VELAS_ESPERA and cambio >= BE_UMBRAL:
                if be_price > sl_actual:
                    sl_actual = be_price; be_on = True
            if cambio >= TRAILING_ACTIVACION:
                sl_trail  = precio * (1 - TRAILING_DISTANCIA / 100)
                sl_actual = max(sl_actual, sl_trail)

            if cambio >= tp_pct:
                gan = unidades * precio - unidades * precio_entrada
                capital += gan - gan * COMISION
                ops.append({"tipo": "TP", "pnl": gan})
                en_pos = be_on = False
            elif precio <= sl_actual:
                pnl_real   = abs(unidades * sl_actual - unidades * precio_entrada)
                es_ganancia = sl_actual >= precio_entrada
                if es_ganancia:
                    capital += pnl_real - pnl_real * COMISION
                    ops.append({"tipo": "TSL", "pnl": pnl_real})
                else:
                    capital -= pnl_real + pnl_real * COMISION
                    ops.append({"tipo": "SL", "pnl": -pnl_real})
                en_pos = be_on = False

    return ops, capital

def simular_bajista(velas, p):
    rsi_min = p["rsi_min"]; rsi_max = p["rsi_max"]
    sl_pct  = p["sl"];      tp_pct  = p["tp"]
    ec      = p["ec"];      el      = p["el"]
    ventana = max(el, 14) + 2

    capital = CAPITAL_INICIAL
    en_pos  = False
    ops     = []
    precio_entrada = sl_actual = be_price = 0.0
    be_on = False; unidades = 0.0; vela_entrada = 0

    for i in range(ventana, len(velas)):
        c = [velas[j]["close"] for j in range(i - ventana, i + 1)]
        rsi   = calcular_rsi(c)
        ema_c = calcular_ema(c, ec)
        ema_l = calcular_ema(c, el)
        if rsi is None or ema_c is None or ema_l is None:
            continue
        precio = velas[i]["close"]

        if not en_pos:
            if rsi_min <= rsi <= rsi_max and ema_c < ema_l:
                precio_entrada = precio * (1 - SLIPPAGE)
                sl_actual      = precio_entrada * (1 + sl_pct / 100)  # short: SL arriba
                be_price       = precio_entrada * (1 - BE_COMISION / 100)
                be_on          = False
                monto          = capital * RIESGO_POR_OP
                unidades       = monto / precio_entrada
                capital       -= monto * COMISION
                en_pos         = True
                vela_entrada   = i
        else:
            cambio = (precio_entrada - precio) / precio_entrada * 100  # positivo cuando baja
            velas_en = i - vela_entrada

            if not be_on and velas_en >= BE_VELAS_ESPERA and cambio >= BE_UMBRAL:
                if be_price < sl_actual:
                    sl_actual = be_price; be_on = True
            if cambio >= TRAILING_ACTIVACION:
                sl_trail  = precio * (1 + TRAILING_DISTANCIA / 100)
                sl_actual = min(sl_actual, sl_trail)

            if cambio >= tp_pct:
                gan = unidades * precio_entrada - unidades * precio
                capital += gan - gan * COMISION
                ops.append({"tipo": "TP", "pnl": gan})
                en_pos = be_on = False
            elif precio >= sl_actual:
                pnl_real    = abs(unidades * sl_actual - unidades * precio_entrada)
                es_ganancia = sl_actual <= precio_entrada
                if es_ganancia:
                    capital += pnl_real - pnl_real * COMISION
                    ops.append({"tipo": "TSL", "pnl": pnl_real})
                else:
                    capital -= pnl_real + pnl_real * COMISION
                    ops.append({"tipo": "SL", "pnl": -pnl_real})
                en_pos = be_on = False

    return ops, capital

def simular_lateral(velas, p):
    # Lateral = long cuando RSI en rango neutro (sin condicion EMA)
    rsi_min = p["rsi_min"]; rsi_max = p["rsi_max"]
    sl_pct  = p["sl"];      tp_pct  = p["tp"]
    ec      = p["ec"];      el      = p["el"]
    ventana = max(el, 14) + 2

    capital = CAPITAL_INICIAL
    en_pos  = False
    ops     = []
    precio_entrada = sl_actual = be_price = 0.0
    be_on = False; unidades = 0.0; vela_entrada = 0

    for i in range(ventana, len(velas)):
        c = [velas[j]["close"] for j in range(i - ventana, i + 1)]
        rsi = calcular_rsi(c)
        if rsi is None:
            continue
        precio = velas[i]["close"]

        if not en_pos:
            if rsi_min <= rsi <= rsi_max:
                precio_entrada = precio * (1 + SLIPPAGE)
                sl_actual      = precio_entrada * (1 - sl_pct / 100)
                be_price       = precio_entrada * (1 + BE_COMISION / 100)
                be_on          = False
                monto          = capital * RIESGO_POR_OP
                unidades       = monto / precio_entrada
                capital       -= monto * COMISION
                en_pos         = True
                vela_entrada   = i
        else:
            cambio   = (precio - precio_entrada) / precio_entrada * 100
            velas_en = i - vela_entrada

            if not be_on and velas_en >= BE_VELAS_ESPERA and cambio >= BE_UMBRAL:
                if be_price > sl_actual:
                    sl_actual = be_price; be_on = True
            if cambio >= TRAILING_ACTIVACION:
                sl_trail  = precio * (1 - TRAILING_DISTANCIA / 100)
                sl_actual = max(sl_actual, sl_trail)

            if cambio >= tp_pct:
                gan = unidades * precio - unidades * precio_entrada
                capital += gan - gan * COMISION
                ops.append({"tipo": "TP", "pnl": gan})
                en_pos = be_on = False
            elif precio <= sl_actual:
                pnl_real    = abs(unidades * sl_actual - unidades * precio_entrada)
                es_ganancia = sl_actual >= precio_entrada
                if es_ganancia:
                    capital += pnl_real - pnl_real * COMISION
                    ops.append({"tipo": "TSL", "pnl": pnl_real})
                else:
                    capital -= pnl_real + pnl_real * COMISION
                    ops.append({"tipo": "SL", "pnl": -pnl_real})
                en_pos = be_on = False

    return ops, capital

# -----------------------------------------------------------------------

def resumir(ops, capital):
    if not ops:
        return {"trades": 0, "wr": 0.0, "pnl": 0.0}
    ganadoras = sum(1 for o in ops if o["tipo"] in ("TP", "TSL"))
    pnl       = round(capital - CAPITAL_INICIAL, 2)
    wr        = round(ganadoras / len(ops) * 100, 1)
    return {"trades": len(ops), "wr": wr, "pnl": pnl}

SIMULADORES = {"alcista": simular_alcista, "bajista": simular_bajista, "lateral": simular_lateral}

def correr_escenario(nombre, params_dict):
    print(f"\n{'='*60}")
    print(f"  ESCENARIO: {nombre}")
    print(f"{'='*60}")

    todos_ops   = []
    pnl_total   = 0.0

    for symbol in SIMBOLOS:
        velas = leer_csv(symbol)
        if not velas:
            continue
        for fase in FASES:
            p       = params_dict[symbol][fase]
            simular = SIMULADORES[fase]
            ops, capital_final = simular(velas, p)
            r = resumir(ops, capital_final)
            pnl_total   += r["pnl"]
            todos_ops.extend(ops)
            indicador = "✅" if r["wr"] >= 55 else ("⚠️" if r["wr"] >= 45 else "❌")
            print(f"  {symbol:10s} {fase.upper():8s}  trades={r['trades']:4d}  WR={r['wr']:5.1f}%  PNL=${r['pnl']:+8.2f}  {indicador}")

    total_trades = len(todos_ops)
    if total_trades > 0:
        ganadoras_global = sum(1 for o in todos_ops if o["tipo"] in ("TP", "TSL"))
        wr_global        = round(ganadoras_global / total_trades * 100, 1)
    else:
        wr_global = 0.0

    print(f"\n  {'─'*50}")
    print(f"  TOTAL TRADES : {total_trades}")
    print(f"  WR GLOBAL    : {wr_global}%")
    print(f"  PNL GLOBAL   : ${pnl_total:+.2f}  (suma de 15 francotiradores, $1000 c/u)")
    print(f"  {'─'*50}")
    return {"wr": wr_global, "pnl": pnl_total, "trades": total_trades}

if __name__ == "__main__":
    print("\n" + "="*60)
    print("  BACKTEST: PARAMETROS ACTUALES vs CONFIG_CARTERA")
    print("  Datos: velas 4H historicas | Comision: 0.1% | Slippage: 0.05%")
    print("  Logica: RSI + EMA + Breakeven + Trailing Stop")
    print("="*60)

    r_actual    = correr_escenario("ACTUAL (hardcodeado)", ACTUAL)
    r_propuesto = correr_escenario("PROPUESTO (config_cartera.py)", PROPUESTO)

    print("\n" + "="*60)
    print("  COMPARACION FINAL")
    print("="*60)
    print(f"  {'Metrica':<20} {'ACTUAL':>12} {'PROPUESTO':>12} {'Delta':>10}")
    print(f"  {'─'*56}")
    delta_wr  = round(r_propuesto["wr"]  - r_actual["wr"],  1)
    delta_pnl = round(r_propuesto["pnl"] - r_actual["pnl"], 2)
    delta_tr  = r_propuesto["trades"] - r_actual["trades"]
    print(f"  {'WR Global':<20} {r_actual['wr']:>11.1f}% {r_propuesto['wr']:>11.1f}% {delta_wr:>+9.1f}%")
    print(f"  {'PNL Global ($)':<20} {r_actual['pnl']:>+11.2f}  {r_propuesto['pnl']:>+11.2f}  {delta_pnl:>+9.2f}")
    print(f"  {'Total Trades':<20} {r_actual['trades']:>12d} {r_propuesto['trades']:>12d} {delta_tr:>+10d}")
    print()
    if r_propuesto["wr"] > r_actual["wr"] and r_propuesto["pnl"] > r_actual["pnl"]:
        print("  VEREDICTO: ✅ PROPUESTO SUPERA AL ACTUAL en WR y PNL")
    elif r_propuesto["wr"] > r_actual["wr"]:
        print("  VEREDICTO: ⚠️  PROPUESTO tiene mejor WR pero menor PNL")
    elif r_propuesto["pnl"] > r_actual["pnl"]:
        print("  VEREDICTO: ⚠️  PROPUESTO tiene mejor PNL pero menor WR")
    else:
        print("  VEREDICTO: ❌ ACTUAL supera al PROPUESTO — NO aplicar cambios")
    print("="*60 + "\n")
