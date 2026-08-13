# ============================================================
# backtest_frecuencia_calidad.py
# Busca el balance optimo entre frecuencia y calidad
# Meta: maximo trades/mes con PF > 1.5 sostenido
# Capital $20, riesgo 1% por trade
# SOLO LECTURA — no toca nada del bot
# ============================================================

import csv, os, json

SIMBOLOS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "AVAXUSDT"]
RUTA     = "/home/ariel/bot-padre-v3-backup/data/historico_4h/{}_4h.csv"

CAPITAL_INICIAL = 20.0
RIESGO_PCT      = 1.0

# Configuraciones a probar — variando rango RSI y momentum
CONFIGS = [
    {"rsi_min": 70, "rsi_max": 80, "mom_v": 4, "mom_m": 3, "sl": 2.0, "tp": 10.0, "label": "RSI70-80+mom3de4"},
    {"rsi_min": 65, "rsi_max": 80, "mom_v": 4, "mom_m": 3, "sl": 2.0, "tp": 10.0, "label": "RSI65-80+mom3de4"},
    {"rsi_min": 60, "rsi_max": 80, "mom_v": 4, "mom_m": 3, "sl": 2.0, "tp": 10.0, "label": "RSI60-80+mom3de4"},
    {"rsi_min": 70, "rsi_max": 80, "mom_v": 3, "mom_m": 2, "sl": 2.0, "tp": 10.0, "label": "RSI70-80+mom2de3"},
    {"rsi_min": 65, "rsi_max": 80, "mom_v": 3, "mom_m": 2, "sl": 2.0, "tp": 10.0, "label": "RSI65-80+mom2de3"},
    {"rsi_min": 60, "rsi_max": 80, "mom_v": 3, "mom_m": 2, "sl": 2.0, "tp": 10.0, "label": "RSI60-80+mom2de3"},
    {"rsi_min": 70, "rsi_max": 80, "mom_v": 2, "mom_m": 1, "sl": 2.0, "tp": 10.0, "label": "RSI70-80+mom1de2"},
    {"rsi_min": 65, "rsi_max": 80, "mom_v": 2, "mom_m": 1, "sl": 2.0, "tp": 10.0, "label": "RSI65-80+mom1de2"},
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
    if idx < n_velas: return False
    return sum(1 for j in range(idx-n_velas, idx)
               if velas[j]['close'] > velas[j]['open']) >= n_minimas

def simular_trade(velas, idx, sl_pct, tp_pct):
    precio_entrada = velas[idx]['close']
    precio_tp = precio_entrada * (1 + tp_pct/100)
    precio_sl = precio_entrada * (1 - sl_pct/100)
    for i in range(idx+1, min(idx+201, len(velas))):
        if velas[i]['high'] >= precio_tp: return 'TP', i-idx
        if velas[i]['low']  <= precio_sl: return 'SL', i-idx
    return 'TIMEOUT', 200

def backtest(velas, rsi_arr, cfg, capital_ini, riesgo_pct):
    capital     = capital_ini
    capital_max = capital_ini
    dd_max      = 0.0
    tp_c = sl_c = to_c = 0
    en_trade    = False
    idx_salida  = 0

    sl  = cfg['sl']
    tp  = cfg['tp']
    mv  = cfg['mom_v']
    mm  = cfg['mom_m']
    rsi_min = cfg['rsi_min']
    rsi_max = cfg['rsi_max']

    for i in range(20, len(velas)):
        if capital <= 0: break
        if en_trade and i <= idx_salida:
            continue
        en_trade = False

        rsi = rsi_arr[i]
        if rsi is None or not (rsi_min <= rsi <= rsi_max):
            continue
        if not tiene_momentum(velas, i, mv, mm):
            continue

        monto    = capital * (riesgo_pct/100)
        resultado, duracion = simular_trade(velas, i, sl, tp)

        if resultado == 'TP':
            capital += monto * (tp/sl)
            tp_c += 1
        elif resultado == 'SL':
            capital -= monto
            sl_c += 1
        else:
            to_c += 1

        if capital > capital_max:
            capital_max = capital
        dd = (capital_max - capital) / capital_max * 100
        if dd > dd_max:
            dd_max = dd

        idx_salida = i + duracion
        en_trade   = True

    total  = tp_c + sl_c
    wr     = round(tp_c/total*100,1) if total else 0
    pf     = round((tp_c*tp)/(sl_c*sl),2) if sl_c else 0
    años   = (len(velas)*4)/(365*24)
    tm     = round((total+to_c)/años/12,1)
    retorno= round((capital-capital_ini)/capital_ini*100,1)
    gan_mes= round((capital-capital_ini)/años/12,2)

    return {
        'tp': tp_c, 'sl': sl_c, 'to': to_c,
        'wr': wr, 'pf': pf, 'tm': tm,
        'capital_final': round(capital,2),
        'dd_max': round(dd_max,2),
        'retorno': retorno,
        'gan_mes': gan_mes,
    }

def main():
    print("="*75)
    print(f"BACKTEST FRECUENCIA vs CALIDAD — Capital ${CAPITAL_INICIAL} | Riesgo {RIESGO_PCT}%")
    print("RSI variable + MOMENTUM variable — 9 AÑOS DATOS REALES")
    print("="*75)

    reporte = {}

    for symbol in SIMBOLOS:
        print(f"\nCargando {symbol}...", flush=True)
        try:
            velas = cargar_velas(symbol)
        except FileNotFoundError:
            print(f"  No encontrado"); continue

        años = round((len(velas)*4)/(365*24),1)
        print(f"  {len(velas)} velas ({años} años)", flush=True)
        rsi_arr = precalcular_rsi(velas)

        resultados = []
        for cfg in CONFIGS:
            r = backtest(velas, rsi_arr, cfg, CAPITAL_INICIAL, RIESGO_PCT)
            resultados.append((cfg['label'], r))
            print(f"    {cfg['label']} listo", flush=True)

        print(f"\n  {symbol}:")
        print(f"  {'Config':<22} {'T/mes':<7} {'WR%':<7} {'PF':<7} {'DD%':<7} {'$/mes':<8} {'Capital$'}")
        print("  "+"-"*72)

        for label, r in sorted(resultados, key=lambda x: x[1]['gan_mes'], reverse=True):
            marca = " ✅" if r['pf'] >= 1.5 and r['tm'] >= 3 else ""
            print(f"  {label:<22} {r['tm']:<7} {r['wr']:<7} {r['pf']:<7} "
                  f"{r['dd_max']:<7} ${r['gan_mes']:<7} ${r['capital_final']}{marca}")

        reporte[symbol] = resultados

    print("\n"+"="*75)
    print("TOP COMBINACION POR MONEDA — Mayor $/mes con PF>1.5 y T/mes>3")
    print("="*75)
    print(f"{'Moneda':<12} {'Config':<22} {'T/mes':<7} {'PF':<7} {'DD%':<7} {'$/mes'}")
    print("-"*65)

    for symbol, resultados in reporte.items():
        viables = [(l,r) for l,r in resultados
                   if r['pf'] >= 1.5 and r['tm'] >= 3]
        if viables:
            mejor = max(viables, key=lambda x: x[1]['gan_mes'])
            l, r = mejor
            print(f"{symbol:<12} {l:<22} {r['tm']:<7} {r['pf']:<7} "
                  f"{r['dd_max']:<7} ${r['gan_mes']}")
        else:
            print(f"{symbol:<12} Sin combinación viable con T/mes≥3 y PF≥1.5")

    os.makedirs('/home/ariel/bot-padre-v2/reports', exist_ok=True)
    with open('/home/ariel/bot-padre-v2/reports/backtest_frecuencia_calidad.json','w') as f:
        json.dump({s: [(l,r) for l,r in rs]
                   for s,rs in reporte.items()}, f, indent=2)
    print("\nReporte guardado en reports/backtest_frecuencia_calidad.json")

if __name__ == "__main__":
    main()
