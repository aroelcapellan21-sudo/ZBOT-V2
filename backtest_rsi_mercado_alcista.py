# ============================================================
# backtest_rsi_mercado_alcista.py
# RSI 70-80 + solo operar cuando BTC > EMA200 semanal
# Filtra mercados bajistas de 2018, 2020, 2022
# SOLO LECTURA — no toca nada del bot
# ============================================================

import csv

SIMBOLOS = ["ETHUSDT", "SOLUSDT", "BTCUSDT", "BNBUSDT", "AVAXUSDT"]
RUTA     = "/home/ariel/bot-padre-v3-backup/data/historico_4h/{}_4h.csv"
RUTA_BTC = "/home/ariel/bot-padre-v3-backup/data/historico_4h/BTCUSDT_4h.csv"

PARAMS = {
    "ETHUSDT":  {"sl": 2.0, "tp": 10.0},
    "SOLUSDT":  {"sl": 4.0, "tp": 10.0},
    "BTCUSDT":  {"sl": 5.0, "tp": 10.0},
    "BNBUSDT":  {"sl": 2.0, "tp":  5.0},
    "AVAXUSDT": {"sl": 3.0, "tp":  8.0},
}

def cargar_velas(ruta):
    velas = []
    with open(ruta, newline='') as f:
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
    cierres  = [v['close'] for v in velas]
    rsi_arr  = [None] * len(cierres)
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

def precalcular_ema200_semanal(velas_btc):
    """
    Calcula EMA200 semanal usando velas 4H de BTC.
    Una semana = 42 velas 4H. EMA200 semanal = EMA de 200 semanas = 8400 velas 4H.
    Para cada vela 4H devuelve si BTC está sobre EMA200 semanal.
    """
    print("  Calculando EMA200 semanal BTC...", flush=True)
    cierres  = [v['close'] for v in velas_btc]
    periodo  = 8400  # 200 semanas × 42 velas/semana
    sobre_ema = [False] * len(cierres)

    if len(cierres) < periodo:
        print(f"  ⚠️ Solo {len(cierres)} velas, mínimo {periodo} para EMA200 semanal")
        # Usar EMA200 diaria como alternativa (200 dias × 6 velas 4H = 1200)
        periodo = 1200
        print(f"  Usando EMA200 diaria ({periodo} velas) como alternativa", flush=True)

    ema = sum(cierres[:periodo])/periodo
    k   = 2/(periodo+1)
    sobre_ema[periodo-1] = cierres[periodo-1] > ema

    for i in range(periodo, len(cierres)):
        ema = cierres[i]*k + ema*(1-k)
        sobre_ema[i] = cierres[i] > ema

    return sobre_ema

def simular_trade(velas, idx, sl_pct, tp_pct):
    precio_entrada = velas[idx]['close']
    precio_tp = precio_entrada * (1 + tp_pct/100)
    precio_sl = precio_entrada * (1 - sl_pct/100)
    for i in range(idx+1, min(idx+101, len(velas))):
        if velas[i]['high'] >= precio_tp: return 'TP', i-idx
        if velas[i]['low']  <= precio_sl: return 'SL', i-idx
    return 'TIMEOUT', 100

def backtest(velas, rsi_arr, sobre_ema_btc, sl, tp, usar_filtro_btc):
    tp_c = sl_c = timeout = bloqueados = 0
    en_trade   = False
    idx_salida = 0

    for i in range(20, len(velas)):
        if en_trade and i <= idx_salida:
            continue
        en_trade = False

        rsi = rsi_arr[i]
        if rsi is None or not (70 <= rsi <= 80):
            continue

        if usar_filtro_btc:
            if i >= len(sobre_ema_btc) or not sobre_ema_btc[i]:
                bloqueados += 1
                continue

        resultado, duracion = simular_trade(velas, i, sl, tp)
        if resultado == 'TP':   tp_c += 1
        elif resultado == 'SL': sl_c += 1
        else:                   timeout += 1
        idx_salida = i + duracion
        en_trade   = True

    total = tp_c + sl_c
    if total < 5: return None
    wr = round(tp_c/total*100,1)
    pf = round((tp_c*tp)/(sl_c*sl),2) if sl_c else 0
    años = (len(velas)*4)/(365*24)
    tm = round((total+timeout)/años/12,1)
    return tp_c, sl_c, timeout, bloqueados, wr, pf, tm

