"""
backtest_sar_vs_sl.py
Compara estrategia lateral BTC:
  A) SL fijo -3.5%
  B) SAR como salida inteligente + SL -3.5% como respaldo
Usa historico real de 9 años (4H)
"""

import csv
import random
from datetime import datetime

# ─── CONFIGURACION ────────────────────────────────────────────
ARCHIVO = "/home/ariel/bot-padre-v2/data/historico_4h/BTCUSDT_4h.csv"
CAPITAL_INICIAL = 1000.0
MONTO_POR_OP    = 10.0
TAKE_PROFIT     = 6.0    # %
STOP_LOSS       = 3.5    # %
RSI_MIN         = 45
RSI_MAX         = 55
EMA_CORTA       = 20
EMA_LARGA       = 50
DIFF_EMA_MAX    = 2.0    # %
VENTANA_FASE    = 30
UMBRAL_BAJISTA  = 2.5    # % cambio 30 velas para detectar bajista
# SAR parametros conservadores para laterales
SAR_ACELERACION = 0.01
SAR_MAXIMO      = 0.10
MONTECARLO_SIMS = 1000

# ─── FUNCIONES ────────────────────────────────────────────────

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
    if cambio > UMBRAL_BAJISTA:
        return "ALCISTA"
    elif cambio < -UMBRAL_BAJISTA:
        return "BAJISTA"
    return "LATERAL"

def calcular_sar(highs, lows, cierres, af=SAR_ACELERACION, af_max=SAR_MAXIMO):
    """Parabolic SAR simplificado"""
    if len(cierres) < 5:
        return cierres[-1] * 1.01  # SAR encima por defecto
    
    tendencia = 1  # 1=alcista, -1=bajista
    sar = lows[-5]
    ep  = highs[-5]
    af_actual = af
    
    for i in range(-4, 0):
        precio = cierres[i]
        high   = highs[i]
        low    = lows[i]
        
        if tendencia == 1:
            sar_nuevo = sar + af_actual * (ep - sar)
            sar_nuevo = min(sar_nuevo, lows[i-1], lows[i-2] if i >= -3 else lows[i-1])
            if precio < sar_nuevo:
                tendencia = -1
                sar_nuevo = ep
                ep = low
                af_actual = af
            else:
                if high > ep:
                    ep = high
                    af_actual = min(af_actual + af, af_max)
        else:
            sar_nuevo = sar - af_actual * (sar - ep)
            sar_nuevo = max(sar_nuevo, highs[i-1], highs[i-2] if i >= -3 else highs[i-1])
            if precio > sar_nuevo:
                tendencia = 1
                sar_nuevo = ep
                ep = high
                af_actual = af
            else:
                if low < ep:
                    ep = low
                    af_actual = min(af_actual + af, af_max)
        sar = sar_nuevo
    
    return round(sar, 4)

def señal_entrada(cierres):
    """Retorna True si hay señal de entrada lateral"""
    if len(cierres) < EMA_LARGA + 1:
        return False
    fase = detectar_fase(cierres)
    if fase != "LATERAL":
        return False
    rsi   = calcular_rsi(cierres[-15:])
    ema_c = calcular_ema(cierres, EMA_CORTA)
    ema_l = calcular_ema(cierres, EMA_LARGA)
    if rsi is None or ema_c is None or ema_l is None:
        return False
    diff_ema = abs(ema_c - ema_l) / ema_l * 100
    return RSI_MIN <= rsi <= RSI_MAX and diff_ema < DIFF_EMA_MAX

# ─── BACKTEST ────────────────────────────────────────────────

