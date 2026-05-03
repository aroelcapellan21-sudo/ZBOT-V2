# =========================================
# backtest_bugs_fix.py
# Compara sistema ANTES vs DESPUES de bugs #1, #2, #3
# Bug #1: revisar_cierres mezclaba todos los tipos (sin filtro TIPO_TRADE)
# Bug #2: PNL usaba capital_actual*2%*pct en vez de precio real
# Bug #3: contar_ops_abiertas mezclaba todos los tipos del mismo symbol
# Sin librerias externas. Constitucion RESPETADA
# =========================================

import csv
import os
from datetime import datetime

BASE_DIR = os.path.expanduser("~/bot-padre-v2/data/historico_4h")

QUINTETO = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "AVAXUSDT"]

TIPOS = {
    "ALCISTA": {"rsi_min": 55, "rsi_max": 80, "sl": 3.5, "tp": 6.0, "ec": 20, "el": 50, "max_ops": 2},
    "BAJISTA": {"rsi_min": 20, "rsi_max": 45, "sl": 3.5, "tp": 6.0, "ec": 20, "el": 50, "max_ops": 3},
    "LATERAL": {"rsi_min": 45, "rsi_max": 55, "sl": 3.0, "tp": 3.0, "ec": 20, "el": 50, "max_ops": 2},
}

CAPITAL_INICIAL   = 1000.0
CAPITAL_POR_OP    = 0.02
COMISION_TASA     = 0.001
BE_VELAS_ESPERA   = 2
BE_UMBRAL         = 0.8
BE_COMISION_PCT   = 0.2

# ─── Utilidades ──────────────────────────────────────────────────────────────

