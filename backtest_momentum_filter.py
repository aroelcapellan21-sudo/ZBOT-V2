# ============================================================
# backtest_momentum_filter.py
# RSI 70-80 + confirmacion de momentum alcista
# Filtra entradas donde el precio ya está cayendo
# SOLO LECTURA — no toca nada del bot
# ============================================================

import csv, os, json

SIMBOLOS = ["ETHUSDT", "BTCUSDT", "SOLUSDT", "BNBUSDT", "AVAXUSDT"]
RUTA     = "/home/ariel/bot-padre-v3-backup/data/historico_4h/{}_4h.csv"

PARAMS = {
    "ETHUSDT":  {"sl": 2.5, "tp": 20.0},
    "BTCUSDT":  {"sl": 2.0, "tp": 10.0},
    "SOLUSDT":  {"sl": 1.5, "tp": 20.0},
    "BNBUSDT":  {"sl": 5.0, "tp": 20.0},
    "AVAXUSDT": {"sl": 4.0, "tp": 15.0},
}

# Filtros de momentum a probar
# Cuántas de las últimas N velas deben ser alcistas (close > open)
CONFIGS_MOMENTUM = [
    {"velas": 1, "minimas": 1},   # ultima vela alcista
    {"velas": 2, "minimas": 2},   # 2 de 2 alcistas
    {"velas": 3, "minimas": 2},   # 2 de 3 alcistas
    {"velas": 3, "minimas": 3},   # 3 de 3 alcistas
    {"velas": 4, "minimas": 3},   # 3 de 4 alcistas
    {"velas": 5, "minimas": 3},   # 3 de 5 alcistas
    {"velas": 5, "minimas": 4},   # 4 de 5 alcistas
]

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
    """True si al menos n_minimas de las últimas n_velas son alcistas."""
    if idx < n_velas: return False
    alcistas = sum(
        1 for j in range(idx-n_velas, idx)
        if velas[j]['close'] > velas[j]['open']
    )
    return alcistas >= n_minimas

def simular_trade(velas, idx, sl_pct, tp_pct):
    precio_entrada = velas[idx]['close']
    precio_tp = precio_entrada * (1 + tp_pct/100)
    precio_sl = precio_entrada * (1 - sl_pct/100)
    for i in range(idx+1, min(idx+201, len(velas))):
        if velas[i]['high'] >= precio_tp: return 'TP', i-idx
        if velas[i]['low']  <= precio_sl: return 'SL', i-idx
    return 'TIMEOUT', 200

def backtest(velas, rsi_arr, sl, tp, n_velas, n_minimas):
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

        if not tiene_momentum(velas, i, n_velas, n_minimas):
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
    print("BACKTEST RSI 70-80 + FILTRO MOMENTUM — 9 AÑOS DATOS REALES")
    print("="*70)

    reporte   = {}
    mejores_g = {}

    for symbol in SIMBOLOS:
        print(f"\nCargando {symbol}...", flush=True)
        try:
            velas = cargar_velas(symbol)
        except FileNotFoundError:
            print(f"  No encontrado"); continue

        años = round((len(velas)*4)/(365*24),1)
        print(f"  {len(velas)} velas ({años} años)", flush=True)

        rsi_arr = precalcular_rsi(velas)
        sl = PARAMS[symbol]['sl']
        tp = PARAMS[symbol]['tp']

        # Sin filtro primero
        r_base = backtest(velas, rsi_arr, sl, tp, 1, 0)
        if r_base:
            tp_c,sl_c,to,bl,wr,pf,tm = r_base
            print(f"  BASE (sin momentum): WR:{wr}% PF:{pf} T/mes:{tm}", flush=True)

        resultados = []
        for cfg in CONFIGS_MOMENTUM:
            r = backtest(velas, rsi_arr, sl, tp, cfg['velas'], cfg['minimas'])
            if r:
                tp_c,sl_c,to,bl,wr,pf,tm = r
                label = f"{cfg['minimas']}de{cfg['velas']}"
                resultados.append((label, cfg['velas'], cfg['minimas'],
                                   tp_c, sl_c, to, bl, wr, pf, tm))
            print(f"    Momentum {cfg['minimas']}de{cfg['velas']} listo", flush=True)

        print(f"\n  {symbol} — RSI 70-80 + Momentum:")
        print(f"  {'Filtro':<10} {'TP':<6} {'SL':<6} {'Bloq':<6} {'WR%':<8} {'PF':<8} {'T/mes'}")
        print("  "+"-"*58)
        for r in sorted(resultados, key=lambda x: x[8], reverse=True):
            label,nv,nm,tp_c,sl_c,to,bl,wr,pf,tm = r
            marca = " ✅" if pf >= 1.8 and wr >= 40 else (" ✅PF" if pf >= 1.8 else "")
            print(f"  {label:<10} {tp_c:<6} {sl_c:<6} {bl:<6} {wr:<8} {pf:<8} {tm}{marca}")

        mejor = sorted(resultados, key=lambda x: x[8], reverse=True)[0] if resultados else None
        mejores_g[symbol] = mejor
        reporte[symbol]   = [list(r) for r in resultados]

    print("\n"+"="*70)
    print("MEJOR FILTRO MOMENTUM POR MONEDA")
    print("="*70)
    print(f"{'Moneda':<12} {'Filtro':<10} {'WR%':<8} {'PF':<8} {'T/mes':<8} {'Meta'}")
    print("-"*55)
    for symbol, r in mejores_g.items():
        if r:
            label,nv,nm,tp_c,sl_c,to,bl,wr,pf,tm = r
            meta = "✅" if pf >= 1.8 else "❌"
            print(f"{symbol:<12} {label:<10} {wr:<8} {pf:<8} {tm:<8} {meta}")

    os.makedirs('/home/ariel/bot-padre-v2/reports', exist_ok=True)
    with open('/home/ariel/bot-padre-v2/reports/backtest_momentum_filter.json','w') as f:
        json.dump(reporte, f, indent=2)
    print("\nReporte guardado en reports/backtest_momentum_filter.json")

if __name__ == "__main__":
    main()
