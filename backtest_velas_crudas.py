# ============================================================
# backtest_velas_crudas.py
# Descarga velas crudas de Binance 2024 y aplica filtro
# RSI 4H 60-70 sobre TODAS las velas — sin pre-filtros del bot
# SOLO LECTURA — no toca nada del bot
# ============================================================

import urllib.request, urllib.parse, json, time
from datetime import datetime, timezone

SIMBOLOS = ["ETHUSDT", "SOLUSDT", "BTCUSDT", "BNBUSDT", "AVAXUSDT"]
INTERVALO = "4h"
INICIO    = "2024-01-01"
FIN       = "2024-12-31"

# Parámetros del bot por moneda (solo LONG/ALCISTA y LATERAL)
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

def descargar_velas(symbol):
    """Descarga todas las velas 4H de 2024 en bloques de 500."""
    todas = []
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
            print(f"  Error descargando {symbol}: {e}")
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

def simular_trade(velas, idx_entrada, sl_pct, tp_pct):
    """Simula trade desde idx_entrada hasta TP, SL o TIMEOUT."""
    precio_entrada = float(velas[idx_entrada][4])
    precio_tp = precio_entrada * (1 + tp_pct/100)
    precio_sl = precio_entrada * (1 - sl_pct/100)

    for i in range(idx_entrada+1, min(idx_entrada+51, len(velas))):
        high  = float(velas[i][2])
        low   = float(velas[i][3])
        if high >= precio_tp:
            return 'TP', i - idx_entrada
        if low <= precio_sl:
            return 'SL', i - idx_entrada

    return 'TIMEOUT', 50

def main():
    print("="*60)
    print("BACKTEST VELAS CRUDAS 2024 — Filtro RSI 4H 60-70")
    print("="*60)
    print()

    resumen_total = {'TP':0,'SL':0,'TIMEOUT':0,'trades_mes':{}}

    for symbol in SIMBOLOS:
        print(f"Descargando {symbol}...")
        velas = descargar_velas(symbol)
        print(f"  {len(velas)} velas descargadas")

        cierres = [float(v[4]) for v in velas]
        sl  = PARAMS[symbol]['sl']
        tp  = PARAMS[symbol]['tp']

        resultados = {'TP':0,'SL':0,'TIMEOUT':0}
        por_mes    = {}
        en_trade   = False
        idx_salida = 0

        for i in range(20, len(velas)):
            # No entrar si ya hay un trade abierto
            if en_trade and i <= idx_salida:
                continue
            en_trade = False

            rsi = calcular_rsi(cierres[:i+1])
            if rsi is None: continue

            # Filtro RSI 4H 60-70
            if not (60 <= rsi <= 70):
                continue

            # Entrada confirmada
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

        total = resultados['TP'] + resultados['SL']
        wr    = round(resultados['TP']/total*100,1) if total else 0
        pf    = round((resultados['TP']*tp) / (resultados['SL']*sl), 2) \
                if resultados['SL'] else 0
        tmes  = round((total+resultados['TIMEOUT'])/12, 1)

        print(f"\n  {symbol}")
        print(f"  TP:{resultados['TP']} SL:{resultados['SL']} "
              f"TIMEOUT:{resultados['TIMEOUT']}")
        print(f"  WR:{wr}% | PF:{pf} | Trades/mes:{tmes}")
        print(f"  Por mes:")
        for mes in sorted(por_mes):
            t = por_mes[mes]['TP']+por_mes[mes]['SL']
            w = round(por_mes[mes]['TP']/t*100,1) if t else 0
            print(f"    {mes}: {t} trades WR {w}%")

        resumen_total['TP']      += resultados['TP']
        resumen_total['SL']      += resultados['SL']
        resumen_total['TIMEOUT'] += resultados['TIMEOUT']
        print()

    # Resumen global
    t = resumen_total['TP']+resumen_total['SL']
    wr = round(resumen_total['TP']/t*100,1) if t else 0
    print("="*60)
    print("RESUMEN GLOBAL — 5 MONEDAS")
    print("="*60)
    print(f"Total trades  : {t+resumen_total['TIMEOUT']}")
    print(f"TP            : {resumen_total['TP']}")
    print(f"SL            : {resumen_total['SL']}")
    print(f"TIMEOUT       : {resumen_total['TIMEOUT']}")
    print(f"WR            : {wr}%")
    print(f"Trades/mes    : {round((t+resumen_total['TIMEOUT'])/12,1)}")

    # Guardar reporte
    import os
    os.makedirs('/home/ariel/bot-padre-v2/reports', exist_ok=True)
    with open('/home/ariel/bot-padre-v2/reports/backtest_velas_crudas.json','w') as f:
        json.dump(resumen_total, f, indent=2)
    print("\nReporte guardado en reports/backtest_velas_crudas.json")

if __name__ == "__main__":
    main()