def correr_backtest(datos, usar_sar=False):
    capital    = CAPITAL_INICIAL
    trades     = []
    en_trade   = False
    precio_entrada = 0
    vela_entrada   = 0

    cierres = [d["close"] for d in datos]
    highs   = [d["high"]  for d in datos]
    lows    = [d["low"]   for d in datos]

    for i in range(EMA_LARGA + 15, len(datos)):
        c_slice = cierres[:i+1]
        h_slice = highs[:i+1]
        l_slice = lows[:i+1]
        precio  = cierres[i]

        if not en_trade:
            if señal_entrada(c_slice):
                en_trade       = True
                precio_entrada = precio
                vela_entrada   = i
        else:
            cambio = ((precio - precio_entrada) / precio_entrada) * 100

            # TP
            if cambio >= TAKE_PROFIT:
                ganancia = round((TAKE_PROFIT / 100) * MONTO_POR_OP, 4)
                capital += ganancia
                trades.append({
                    "tipo": "TP",
                    "entrada": precio_entrada,
                    "salida": round(precio_entrada * (1 + TAKE_PROFIT/100), 4),
                    "ganancia_pct": TAKE_PROFIT,
                    "ganancia_usd": ganancia,
                    "velas": i - vela_entrada,
                    "metodo_salida": "TP"
                })
                en_trade = False
                continue

            # SAR salida (solo modo B)
            if usar_sar and i >= 10:
                sar = calcular_sar(h_slice, l_slice, c_slice)
                ema_c = calcular_ema(c_slice, EMA_CORTA)
                # SAR encima del precio Y precio bajo EMA20 = salir
                if sar > precio and ema_c and precio < ema_c:
                    ganancia_pct = round(cambio, 4)
                    ganancia_usd = round((cambio / 100) * MONTO_POR_OP, 4)
                    capital += ganancia_usd
                    trades.append({
                        "tipo": "SAR",
                        "entrada": precio_entrada,
                        "salida": precio,
                        "ganancia_pct": ganancia_pct,
                        "ganancia_usd": ganancia_usd,
                        "velas": i - vela_entrada,
                        "metodo_salida": "SAR"
                    })
                    en_trade = False
                    continue

            # SL fijo (siempre activo como respaldo)
            if cambio <= -STOP_LOSS:
                perdida = round((STOP_LOSS / 100) * MONTO_POR_OP, 4)
                capital -= perdida
                trades.append({
                    "tipo": "SL",
                    "entrada": precio_entrada,
                    "salida": round(precio_entrada * (1 - STOP_LOSS/100), 4),
                    "ganancia_pct": -STOP_LOSS,
                    "ganancia_usd": -perdida,
                    "velas": i - vela_entrada,
                    "metodo_salida": "SL"
                })
                en_trade = False

    return capital, trades

def calcular_metricas(capital_final, trades):
    if not trades:
        return {}
    total    = len(trades)
    ganados  = [t for t in trades if t["ganancia_usd"] > 0]
    perdidos = [t for t in trades if t["ganancia_usd"] <= 0]
    win_rate = round(len(ganados) / total * 100, 2)
    
    sum_ganancias = sum(t["ganancia_usd"] for t in ganados) if ganados else 0
    sum_perdidas  = abs(sum(t["ganancia_usd"] for t in perdidos)) if perdidos else 0.001
    profit_factor = round(sum_ganancias / sum_perdidas, 3)
    
    # Drawdown maximo
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
    
    avg_velas = round(sum(t["velas"] for t in trades) / total, 1)
    
    return {
        "total_trades":   total,
        "ganados":        len(ganados),
        "perdidos":       len(perdidos),
        "win_rate":       win_rate,
        "profit_factor":  profit_factor,
        "max_drawdown":   round(max_dd, 2),
        "capital_final":  round(capital_final, 2),
        "ganancia_neta":  round(capital_final - CAPITAL_INICIAL, 2),
        "avg_velas":      avg_velas,
    }

def montecarlo(trades, n=MONTECARLO_SIMS):
    """Simula N shuffles de los trades y calcula DD maximo promedio"""
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
    p95 = resultados_dd[int(n * 0.95)]
    p99 = resultados_dd[int(n * 0.99)]
    cap_promedio = round(sum(resultados_cap) / n, 2)
    aprobacion   = sum(1 for c in resultados_cap if c > CAPITAL_INICIAL) / n * 100
    
    return {
        "dd_p95":       round(p95, 2),
        "dd_p99":       round(p99, 2),
        "cap_promedio": cap_promedio,
        "aprobacion":   round(aprobacion, 2),
    }