def leer_csv(symbol):
    ruta = os.path.join(BASE_DIR, f"{symbol}_4h.csv")
    velas = []
    try:
        with open(ruta, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                velas.append({
                    "ts":     row["timestamp"],
                    "close":  float(row["close"]),
                    "high":   float(row["high"]),
                    "low":    float(row["low"]),
                    "volume": float(row["volume"]),
                })
    except Exception as e:
        print(f"[ERROR] {symbol}: {e}")
    return velas

def calcular_rsi(cierres, periodo=14):
    if len(cierres) < periodo + 1:
        return None
    gs = [max(cierres[i] - cierres[i-1], 0) for i in range(1, len(cierres))]
    ps = [max(cierres[i-1] - cierres[i], 0) for i in range(1, len(cierres))]
    ag = sum(gs[:periodo]) / periodo
    ap = sum(ps[:periodo]) / periodo
    for i in range(periodo, len(gs)):
        ag = (ag * (periodo - 1) + gs[i]) / periodo
        ap = (ap * (periodo - 1) + ps[i]) / periodo
    return round(100 - (100 / (1 + ag / ap)), 2) if ap > 0 else 100.0

def calcular_ema(cierres, periodo):
    if len(cierres) < periodo:
        return None
    k   = 2 / (periodo + 1)
    ema = sum(cierres[:periodo]) / periodo
    for p in cierres[periodo:]:
        ema = p * k + ema * (1 - k)
    return round(ema, 6)

def detectar_fase_vela(cierres, tipo):
    rsi  = calcular_rsi(cierres)
    ec   = calcular_ema(cierres, TIPOS[tipo]["ec"])
    el   = calcular_ema(cierres, TIPOS[tipo]["el"])
    if rsi is None or ec is None or el is None:
        return False, rsi
    p = TIPOS[tipo]
    precio = cierres[-1]
    if tipo == "ALCISTA":
        return (p["rsi_min"] <= rsi <= p["rsi_max"] and precio > ec > el), rsi
    if tipo == "BAJISTA":
        return (p["rsi_min"] <= rsi <= p["rsi_max"] and precio < ec < el), rsi
    if tipo == "LATERAL":
        diff = abs(ec - el) / el * 100
        return (p["rsi_min"] <= rsi <= p["rsi_max"] and diff <= 3.0), rsi
    return False, rsi

# ─── Motor de simulacion ─────────────────────────────────────────────────────

def pnl_buggy_tp(capital_actual, tp_pct):
    """Bug #2: usa capital actual * 2% * tp_pct en vez de precio real."""
    monto = capital_actual * CAPITAL_POR_OP
    return round(monto * (tp_pct / 100), 4)

def pnl_buggy_sl(capital_actual, sl_pct):
    monto = capital_actual * CAPITAL_POR_OP
    return round(monto * (sl_pct / 100), 4)

def pnl_real_cierre(monto_inv, precio_entrada, precio_salida, tipo):
    cantidad = monto_inv / precio_entrada
    if tipo == "BAJISTA":
        return round(monto_inv - cantidad * precio_salida, 4)
    return round(cantidad * precio_salida - monto_inv, 4)

class Posicion:
    def __init__(self, tipo, precio_entrada, monto, vela_idx):
        self.tipo          = tipo
        self.precio_entrada = precio_entrada
        self.monto         = monto
        self.vela_idx      = vela_idx
        self.sl_actual     = 0.0
        self.be_activado   = False

def simular(velas, modo):
    """
    modo: "BUGGY" o "FIXED"
    Retorna dict con metricas globales de las 3 estrategias.
    """
    capital    = CAPITAL_INICIAL
    posiciones = []   # lista de Posicion activas
    ops        = []   # lista de resultados cerrados

    EL_MAX = max(p["el"] for p in TIPOS.values())

    for i in range(EL_MAX, len(velas)):
        ventana  = velas[max(0, i - EL_MAX): i + 1]
        cierres  = [v["close"] for v in ventana]
        precio   = velas[i]["close"]

        # ── 1. REVISAR CIERRES ────────────────────────────────────────────
        cerradas = []
        for pos in posiciones:
            p      = TIPOS[pos.tipo]
            sl_pct = p["sl"]
            tp_pct = p["tp"]

            # BUG #1: en modo BUGGY, revisar_cierres no filtra por tipo.
            # Simula el efecto de que una estrategia puede cerrar posiciones
            # de otro tipo usando sus propios parametros TP/SL.
            # En la practica: el primer tipo en iterar cierra las posiciones
            # del segundo con parametros incorrectos.
            # Aqui lo modelamos: en BUGGY el TP/SL que se aplica es el del
            # primer tipo que encuentre la posicion (ALCISTA = mas exigente).
            if modo == "BUGGY":
                tipo_gestor = "ALCISTA"   # LATERAL era el que contaminaba
                p_gestor    = TIPOS[tipo_gestor]
                tp_pct      = p_gestor["tp"]
                sl_pct      = p_gestor["sl"]

            velas_en_trade = i - pos.vela_idx

            if pos.tipo == "BAJISTA":
                cambio = ((pos.precio_entrada - precio) / pos.precio_entrada) * 100
            else:
                cambio = ((precio - pos.precio_entrada) / pos.precio_entrada) * 100

            # Inicializar SL si es la primera vela
            if pos.sl_actual == 0.0:
                if pos.tipo == "BAJISTA":
                    pos.sl_actual = pos.precio_entrada * (1 + sl_pct / 100)
                else:
                    pos.sl_actual = pos.precio_entrada * (1 - sl_pct / 100)

            # Breakeven
            if not pos.be_activado and velas_en_trade >= BE_VELAS_ESPERA and cambio >= BE_UMBRAL:
                if pos.tipo == "BAJISTA":
                    be_price = pos.precio_entrada * (1 - BE_COMISION_PCT / 100)
                    if pos.sl_actual > be_price:
                        pos.sl_actual  = be_price
                        pos.be_activado = True
                else:
                    be_price = pos.precio_entrada * (1 + BE_COMISION_PCT / 100)
                    if pos.sl_actual < be_price:
                        pos.sl_actual  = be_price
                        pos.be_activado = True

            # Trailing
            if cambio > 0:
                if pos.tipo == "BAJISTA":
                    trail = precio * (1 + sl_pct / 100)
                    pos.sl_actual = min(pos.sl_actual, trail)
                else:
                    trail = precio * (1 - sl_pct / 100)
                    pos.sl_actual = max(pos.sl_actual, trail)

            resultado = None

            if cambio >= tp_pct:
                if modo == "BUGGY":
                    ganancia = pnl_buggy_tp(capital, tp_pct)
                else:
                    ganancia = pnl_real_cierre(pos.monto, pos.precio_entrada, precio, pos.tipo)
                capital += ganancia * (1 - COMISION_TASA)
                resultado = {"tipo_trade": pos.tipo, "cierre": "TP", "pnl": ganancia, "cambio": cambio}

            elif (pos.tipo != "BAJISTA" and precio <= pos.sl_actual) or \
                 (pos.tipo == "BAJISTA" and precio >= pos.sl_actual):
                if pos.tipo == "BAJISTA":
                    es_ganancia = pos.sl_actual <= pos.precio_entrada
                else:
                    es_ganancia = pos.sl_actual >= pos.precio_entrada

                if modo == "BUGGY":
                    pnl_sl = pnl_buggy_sl(capital, sl_pct)
                    if es_ganancia:
                        capital += pnl_sl * (1 - COMISION_TASA)
                    else:
                        capital -= pnl_sl * (1 + COMISION_TASA)
                    pnl_val = pnl_sl if es_ganancia else -pnl_sl
                else:
                    pnl_val = pnl_real_cierre(pos.monto, pos.precio_entrada, pos.sl_actual, pos.tipo)
                    if es_ganancia:
                        capital += pnl_val * (1 - COMISION_TASA)
                    else:
                        capital -= abs(pnl_val) * (1 + COMISION_TASA)
                        pnl_val = -abs(pnl_val)

                tipo_cierre = "BE" if pos.be_activado and es_ganancia else ("TRAILING_SL" if es_ganancia else "SL")
                resultado = {"tipo_trade": pos.tipo, "cierre": tipo_cierre, "pnl": pnl_val, "cambio": cambio}

            if resultado:
                ops.append(resultado)
                cerradas.append(pos)

        posiciones = [p for p in posiciones if p not in cerradas]

        # ── 2. EVALUAR NUEVAS ENTRADAS ────────────────────────────────────
        for tipo in ["ALCISTA", "BAJISTA", "LATERAL"]:
            p = TIPOS[tipo]

            # BUG #3: en modo BUGGY, el contador no filtra por tipo.
            # Cuenta TODAS las posiciones abiertas del mismo symbol.
            if modo == "BUGGY":
                ops_abiertas = len(posiciones)
                max_permitido = min(p["max_ops"] for p in TIPOS.values())
            else:
                ops_abiertas  = sum(1 for pos in posiciones if pos.tipo == tipo)
                max_permitido = p["max_ops"]

            if ops_abiertas >= max_permitido:
                continue

            monto = capital * CAPITAL_POR_OP
            if monto < 5.0:
                continue

            señal, rsi = detectar_fase_vela(cierres, tipo)
            if not señal:
                continue

            nueva = Posicion(tipo, precio, monto, i)
            posiciones.append(nueva)
            capital -= monto * COMISION_TASA

    return ops

# ─── Metricas ─────────────────────────────────────────────────────────────────

def calcular_metricas(ops, nombre):
    if not ops:
        return None
    total    = len(ops)
    tps      = [o for o in ops if o["cierre"] == "TP"]
    bes      = [o for o in ops if o["cierre"] == "BE"]
    trails   = [o for o in ops if o["cierre"] == "TRAILING_SL"]
    sls      = [o for o in ops if o["cierre"] == "SL"]

    wins     = len(tps) + len(bes) + len(trails)
    wr       = round(wins / total * 100, 2)
    pnl      = round(sum(o["pnl"] for o in ops), 2)
    sum_g    = sum(o["pnl"] for o in ops if o["pnl"] > 0)
    sum_p    = abs(sum(o["pnl"] for o in ops if o["pnl"] < 0))
    pf       = round(sum_g / sum_p, 2) if sum_p > 0 else 99.0

    por_tipo = {}
    for tipo in ["ALCISTA", "BAJISTA", "LATERAL"]:
        t_ops  = [o for o in ops if o["tipo_trade"] == tipo]
        if t_ops:
            t_wins = sum(1 for o in t_ops if o["pnl"] > 0)
            por_tipo[tipo] = {
                "ops": len(t_ops),
                "wr":  round(t_wins / len(t_ops) * 100, 1),
                "pnl": round(sum(o["pnl"] for o in t_ops), 2),
            }

    return {
        "nombre":  nombre,
        "total":   total,
        "tp":      len(tps),
        "be":      len(bes),
        "trail":   len(trails),
        "sl":      len(sls),
        "wr":      wr,
        "pnl":     pnl,
        "pf":      pf,
        "por_tipo": por_tipo,
    }

def imprimir_resultado(m):
    print(f"\n  {'─'*60}")
    print(f"  Modo: {m['nombre']}")
    print(f"  {'─'*60}")
    print(f"  Ops totales : {m['total']}  (TP:{m['tp']} BE:{m['be']} Trail:{m['trail']} SL:{m['sl']})")
    print(f"  Win Rate    : {m['wr']}%")
    print(f"  PNL total   : ${m['pnl']}")
    print(f"  Profit Factor: {m['pf']}")
    print(f"\n  Por tipo de trade:")
    for tipo, t in m["por_tipo"].items():
        print(f"    {tipo:<8}  Ops:{t['ops']:>4}  WR:{t['wr']:>5}%  PNL:${t['pnl']:>8.2f}")

def imprimir_delta(antes, despues):
    print(f"\n  {'═'*60}")
    print(f"  IMPACTO DE LOS 3 BUGS (ANTES → DESPUÉS)")
    print(f"  {'═'*60}")

    d_ops = despues["total"] - antes["total"]
    d_wr  = round(despues["wr"] - antes["wr"], 2)
    d_pnl = round(despues["pnl"] - antes["pnl"], 2)
    d_pf  = round(despues["pf"] - antes["pf"], 2)

    def signo(v): return f"+{v}" if v >= 0 else str(v)

    print(f"  Ops totales  : {antes['total']} → {despues['total']}  ({signo(d_ops)})")
    print(f"  Win Rate     : {antes['wr']}% → {despues['wr']}%  ({signo(d_wr)}pp)")
    print(f"  PNL          : ${antes['pnl']} → ${despues['pnl']}  ({signo(d_pnl)})")
    print(f"  Profit Factor: {antes['pf']} → {despues['pf']}  ({signo(d_pf)})")

    print(f"\n  Por tipo de trade:")
    for tipo in ["ALCISTA", "BAJISTA", "LATERAL"]:
        a = antes["por_tipo"].get(tipo)
        d = despues["por_tipo"].get(tipo)
        if a and d:
            dwr  = round(d["wr"] - a["wr"], 1)
            dpnl = round(d["pnl"] - a["pnl"], 2)
            print(f"    {tipo:<8}  WR: {a['wr']}% → {d['wr']}% ({signo(dwr)}pp)  "
                  f"PNL: ${a['pnl']:.2f} → ${d['pnl']:.2f} ({signo(dpnl)})")

    print(f"\n  VEREDICTO:")
    if d_pnl > 0 and d_wr > 0:
        print(f"  ✅ Los bugs reducian WR y PNL. El fix mejora ambos.")
    elif d_pnl > 0:
        print(f"  ✅ PNL real mejorado. WR neutro (ruido estadístico).")
    elif d_pnl < -50 and d_ops > 0:
        print(f"  ⚠️  Los bugs inflaban el PNL artificialmente (+${abs(d_pnl):.0f}).")
        print(f"  El fix expone la performance real: más ops (+{d_ops}) pero con métricas honestas.")
        print(f"  Bug #1 aplicaba TP/SL incorrectos — especialmente LATERAL usaba TP de ALCISTA.")
        print(f"  Bug #3 bloqueaba entradas válidas — ahora cada tipo tiene su propio contador.")
    elif d_wr > 0:
        print(f"  ⚠️  WR mejorado pero PNL similar. Bugs eran contables, no financieros.")
    else:
        print(f"  ℹ️  Impacto acotado. Bugs eran principalmente defensivos (integridad de datos).")

# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 62)
    print("  BACKTEST BUGS FIX — ANTES vs DESPUES")
    print("  Bug #1: revisar_cierres filtra por TIPO_TRADE")
    print("  Bug #2: PNL calculado con precio real (no porcentaje fijo)")
    print("  Bug #3: contar_ops_abiertas filtra por TIPO_TRADE")
    print(f"  Capital inicial: ${CAPITAL_INICIAL} | Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 62)

    acum_buggy = []
    acum_fixed = []

    for symbol in QUINTETO:
        print(f"\n[{symbol}] Cargando datos...")
        velas = leer_csv(symbol)
        if len(velas) < 200:
            print(f"  ⚠️  Datos insuficientes para {symbol}, saltando.")
            continue

        print(f"  Velas disponibles: {len(velas)}")
        print(f"  Simulando modo BUGGY...")
        ops_buggy = simular(velas, "BUGGY")
        print(f"  Simulando modo FIXED...")
        ops_fixed = simular(velas, "FIXED")

        m_buggy = calcular_metricas(ops_buggy, f"ANTES — {symbol}")
        m_fixed = calcular_metricas(ops_fixed, f"DESPUÉS — {symbol}")

        if not m_buggy or not m_fixed:
            print(f"  ⚠️  Sin operaciones suficientes para {symbol}.")
            continue

        print(f"\n{'='*62}")
        print(f"  {symbol}")
        print(f"{'='*62}")
        imprimir_resultado(m_buggy)
        imprimir_resultado(m_fixed)
        imprimir_delta(m_buggy, m_fixed)

        acum_buggy.extend(ops_buggy)
        acum_fixed.extend(ops_fixed)

    if acum_buggy and acum_fixed:
        print(f"\n\n{'#'*62}")
        print(f"  RESUMEN GLOBAL — TODOS LOS ACTIVOS COMBINADOS")
        print(f"{'#'*62}")
        m_global_buggy = calcular_metricas(acum_buggy, "GLOBAL ANTES")
        m_global_fixed = calcular_metricas(acum_fixed, "GLOBAL DESPUÉS")
        imprimir_resultado(m_global_buggy)
        imprimir_resultado(m_global_fixed)
        imprimir_delta(m_global_buggy, m_global_fixed)
        print()
