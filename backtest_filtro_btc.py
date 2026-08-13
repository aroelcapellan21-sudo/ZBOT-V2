# ============================================================
# backtest_filtro_btc.py
# Filtro RSI 4H 60-70 + tendencia BTC semanal como termómetro
# Si BTC semanal es alcista → operar. Si no → esperar.
# SOLO LECTURA — no toca nada del bot
# ============================================================

import urllib.request, urllib.parse, json, time
from datetime import datetime, timezone

SIMBOLOS  = ["ETHUSDT", "SOLUSDT", "BTCUSDT", "BNBUSDT", "AVAXUSDT"]
INICIO    = "2024-01-01"
FIN       = "2024-12-31"

PARAMS = {
    "ETHUSDT":  {"sl": 4.5, "tp": 5.5},
    "SOLUSDT":  {"sl": 3.5, "tp": 5.0},
    "BTCUSDT":  {"sl": 5.0, "tp": 6.0},
    "BNBUSDT":  {"sl": 4.5, "tp": 5.0},
    "AVAXUSDT": {"sl": 4.5, "tp": 5.0},
}

def ts(fecha):
    return int(datetime.strptime(fecha,'%Y-%m-%d')
               .replace(tzinfo=timezone.utc).timestamp()*1000)

def descargar_velas(symbol, intervalo):
    todas  = []
    inicio = ts(INICIO)
    fin    = ts(FIN)
    while inicio < fin:
        params = urllib.parse.urlencode({
            'symbol': symbol, 'interval': intervalo,
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
    return ema

def btc_alcista(ts_vela, btc_semanas):
    """
    Devuelve True si BTC en timeframe semanal está alcista:
    - Precio > EMA20 semanal
    - RSI semanal > 50
    """
    # Encontrar velas semanales hasta este timestamp
    velas_hasta = [v for v in btc_semanas if int(v[0]) <= ts_vela]
    if len(velas_hasta) < 22: return False
    cierres = [float(v[4]) for v in velas_hasta]
    rsi_w = calcular_rsi(cierres)
    ema_w = calcular_ema(cierres, 20)
    if rsi_w is None or ema_w is None: return False
    precio = cierres[-1]
    return precio > ema_w and rsi_w > 50

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

def analizar(symbol, velas_4h, btc_semanas, sl, tp, usar_btc_filtro):
    cierres    = [float(v[4]) for v in velas_4h]
    resultados = {'TP':0,'SL':0,'TIMEOUT':0}
    por_mes    = {}
    en_trade   = False
    idx_salida = 0

    for i in range(20, len(velas_4h)):
        if en_trade and i <= idx_salida:
            continue
        en_trade = False

        rsi = calcular_rsi(cierres[:i+1])
        if rsi is None or not (60 <= rsi <= 70):
            continue

        if usar_btc_filtro:
            ts_vela = int(velas_4h[i][0])
            if not btc_alcista(ts_vela, btc_semanas):
                continue

        resultado, duracion = simular_trade(velas_4h, i, sl, tp)
        resultados[resultado] += 1
        idx_salida = i + duracion
        en_trade   = True

        fecha = datetime.fromtimestamp(
            int(velas_4h[i][0])/1000, tz=timezone.utc
        ).strftime('%Y-%m')
        if fecha not in por_mes:
            por_mes[fecha] = {'TP':0,'SL':0}
        if resultado in ('TP','SL'):
            por_mes[fecha][resultado] += 1

    return resultados, por_mes

def imprimir_resumen(label, res):
    t  = res['TP']+res['SL']
    wr = round(res['TP']/t*100,1) if t else 0
    tm = round((t+res['TIMEOUT'])/12,1)
    print(f"{label}: WR:{wr}% | TP:{res['TP']} SL:{res['SL']} "
          f"TO:{res['TIMEOUT']} | Trades/mes:{tm}")
    return wr, t

def main():
    print("="*65)
    print("BACKTEST RSI 4H 60-70 + FILTRO TENDENCIA BTC SEMANAL")
    print("="*65)

    print("\nDescargando BTC semanal (termómetro del mercado)...")
    btc_semanas = descargar_velas("BTCUSDT", "1w")
    print(f"  {len(btc_semanas)} velas semanales BTC")

    resumen_sin = {'TP':0,'SL':0,'TIMEOUT':0}
    resumen_con = {'TP':0,'SL':0,'TIMEOUT':0}

    for symbol in SIMBOLOS:
        print(f"\n{symbol}")
        print("-"*45)
        velas = descargar_velas(symbol, "4h")
        print(f"  {len(velas)} velas 4H")

        sl = PARAMS[symbol]['sl']
        tp = PARAMS[symbol]['tp']

        r_sin, _ = analizar(symbol, velas, btc_semanas, sl, tp, False)
        r_con, m_con = analizar(symbol, velas, btc_semanas, sl, tp, True)

        t_sin = r_sin['TP']+r_sin['SL']
        wr_sin = round(r_sin['TP']/t_sin*100,1) if t_sin else 0
        t_con = r_con['TP']+r_con['SL']
        wr_con = round(r_con['TP']/t_con*100,1) if t_con else 0
        tm_sin = round((t_sin+r_sin['TIMEOUT'])/12,1)
        tm_con = round((t_con+r_con['TIMEOUT'])/12,1)

        print(f"  [SIN FILTRO] WR:{wr_sin}% Trades/mes:{tm_sin}")
        print(f"  [CON FILTRO] WR:{wr_con}% Trades/mes:{tm_con} "
              f"(TP:{r_con['TP']} SL:{r_con['SL']} TO:{r_con['TIMEOUT']})")

        print("  Por mes CON FILTRO:")
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
    imprimir_resumen("SIN FILTRO BTC", resumen_sin)
    imprimir_resumen("CON FILTRO BTC", resumen_con)

    # Guardar
    import os
    os.makedirs('/home/ariel/bot-padre-v2/reports', exist_ok=True)
    with open('/home/ariel/bot-padre-v2/reports/backtest_filtro_btc.json','w') as f:
        json.dump({'sin_filtro': resumen_sin, 'con_filtro': resumen_con}, f, indent=2)
    print("\nReporte guardado en reports/backtest_filtro_btc.json")

if __name__ == "__main__":
    main()