# ─── MAIN ────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  BACKTEST COMPARATIVO: SL Fijo vs SAR")
    print("  BTCUSDT 4H — 9 años de histórico")
    print("=" * 60)
    
    print("\n📂 Cargando datos...")
    datos = cargar_csv(ARCHIVO)
    print(f"   {len(datos)} velas cargadas ({datos[0]['ts'][:10]} → {datos[-1]['ts'][:10]})")
    
    print("\n⚙️  Corriendo Simulación A (SL Fijo -3.5%)...")
    cap_a, trades_a = correr_backtest(datos, usar_sar=False)
    met_a = calcular_metricas(cap_a, trades_a)
    
    print("⚙️  Corriendo Simulación B (SAR + SL Respaldo)...")
    cap_b, trades_b = correr_backtest(datos, usar_sar=True)
    met_b = calcular_metricas(cap_b, trades_b)
    
    print(f"\n🎲 Monte Carlo {MONTECARLO_SIMS} simulaciones...")
    mc_a = montecarlo(trades_a) if trades_a else {}
    mc_b = montecarlo(trades_b) if trades_b else {}
    
    # ─── TABLA COMPARATIVA ───────────────────────────────────
    print("\n" + "=" * 60)
    print("  RESULTADOS COMPARATIVOS")
    print("=" * 60)
    print(f"{'Métrica':<25} {'A: SL Fijo':>15} {'B: SAR+SL':>15}")
    print("-" * 60)
    print(f"{'Total trades':<25} {met_a.get('total_trades',0):>15} {met_b.get('total_trades',0):>15}")
    print(f"{'Ganados':<25} {met_a.get('ganados',0):>15} {met_b.get('ganados',0):>15}")
    print(f"{'Perdidos':<25} {met_a.get('perdidos',0):>15} {met_b.get('perdidos',0):>15}")
    print(f"{'Win Rate':<25} {str(met_a.get('win_rate',0))+'%':>15} {str(met_b.get('win_rate',0))+'%':>15}")
    print(f"{'Profit Factor':<25} {met_a.get('profit_factor',0):>15} {met_b.get('profit_factor',0):>15}")
    print(f"{'Max Drawdown':<25} {str(met_a.get('max_drawdown',0))+'%':>15} {str(met_b.get('max_drawdown',0))+'%':>15}")
    print(f"{'Capital Final':<25} {'$'+str(met_a.get('capital_final',0)):>15} {'$'+str(met_b.get('capital_final',0)):>15}")
    print(f"{'Ganancia Neta':<25} {'$'+str(met_a.get('ganancia_neta',0)):>15} {'$'+str(met_b.get('ganancia_neta',0)):>15}")
    print(f"{'Avg duración (velas)':<25} {met_a.get('avg_velas',0):>15} {met_b.get('avg_velas',0):>15}")
    print("-" * 60)
    print(f"{'MONTE CARLO':<25}")
    print(f"{'DD P95':<25} {str(mc_a.get('dd_p95',0))+'%':>15} {str(mc_b.get('dd_p95',0))+'%':>15}")
    print(f"{'DD P99':<25} {str(mc_a.get('dd_p99',0))+'%':>15} {str(mc_b.get('dd_p99',0))+'%':>15}")
    print(f"{'Cap. Promedio':<25} {'$'+str(mc_a.get('cap_promedio',0)):>15} {'$'+str(mc_b.get('cap_promedio',0)):>15}")
    print(f"{'% Aprobación':<25} {str(mc_a.get('aprobacion',0))+'%':>15} {str(mc_b.get('aprobacion',0))+'%':>15}")
    print("=" * 60)
    
    # Veredicto
    print("\n📊 VEREDICTO:")
    if met_b.get('profit_factor',0) > met_a.get('profit_factor',0) and met_b.get('max_drawdown',100) < met_a.get('max_drawdown',100):
        print("   ✅ SAR GANA — Mejor Profit Factor Y menor Drawdown")
        print("   → Recomendado implementar SAR como salida")
    elif met_a.get('profit_factor',0) > met_b.get('profit_factor',0):
        print("   ⚠️  SL FIJO GANA en Profit Factor")
        print("   → Evaluar si la diferencia justifica la complejidad del SAR")
    else:
        print("   🔄 RESULTADOS MIXTOS — Revisar métricas individualmente")
    
    # Desglose salidas SAR
    if trades_b:
        sar_exits = [t for t in trades_b if t["metodo_salida"] == "SAR"]
        if sar_exits:
            avg_sar = round(sum(t["ganancia_pct"] for t in sar_exits) / len(sar_exits), 3)
            print(f"\n   📌 SAR activó {len(sar_exits)} salidas con promedio {avg_sar}% c/u")
            positivas = sum(1 for t in sar_exits if t["ganancia_pct"] > 0)
            print(f"   📌 De esas, {positivas} fueron con ganancia ({round(positivas/len(sar_exits)*100,1)}%)")
    
    print("\n✅ Backtest completado")

