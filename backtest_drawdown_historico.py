# ============================================================
# backtest_drawdown_historico.py
# Calcula drawdown maximo historico con RSI 70-80 + momentum
# Valida si el bot puede mantener drawdown < 10%
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

CAPITAL_INICIAL = 1000.0

def cargar_velas(symbol):
    velas = []
    with open(RUTA.format(symbol), newline='') as f:
        for row in csv.DictReader(f):
            try:
                velas.append({
                    'ts':    row['timestamp'],
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
        if velas[i]['high'] >= precio_tp:
            return 'TP', i-idx, velas[i]['ts']
        if velas[i]['low'] <= precio_sl:
            return 'SL', i-idx, velas[i]['ts']
    return 'TIMEOUT', 200, velas[min(idx+200, len(velas)-1)]['ts']

def backtest_con_capital(velas, rsi_arr, sl, tp, mom_v, mom_m,
                         capital_inicial, riesgo_pct=0.03):
    capital      = capital_inicial
    capital_max  = capital_inicial
    drawdown_max = 0.0
    trades       = []
    en_trade     = False
    idx_salida   = 0
    rachas_sl    = 0
    max_rachas_sl= 0
    cur_racha    = 0

    for i in range(20, len(velas)):
        if en_trade and i <= idx_salida:
            continue
        en_trade = False

        rsi = rsi_arr[i]
        if rsi is None or not (70 <= rsi <= 80):
            continue
        if not tiene_momentum(velas, i, mom_v, mom_m):
            continue

        # Monto fijo: riesgo_pct del capital actual
        monto     = capital * riesgo_pct
        resultado, duracion, ts_sal = simular_trade(velas, i, sl, tp)

        if resultado == 'TP':
            ganancia = monto * (tp/sl)  # ratio tp/sl aplicado al monto en riesgo
            capital += ganancia
            cur_racha = 0
        elif resultado == 'SL':
            capital -= monto
            cur_racha += 1
            max_rachas_sl = max(max_rachas_sl, cur_racha)
        else:
            cur_racha = 0

        # Drawdown
        if capital > capital_max:
            capital_max = capital
        dd = (capital_max - capital) / capital_max * 100
        if dd > drawdown_max:
            drawdown_max = dd

        trades.append({
            'ts':        velas[i]['ts'],
            'ts_sal':    ts_sal,
            'resultado': resultado,
            'capital':   round(capital, 2),
            'drawdown':  round(dd, 2),
        })

        idx_salida = i + duracion
        en_trade   = True

    return trades, round(drawdown_max, 2), round(capital, 2), max_rachas_sl

def main():
    print("="*70)
    print("BACKTEST DRAWDOWN — RSI 70-80 + MOMENTUM — 9 AÑOS")
    print(f"Capital inicial: ${CAPITAL_INICIAL} | Riesgo por trade: 3%")
    print("="*70)

    reporte = {}
    todos_trades = []

    for symbol in SIMBOLOS:
        cfg = CONFIGS[symbol]
        print(f"\nCargando {symbol}...", flush=True)
        try:
            velas = cargar_velas(symbol)
        except FileNotFoundError:
            print(f"  No encontrado"); continue

        años = round((len(velas)*4)/(365*24),1)
        print(f"  {len(velas)} velas ({años} años)", flush=True)

        rsi_arr = precalcular_rsi(velas)
        trades, dd_max, capital_final, max_racha = backtest_con_capital(
            velas, rsi_arr,
            cfg['sl'], cfg['tp'], cfg['mom_v'], cfg['mom_m'],
            CAPITAL_INICIAL, riesgo_pct=0.03
        )

        tp_c  = sum(1 for t in trades if t['resultado']=='TP')
        sl_c  = sum(1 for t in trades if t['resultado']=='SL')
        to_c  = sum(1 for t in trades if t['resultado']=='TIMEOUT')
        total = tp_c + sl_c
        wr    = round(tp_c/total*100,1) if total else 0
        retorno = round((capital_final-CAPITAL_INICIAL)/CAPITAL_INICIAL*100,1)

        # Meses con drawdown > 5% y > 10%
        dd5  = sum(1 for t in trades if t['drawdown'] > 5)
        dd10 = sum(1 for t in trades if t['drawdown'] > 10)

        marca_dd = "✅" if dd_max < 10 else "❌ VIOLA REGLA"

        print(f"\n  {symbol}:")
        print(f"  TP:{tp_c} SL:{sl_c} TO:{to_c} | WR:{wr}%")
        print(f"  Capital final: ${capital_final} | Retorno: {retorno}%")
        print(f"  Drawdown máximo: {dd_max}% {marca_dd}")
        print(f"  Momentos con DD>5%: {dd5} trades")
        print(f"  Momentos con DD>10%: {dd10} trades")
        print(f"  Racha máx SL seguidos: {max_racha}")

        reporte[symbol] = {
            'dd_max': dd_max,
            'capital_final': capital_final,
            'retorno_pct': retorno,
            'wr': wr,
            'max_racha_sl': max_racha,
            'dd10_count': dd10,
        }
        todos_trades.extend(trades)

    # Análisis combinado — si el bot opera las 5 monedas simultáneamente
    print("\n"+"="*70)
    print("RESUMEN — RIESGO DE VIOLAR REGLA DRAWDOWN 10%")
    print("="*70)
    print(f"{'Moneda':<12} {'DD Max%':<10} {'Racha SL':<10} {'Retorno%':<12} {'Regla'}")
    print("-"*55)
    for symbol, r in reporte.items():
        marca = "✅ OK" if r['dd_max'] < 10 else "❌ VIOLA"
        print(f"{symbol:<12} {r['dd_max']:<10} {r['max_racha_sl']:<10} "
              f"{r['retorno_pct']:<12} {marca}")

    os.makedirs('/home/ariel/bot-padre-v2/reports', exist_ok=True)
    with open('/home/ariel/bot-padre-v2/reports/backtest_drawdown.json','w') as f:
        json.dump(reporte, f, indent=2)
    print("\nReporte guardado en reports/backtest_drawdown.json")

if __name__ == "__main__":
    main()
