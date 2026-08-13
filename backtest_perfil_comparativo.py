# ============================================================
# backtest_perfil_comparativo.py
# Compara 3 perfiles con $20 capital, $5 por trade
# Datos historicos reales 4H
# SOLO LECTURA — no toca nada del bot
# ============================================================

import csv, os, json

RUTA = "/home/ariel/bot-padre-v3-backup/data/historico_4h/{}_4h.csv"

CAPITAL_INICIAL = 20.0
MONTO_FIJO      = 5.0  # fijo, no porcentaje

# Parametros actuales del bot
PARAMS = {
    "BTCUSDT": {
        "alcista": {"rsi_min": 55, "rsi_max": 75, "sl": 5.0, "tp": 6.0},
        "bajista": {"rsi_min": 30, "rsi_max": 50, "sl": 3.5, "tp": 4.0},
        "lateral": {"rsi_min": 43, "rsi_max": 57, "sl": 3.5, "tp": 4.0},
    },
    "ETHUSDT": {
        "alcista": {"rsi_min": 60, "rsi_max": 75, "sl": 4.5, "tp": 5.0},
        "bajista": {"rsi_min": 30, "rsi_max": 50, "sl": 3.0, "tp": 4.0},
        "lateral": {"rsi_min": 43, "rsi_max": 57, "sl": 4.5, "tp": 6.0},
    },
    "SOLUSDT": {
        "alcista": {"rsi_min": 50, "rsi_max": 70, "sl": 5.0, "tp": 6.0},
        "bajista": {"rsi_min": 30, "rsi_max": 50, "sl": 3.5, "tp": 5.0},
        "lateral": {"rsi_min": 43, "rsi_max": 57, "sl": 3.5, "tp": 4.0},
    },
    "BNBUSDT": {
        "alcista": {"rsi_min": 60, "rsi_max": 75, "sl": 4.5, "tp": 5.0},
        "bajista": {"rsi_min": 30, "rsi_max": 50, "sl": 3.5, "tp": 4.0},
        "lateral": {"rsi_min": 43, "rsi_max": 57, "sl": 4.5, "tp": 5.0},
    },
    "AVAXUSDT": {
        "alcista": {"rsi_min": 60, "rsi_max": 75, "sl": 4.5, "tp": 5.0},
        "bajista": {"rsi_min": 30, "rsi_max": 50, "sl": 3.5, "tp": 4.0},
        "lateral": {"rsi_min": 43, "rsi_max": 57, "sl": 5.0, "tp": 6.0},
    },
}

