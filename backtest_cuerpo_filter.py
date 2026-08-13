# ============================================================
# backtest_cuerpo_filter.py
# RSI 70-80 + Momentum + Filtro de cuerpo de vela < umbral%
# SOLO LECTURA — no toca nada del bot
# ============================================================

import csv, os, json

SIMBOLOS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "AVAXUSDT"]
RUTA     = "/home/ariel/bot-padre-v3-backup/data/historico_4h/{}_4h.csv"

CONFIGS = {
    "BTCUSDT": {"sl": 2.0, "tp": 10.0, "mom_v": 4, "mom_m": 3},
    "ETHUSDT": {"sl": 2.5, "tp": 20.0, "mom_v": 5, "mom_m": 3},
    "SOLUSDT": {"sl": 1.5, "tp": 20.0, "mom_v": 5, "mom_m": 4},
    "BNBUSDT": {"sl": 5.0, "tp": 20.0, "mom_v": 2, "mom_m": 2},
    "AVAXUSDT":{"sl": 4.0, "tp": 15.0, "mom_v": 3, "mom_m": 3},
}

# Umbrales de cuerpo a probar
UMBRALES_CUERPO = [30, 35, 40, 45, 50, 55, 60]

def cargar_velas(symbol):
    velas = []
    with open(RUTA.format(symbol), newline='') as f:
        for row in csv.DictReader(f):
            try:
                velas.append({
                    'open':  float(row['open']),
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

def tiene_momentum(velas, idx, n_velas, n_minimas):
    if idx < n_velas: return False
    alcistas = sum(1 for j in range(idx-n_velas, idx)
                   if velas[j]['close'] > velas[j]['open'])
    return alcistas >= n_minimas

def cuerpo_pct(vela):
    rango = vela['high'] - vela['low']
    if rango == 0: return 0
    return abs(vela['close'] - vela['open']) / rango * 100

def simular_trade(velas, idx, sl_pct, tp_pct):
    precio_entrada = velas[idx]['close']
    precio_tp = precio_entrada * (1 + tp_pct/100)
    precio_sl = precio_entrada * (1 - sl_pct/100)
    for i in range(idx+1, min(idx+201, len(velas))):
        if velas[i]['high'] >= precio_tp: return 'TP', i-idx
        if velas[i]['low']  <= precio_sl: return 'SL', i-idx
    return 'TIMEOUT', 200

def backtest(velas, rsi_arr, sl, tp, mom_v, mom_m, umbral_cuerpo=None):
    tp_c = sl_c = timeout = bloq = 0
    en_trade   = False
    idx_salida = 0

    for i in range(20, len(velas)):
        if en_trade and i <= idx_salida:
            continue
        en_trade = False

        rsi = rsi_arr[i]
        if rsi is None or not (70 <= rsi <= 80):
            continue
        if not tiene_momentum(velas, i, mom_v, mom_m):
            continue
        if umbral_cuerpo is not None:
            if cuerpo_pct(velas[i]) >= umbral_cuerpo:
                bloq += 1
                continue

        resultado, duracion = simular_trade(velas, i, sl, tp)
        if resultado == 'TP':   tp_c += 1
        elif resultado == 'SL': sl_c += 1
        else:                   timeout += 1
        idx_salida = i + duracion
        en_trade   = True

    total = tp_c + sl_c
    if total < 5: return None
    wr  = round(tp_c/total*100,1)
    pf  = round((tp_c*tp)/(sl_c*sl),2) if sl_c else 0
    años = (len(velas)*4)/(365*24)
    tm  = round((total+timeout)/años/12,1)
    return tp_c, sl_c, timeout, bloq, wr, pf, tm

def main():
    print("="*70)
    print("BACKTEST RSI 70-80 + MOMENTUM + FILTRO CUERPO — 9 AÑOS")
    print("="*70)

    reporte   = {}
    mejores_g = {}

    for symbol in SIMBOLOS:
        cfg    = CONFIGS[symbol]
        sl     = cfg['sl']
        tp     = cfg['tp']
        mom_v  = cfg['mom_v']
        mom_m  = cfg['mom_m']

        print(f"\nCargando {symbol}...", flush=True)
        try:
            velas = cargar_velas(symbol)
        except FileNotFoundError:
            print(f"  No encontrado"); continue

        años = round((len(velas)*4)/(365*24),1)
        print(f"  {len(velas)} velas ({años} años)", flush=True)
        rsi_arr = precalcular_rsi(velas)

        # Base sin filtro cuerpo
        r_base = backtest(velas, rsi_arr, sl, tp, mom_v, mom_m, None)
        if r_base:
            tp_c,sl_c,to,bl,wr,pf,tm = r_base
            print(f"  BASE: WR:{wr}% PF:{pf} T/mes:{tm}", flush=True)

        resultados = []
        for umbral in UMBRALES_CUERPO:
            r = backtest(velas, rsi_arr, sl, tp, mom_v, mom_m, umbral)
            if r:
                tp_c,sl_c,to,bl,wr,pf,tm = r
                resultados.append((umbral, tp_c, sl_c, to, bl, wr, pf, tm))
            print(f"    Cuerpo <{umbral}% listo", flush=True)

        print(f"\n  {symbol} — RSI 70-80 + Momentum + Cuerpo:")
        print(f"  {'Cuerpo<':<10} {'TP':<6} {'SL':<6} {'Bloq':<6} {'WR%':<8} {'PF':<8} {'T/mes'}")
        print("  "+"-"*58)
        for r in sorted(resultados, key=lambda x: x[6], reverse=True):
            u,tp_c,sl_c,to,bl,wr,pf,tm = r
            marca = " ✅" if pf >= 1.8 and wr >= 35 else (" ✅PF" if pf >= 1.8 else "")
            print(f"  {u}%{'':<7} {tp_c:<6} {sl_c:<6} {bl:<6} {wr:<8} {pf:<8} {tm}{marca}")

        mejor = sorted(resultados, key=lambda x: x[6], reverse=True)[0] if resultados else None
        mejores_g[symbol] = mejor
        reporte[symbol]   = [list(r) for r in resultados]

    print("\n"+"="*70)
    print("MEJOR FILTRO CUERPO POR MONEDA — 9 AÑOS")
    print("="*70)
    print(f"{'Moneda':<12} {'Cuerpo<':<10} {'WR%':<8} {'PF':<8} {'T/mes':<8} {'Meta'}")
    print("-"*55)
    for symbol, r in mejores_g.items():
        if r:
            u,tp_c,sl_c,to,bl,wr,pf,tm = r
            meta = "✅ PF≥1.8" if pf >= 1.8 else "❌"
            print(f"{symbol:<12} <{u}%{'':<6} {wr:<8} {pf:<8} {tm:<8} {meta}")

    os.makedirs('/home/ariel/bot-padre-v2/reports', exist_ok=True)
    with open('/home/ariel/bot-padre-v2/reports/backtest_cuerpo_filter.json','w') as f:
        json.dump(reporte, f, indent=2)
    print("\nReporte guardado en reports/backtest_cuerpo_filter.json")

if __name__ == "__main__":
    main()
