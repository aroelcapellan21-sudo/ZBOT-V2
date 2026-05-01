"""
backtest_trailing_vs_sl.py
Compara tres estrategias de salida para francotirador lateral BTC:
  A) SL Fijo -3.5%
  B) Trailing Stop Dinamico
  C) Trailing Stop + SAR como confirmacion
Usa historico real 4H de 9 años
"""

import csv
import random

# ─── CONFIGURACION ────────────────────────────────────────────
ARCHIVO         = "/home/ariel/bot-padre-v2/data/historico_4h/BTCUSDT_4h.csv"
CAPITAL_INICIAL = 1000.0
MONTO_POR_OP    = 10.0
TAKE_PROFIT     = 6.0    # %
STOP_LOSS       = 3.5    # % SL fijo respaldo
RSI_MIN         = 45
RSI_MAX         = 55
EMA_CORTA       = 20
EMA_LARGA       = 50
DIFF_EMA_MAX    = 2.0
VENTANA_FASE    = 30
UMBRAL_FASE     = 2.5

# Trailing Stop
TRAILING_ACTIVACION = 3.0   # % ganancia para activar trailing
TRAILING_DISTANCIA  = 1.5   # % que el SL sigue al precio desde el maximo

# SAR
SAR_AF      = 0.01
SAR_AF_MAX  = 0.10

MONTECARLO_SIMS = 1000

# ─── FUNCIONES BASE ───────────────────────────────────────────

