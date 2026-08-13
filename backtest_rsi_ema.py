# ============================================================
# backtest_rsi_ema.py
# Filtro RSI 4H 60-70 + EMA confirmacion de tendencia
# Solo LONG cuando precio > EMA en el momento de entrada
# SOLO LECTURA — no toca nada del bot
# ============================================================

import urllib.request, urllib.parse, json, time
from datetime import datetime, timezone

SIMBOLOS  = ["ETHUSDT", "SOLUSDT", "BTCUSDT", "BNBUSDT", "AVAXUSDT"]
INTERVALO = "4h"
INICIO    = "2024-01-01"
FIN       = "2024-12-31"

PARAMS = {
    "ETHUSDT":  {"sl": 4.5, "tp": 5.5, "ema": 20},
    "SOLUSDT":  {"sl": 3.5, "tp": 5.0, "ema": 20},
    "BTCUSDT":  {"sl": 5.0, "tp": 6.0, "ema": 20},
    "BNBUSDT":  {"sl": 4.5, "tp": 5.0, "ema": 20},
    "AVAXUSDT": {"sl": 4.5, "tp": 5.0, "ema": 20},
}

def ts(fecha):
    return int(datetime.strptime(fecha,'%Y-%m-%d')
               .replace(tzinfo=timezone.utc).timestamp()*1000)

def descargar_velas(symbol):
    todas  = []
    inicio = ts(INICIO)
    fin    = ts(FIN)
    while inicio < fin:
        params = urllib.parse.urlencode({
            'symbol': symbol, 'interval': INTERVALO,
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

def calcular_ema(cierres, periodo=20):
    if len(cierres) < periodo: return None
    k   = 2/(periodo+1)
    ema = sum(cierres[:periodo])/periodo
    for precio in cierres[periodo:]:
        ema = precio*k + ema*(1-k)
    return round(ema, 4)

def simular_trade(velas, idx, sl_pct, tp_pct):
    precio_entrada = float(velas[idx][4])
    precio_tp = precio_entrada * (1 + tp_pct/100)
    precio_sl = precio_entrada * (1 - sl_pct/100)
    for i in range(idx+1, min(idx+51, len(velas))):
        high = float(velas[i][2])
        low  = float(velas[i][3])
        if high >= precio_tp: return 'TP', i-idx
        if low  <= precio_sl: return 'SL', i-idx
    return 'TIMEOUT', 50

def analizar(symbol, velas, ema_periodo, sl, tp, usar_ema):
    cierres = [float(v[4]) for v in velas]
    resultados = {'TP':0,'SL':0,'TIMEOUT':0}
    por_mes    = {}
    en_trade   = False
    idx_salida = 0

    for i in range(max(ema_periodo, 20), len(velas)):
        if en_trade and i <= idx_salida:
            continue
        en_trade = False

        rsi = calcular_rsi(cierres[:i+1])
        if rsi is None or not (60 <= rsi <= 70):
            continue

        if usar_ema:
            ema = calcular_ema(cierres[:i+1], ema_periodo)
            if ema is None or cierres[i] <= ema:
                continue

        resultado, duracion = simular_trade(velas, i, sl, tp)
        resultados[resultado] += 1
        idx_salida = i + duracion
        en_trade   = True

        fecha = datetime.fromtimestamp(
            int(velas[i][0])/1000, tz=timezone.utc
        ).strftime('%Y-%m')
        if fecha not in por_mes:
            por_mes[fecha] = {'TP':0,'SL':0}
        if resultado in ('TP','SL'):
            por_mes[fecha][resultado] += 1

    return resultados, por_mes

def imprimir(symbol, resultados, por_mes, label):
    total = resultados['TP']+resultados['SL']
    wr    = round(resultados['TP']/total*100,1) if total else 0
    sl    = PARAMS[symbol]['sl']
    tp    = PARAMS[symbol]['tp']
    pf    = round((resultados['TP']*tp)/(resultados['SL']*sl),2) \
            if resultados['SL'] else 0
    tmes  = round((total+resultados['TIMEOUT'])/12,1)
    print(f"  [{label}] WR:{wr}% PF:{pf} Trades/mes:{tmes} "
          f"(TP:{resultados['TP']} SL:{resultados['SL']} TO:{resultados['TIMEOUT']})")
    return wr, pf, tmes, total

def main():
    print("="*65)
    print("BACKTEST RSI 4H 60-70 + EMA20 vs SIN EMA — 2024")
    print("="*65)

    resumen_sin = {'TP':0,'SL':0,'TIMEOUT':0}
    resumen_con = {'TP':0,'SL':0,'TIMEOUT':0}

    for symbol in SIMBOLOS:
        print(f"\n{symbol}")
        print("-"*40)
        velas = descargar_velas(symbol)
        print(f"  {len(velas)} velas")

        ema = PARAMS[symbol]['ema']
        sl  = PARAMS[symbol]['sl']
        tp  = PARAMS[symbol]['tp']

        r_sin, m_sin = analizar(symbol, velas, ema, sl, tp, usar_ema=False)
        r_con, m_con = analizar(symbol, velas, ema, sl, tp, usar_ema=True)

        imprimir(symbol, r_sin, m_sin, "SIN EMA")
        imprimir(symbol, r_con, m_con, "CON EMA")

        print("  Por mes CON EMA:")
        for mes in sorted(m_con):
            t = m_con[mes]['TP']+m_con[mes]['SL']
            w = round(m_con[mes]['TP']/t*100,1) if t else 0
            print(f"    {mes}: {t} trades WR {w}%")

        for k in ('TP','SL','TIMEOUT'):
            resumen_sin[k] += r_sin[k]
            resumen_con[k] += r_con[k]

    print("\n"+"="*65)
    print("RESUMEN GLOBAL")
    print("="*65)
    for label, res in [("SIN EMA", resumen_sin), ("CON EMA", resumen_con)]:
        t  = res['TP']+res['SL']
        wr = round(res['TP']/t*100,1) if t else 0
        tm = round((t+res['TIMEOUT'])/12,1)
        print(f"{label}: WR:{wr}% | TP:{res['TP']} SL:{res['SL']} "
              f"TO:{res['TIMEOUT']} | Trades/mes:{tm}")

if __name__ == "__main__":
    main()
