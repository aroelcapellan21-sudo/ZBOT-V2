"""
backtest_trailing_halfback.py
Compara dos variantes de trailing stop:
  A) Trailing fijo 1.5% distancia
  B) Trailing 50% del movimiento (half-back)
  C) Trailing 50% con paso 1% (cada +1% sube SL +0.5%)
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

def correr_backtest(datos, modo="FIJO"):
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

            ganancia_max_pct = ((precio_max - precio_entrada) / precio_entrada) * 100

            # Activar trailing
            if ganancia_max_pct >= TRAILING_ACTIVACION:
                trailing_activo = True

                if modo == "FIJO":
                    # SL a 1.5% bajo el maximo
                    sl_nuevo = precio_max * (1 - 1.5 / 100)

                elif modo == "HALFBACK":
                    # SL al 50% del movimiento desde entrada hasta maximo
                    sl_nuevo = precio_entrada + (precio_max - precio_entrada) * 0.5

                elif modo == "PASO":
                    # Cada +1% adicional sobre activacion, SL sube +0.5%
                    pasos = int((ganancia_max_pct - TRAILING_ACTIVACION) / 1.0)
                    sl_pct = pasos * 0.5  # % sobre precio entrada
                    sl_nuevo = precio_entrada * (1 + sl_pct / 100)

                # Solo subir el SL, nunca bajarlo
                if sl_nuevo > sl_actual:
                    sl_actual = sl_nuevo

            # TP
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

            # SL o Trailing SL
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

    metodos = {}
    for t in trades:
        m = t["metodo"]
        if m not in metodos:
            metodos[m] = {"count": 0, "sum": 0}
        metodos[m]["count"] += 1
        metodos[m]["sum"]   += t["ganancia_pct"]

    return {
        "total":         total,
        "ganados":       len(ganados),
        "perdidos":      len(perdidos),
        "win_rate":      round(len(ganados)/total*100, 2),
        "profit_factor": round(sum_g/sum_p, 3),
        "max_drawdown":  round(max_dd, 2),
        "capital_final": round(capital_final, 2),
        "ganancia_neta": round(capital_final - CAPITAL_INICIAL, 2),
        "avg_velas":     round(sum(t["velas"] for t in trades)/total, 1),
        "metodos":       metodos,
    }

def montecarlo(trades, n=MONTECARLO_SIMS):
    if not trades:
        return {}
    dds, caps = [], []
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
        caps.append(cap)
    dds.sort()
    return {
        "dd_p95":       round(dds[int(n*0.95)], 2),
        "dd_p99":       round(dds[int(n*0.99)], 2),
        "cap_promedio": round(sum(caps)/n, 2),
        "aprobacion":   round(sum(1 for c in caps if c > CAPITAL_INICIAL)/n*100, 2),
    }

if __name__ == "__main__":
    print("=" * 65)
    print("  BACKTEST: Trailing Fijo vs Half-Back vs Paso 1%/0.5%")
    print("  BTCUSDT 4H — 9 años")
    print("=" * 65)

    datos = cargar_csv(ARCHIVO)
    print(f"   {len(datos)} velas cargadas\n")

    print("⚙️  A) Trailing Fijo 1.5%...")
    ca, ta = correr_backtest(datos, "FIJO")
    ma = metricas(ca, ta)

    print("⚙️  B) Trailing Half-Back 50%...")
    cb, tb = correr_backtest(datos, "HALFBACK")
    mb = metricas(cb, tb)

    print("⚙️  C) Trailing Paso +1%/+0.5%...")
    cc, tc = correr_backtest(datos, "PASO")
    mc_res = metricas(cc, tc)

    print("\n🎲 Monte Carlo...")
    mca = montecarlo(ta)
    mcb = montecarlo(tb)
    mcc = montecarlo(tc)

    print("\n" + "=" * 65)
    print(f"{'Métrica':<25} {'A: Fijo 1.5%':>12} {'B: Half-Back':>12} {'C: Paso':>12}")
    print("-" * 65)
    for label, k in [
        ("Total trades",  "total"),
        ("Ganados",       "ganados"),
        ("Perdidos",      "perdidos"),
        ("Win Rate %",    "win_rate"),
        ("Profit Factor", "profit_factor"),
        ("Max Drawdown%", "max_drawdown"),
        ("Capital Final", "capital_final"),
        ("Ganancia Neta", "ganancia_neta"),
        ("Avg velas",     "avg_velas"),
    ]:
        va = str(ma.get(k, "-"))
        vb = str(mb.get(k, "-"))
        vc = str(mc_res.get(k, "-"))
        if k in ("capital_final", "ganancia_neta"):
            va = "$"+va; vb = "$"+vb; vc = "$"+vc
        print(f"{label:<25} {va:>12} {vb:>12} {vc:>12}")

    print("-" * 65)
    print(f"{'DD P95':<25} {str(mca.get('dd_p95'))+'%':>12} {str(mcb.get('dd_p95'))+'%':>12} {str(mcc.get('dd_p95'))+'%':>12}")
    print(f"{'DD P99':<25} {str(mca.get('dd_p99'))+'%':>12} {str(mcb.get('dd_p99'))+'%':>12} {str(mcc.get('dd_p99'))+'%':>12}")
    print(f"{'Aprobación':<25} {str(mca.get('aprobacion'))+'%':>12} {str(mcb.get('aprobacion'))+'%':>12} {str(mcc.get('aprobacion'))+'%':>12}")
    print("=" * 65)

    # Desglose metodos
    for nombre, m in [("A Fijo", ma), ("B Half-Back", mb), ("C Paso", mc_res)]:
        print(f"\n📌 {nombre}:")
        for met, v in m.get("metodos", {}).items():
            avg = round(v["sum"]/v["count"], 3) if v["count"] else 0
            print(f"   {met:<15} {v['count']:>4} salidas | avg {avg:>+.3f}%")

    # Veredicto
    scores = {
        "A: Fijo 1.5%":   ma.get("profit_factor", 0),
        "B: Half-Back":   mb.get("profit_factor", 0),
        "C: Paso +1/0.5": mc_res.get("profit_factor", 0),
    }
    ganador = max(scores, key=scores.get)
    print(f"\n🏆 GANADOR: {ganador} con PF {scores[ganador]}")
    print("\n✅ Listo")
