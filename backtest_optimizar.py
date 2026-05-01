# =========================================
# backtest_optimizar.py
# Prueba diferentes combinaciones TP/SL
# Encuentra la combinacion mas rentable
# Sin librerias externas. Constitucion RESPETADA
# =========================================

import json
import os
import urllib.request
import urllib.parse
from datetime import datetime

REPORTE = os.path.expanduser("~/bot-padre-v2/reports_historicos/backtest_optimizacion.json")
SIMBOLOS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "AVAXUSDT"]

COMBINACIONES = [
    {"tp": 3, "sl": 2},
    {"tp": 4, "sl": 2},
    {"tp": 4, "sl": 3},
    {"tp": 5, "sl": 3},
    {"tp": 6, "sl": 3},
    {"tp": 6, "sl": 3.5},
    {"tp": 5, "sl": 2.5},
    {"tp": 7, "sl": 3},
]

def fetch_velas(symbol, limite=500):
    try:
        params = urllib.parse.urlencode({"symbol": symbol, "interval": "4h", "limit": limite})
        url = f"https://api.binance.com/api/v3/klines?{params}"
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        return [float(k[4]) for k in data]
    except:
        return []

def calcular_rsi(cierres, periodo=14):
    if len(cierres) < periodo + 1:
        return None
    ganancias, perdidas = [], []
    for i in range(1, periodo + 1):
        diff = cierres[i] - cierres[i-1]
        if diff > 0:
            ganancias.append(diff)
            perdidas.append(0)
        else:
            ganancias.append(0)
            perdidas.append(abs(diff))
    avg_gan = sum(ganancias) / periodo
    avg_per = sum(perdidas) / periodo
    if avg_per == 0:
        return 100
    rs = avg_gan / avg_per
    return round(100 - (100 / (1 + rs)), 2)

def calcular_ema(cierres, periodo):
    if len(cierres) < periodo:
        return None
    k = 2 / (periodo + 1)
    ema = sum(cierres[:periodo]) / periodo
    for precio in cierres[periodo:]:
        ema = precio * k + ema * (1 - k)
    return round(ema, 4)

def detectar_fase(cierres):
    if len(cierres) < 30:
        return "DESCONOCIDA"
    cambio = ((cierres[-1] - cierres[-30]) / cierres[-30]) * 100
    if cambio > 10:
        return "ALCISTA"
    elif cambio < -10:
        return "BAJISTA"
    else:
        return "LATERAL"

def simular(symbol, cierres, tp_pct, sl_pct):
    capital = 1000.0
    capital_max = 1000.0
    max_dd = 0.0
    en_op = False
    precio_entrada = 0
    tp_count = 0
    sl_count = 0

    for i in range(60, len(cierres) - 1):
        ventana = cierres[max(0, i-60):i]
        rsi = calcular_rsi(ventana[-15:])
        ema_c = calcular_ema(ventana, 20)
        ema_l = calcular_ema(ventana, 50)
        fase = detectar_fase(ventana)

        if rsi is None or ema_c is None or ema_l is None:
            continue

        precio_actual = cierres[i]

        if en_op:
            cambio = ((precio_actual - precio_entrada) / precio_entrada) * 100
            if cambio >= tp_pct:
                monto = capital * 0.01
                capital += monto * (tp_pct / 100)
                capital_max = max(capital_max, capital)
                max_dd = max(max_dd, ((capital_max - capital) / capital_max) * 100)
                tp_count += 1
                en_op = False
            elif cambio <= -sl_pct:
                monto = capital * 0.01
                capital -= monto * (sl_pct / 100)
                capital_max = max(capital_max, capital)
                max_dd = max(max_dd, ((capital_max - capital) / capital_max) * 100)
                sl_count += 1
                en_op = False
        else:
            if fase == "LATERAL" and 45 <= rsi <= 55 and abs(ema_c - ema_l) / ema_l * 100 < 2.0:
                en_op = True
                precio_entrada = precio_actual
            elif fase == "ALCISTA" and 50 <= rsi <= 70 and ema_c > ema_l:
                en_op = True
                precio_entrada = precio_actual

    total = tp_count + sl_count
    winrate = round((tp_count / total) * 100, 2) if total > 0 else 0
    ganancia = round(capital - 1000, 4)
    return total, tp_count, sl_count, winrate, ganancia, round(max_dd, 2)

def ejecutar_optimizacion():
    print("🔬 Optimizando parametros TP/SL...\n")
    os.makedirs(os.path.dirname(REPORTE), exist_ok=True)

    datos = {}
    for symbol in SIMBOLOS:
        print(f"  📊 Cargando {symbol}...")
        datos[symbol] = fetch_velas(symbol)

    resultados = []
    mejor = None
    mejor_ganancia = -9999

    print(f"\n{'TP':>4} {'SL':>4} {'Ops':>5} {'TP#':>5} {'SL#':>5} {'WR%':>7} {'Ganancia':>10} {'MaxDD':>7}")
    print("-" * 60)

    for combo in COMBINACIONES:
        tp = combo["tp"]
        sl = combo["sl"]
        total_ops = 0
        total_tp = 0
        total_sl = 0
        ganancia_total = 0
        max_dd_total = 0

        for symbol in SIMBOLOS:
            if not datos[symbol]:
                continue
            ops, tp_c, sl_c, wr, gan, dd = simular(symbol, datos[symbol], tp, sl)
            total_ops += ops
            total_tp += tp_c
            total_sl += sl_c
            ganancia_total += gan
            max_dd_total = max(max_dd_total, dd)

        wr_global = round((total_tp / total_ops) * 100, 2) if total_ops > 0 else 0
        ganancia_total = round(ganancia_total, 4)

        print(f"  {tp:>3}% {sl:>3}% {total_ops:>5} {total_tp:>5} {total_sl:>5} {wr_global:>6}% ${ganancia_total:>9} {max_dd_total:>6}%")

        resultado = {
            "tp": tp, "sl": sl,
            "total_ops": total_ops,
            "total_tp": total_tp,
            "total_sl": total_sl,
            "winrate": wr_global,
            "ganancia_total": ganancia_total,
            "max_drawdown": max_dd_total
        }
        resultados.append(resultado)

        if ganancia_total > mejor_ganancia:
            mejor_ganancia = ganancia_total
            mejor = resultado

    print(f"\n🏆 MEJOR COMBINACION:")
    print(f"  TP: {mejor['tp']}% | SL: {mejor['sl']}%")
    print(f"  Win Rate : {mejor['winrate']}%")
    print(f"  Ganancia : ${mejor['ganancia_total']}")
    print(f"  Max DD   : {mejor['max_drawdown']}%")

    reporte = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mejor_combinacion": mejor,
        "todas_combinaciones": resultados
    }

    with open(REPORTE, "w") as f:
        json.dump(reporte, f, indent=2)

    print(f"\n✅ Reporte guardado en reports_historicos/backtest_optimizacion.json")

if __name__ == "__main__":
    ejecutar_optimizacion()
