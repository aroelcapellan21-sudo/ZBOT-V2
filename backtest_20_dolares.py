# ============================================================
# backtest_20_dolares.py
# Simula el bot con $20 de capital y 25% por trade
# Usando configuracion ACTUAL del bot (no filtros nuevos)
# RSI actual + fases actuales
# SOLO LECTURA — no toca nada del bot
# ============================================================

import csv, os, json

SIMBOLOS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "AVAXUSDT"]
RUTA     = "/home/ariel/bot-padre-v3-backup/data/historico_4h/{}_4h.csv"

CAPITAL_INICIAL  = 20.0
CAPITAL_MAX_POR_OP = 0.25
MONTO_MINIMO     = 5.0

# Parametros ACTUALES del bot — sin cambiar nada
PARAMS = {
    "BTCUSDT": {
        "alcista": {"rsi_min": 55, "rsi_max": 75, "sl": 5.0, "tp": 6.0},
        "lateral": {"rsi_min": 43, "rsi_max": 57, "sl": 3.5, "tp": 4.0},
    },
    "ETHUSDT": {
        "alcista": {"rsi_min": 60, "rsi_max": 75, "sl": 4.5, "tp": 5.0},
        "lateral": {"rsi_min": 43, "rsi_max": 57, "sl": 4.5, "tp": 6.0},
    },
    "SOLUSDT": {
        "alcista": {"rsi_min": 50, "rsi_max": 70, "sl": 5.0, "tp": 6.0},
        "lateral": {"rsi_min": 43, "rsi_max": 57, "sl": 3.5, "tp": 4.0},
    },
    "BNBUSDT": {
        "alcista": {"rsi_min": 60, "rsi_max": 75, "sl": 4.5, "tp": 5.0},
        "lateral": {"rsi_min": 43, "rsi_max": 57, "sl": 4.5, "tp": 5.0},
    },
    "AVAXUSDT": {
        "alcista": {"rsi_min": 60, "rsi_max": 75, "sl": 4.5, "tp": 5.0},
        "lateral": {"rsi_min": 43, "rsi_max": 57, "sl": 5.0, "tp": 6.0},
    },
}

def cargar_velas(symbol):
    velas = []
    with open(RUTA.format(symbol), newline='') as f:
        for row in csv.DictReader(f):
            try:
                velas.append({
                    'ts':    row['timestamp'],
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
    for i in range(idx+1, min(idx+101, len(velas))):
        if velas[i]['high'] >= precio_tp: return 'TP', i-idx
        if velas[i]['low']  <= precio_sl: return 'SL', i-idx
    return 'TIMEOUT', 100

def backtest_symbol(symbol, velas, rsi_arr, capital_ini):
    capital      = capital_ini
    capital_max  = capital_ini
    dd_max       = 0.0
    tp_c = sl_c = to_c = rechazados = 0
    en_trade     = False
    idx_salida   = 0
    historial    = []

    fases_params = PARAMS[symbol]

    for i in range(20, len(velas)):
        if en_trade and i <= idx_salida:
            continue
        en_trade = False

        rsi = rsi_arr[i]
        if rsi is None: continue

        # Detectar fase por RSI
        fase = None
        for f, p in fases_params.items():
            if p['rsi_min'] <= rsi <= p['rsi_max']:
                fase = f
                params = p
                break
        if fase is None: continue

        # Calcular monto
        monto = capital * CAPITAL_MAX_POR_OP
        if monto < MONTO_MINIMO:
            rechazados += 1
            continue

        resultado, duracion = simular_trade(
            velas, i, params['sl'], params['tp']
        )

        if resultado == 'TP':
            ganancia = monto * (params['tp'] / params['sl'])
            capital += ganancia
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

        mes = velas[i]['ts'][:7]
        historial.append({
            'mes': mes,
            'resultado': resultado,
            'capital': round(capital, 2),
            'monto': round(monto, 2),
        })

        idx_salida = i + duracion
        en_trade   = True

    # Resumen por mes
    por_mes = {}
    for h in historial:
        m = h['mes']
        if m not in por_mes:
            por_mes[m] = {'TP':0,'SL':0,'TO':0,'capital_fin':0}
        por_mes[m][h['resultado']] += 1
        por_mes[m]['capital_fin'] = h['capital']

    total = tp_c + sl_c
    wr    = round(tp_c/total*100,1) if total else 0
    años  = (len(velas)*4)/(365*24)
    tm    = round((total+to_c)/años/12,1)
    retorno = round((capital-capital_ini)/capital_ini*100,1)
    gan_mes = round((capital-capital_ini)/años/12,2)

    return {
        'tp': tp_c, 'sl': sl_c, 'to': to_c,
        'rechazados': rechazados,
        'wr': wr, 'tm': tm,
        'capital_final': round(capital,2),
        'dd_max': round(dd_max,2),
        'retorno': retorno,
        'gan_mes': gan_mes,
        'por_mes': por_mes,
    }

def main():
    print("="*70)
    print(f"BACKTEST REAL — Capital ${CAPITAL_INICIAL} | {CAPITAL_MAX_POR_OP*100}% por trade")
    print("Configuracion ACTUAL del bot — 9 años datos reales")
    print("="*70)

    reporte = {}
    capital_combinado = CAPITAL_INICIAL

    for symbol in SIMBOLOS:
        print(f"\nCargando {symbol}...", flush=True)
        try:
            velas = cargar_velas(symbol)
        except FileNotFoundError:
            print(f"  No encontrado"); continue

        años = round((len(velas)*4)/(365*24),1)
        rsi_arr = precalcular_rsi(velas)
        r = backtest_symbol(symbol, velas, rsi_arr, CAPITAL_INICIAL)

        print(f"\n  {symbol} ({años} años):")
        print(f"  TP:{r['tp']} SL:{r['sl']} TO:{r['to']} Rechazados:{r['rechazados']}")
        print(f"  WR:{r['wr']}% | T/mes:{r['tm']} | DD max:{r['dd_max']}%")
        print(f"  Capital: ${CAPITAL_INICIAL} → ${r['capital_final']} ({r['retorno']}%)")
        print(f"  Ganancia promedio: ${r['gan_mes']}/mes")

        print(f"  Últimos 6 meses:")
        meses = sorted(r['por_mes'].keys())[-6:]
        for mes in meses:
            m = r['por_mes'][mes]
            total = m['TP']+m['SL']
            wr = round(m['TP']/total*100,1) if total else 0
            print(f"    {mes}: TP:{m['TP']} SL:{m['SL']} WR:{wr}% Capital:${m['capital_fin']}")

        reporte[symbol] = r

    print("\n"+"="*70)
    print("RESUMEN FINAL — LAS 5 MONEDAS")
    print("="*70)
    print(f"{'Moneda':<12} {'WR%':<8} {'T/mes':<8} {'DD%':<8} {'$/mes':<10} {'Capital final'}")
    print("-"*58)
    for symbol, r in reporte.items():
        print(f"{symbol:<12} {r['wr']:<8} {r['tm']:<8} {r['dd_max']:<8} "
              f"${r['gan_mes']:<9} ${r['capital_final']}")

    os.makedirs('/home/ariel/bot-padre-v2/reports', exist_ok=True)
    with open('/home/ariel/bot-padre-v2/reports/backtest_20_dolares.json','w') as f:
        json.dump(reporte, f, indent=2)
    print("\nReporte guardado en reports/backtest_20_dolares.json")

if __name__ == "__main__":
    main()
