# ============================================================
# backtest_tp_sl_historico.py
# Optimiza TP/SL para RSI 70-80 usando 9 años de datos reales
# SOLO LECTURA — no toca nada del bot
# ============================================================

import csv, os, json

SIMBOLOS = ["ETHUSDT", "SOLUSDT", "BTCUSDT", "BNBUSDT", "AVAXUSDT"]
RUTA     = "/home/ariel/bot-padre-v3-backup/data/historico_4h/{}_4h.csv"

# Combinaciones a probar
TP_VALORES = [4.0, 5.0, 6.0, 7.0, 8.0, 10.0, 12.0, 15.0, 20.0]
SL_VALORES = [1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0]

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
    cierres = [v['close'] for v in velas]
    rsi_arr = [None] * len(cierres)
    if len(cierres) < periodo + 1: return rsi_arr
    g = [max(cierres[i]-cierres[i-1],0) for i in range(1,len(cierres))]
    p = [max(cierres[i-1]-cierres[i],0) for i in range(1,len(cierres))]
    ag = sum(g[:periodo])/periodo
    ap = sum(p[:periodo])/periodo
    rsi_arr[periodo] = round(100-(100/(1+ag/ap)),1) if ap else 100.0
    for i in range(periodo, len(g)):
        ag = (ag*(periodo-1)+g[i])/periodo
        ap = (ap*(periodo-1)+p[i])/periodo
        rsi_arr[i+1] = round(100-(100/(1+ag/ap)),1) if ap else 100.0
    return rsi_arr

def simular_trade(velas, idx, sl_pct, tp_pct):
    precio_entrada = velas[idx]['close']
    precio_tp = precio_entrada * (1 + tp_pct/100)
    precio_sl = precio_entrada * (1 - sl_pct/100)
    for i in range(idx+1, min(idx+201, len(velas))):
        if velas[i]['high'] >= precio_tp: return 'TP', i-idx
        if velas[i]['low']  <= precio_sl: return 'SL', i-idx
    return 'TIMEOUT', 200

def backtest_combinacion(velas, rsi_arr, sl, tp):
    tp_c = sl_c = timeout = 0
    en_trade   = False
    idx_salida = 0

    for i in range(20, len(velas)):
        if en_trade and i <= idx_salida:
            continue
        en_trade = False

        rsi = rsi_arr[i]
        if rsi is None or not (70 <= rsi <= 80):
            continue

        resultado, duracion = simular_trade(velas, i, sl, tp)
        if resultado == 'TP':   tp_c += 1
        elif resultado == 'SL': sl_c += 1
        else:                   timeout += 1
        idx_salida = i + duracion
        en_trade   = True

    total = tp_c + sl_c
    if total < 10: return None
    wr  = round(tp_c/total*100,1)
    pf  = round((tp_c*tp)/(sl_c*sl),2) if sl_c else 0
    años = (len(velas)*4)/(365*24)
    tm  = round((total+timeout)/años/12,1)
    return tp_c, sl_c, timeout, wr, pf, tm

def main():
    print("="*70)
    print("BACKTEST OPTIMIZACION TP/SL — RSI 70-80 — 9 AÑOS DATOS REALES")
    print("="*70)

    combos = len(TP_VALORES) * len(SL_VALORES)
    mejores_global = {}
    reporte = {}

    for symbol in SIMBOLOS:
        print(f"\nCargando {symbol}...", flush=True)
        try:
            velas = cargar_velas(symbol)
        except FileNotFoundError:
            print(f"  No encontrado")
            continue

        años = round((len(velas)*4)/(365*24),1)
        print(f"  {len(velas)} velas ({años} años)")
        print(f"  Probando {combos} combinaciones TP/SL...", flush=True)

        rsi_arr    = precalcular_rsi(velas)
        resultados = []

        for sl in SL_VALORES:
            for tp in TP_VALORES:
                if tp <= sl * 1.5: continue  # ratio mínimo 1.5
                r = backtest_combinacion(velas, rsi_arr, sl, tp)
                if r:
                    tp_c, sl_c, to, wr, pf, tm = r
                    resultados.append((sl, tp, tp_c, sl_c, to, wr, pf, tm))

        # Top 8 por PF
        top = sorted(resultados, key=lambda x: x[6], reverse=True)[:8]

        print(f"\n  {symbol} — Top 8 por PF:")
        print(f"  {'SL%':<6} {'TP%':<6} {'TP':<6} {'SL':<6} {'WR%':<8} {'PF':<8} {'T/mes':<8} {'Ratio'}")
        print("  "+"-"*60)
        for r in top:
            sl, tp, tp_c, sl_c, to, wr, pf, tm = r
            ratio = round(tp/sl,1)
            marca = " ✅" if pf >= 1.8 else ""
            print(f"  {sl:<6} {tp:<6} {tp_c:<6} {sl_c:<6} {wr:<8} {pf:<8} {tm:<8} {ratio}{marca}")

        mejores_global[symbol] = top[0] if top else None
        reporte[symbol] = [list(r) for r in top]

    print("\n"+"="*70)
    print("MEJOR COMBINACION POR MONEDA — 9 AÑOS")
    print("="*70)
    print(f"{'Moneda':<12} {'SL%':<6} {'TP%':<6} {'WR%':<8} {'PF':<8} {'T/mes':<8} {'Meta'}")
    print("-"*58)
    for symbol, r in mejores_global.items():
        if r:
            sl, tp, tp_c, sl_c, to, wr, pf, tm = r
            meta = "✅ PF≥1.8" if pf >= 1.8 else "❌"
            print(f"{symbol:<12} {sl:<6} {tp:<6} {wr:<8} {pf:<8} {tm:<8} {meta}")

    os.makedirs('/home/ariel/bot-padre-v2/reports', exist_ok=True)
    with open('/home/ariel/bot-padre-v2/reports/backtest_tp_sl_historico.json','w') as f:
        json.dump(reporte, f, indent=2)
    print("\nReporte guardado en reports/backtest_tp_sl_historico.json")

if __name__ == "__main__":
    main()
