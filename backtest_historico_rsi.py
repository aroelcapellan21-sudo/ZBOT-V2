# ============================================================
# backtest_historico_rsi.py v2
# Version optimizada — RSI incremental, no recalcula desde cero
# SOLO LECTURA — no toca nada del bot
# ============================================================

import csv

SIMBOLOS = ["ETHUSDT", "SOLUSDT", "BTCUSDT", "BNBUSDT", "AVAXUSDT"]
RUTA     = "/home/ariel/bot-padre-v3-backup/data/historico_4h/{}_4h.csv"

PARAMS = {
    "ETHUSDT":  {"sl": 2.0, "tp": 10.0},
    "SOLUSDT":  {"sl": 4.0, "tp": 10.0},
    "BTCUSDT":  {"sl": 5.0, "tp": 10.0},
    "BNBUSDT":  {"sl": 2.0, "tp":  5.0},
    "AVAXUSDT": {"sl": 3.0, "tp":  8.0},
}

RANGOS_RSI = [
    (70,80),(65,75),(60,70),(55,65),(50,60),(45,55),(40,50)
]

def cargar_velas(symbol):
    velas = []
    with open(RUTA.format(symbol), newline='') as f:
        for row in csv.DictReader(f):
            try:
                velas.append({
                    'high':  float(row['high']),
                    'low':   float(row['low']),
                    'close': float(row['close']),
                })
            except: continue
    return velas

def precalcular_rsi(velas, periodo=14):
    """Calcula RSI para todas las velas de una vez — O(n)."""
    cierres = [v['close'] for v in velas]
    rsi_arr = [None] * len(cierres)
    if len(cierres) < periodo + 1:
        return rsi_arr

    g = [max(cierres[i]-cierres[i-1],0) for i in range(1,len(cierres))]
    p = [max(cierres[i-1]-cierres[i],0) for i in range(1,len(cierres))]

    ag = sum(g[:periodo])/periodo
    ap = sum(p[:periodo])/periodo

    if ap == 0:
        rsi_arr[periodo] = 100.0
    else:
        rsi_arr[periodo] = round(100-(100/(1+ag/ap)),1)

    for i in range(periodo, len(g)):
        ag = (ag*(periodo-1)+g[i])/periodo
        ap = (ap*(periodo-1)+p[i])/periodo
        idx = i+1
        if ap == 0:
            rsi_arr[idx] = 100.0
        else:
            rsi_arr[idx] = round(100-(100/(1+ag/ap)),1)

    return rsi_arr

def simular_trade(velas, idx, sl_pct, tp_pct):
    precio_entrada = velas[idx]['close']
    precio_tp = precio_entrada * (1 + tp_pct/100)
    precio_sl = precio_entrada * (1 - sl_pct/100)
    for i in range(idx+1, min(idx+101, len(velas))):
        if velas[i]['high'] >= precio_tp: return 'TP', i-idx
        if velas[i]['low']  <= precio_sl: return 'SL', i-idx
    return 'TIMEOUT', 100

def backtest_rango(velas, rsi_arr, rsi_min, rsi_max, sl, tp):
    tp_c = sl_c = timeout = 0
    en_trade   = False
    idx_salida = 0

    for i in range(20, len(velas)):
        if en_trade and i <= idx_salida:
            continue
        en_trade = False

        rsi = rsi_arr[i]
        if rsi is None or not (rsi_min <= rsi <= rsi_max):
            continue

        resultado, duracion = simular_trade(velas, i, sl, tp)
        if resultado == 'TP':   tp_c += 1
        elif resultado == 'SL': sl_c += 1
        else:                   timeout += 1
        idx_salida = i + duracion
        en_trade   = True

    total = tp_c + sl_c
    if total < 10: return None
    wr = round(tp_c/total*100,1)
    pf = round((tp_c*tp)/(sl_c*sl),2) if sl_c else 0
    años = (len(velas)*4)/(365*24)
    tm = round((total+timeout)/años/12,1)
    return tp_c, sl_c, timeout, wr, pf, tm

def main():
    print("="*70)
    print("BACKTEST HISTORICO RSI — 2017 a 2026 — OPTIMIZADO")
    print("="*70)

    mejores = {}

    for symbol in SIMBOLOS:
        print(f"\nCargando {symbol}...", flush=True)
        try:
            velas = cargar_velas(symbol)
        except FileNotFoundError:
            print(f"  No encontrado: {symbol}")
            continue

        años = round((len(velas)*4)/(365*24),1)
        print(f"  {len(velas)} velas ({años} años)")
        print(f"  Calculando RSI...", flush=True)

        rsi_arr = precalcular_rsi(velas)

        print(f"  Probando {len(RANGOS_RSI)} rangos...", flush=True)

        sl = PARAMS[symbol]['sl']
        tp = PARAMS[symbol]['tp']
        resultados = []

        for rsi_min, rsi_max in RANGOS_RSI:
            r = backtest_rango(velas, rsi_arr, rsi_min, rsi_max, sl, tp)
            if r:
                resultados.append((rsi_min, rsi_max) + r)
            print(f"    RSI {rsi_min}-{rsi_max} listo", flush=True)

        print(f"\n  {symbol} — Rangos RSI por PF:")
        print(f"  {'RSI':<12} {'TP':<6} {'SL':<6} {'WR%':<8} {'PF':<8} {'T/mes'}")
        print("  "+"-"*50)
        for r in sorted(resultados, key=lambda x: x[6], reverse=True):
            rmin,rmax,tp_c,sl_c,to,wr,pf,tm = r
            marca = " ✓" if pf >= 1.8 else ""
            print(f"  {rmin}-{rmax:<8} {tp_c:<6} {sl_c:<6} {wr:<8} {pf:<8} {tm}{marca}")

        mejores[symbol] = sorted(resultados, key=lambda x: x[6], reverse=True)[0] if resultados else None

    print("\n"+"="*70)
    print("RESUMEN — MEJOR RANGO RSI POR MONEDA (9 AÑOS)")
    print("="*70)
    print(f"{'Moneda':<12} {'RSI':<12} {'WR%':<8} {'PF':<8} {'T/mes':<8} {'Meta'}")
    print("-"*55)
    for symbol, r in mejores.items():
        if r:
            rmin,rmax,tp_c,sl_c,to,wr,pf,tm = r
            meta = "✅ PF OK" if pf >= 1.8 else "❌"
            print(f"{symbol:<12} {rmin}-{rmax:<8} {wr:<8} {pf:<8} {tm:<8} {meta}")

    import os, json
    os.makedirs('/home/ariel/bot-padre-v2/reports', exist_ok=True)
    with open('/home/ariel/bot-padre-v2/reports/backtest_historico_rsi.json','w') as f:
        json.dump({s: list(r) if r else None for s,r in mejores.items()}, f, indent=2)
    print("\nReporte guardado en reports/backtest_historico_rsi.json")

if __name__ == "__main__":
    main()