def cargar_csv(ruta):
    datos = []
    with open(ruta, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            datos.append({
                "ts":    row["timestamp"],
                "open":  float(row["open"]),
                "high":  float(row["high"]),
                "low":   float(row["low"]),
                "close": float(row["close"]),
            })
    return datos

def calcular_rsi(cierres, periodo=14):
    if len(cierres) < periodo + 1:
        return None
    ganancias, perdidas = [], []
    for i in range(1, periodo + 1):
        diff = cierres[i] - cierres[i-1]
        ganancias.append(max(diff, 0))
        perdidas.append(max(-diff, 0))
    ag = sum(ganancias) / periodo
    ap = sum(perdidas) / periodo
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

def calcular_sar(highs, lows, cierres):
    if len(cierres) < 5:
        return cierres[-1] * 1.01
    tendencia = 1
    sar = lows[-5]
    ep  = highs[-5]
    af  = SAR_AF
    for i in range(-4, 0):
        precio = cierres[i]
        high   = highs[i]
        low    = lows[i]
        if tendencia == 1:
            sar_nuevo = sar + af * (ep - sar)
            sar_nuevo = min(sar_nuevo, lows[i-1], lows[i-2] if i >= -3 else lows[i-1])
            if precio < sar_nuevo:
                tendencia = -1
                sar_nuevo = ep
                ep = low
                af = SAR_AF
            else:
                if high > ep:
                    ep = high
                    af = min(af + SAR_AF, SAR_AF_MAX)
        else:
            sar_nuevo = sar - af * (sar - ep)
            sar_nuevo = max(sar_nuevo, highs[i-1], highs[i-2] if i >= -3 else highs[i-1])
            if precio > sar_nuevo:
                tendencia = 1
                sar_nuevo = ep
                ep = high
                af = SAR_AF
            else:
                if low < ep:
                    ep = low
                    af = min(af + SAR_AF, SAR_AF_MAX)
        sar = sar_nuevo
    return round(sar, 4)

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

# ─── BACKTEST ─────────────────────────────────────────────────

def correr_backtest(datos, modo="SL"):
    """
    modo: 'SL' | 'TRAILING' | 'TRAILING_SAR'
    """
    capital        = CAPITAL_INICIAL
    trades         = []
    en_trade       = False
    precio_entrada = 0
    precio_max     = 0
    sl_actual      = 0
    trailing_activo = False
    vela_entrada   = 0

    cierres = [d["close"] for d in datos]
    highs   = [d["high"]  for d in datos]
    lows    = [d["low"]   for d in datos]

    for i in range(EMA_LARGA + 15, len(datos)):
        c_slice = cierres[:i+1]
        h_slice = highs[:i+1]
        l_slice = lows[:i+1]
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
            cambio = ((precio - precio_entrada) / precio_entrada) * 100

            # Actualizar precio maximo
            if high > precio_max:
                precio_max = high

            # ── Activar y actualizar trailing ──────────────────
            if modo in ("TRAILING", "TRAILING_SAR"):
                ganancia_max = ((precio_max - precio_entrada) / precio_entrada) * 100
                if ganancia_max >= TRAILING_ACTIVACION:
                    trailing_activo = True
                    # SL sube con el precio maximo
                    sl_trailing = precio_max * (1 - TRAILING_DISTANCIA / 100)
                    # Solo subir el SL, nunca bajarlo
                    if sl_trailing > sl_actual:
                        sl_actual = sl_trailing

            # ── TP ─────────────────────────────────────────────
            if cambio >= TAKE_PROFIT:
                gan_usd = round((TAKE_PROFIT / 100) * MONTO_POR_OP, 4)
                capital += gan_usd
                trades.append({
                    "tipo": "TP", "entrada": precio_entrada,
                    "salida": round(precio_entrada * (1 + TAKE_PROFIT/100), 4),
                    "ganancia_pct": TAKE_PROFIT, "ganancia_usd": gan_usd,
                    "velas": i - vela_entrada, "metodo": "TP",
                    "trailing_activo": trailing_activo
                })
                en_trade = False
                continue

            # ── SAR confirmacion (solo modo C) ─────────────────
            if modo == "TRAILING_SAR" and trailing_activo and i >= 10:
                sar = calcular_sar(h_slice, l_slice, c_slice)
                ema_c = calcular_ema(c_slice, EMA_CORTA)
                if sar > precio and ema_c and precio < ema_c:
                    gan_pct = round(cambio, 4)
                    gan_usd = round((cambio / 100) * MONTO_POR_OP, 4)
                    capital += gan_usd
                    trades.append({
                        "tipo": "SAR", "entrada": precio_entrada,
                        "salida": precio,
                        "ganancia_pct": gan_pct, "ganancia_usd": gan_usd,
                        "velas": i - vela_entrada, "metodo": "SAR",
                        "trailing_activo": True
                    })
                    en_trade = False
                    continue

            # ── SL (fijo o trailing) ────────────────────────────
            if precio <= sl_actual:
                gan_pct = round(((sl_actual - precio_entrada) / precio_entrada) * 100, 4)
                gan_usd = round((gan_pct / 100) * MONTO_POR_OP, 4)
                capital += gan_usd
                metodo = "TRAILING_SL" if trailing_activo else "SL"
                trades.append({
                    "tipo": metodo, "entrada": precio_entrada,
                    "salida": round(sl_actual, 4),
                    "ganancia_pct": gan_pct, "ganancia_usd": gan_usd,
                    "velas": i - vela_entrada, "metodo": metodo,
                    "trailing_activo": trailing_activo
                })
                en_trade = False

    return capital, trades

# ─── METRICAS ─────────────────────────────────────────────────

def calcular_metricas(capital_final, trades):
    if not trades:
        return {}
    total   = len(trades)
    ganados = [t for t in trades if t["ganancia_usd"] > 0]
    perdidos= [t for t in trades if t["ganancia_usd"] <= 0]
    win_rate= round(len(ganados) / total * 100, 2)
    sum_g   = sum(t["ganancia_usd"] for t in ganados) if ganados else 0
    sum_p   = abs(sum(t["ganancia_usd"] for t in perdidos)) if perdidos else 0.001
    pf      = round(sum_g / sum_p, 3)

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

    # Desglose por metodo de salida
    metodos = {}
    for t in trades:
        m = t.get("metodo", "?")
        if m not in metodos:
            metodos[m] = {"count": 0, "sum_pct": 0}
        metodos[m]["count"]   += 1
        metodos[m]["sum_pct"] += t["ganancia_pct"]

    return {
        "total":         total,
        "ganados":       len(ganados),
        "perdidos":      len(perdidos),
        "win_rate":      win_rate,
        "profit_factor": pf,
        "max_drawdown":  round(max_dd, 2),
        "capital_final": round(capital_final, 2),
        "ganancia_neta": round(capital_final - CAPITAL_INICIAL, 2),
        "avg_velas":     round(sum(t["velas"] for t in trades) / total, 1),
        "metodos":       metodos,
    }

def montecarlo(trades, n=MONTECARLO_SIMS):
    if not trades:
        return {}
    resultados_dd  = []
    resultados_cap = []
    for _ in range(n):
        muestra = random.sample(trades, len(trades))
        capital = CAPITAL_INICIAL
        peak    = CAPITAL_INICIAL
        max_dd  = 0
        for t in muestra:
            capital += t["ganancia_usd"]
            if capital > peak:
                peak = capital
            dd = (peak - capital) / peak * 100
            if dd > max_dd:
                max_dd = dd
        resultados_dd.append(max_dd)
        resultados_cap.append(capital)
    resultados_dd.sort()
    return {
        "dd_p95":       round(resultados_dd[int(n*0.95)], 2),
        "dd_p99":       round(resultados_dd[int(n*0.99)], 2),
        "cap_promedio": round(sum(resultados_cap)/n, 2),
        "aprobacion":   round(sum(1 for c in resultados_cap if c > CAPITAL_INICIAL)/n*100, 2),
    }

# ─── MAIN ─────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 65)
    print("  BACKTEST: SL Fijo vs Trailing Stop vs Trailing+SAR")
    print("  BTCUSDT 4H — 9 años de histórico")
    print("=" * 65)

    print("\n📂 Cargando datos...")
    datos = cargar_csv(ARCHIVO)
    print(f"   {len(datos)} velas ({datos[0]['ts'][:10]} → {datos[-1]['ts'][:10]})")

    print("\n⚙️  A) SL Fijo -3.5%...")
    cap_a, tr_a = correr_backtest(datos, modo="SL")
    met_a = calcular_metricas(cap_a, tr_a)

    print("⚙️  B) Trailing Stop Dinámico...")
    cap_b, tr_b = correr_backtest(datos, modo="TRAILING")
    met_b = calcular_metricas(cap_b, tr_b)

    print("⚙️  C) Trailing + SAR confirmación...")
    cap_c, tr_c = correr_backtest(datos, modo="TRAILING_SAR")
    met_c = calcular_metricas(cap_c, tr_c)

    print(f"\n🎲 Monte Carlo {MONTECARLO_SIMS} sims...")
    mc_a = montecarlo(tr_a)
    mc_b = montecarlo(tr_b)
    mc_c = montecarlo(tr_c)

    # ── TABLA ─────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print(f"{'Métrica':<25} {'A: SL Fijo':>12} {'B: Trailing':>12} {'C: Trail+SAR':>13}")
    print("-" * 65)
    for label, ka, kb, kc in [
        ("Total trades",   "total",         "total",         "total"),
        ("Ganados",        "ganados",        "ganados",        "ganados"),
        ("Perdidos",       "perdidos",       "perdidos",       "perdidos"),
        ("Win Rate",       "win_rate",       "win_rate",       "win_rate"),
        ("Profit Factor",  "profit_factor",  "profit_factor",  "profit_factor"),
        ("Max Drawdown",   "max_drawdown",   "max_drawdown",   "max_drawdown"),
        ("Capital Final",  "capital_final",  "capital_final",  "capital_final"),
        ("Ganancia Neta",  "ganancia_neta",  "ganancia_neta",  "ganancia_neta"),
        ("Avg velas",      "avg_velas",      "avg_velas",      "avg_velas"),
    ]:
        va = str(met_a.get(ka, "-"))
        vb = str(met_b.get(kb, "-"))
        vc = str(met_c.get(kc, "-"))
        if ka in ("win_rate", "max_drawdown"):
            va += "%"; vb += "%"; vc += "%"
        if ka in ("capital_final", "ganancia_neta"):
            va = "$"+va; vb = "$"+vb; vc = "$"+vc
        print(f"{label:<25} {va:>12} {vb:>12} {vc:>13}")

    print("-" * 65)
    print(f"{'MONTE CARLO':<25}")
    print(f"{'DD P95':<25} {str(mc_a.get('dd_p95',0))+'%':>12} {str(mc_b.get('dd_p95',0))+'%':>12} {str(mc_c.get('dd_p95',0))+'%':>13}")
    print(f"{'DD P99':<25} {str(mc_a.get('dd_p99',0))+'%':>12} {str(mc_b.get('dd_p99',0))+'%':>12} {str(mc_c.get('dd_p99',0))+'%':>13}")
    print(f"{'Cap. Promedio':<25} {'$'+str(mc_a.get('cap_promedio',0)):>12} {'$'+str(mc_b.get('cap_promedio',0)):>12} {'$'+str(mc_c.get('cap_promedio',0)):>13}")
    print(f"{'% Aprobación':<25} {str(mc_a.get('aprobacion',0))+'%':>12} {str(mc_b.get('aprobacion',0))+'%':>12} {str(mc_c.get('aprobacion',0))+'%':>13}")
    print("=" * 65)

    # ── Desglose metodos salida B y C ─────────────────────────
    print("\n📌 DESGLOSE SALIDAS — B (Trailing):")
    for m, v in met_b.get("metodos", {}).items():
        avg = round(v["sum_pct"] / v["count"], 3) if v["count"] else 0
        print(f"   {m:<15} {v['count']:>4} salidas | avg {avg}%")

    print("\n📌 DESGLOSE SALIDAS — C (Trailing+SAR):")
    for m, v in met_c.get("metodos", {}).items():
        avg = round(v["sum_pct"] / v["count"], 3) if v["count"] else 0
        print(f"   {m:<15} {v['count']:>4} salidas | avg {avg}%")

    # ── VEREDICTO ─────────────────────────────────────────────
    print("\n📊 VEREDICTO FINAL:")
    scores = {
        "A: SL Fijo":    met_a.get("profit_factor", 0),
        "B: Trailing":   met_b.get("profit_factor", 0),
        "C: Trail+SAR":  met_c.get("profit_factor", 0),
    }
    ganador = max(scores, key=scores.get)
    print(f"   🏆 GANADOR por Profit Factor: {ganador}")

    # Ganador por menor drawdown
    dds = {
        "A: SL Fijo":    met_a.get("max_drawdown", 999),
        "B: Trailing":   met_b.get("max_drawdown", 999),
        "C: Trail+SAR":  met_c.get("max_drawdown", 999),
    }
    menor_dd = min(dds, key=dds.get)
    print(f"   🛡️  Menor Drawdown:           {menor_dd}")

    if ganador == menor_dd:
        print(f"\n   ✅ RECOMENDACIÓN: Implementar {ganador}")
        print(f"      Gana en rentabilidad Y en protección de capital")
    else:
        print(f"\n   ⚖️  TRADE-OFF detectado:")
        print(f"      Más rentable:      {ganador}")
        print(f"      Más conservador:   {menor_dd}")
        print(f"      → Decidir según tolerancia al riesgo")

    print("\n✅ Backtest completado")
