# =========================================
# backtest_motor.py
# Prueba el sistema con datos historicos
# Valida estrategia antes de cuenta real
# Sin librerias externas. Constitucion RESPETADA
# =========================================

import json
import os
import urllib.request
import urllib.parse
from datetime import datetime

REPORTE_BACKTEST = os.path.expanduser("~/bot-padre-v2/reports_historicos/backtest_resultado.json")

SIMBOLOS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "AVAXUSDT"]

def fetch_velas_historicas(symbol, intervalo="4h", limite=500):
    try:
        params = urllib.parse.urlencode({
            "symbol": symbol,
            "interval": intervalo,
            "limit": limite
        })
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

def simular_operaciones(symbol, cierres, tp_pct, sl_pct, rsi_min, rsi_max):
    operaciones = []
    capital = 1000.0
    capital_max = 1000.0
    max_drawdown = 0.0
    en_operacion = False
    precio_entrada = 0

    for i in range(60, len(cierres) - 1):
        ventana = cierres[max(0, i-60):i]
        rsi = calcular_rsi(ventana[-15:])
        ema_c = calcular_ema(ventana, 20)
        ema_l = calcular_ema(ventana, 50)
        fase = detectar_fase(ventana)

        if rsi is None or ema_c is None or ema_l is None:
            continue

        precio_actual = cierres[i]

        if en_operacion:
            cambio = ((precio_actual - precio_entrada) / precio_entrada) * 100
            if cambio >= tp_pct:
                monto = capital * 0.01
                ganancia = monto * (tp_pct / 100)
                capital += ganancia
                capital_max = max(capital_max, capital)
                dd = ((capital_max - capital) / capital_max) * 100
                max_drawdown = max(max_drawdown, dd)
                operaciones.append({"tipo": "TP", "entrada": precio_entrada, "salida": precio_actual, "ganancia": round(ganancia, 4), "capital": round(capital, 4)})
                en_operacion = False
            elif cambio <= -sl_pct:
                monto = capital * 0.01
                perdida = monto * (sl_pct / 100)
                capital -= perdida
                capital_max = max(capital_max, capital)
                dd = ((capital_max - capital) / capital_max) * 100
                max_drawdown = max(max_drawdown, dd)
                operaciones.append({"tipo": "SL", "entrada": precio_entrada, "salida": precio_actual, "ganancia": round(-perdida, 4), "capital": round(capital, 4)})
                en_operacion = False
        else:
            if fase == "LATERAL" and rsi_min <= rsi <= rsi_max and abs(ema_c - ema_l) / ema_l * 100 < 2.0:
                en_operacion = True
                precio_entrada = precio_actual
            elif fase == "ALCISTA" and rsi_min <= rsi <= 70 and ema_c > ema_l:
                en_operacion = True
                precio_entrada = precio_actual

    return operaciones, capital, max_drawdown

def ejecutar_backtest():
    print("🔬 Ejecutando backtest historico...\n")
    os.makedirs(os.path.dirname(REPORTE_BACKTEST), exist_ok=True)

    resultados = {}
    total_ops = 0
    total_tp = 0
    total_sl = 0
    capital_global = 1000.0

    for symbol in SIMBOLOS:
        print(f"  📊 Procesando {symbol}...")
        cierres = fetch_velas_historicas(symbol, limite=500)
        if not cierres:
            print(f"  ⚠️ Sin datos para {symbol}")
            continue

        ops, capital_final, max_dd = simular_operaciones(symbol, cierres, 3, 3, 45, 55)
        tp = len([o for o in ops if o["tipo"] == "TP"])
        sl = len([o for o in ops if o["tipo"] == "SL"])
        winrate = round((tp / len(ops)) * 100, 2) if ops else 0
        ganancia = round(capital_final - 1000, 4)

        resultados[symbol] = {
            "total_operaciones": len(ops),
            "tp": tp,
            "sl": sl,
            "winrate": winrate,
            "capital_final": round(capital_final, 4),
            "ganancia_neta": ganancia,
            "max_drawdown": round(max_dd, 2)
        }

        total_ops += len(ops)
        total_tp += tp
        total_sl += sl

        print(f"  ✅ {symbol} | Ops: {len(ops)} | TP: {tp} | SL: {sl} | WR: {winrate}% | Ganancia: ${ganancia} | MaxDD: {round(max_dd,2)}%")

    winrate_global = round((total_tp / total_ops) * 100, 2) if total_ops else 0

    reporte = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "resumen": {
            "total_operaciones": total_ops,
            "total_tp": total_tp,
            "total_sl": total_sl,
            "winrate_global": winrate_global,
        },
        "por_simbolo": resultados
    }

    with open(REPORTE_BACKTEST, "w") as f:
        json.dump(reporte, f, indent=2)

    print(f"\n📈 RESUMEN GLOBAL")
    print(f"  Total operaciones : {total_ops}")
    print(f"  Total TP          : {total_tp}")
    print(f"  Total SL          : {total_sl}")
    print(f"  Win Rate global   : {winrate_global}%")
    print(f"\n✅ Reporte guardado en reports_historicos/backtest_resultado.json")

if __name__ == "__main__":
    ejecutar_backtest()
