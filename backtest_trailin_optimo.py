"""
backtest_trailing_optimo.py
Optimiza la distancia del trailing stop entre 1.5% y 2.5%
Activacion fija en +3%, SL respaldo -3.5%, TP +6%
"""

import csv
import random

ARCHIVO         = "/home/ariel/bot-padre-v2/data/historico_4h/BTCUSDT_4h.csv"
CAPITAL_INICIAL = 1000.0
MONTO_POR_OP    = 10.0
TAKE_PROFIT     = 6.0
STOP_LOSS       = 3.5
RSI_MIN         = 45
RSI_MAX         = 55
EMA_CORTA       = 20
EMA_LARGA       = 50
DIFF_EMA_MAX    = 2.0
VENTANA_FASE    = 30
UMBRAL_FASE     = 2.5
TRAILING_ACTIVACION = 3.0
MONTECARLO_SIMS = 1000

VARIANTES = [1.5, 1.7, 2.0, 2.2, 2.5]

def cargar_csv(ruta):
    datos = []
    with open(ruta, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            datos.append({
                "close": float(row["close"]),
                "high":  float(row["high"]),
                "low":   float(row["low"]),
            })
    return datos

def calcular_rsi(cierres, periodo=14):
    if len(cierres) < periodo + 1:
        return None
    g, p = [], []
    for i in range(1, periodo + 1):
        d = cierres[i] - cierres[i-1]
        g.append(max(d, 0))
        p.append(max(-d, 0))
    ag = sum(g) / periodo
    ap = sum(p) / periodo
    if ap == 0:
        return 100.0
    return round(100 - (100 / (1 + ag/ap)), 2)

def calcular_ema(cierres, periodo):
    if len(cierres) < periodo:
        return None
    k = 2 / (periodo + 1)
    ema = sum(cierres[:periodo]) / periodo
    for p in cierres[periodo:]:
        ema = p * k + ema * (1 - k)
    return round(ema, 2)

def detectar_fase(cierres):
    if len(cierres) < VENTANA_FASE:
        return "DESCONOCIDA"
    cambio = ((cierres[-1] - cierres[-VENTANA_FASE]) / cierres[-VENTANA_FASE]) * 100
    if cambio > UMBRAL_FASE:
        return "ALCISTA"
    elif cambio < -UMBRAL_FASE:
        return "BAJISTA"
    return "LATERAL"

def señal_entrada(cierres):
    if len(cierres) < EMA_LARGA + 1:
        return False
    if detectar_fase(cierres) != "LATERAL":
        return False
    rsi   = calcular_rsi(cierres[-15:])
    ema_c = calcular_ema(cierres, EMA_CORTA)
    ema_l = calcular_ema(cierres, EMA_LARGA)
    if rsi is None or ema_c is None or ema_l is None:
        return False
    diff = abs(ema_c - ema_l) / ema_l * 100
    return RSI_MIN <= rsi <= RSI_MAX and diff < DIFF_EMA_MAX

def correr_backtest(datos, distancia):
    capital        = CAPITAL_INICIAL
    trades         = []
    en_trade       = False
    precio_entrada = 0
    precio_max     = 0
    sl_actual      = 0
    trailing_activo= False
    vela_entrada   = 0

    cierres = [d["close"] for d in datos]
    highs   = [d["high"]  for d in datos]

    for i in range(EMA_LARGA + 15, len(datos)):
        c_slice = cierres[:i+1]
        precio  = cierres[i]
        high    = highs[i]

        if not en_trade:
            if señal_entrada(c_slice):
                en_trade        = True
                precio_entrada  = precio
                precio_max      = precio
                sl_actual       = precio_entrada * (1 - STOP_LOSS / 100)
                trailing_activo = False
                vela_entrada    = i
        else:
            if high > precio_max:
                precio_max = high

            ganancia_max = ((precio_max - precio_entrada) / precio_entrada) * 100

            if ganancia_max >= TRAILING_ACTIVACION:
                trailing_activo = True
                sl_nuevo = precio_max * (1 - distancia / 100)
                if sl_nuevo > sl_actual:
                    sl_actual = sl_nuevo

            cambio = ((precio - precio_entrada) / precio_entrada) * 100

            if cambio >= TAKE_PROFIT:
                gan_usd = round((TAKE_PROFIT / 100) * MONTO_POR_OP, 4)
                capital += gan_usd
                trades.append({
                    "ganancia_pct": TAKE_PROFIT,
                    "ganancia_usd": gan_usd,
                    "velas": i - vela_entrada,
                    "metodo": "TP"
                })
                en_trade = False
                continue

            if precio <= sl_actual:
                gan_pct = round(((sl_actual - precio_entrada) / precio_entrada) * 100, 4)
                gan_usd = round((gan_pct / 100) * MONTO_POR_OP, 4)
                capital += gan_usd
                metodo = "TRAILING_SL" if trailing_activo else "SL"
                trades.append({
                    "ganancia_pct": gan_pct,
                    "ganancia_usd": gan_usd,
                    "velas": i - vela_entrada,
                    "metodo": metodo
                })
                en_trade = False

    return capital, trades

def metricas(capital_final, trades):
    if not trades:
        return {}
    total   = len(trades)
    ganados = [t for t in trades if t["ganancia_usd"] > 0]
    perdidos= [t for t in trades if t["ganancia_usd"] <= 0]
    sum_g   = sum(t["ganancia_usd"] for t in ganados) if ganados else 0
    sum_p   = abs(sum(t["ganancia_usd"] for t in perdidos)) if perdidos else 0.001

    capital = CAPITAL_INICIAL
    peak    = CAPITAL_INICIAL
    max_dd  = 0
    for t in trades:
        capital += t["ganancia_usd"]
        if capital > peak:
            peak = capital
        dd = (peak - capital) / peak * 100
        if dd > max_dd:
            max_dd = dd

    tp_count      = sum(1 for t in trades if t["metodo"] == "TP")
    trailing_count= sum(1 for t in trades if t["metodo"] == "TRAILING_SL")
    sl_count      = sum(1 for t in trades if t["metodo"] == "SL")
    trailing_avg  = round(sum(t["ganancia_pct"] for t in trades if t["metodo"] == "TRAILING_SL") / trailing_count, 3) if trailing_count else 0

    return {
        "total":          total,
        "ganados":        len(ganados),
        "win_rate":       round(len(ganados)/total*100, 2),
        "profit_factor":  round(sum_g/sum_p, 3),
        "max_drawdown":   round(max_dd, 2),
        "ganancia_neta":  round(capital_final - CAPITAL_INICIAL, 2),
        "tp_count":       tp_count,
        "trailing_count": trailing_count,
        "sl_count":       sl_count,
        "trailing_avg":   trailing_avg,
    }

def montecarlo(trades, n=MONTECARLO_SIMS):
    if not trades:
        return {}
    dds = []
    for _ in range(n):
        muestra = random.sample(trades, len(trades))
        cap = CAPITAL_INICIAL
        peak = cap
        max_dd = 0
        for t in muestra:
            cap += t["ganancia_usd"]
            if cap > peak:
                peak = cap
            dd = (peak - cap) / peak * 100
            if dd > max_dd:
                max_dd = dd
        dds.append(max_dd)
    dds.sort()
    return {
        "dd_p95": round(dds[int(n*0.95)], 2),
        "dd_p99": round(dds[int(n*0.99)], 2),
    }

if __name__ == "__main__":
    print("=" * 72)
    print("  OPTIMIZACIÓN DISTANCIA TRAILING — BTCUSDT 4H 9 años")
    print("  Activación fija +3% | SL respaldo -3.5% | TP +6%")
    print("=" * 72)

    datos = cargar_csv(ARCHIVO)
    print(f"  {len(datos)} velas cargadas\n")

    resultados = {}
    for dist in VARIANTES:
        print(f"⚙️  Trailing {dist}%...")
        cap, trades = correr_backtest(datos, dist)
        m = metricas(cap, trades)
        mc = montecarlo(trades)
        resultados[dist] = {**m, **mc}

    # ── TABLA ──────────────────────────────────────────────────
    print("\n" + "=" * 72)
    header = f"{'Métrica':<22}"
    for d in VARIANTES:
        header += f"  {str(d)+'%':>9}"
    print(header)
    print("-" * 72)

    for label, k in [
        ("Total trades",   "total"),
        ("Ganados",        "ganados"),
        ("Win Rate",       "win_rate"),
        ("Profit Factor",  "profit_factor"),
        ("Max Drawdown",   "max_drawdown"),
        ("Ganancia Neta",  "ganancia_neta"),
        ("TP alcanzados",  "tp_count"),
        ("Trailing exits", "trailing_count"),
        ("SL activados",   "sl_count"),
        ("Trailing avg%",  "trailing_avg"),
        ("DD P95",         "dd_p95"),
        ("DD P99",         "dd_p99"),
    ]:
        row = f"{label:<22}"
        for d in VARIANTES:
            v = resultados[d].get(k, "-")
            row += f"  {str(v):>9}"
        print(row)

    print("=" * 72)

    # ── VEREDICTO ──────────────────────────────────────────────
    mejor_pf   = max(VARIANTES, key=lambda d: resultados[d]["profit_factor"])
    mejor_gan  = max(VARIANTES, key=lambda d: resultados[d]["ganancia_neta"])
    menor_dd   = min(VARIANTES, key=lambda d: resultados[d]["max_drawdown"])
    mas_tp     = max(VARIANTES, key=lambda d: resultados[d]["tp_count"])

    print(f"\n📊 ANÁLISIS:")
    print(f"   🏆 Mejor Profit Factor : {mejor_pf}% (PF {resultados[mejor_pf]['profit_factor']})")
    print(f"   💰 Mayor Ganancia Neta : {mejor_gan}% (${resultados[mejor_gan]['ganancia_neta']})")
    print(f"   🛡️  Menor Drawdown      : {menor_dd}% (DD {resultados[menor_dd]['max_drawdown']}%)")
    print(f"   🎯 Más TPs alcanzados  : {mas_tp}% ({resultados[mas_tp]['tp_count']} trades)")

    # Puntaje combinado
    print(f"\n📐 PUNTAJE COMBINADO (PF + Ganancia + DD):")
    scores = {}
    for d in VARIANTES:
        r = resultados[d]
        score = r["profit_factor"] * 10 + r["ganancia_neta"] * 0.1 - r["max_drawdown"] * 5
        scores[d] = round(score, 3)
        print(f"   {d}%: {score}")

    optimo = max(scores, key=scores.get)
    print(f"\n   ✅ PARÁMETRO ÓPTIMO: {optimo}% de distancia trailing")
    print(f"      Implementar en los 5 francotiradores laterales")
    print("\n✅ Optimización completada")