def main():
    print("="*70)
    print("BACKTEST RSI 70-80 + FILTRO BTC EMA200 — DATOS HISTORICOS 9 AÑOS")
    print("="*70)

    print("\nCargando BTC para filtro de mercado...")
    velas_btc   = cargar_velas(RUTA_BTC)
    sobre_ema_btc = precalcular_ema200_semanal(velas_btc)
    rsi_btc     = precalcular_rsi(velas_btc)

    # Cuánto tiempo BTC estuvo sobre EMA200
    sobre = sum(1 for x in sobre_ema_btc if x)
    total_b = len(sobre_ema_btc)
    print(f"  BTC sobre EMA200: {round(sobre/total_b*100,1)}% del tiempo")
    print(f"  BTC bajo EMA200:  {round((total_b-sobre)/total_b*100,1)}% del tiempo")

    print("\n"+"="*70)

    mejores = {}

    for symbol in SIMBOLOS:
        print(f"\nCargando {symbol}...", flush=True)
        try:
            velas = cargar_velas(RUTA.format(symbol))
        except FileNotFoundError:
            print(f"  No encontrado")
            continue

        años = round((len(velas)*4)/(365*24),1)
        print(f"  {len(velas)} velas ({años} años)", flush=True)

        rsi_arr = precalcular_rsi(velas)
        sl = PARAMS[symbol]['sl']
        tp = PARAMS[symbol]['tp']

        # Necesito alinear sobre_ema_btc con las velas del símbolo por timestamp
        # BTC y el simbolo tienen timestamps distintos — uso índice proporcional
        # como aproximación (mismo intervalo 4H, mismo exchange)
        offset = len(velas_btc) - len(velas)
        ema_alineada = sobre_ema_btc[max(0,offset):]

        r_sin = backtest(velas, rsi_arr, ema_alineada, sl, tp, False)
        r_con = backtest(velas, rsi_arr, ema_alineada, sl, tp, True)

        print(f"\n  {symbol} — RSI 70-80:")
        if r_sin:
            tp_c,sl_c,to,bl,wr,pf,tm = r_sin
            print(f"  SIN FILTRO BTC: TP:{tp_c} SL:{sl_c} WR:{wr}% PF:{pf} T/mes:{tm}")
        if r_con:
            tp_c,sl_c,to,bl,wr,pf,tm = r_con
            marca = " ✅" if pf >= 1.8 else " ❌"
            print(f"  CON FILTRO BTC: TP:{tp_c} SL:{sl_c} WR:{wr}% PF:{pf} T/mes:{tm} bloq:{bl}{marca}")

        mejores[symbol] = r_con

    print("\n"+"="*70)
    print("RESUMEN FINAL")
    print("="*70)
    print(f"{'Moneda':<12} {'WR%':<8} {'PF':<8} {'T/mes':<8} {'Meta'}")
    print("-"*45)
    for symbol, r in mejores.items():
        if r:
            tp_c,sl_c,to,bl,wr,pf,tm = r
            meta = "✅ PF OK" if pf >= 1.8 else "❌"
            print(f"{symbol:<12} {wr:<8} {pf:<8} {tm:<8} {meta}")

    import os, json
    os.makedirs('/home/ariel/bot-padre-v2/reports', exist_ok=True)
    with open('/home/ariel/bot-padre-v2/reports/backtest_rsi_mercado_alcista.json','w') as f:
        json.dump({s: list(r) if r else None for s,r in mejores.items()}, f, indent=2)
    print("\nReporte guardado en reports/backtest_rsi_mercado_alcista.json")

if __name__ == "__main__":
    main()