# Perfiles a comparar
PERFILES = {
    "5_monedas_completo": {
        "simbolos": ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","AVAXUSDT"],
        "fases":    ["alcista","bajista","lateral"],
    },
    "ETH_BTC_sin_bajistas": {
        "simbolos": ["BTCUSDT","ETHUSDT"],
        "fases":    ["alcista","lateral"],
    },
    "solo_ETH_sin_bajistas": {
        "simbolos": ["ETHUSDT"],
        "fases":    ["alcista","lateral"],
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

def backtest_perfil(simbolos, fases_permitidas, velas_cache, rsi_cache):
    # Usar el período común a todas las monedas (desde 2021 para incluir SOL/AVAX)
    FECHA_INICIO = "2021-01-01"

    capital     = CAPITAL_INICIAL
    capital_max = CAPITAL_INICIAL
    dd_max      = 0.0
    tp_c = sl_c = to_c = 0
    por_mes     = {}

    # Combinar todos los trades de todas las monedas en orden cronológico
    todos_trades = []
    for symbol in simbolos:
        velas   = velas_cache[symbol]
        rsi_arr = rsi_cache[symbol]
        params  = PARAMS[symbol]

        en_trade   = False
        idx_salida = 0

        for i in range(20, len(velas)):
            if velas[i]['ts'] < FECHA_INICIO:
                continue
            if en_trade and i <= idx_salida:
                continue
            en_trade = False

            rsi = rsi_arr[i]
            if rsi is None: continue

            fase = None
            for f in fases_permitidas:
                p = params.get(f)
                if p and p['rsi_min'] <= rsi <= p['rsi_max']:
                    fase = f
                    break
            if fase is None: continue

            resultado, duracion = simular_trade(
                velas, i,
                params[fase]['sl'],
                params[fase]['tp']
            )

            todos_trades.append({
                'ts':       velas[i]['ts'],
                'symbol':   symbol,
                'fase':     fase,
                'resultado': resultado,
                'sl':       params[fase]['sl'],
                'tp':       params[fase]['tp'],
                'idx_sal':  i + duracion,
            })

            idx_salida = i + duracion
            en_trade   = True

    # Ordenar por timestamp y simular con capital compartido
    todos_trades.sort(key=lambda x: x['ts'])

    for t in todos_trades:
        if capital < MONTO_FIJO:
            break

        monto = MONTO_FIJO
        if t['resultado'] == 'TP':
            ganancia = monto * (t['tp'] / t['sl'])
            capital += ganancia
            tp_c += 1
        elif t['resultado'] == 'SL':
            capital -= monto
            sl_c += 1
        else:
            to_c += 1

        if capital > capital_max:
            capital_max = capital
        dd = (capital_max - capital) / capital_max * 100
        if dd > dd_max:
            dd_max = dd

        mes = t['ts'][:7]
        if mes not in por_mes:
            por_mes[mes] = {'TP':0,'SL':0,'TO':0,'TIMEOUT':0,'capital':0}
        por_mes[mes][t['resultado']] += 1
        por_mes[mes]['capital'] = round(capital, 2)

    total   = tp_c + sl_c
    wr      = round(tp_c/total*100,1) if total else 0
    años    = 4.0  # 2021-2025
    tm      = round((total+to_c)/años/12,1)
    retorno = round((capital-CAPITAL_INICIAL)/CAPITAL_INICIAL*100,1)
    gan_mes = round((capital-CAPITAL_INICIAL)/años/12,2)
    pf      = round((tp_c*5)/(sl_c*3),2) if sl_c else 0

    return {
        'tp': tp_c, 'sl': sl_c, 'to': to_c,
        'wr': wr, 'tm': tm, 'pf': pf,
        'capital_final': round(capital,2),
        'dd_max': round(dd_max,2),
        'retorno': retorno,
        'gan_mes': gan_mes,
        'por_mes': por_mes,
    }

def main():
    print("="*70)
    print(f"COMPARACION DE PERFILES — Capital ${CAPITAL_INICIAL} | Monto fijo ${MONTO_FIJO}")
    print("Periodo: 2021-2025 | Datos reales 4H")
    print("="*70)

    # Cargar todas las velas una sola vez
    print("\nCargando datos...", flush=True)
    todos_simbolos = ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","AVAXUSDT"]
    velas_cache = {}
    rsi_cache   = {}
    for symbol in todos_simbolos:
        try:
            velas_cache[symbol] = cargar_velas(symbol)
            rsi_cache[symbol]   = precalcular_rsi(velas_cache[symbol])
            print(f"  {symbol} listo", flush=True)
        except FileNotFoundError:
            print(f"  {symbol} no encontrado")

    resultados = {}
    for nombre, cfg in PERFILES.items():
        print(f"\nSimulando: {nombre}...", flush=True)
        r = backtest_perfil(
            cfg['simbolos'], cfg['fases'],
            velas_cache, rsi_cache
        )
        resultados[nombre] = r

        print(f"  TP:{r['tp']} SL:{r['sl']} | WR:{r['wr']}% PF:{r['pf']}")
        print(f"  Capital: ${CAPITAL_INICIAL} → ${r['capital_final']} ({r['retorno']}%)")
        print(f"  DD max: {r['dd_max']}% | T/mes: {r['tm']} | $/mes: ${r['gan_mes']}")

        print(f"  Por año:")
        años_data = {}
        for mes, m in r['por_mes'].items():
            año = mes[:4]
            if año not in años_data:
                años_data[año] = {'TP':0,'SL':0,'capital':0}
            años_data[año]['TP'] += m['TP']
            años_data[año]['SL'] += m['SL']
            años_data[año]['capital'] = m['capital']
        for año in sorted(años_data):
            d = años_data[año]
            t = d['TP']+d['SL']
            wr = round(d['TP']/t*100,1) if t else 0
            print(f"    {año}: TP:{d['TP']} SL:{d['SL']} WR:{wr}% Capital:${d['capital']}")

    print("\n"+"="*70)
    print("COMPARACION FINAL")
    print("="*70)
    print(f"{'Perfil':<28} {'WR%':<7} {'PF':<7} {'DD%':<7} {'$/mes':<9} {'Capital$'}")
    print("-"*65)
    for nombre, r in resultados.items():
        print(f"{nombre:<28} {r['wr']:<7} {r['pf']:<7} {r['dd_max']:<7} "
              f"${r['gan_mes']:<8} ${r['capital_final']}")

    os.makedirs('/home/ariel/bot-padre-v2/reports', exist_ok=True)
    with open('/home/ariel/bot-padre-v2/reports/backtest_perfil_comparativo.json','w') as f:
        json.dump(resultados, f, indent=2)
    print("\nReporte guardado en reports/backtest_perfil_comparativo.json")

if __name__ == "__main__":
    main()
