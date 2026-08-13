# ============================================================
# backtest_tp_sl_optimo.py
# Busca el ratio TP/SL optimo para cada moneda
# usando velas crudas 2024 con filtro RSI 4H 60-70
# SOLO LECTURA — no toca nada del bot
# ============================================================

import urllib.request, urllib.parse, json, time
from datetime import datetime, timezone

SIMBOLOS = ["ETHUSDT", "SOLUSDT", "BTCUSDT", "BNBUSDT", "AVAXUSDT"]
INICIO   = "2024-01-01"
FIN      = "2024-12-31"

# Combinaciones a probar
TP_VALORES = [3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 10.0]
SL_VALORES = [2.0, 3.0, 4.0, 5.0]

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

def backtest_combinacion(velas, sl, tp):
    cierres    = [float(v[4]) for v in velas]
    tp_count = sl_count = timeout = 0
    en_trade   = False
    idx_salida = 0

    for i in range(20, len(velas)):
        if en_trade and i <= idx_salida:
            continue
        en_trade = False

        rsi = calcular_rsi(cierres[:i+1])
        if rsi is None or not (60 <= rsi <= 70):
            continue

        resultado, duracion = simular_trade(velas, i, sl, tp)
        if resultado == 'TP': tp_count += 1
        elif resultado == 'SL': sl_count += 1
        else: timeout += 1
        idx_salida = i + duracion
        en_trade   = True

    total = tp_count + sl_count
    wr = round(tp_count/total*100,1) if total else 0
    pf = round((tp_count*tp)/(sl_count*sl),2) if sl_count else 0
    return tp_count, sl_count, timeout, wr, pf

def main():
    print("="*70)
    print("BACKTEST OPTIMIZACION TP/SL — RSI 4H 60-70 — 2024")
    print("="*70)

    mejores = {}

    for symbol in SIMBOLOS:
        print(f"\nDescargando {symbol}...")
        velas = descargar_velas(symbol)
        print(f"  {len(velas)} velas | Probando {len(TP_VALORES)*len(SL_VALORES)} combinaciones...")

        mejor_pf   = 0
        mejor_comb = None
        resultados = []

        for sl in SL_VALORES:
            for tp in TP_VALORES:
                if tp <= sl: continue
                tp_c, sl_c, to, wr, pf = backtest_combinacion(velas, sl, tp)
                total = tp_c + sl_c
                if total < 5: continue
                resultados.append((sl, tp, tp_c, sl_c, to, wr, pf))
                if pf > mejor_pf:
                    mejor_pf   = pf
                    mejor_comb = (sl, tp, tp_c, sl_c, to, wr, pf)

        mejores[symbol] = mejor_comb

        print(f"\n  {symbol} — Top 5 combinaciones por PF:")
        print(f"  {'SL%':<6} {'TP%':<6} {'TP':<6} {'SL':<6} {'WR%':<8} {'PF':<8} {'T/mes'}")
        print("  "+"-"*50)
        for r in sorted(resultados, key=lambda x: x[6], reverse=True)[:5]:
            sl, tp, tp_c, sl_c, to, wr, pf = r
            total = tp_c+sl_c+to
            print(f"  {sl:<6} {tp:<6} {tp_c:<6} {sl_c:<6} {wr:<8} {pf:<8} {round(total/12,1)}")

    print("\n"+"="*70)
    print("MEJOR COMBINACION POR MONEDA")
    print("="*70)
    print(f"{'Moneda':<12} {'SL%':<6} {'TP%':<6} {'WR%':<8} {'PF':<8} {'T/mes'}")
    print("-"*50)
    for symbol, r in mejores.items():
        if r:
            sl, tp, tp_c, sl_c, to, wr, pf = r
            total = tp_c+sl_c+to
            print(f"{symbol:<12} {sl:<6} {tp:<6} {wr:<8} {pf:<8} {round(total/12,1)}")

    import os
    os.makedirs('/home/ariel/bot-padre-v2/reports', exist_ok=True)
    with open('/home/ariel/bot-padre-v2/reports/backtest_tp_sl_optimo.json','w') as f:
        json.dump({s: list(r) if r else None for s,r in mejores.items()}, f, indent=2)
    print("\nReporte guardado en reports/backtest_tp_sl_optimo.json")

if __name__ == "__main__":
    main()
