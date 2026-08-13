import urllib.request, urllib.parse, json, time
from datetime import datetime, timezone

def get_rsi4h(symbol, fecha):
    dt = datetime.strptime(fecha,'%Y-%m-%d').replace(tzinfo=timezone.utc)
    ts = int(dt.timestamp()*1000)
    params = urllib.parse.urlencode({'symbol':symbol,'interval':'4h','endTime':ts,'limit':50})
    url = f'https://api.binance.com/api/v3/klines?{params}'
    with urllib.request.urlopen(url,timeout=10) as r:
        cierres = [float(k[4]) for k in json.loads(r.read())]
    if len(cierres) < 15: return None
    periodo = 14
    g = [max(cierres[i]-cierres[i-1],0) for i in range(1,len(cierres))]
    p = [max(cierres[i-1]-cierres[i],0) for i in range(1,len(cierres))]
    ag = sum(g[:periodo])/periodo
    ap = sum(p[:periodo])/periodo
    for i in range(periodo,len(g)):
        ag = (ag*(periodo-1)+g[i])/periodo
        ap = (ap*(periodo-1)+p[i])/periodo
    return round(100-(100/(1+ag/ap)),1) if ap else 100

with open('/home/ariel/zbot/radar/signals/backtest_2024_resultados.json') as f:
    data = json.load(f)

print('Filtro RSI 4H 60-70 — todas las monedas LONG:')
print()
print(f'{"Symbol":<10} {"Total":<8} {"TP":<6} {"SL":<6} {"WR%":<8} {"Bloq":<8} {"T/mes"}')
print('-'*55)

total_g = {'TP':0,'SL':0,'bloq':0}
for item in data:
    symbol = item['symbol']
    ops = [o for o in item['operaciones_detalle'] if o['direccion']=='LONG']
    tp=sl=bloq=0
    for o in ops:
        rsi = get_rsi4h(symbol, o['fecha'])
        time.sleep(0.05)
        if rsi and 60 <= rsi <= 70:
            if o['resultado']=='TP': tp+=1
            else: sl+=1
        else:
            bloq+=1
    total=tp+sl
    wr=round(tp/total*100,1) if total else 0
    print(f'{symbol:<10} {total:<8} {tp:<6} {sl:<6} {wr:<8} {bloq:<8} {round(total/12,1)}')
    total_g['TP']+=tp; total_g['SL']+=sl; total_g['bloq']+=bloq

t=total_g['TP']+total_g['SL']
print('-'*55)
wr_t=round(total_g['TP']/t*100,1) if t else 0
print(f'{"TOTAL":<10} {t:<8} {total_g["TP"]:<6} {total_g["SL"]:<6} {wr_t:<8} {total_g["bloq"]:<8} {round(t/12,1)}')
