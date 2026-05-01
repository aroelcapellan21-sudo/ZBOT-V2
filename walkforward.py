# =========================================
# walkforward.py
# Prueba el sistema en datos que no vio
# Valida que no hay sobreajuste
# Sin librerias externas. Constitucion RESPETADA
# =========================================

import json
import os
import urllib.request
import urllib.parse
from datetime import datetime

REPORTE = os.path.expanduser("~/bot-padre-v2/reports_historicos/walkforward_resultado.json")
SIMBOLOS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "AVAXUSDT"]

def fetch_velas(symbol, limite=1000):
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

def simular_ventana(cierres, tp_pct, sl_pct):
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

def ejecutar_walkforward():
    print("🚶 Ejecutando Walk-Forward Test...\n")
    print("  Datos totales  : 1000 velas de 4h (~166 dias)")
    print("  Entrenamiento  : primeras 500 velas")
    print("  Validacion     : ultimas 500 velas\n")

    os.makedirs(os.path.dirname(REPORTE), exist_ok=True)

    TP = 6
    SL = 3.5

    resultados_train = []
    resultados_valid = []

    print(f"{'Activo':>10} {'Fase':>12} {'Ops':>5} {'WR%':>7} {'Ganancia':>10} {'MaxDD':>7}")
    print("-" * 60)

    for symbol in SIMBOLOS:
        cierres = fetch_velas(symbol, limite=1000)
        if not cierres or len(cierres) < 600:
            print(f"  ⚠️ Sin datos suficientes para {symbol}")
            continue

        mitad = len(cierres) // 2
        train = cierres[:mitad]
        valid = cierres[mitad:]

        ops_t, tp_t, sl_t, wr_t, gan_t, dd_t = simular_ventana(train, TP, SL)
        ops_v, tp_v, sl_v, wr_v, gan_v, dd_v = simular_ventana(valid, TP, SL)

        print(f"  {symbol:>10} {'TRAIN':>12} {ops_t:>5} {wr_t:>6}% ${gan_t:>9} {dd_t:>6}%")
        print(f"  {symbol:>10} {'VALIDACION':>12} {ops_v:>5} {wr_v:>6}% ${gan_v:>9} {dd_v:>6}%")
        print()

        resultados_train.append({"symbol": symbol, "ops": ops_t, "winrate": wr_t, "ganancia": gan_t, "max_dd": dd_t})
        resultados_valid.append({"symbol": symbol, "ops": ops_v, "winrate": wr_v, "ganancia": gan_v, "max_dd": dd_v})

    wr_train = round(sum(r["winrate"] for r in resultados_train) / len(resultados_train), 2) if resultados_train else 0
    wr_valid = round(sum(r["winrate"] for r in resultados_valid) / len(resultados_valid), 2) if resultados_valid else 0
    gan_train = round(sum(r["ganancia"] for r in resultados_train), 4)
    gan_valid = round(sum(r["ganancia"] for r in resultados_valid), 4)

    print(f"📈 RESUMEN WALK-FORWARD")
    print(f"  {'':>10} {'WR%':>7} {'Ganancia':>10}")
    print(f"  {'TRAIN':>10} {wr_train:>6}% ${gan_train:>9}")
    print(f"  {'VALIDACION':>10} {wr_valid:>6}% ${gan_valid:>9}")

    if abs(wr_train - wr_valid) < 10:
        print(f"\n  ✅ Sistema CONSISTENTE - diferencia WR menor a 10%")
        diagnostico = "CONSISTENTE"
    else:
        print(f"\n  ⚠️ Sistema puede tener SOBREAJUSTE - diferencia WR mayor a 10%")
        diagnostico = "POSIBLE_SOBREAJUSTE"

    reporte = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "parametros": {"tp": TP, "sl": SL},
        "diagnostico": diagnostico,
        "train": {"winrate": wr_train, "ganancia": gan_train, "detalle": resultados_train},
        "validacion": {"winrate": wr_valid, "ganancia": gan_valid, "detalle": resultados_valid}
    }

    with open(REPORTE, "w") as f:
        json.dump(reporte, f, indent=2)

    print(f"\n✅ Reporte guardado en reports_historicos/walkforward_resultado.json")

if __name__ == "__main__":
    ejecutar_walkforward()
