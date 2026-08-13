# ============================================================
# backtest_rsi_rangos.py
# Prueba todos los rangos RSI posibles en bloques de 10
# Para encontrar el rango con mejor WR y PF real
# SOLO LECTURA — no toca nada del bot
# ============================================================

import urllib.request, urllib.parse, json, time
from datetime import datetime, timezone

SIMBOLOS = ["ETHUSDT", "SOLUSDT", "BTCUSDT", "BNBUSDT", "AVAXUSDT"]
INICIO   = "2024-01-01"
FIN      = "2024-12-31"

PARAMS = {
    "ETHUSDT":  {"sl": 2.0, "tp": 10.0},
    "SOLUSDT":  {"sl": 4.0, "tp": 10.0},
    "BTCUSDT":  {"sl": 5.0, "tp": 10.0},
    "BNBUSDT":  {"sl": 2.0, "tp": 5.0},
    "AVAXUSDT": {"sl": 3.0, "tp": 8.0},
}

RANGOS_RSI = [
    (30,40), (35,45), (40,50), (45,55), (50,60),
    (55,65), (60,70), (65,75), (70,80), (55,70),
    (50,65), (60,75), (45,65), (50,70)
]

def ts(fecha):
    return int(datetime.strptime(fecha,'%Y-%m-%d')
               .replace(tzinfo=timezone.utc).timestamp()*1000)

def descargar_velas(symbol):
    todas  = []
    inicio = ts(INICIO)
    fin    = ts(FIN)
    while inicio < fin:
        params = urllib.parse.urlencode({
            'symbol': symbol, 'interval': '4h',
            'startTime': inicio, 'endTime': fin, 'limit': 500
        })
        url = f'https://api.binance.com/api/v3/klines?{params}'
        try:
            with urllib.request.urlopen(url, timeout=15) as r:
                bloque = json.loads(r.read())
            if not bloque: break
            todas.extend(bloque)
            inicio = int(bloque[-1][0]) + 1
            time.sleep(0.1)
        except Exception as e:
            print(f"  Error: {e}")
            break
    return todas

def calcular_rsi(cierres, periodo=14):
    if len(cierres) < periodo + 1: return None
    g = [max(cierres[i]-cierres[i-1],0) for i in range(1,len(cierres))]
    p = [max(cierres[i-1]-cierres[i],0) for i in range(1,len(cierres))]
    ag = sum(g[:periodo])/periodo
    ap = sum(p[:periodo])/periodo
    for i in range(periodo,len(g)):
        ag = (ag*(periodo-1)+g[i])/periodo
        ap = (ap*(periodo-1)+p[i])/periodo
    return round(100-(100/(1+ag/ap)),1) if ap else 100

def simular_trade(velas, idx, sl_pct, tp_pct):
    precio_entrada = float(velas[idx][4])
    precio_tp = precio_entrada * (1 + tp_pct/100)
    precio_sl = precio_entrada * (1 - sl_pct/100)
    for i in range(idx+1, min(idx+101, len(velas))):
        high = float(velas[i][2])
        low  = float(velas[i][3])
        if high >= precio_tp: return 'TP', i-idx
        if low  <= precio_sl: return 'SL', i-idx
    return 'TIMEOUT', 100

def backtest_rango(velas, rsi_min, rsi_max, sl, tp):
    cierres  = [float(v[4]) for v in velas]
    tp_c = sl_c = timeout = 0
    en_trade   = False
    idx_salida = 0

    for i in range(20, len(velas)):
        if en_trade and i <= idx_salida:
            continue
        en_trade = False

        rsi = calcular_rsi(cierres[:i+1])
        if rsi is None or not (rsi_min <= rsi <= rsi_max):
            continue

        resultado, duracion = simular_trade(velas, i, sl, tp)
        if resultado == 'TP': tp_c += 1
        elif resultado == 'SL': sl_c += 1
        else: timeout += 1
        idx_salida = i + duracion
        en_trade   = True

    total = tp_c + sl_c
    if total < 5: return None
    wr = round(tp_c/total*100,1)
    pf = round((tp_c*tp)/(sl_c*sl),2) if sl_c else 0
    tm = round((total+timeout)/12,1)
    return tp_c, sl_c, timeout, wr, pf, tm

def main():
    print("="*70)
    print("BACKTEST TODOS LOS RANGOS RSI — 2024")
    print("="*70)

    resumen_global = {}

    for symbol in SIMBOLOS:
        print(f"\nDescargando {symbol}...")
        velas = descargar_velas(symbol)
        print(f"  {len(velas)} velas | Probando {len(RANGOS_RSI)} rangos RSI...")

        sl = PARAMS[symbol]['sl']
        tp = PARAMS[symbol]['tp']
        resultados = []

        for rsi_min, rsi_max in RANGOS_RSI:
            r = backtest_rango(velas, rsi_min, rsi_max, sl, tp)
            if r:
                tp_c, sl_c, to, wr, pf, tm = r
                resultados.append((rsi_min, rsi_max, tp_c, sl_c, to, wr, pf, tm))

        print(f"\n  {symbol} — Rangos RSI ordenados por PF:")
        print(f"  {'RSI':<12} {'TP':<6} {'SL':<6} {'WR%':<8} {'PF':<8} {'T/mes'}")
        print("  "+"-"*50)
        for r in sorted(resultados, key=lambda x: x[6], reverse=True):
            rsi_min, rsi_max, tp_c, sl_c, to, wr, pf, tm = r
            rango = f"{rsi_min}-{rsi_max}"
            print(f"  {rango:<12} {tp_c:<6} {sl_c:<6} {wr:<8} {pf:<8} {tm}")

        resumen_global[symbol] = sorted(resultados, key=lambda x: x[6], reverse=True)

    print("\n"+"="*70)
    print("MEJOR RANGO RSI POR MONEDA")
    print("="*70)
    print(f"{'Moneda':<12} {'RSI':<12} {'WR%':<8} {'PF':<8} {'T/mes'}")
    print("-"*50)
    for symbol, resultados in resumen_global.items():
        if resultados:
            r = resultados[0]
            rsi_min, rsi_max, tp_c, sl_c, to, wr, pf, tm = r
            print(f"{symbol:<12} {rsi_min}-{rsi_max:<8} {wr:<8} {pf:<8} {tm}")

    import os
    os.makedirs('/home/ariel/bot-padre-v2/reports', exist_ok=True)
    with open('/home/ariel/bot-padre-v2/reports/backtest_rsi_rangos.json','w') as f:
        json.dump({s: [list(r) for r in rs] for s,rs in resumen_global.items()}, f, indent=2)
    print("\nReporte guardado en reports/backtest_rsi_rangos.json")

if __name__ == "__main__":
    main()
