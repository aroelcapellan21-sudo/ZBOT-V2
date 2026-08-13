# ============================================================
# backtest_anatomia_tp_sl.py
# Analiza qué caracteristicas tienen los TP vs SL
# RSI 70-80 + momentum 3de4 (BTC) y 3de5 (ETH)
# SOLO LECTURA — no toca nada del bot
# ============================================================

import csv, os, json

SIMBOLOS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
RUTA     = "/home/ariel/bot-padre-v3-backup/data/historico_4h/{}_4h.csv"

CONFIGS = {
    "BTCUSDT": {"sl": 2.0, "tp": 10.0, "mom_v": 4, "mom_m": 3},
    "ETHUSDT": {"sl": 2.5, "tp": 20.0, "mom_v": 5, "mom_m": 3},
    "SOLUSDT": {"sl": 1.5, "tp": 20.0, "mom_v": 5, "mom_m": 4},
}

def cargar_velas(symbol):
    velas = []
    with open(RUTA.format(symbol), newline='') as f:
        for row in csv.DictReader(f):
            try:
                velas.append({
                    'open':   float(row['open']),
                    'high':   float(row['high']),
                    'low':    float(row['low']),
                    'close':  float(row['close']),
                    'volume': float(row['volume']),
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

def volumen_relativo(velas, idx, ventana=20):
    """Volumen actual vs promedio de últimas N velas."""
    if idx < ventana: return 1.0
    vol_prom = sum(velas[j]['volume'] for j in range(idx-ventana, idx)) / ventana
    return round(velas[idx]['volume'] / vol_prom, 2) if vol_prom else 1.0

def cuerpo_vela(vela):
    """% de cuerpo vs rango total de la vela."""
    rango = vela['high'] - vela['low']
    if rango == 0: return 0
    cuerpo = abs(vela['close'] - vela['open'])
    return round(cuerpo/rango*100, 1)

def cambio_precio_previo(velas, idx, n=5):
    """% de cambio en las últimas N velas."""
    if idx < n: return 0
    inicio = velas[idx-n]['close']
    fin    = velas[idx]['close']
    return round((fin-inicio)/inicio*100, 2)

def simular_trade(velas, idx, sl_pct, tp_pct):
    precio_entrada = velas[idx]['close']
    precio_tp = precio_entrada * (1 + tp_pct/100)
    precio_sl = precio_entrada * (1 - sl_pct/100)
    for i in range(idx+1, min(idx+201, len(velas))):
        if velas[i]['high'] >= precio_tp: return 'TP', i-idx
        if velas[i]['low']  <= precio_sl: return 'SL', i-idx
    return 'TIMEOUT', 200

def main():
    print("="*70)
    print("ANATOMIA TP vs SL — RSI 70-80 + MOMENTUM — 9 AÑOS")
    print("="*70)

    reporte = {}

    for symbol in SIMBOLOS:
        cfg = CONFIGS[symbol]
        sl  = cfg['sl']
        tp  = cfg['tp']
        mv  = cfg['mom_v']
        mm  = cfg['mom_m']

        print(f"\nCargando {symbol}...", flush=True)
        velas   = cargar_velas(symbol)
        rsi_arr = precalcular_rsi(velas)

        tp_datos = []
        sl_datos = []
        en_trade   = False
        idx_salida = 0

        for i in range(20, len(velas)):
            if en_trade and i <= idx_salida:
                continue
            en_trade = False

            rsi = rsi_arr[i]
            if rsi is None or not (70 <= rsi <= 80):
                continue
            if not tiene_momentum(velas, i, mv, mm):
                continue

            # Características de la entrada
            vol_rel  = volumen_relativo(velas, i)
            cuerpo   = cuerpo_vela(velas[i])
            cambio5  = cambio_precio_previo(velas, i, 5)
            cambio10 = cambio_precio_previo(velas, i, 10)
            cambio20 = cambio_precio_previo(velas, i, 20)

            resultado, duracion = simular_trade(velas, i, sl, tp)
            datos = {
                'rsi':      rsi,
                'vol_rel':  vol_rel,
                'cuerpo':   cuerpo,
                'cambio5':  cambio5,
                'cambio10': cambio10,
                'cambio20': cambio20,
                'duracion': duracion,
            }

            if resultado == 'TP':
                tp_datos.append(datos)
            elif resultado == 'SL':
                sl_datos.append(datos)

            idx_salida = i + duracion
            en_trade   = True

        def prom(lista, campo):
            vals = [d[campo] for d in lista]
            return round(sum(vals)/len(vals),2) if vals else 0

        print(f"\n  {symbol} — TP:{len(tp_datos)} vs SL:{len(sl_datos)}")
        print(f"  {'Campo':<15} {'Prom TP':>10} {'Prom SL':>10} {'Diferencia':>12}")
        print("  "+"-"*50)
        campos = ['rsi','vol_rel','cuerpo','cambio5','cambio10','cambio20','duracion']
        for campo in campos:
            pt = prom(tp_datos, campo)
            ps = prom(sl_datos, campo)
            diff = round(pt-ps, 2)
            signo = "↑TP" if diff > 0 else "↓SL"
            print(f"  {campo:<15} {pt:>10} {ps:>10} {diff:>+10} {signo}")

        reporte[symbol] = {
            'tp_count': len(tp_datos),
            'sl_count': len(sl_datos),
            'tp_prom':  {c: prom(tp_datos,c) for c in campos},
            'sl_prom':  {c: prom(sl_datos,c) for c in campos},
        }

    os.makedirs('/home/ariel/bot-padre-v2/reports', exist_ok=True)
    with open('/home/ariel/bot-padre-v2/reports/backtest_anatomia_tp_sl.json','w') as f:
        json.dump(reporte, f, indent=2)
    print(f"\nReporte guardado en reports/backtest_anatomia_tp_sl.json")

if __name__ == "__main__":
    main()
