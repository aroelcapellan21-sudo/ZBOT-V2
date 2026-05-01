# =========================================
# backtesting_fase.py
# Backtesting del detector de fase por separado
# Validacion por maximo/minimo alcanzado
# en cualquier momento de las 20 velas futuras
# Sin librerias externas. Constitucion RESPETADA
# =========================================

import urllib.request
import urllib.parse
import json
from datetime import datetime
from utils import detectar_fase

ACTIVOS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "AVAXUSDT"]
UMBRAL = 3.0

def fetch_historico(symbol, limit=1000):
    params = urllib.parse.urlencode({
        "symbol": symbol,
        "interval": "4h",
        "limit": limit
    })
    url = f"https://api.binance.com/api/v3/klines?{params}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        return [float(k[4]) for k in data]
    except Exception as e:
        print(f"Error {symbol}: {e}")
        return []

def validar_fase(fase_detectada, cierres_futuros):
    if len(cierres_futuros) < 20:
        return None
    precio_entrada = cierres_futuros[0]
    maximo = max(cierres_futuros[:20])
    minimo = min(cierres_futuros[:20])
    subida_max = ((maximo - precio_entrada) / precio_entrada) * 100
    bajada_max = ((precio_entrada - minimo) / precio_entrada) * 100

    if fase_detectada == "ALCISTA":
        return "CORRECTO" if subida_max >= UMBRAL else "INCORRECTO"
    elif fase_detectada == "BAJISTA":
        return "CORRECTO" if bajada_max >= UMBRAL else "INCORRECTO"
    else:
        return "CORRECTO" if subida_max < UMBRAL and bajada_max < UMBRAL else "INCORRECTO"

def backtest_detector(symbol):
    print(f"\n{'='*50}")
    print(f"BACKTESTING DETECTOR DE FASE: {symbol}")
    print(f"{'='*50}")

    cierres = fetch_historico(symbol, limit=1000)
    if not cierres:
        print("Sin datos.")
        return None

    resultados = {
        "ALCISTA": {"correctos": 0, "incorrectos": 0},
        "BAJISTA": {"correctos": 0, "incorrectos": 0},
        "LATERAL": {"correctos": 0, "incorrectos": 0}
    }

    total = 0
    correctos_total = 0
    ventana = 210

    for i in range(ventana, len(cierres) - 20):
        segmento = cierres[i-ventana:i]
        futuros = cierres[i:i+20]
        fase = detectar_fase(segmento)
        if fase == "DESCONOCIDA":
            continue
        resultado = validar_fase(fase, futuros)
        if resultado is None:
            continue
        resultados[fase][resultado.lower() + "s"] += 1
        total += 1
        if resultado == "CORRECTO":
            correctos_total += 1

    if total == 0:
        print("Sin evaluaciones suficientes.")
        return None

    print(f"\nTotal evaluaciones : {total}")
    print(f"Correctas          : {correctos_total}")
    print(f"Precision global   : {round((correctos_total/total)*100, 2)}%")
    print(f"\nDesglose por fase:")
    for fase, res in resultados.items():
        tot = res["correctos"] + res["incorrectos"]
        if tot > 0:
            pct = round((res["correctos"] / tot) * 100, 2)
            print(f"  {fase:8}: {res['correctos']}/{tot} correctos ({pct}%)")

    return round((correctos_total/total)*100, 2)

def main():
    print("="*50)
    print("BACKTESTING DETECTOR DE FASE - QUINTETO")
    print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Umbral validacion : {UMBRAL}%")
    print(f"Ventana futura    : 20 velas 4H = 80 horas")
    print("="*50)

    resultados_finales = {}
    for symbol in ACTIVOS:
        precision = backtest_detector(symbol)
        if precision is not None:
            resultados_finales[symbol] = precision

    print(f"\n{'='*50}")
    print("RESUMEN FINAL")
    print(f"{'='*50}")
    for symbol, precision in resultados_finales.items():
        estado = "✅ APROBADO" if precision >= 60 else "❌ REPROBADO"
        print(f"{symbol}: {precision}% {estado}")

    if resultados_finales:
        promedio = sum(resultados_finales.values()) / len(resultados_finales)
        print(f"\nPrecision promedio: {round(promedio, 2)}%")
        if promedio >= 60:
            print("✅ DETECTOR APROBADO - Se puede soltar el freno")
        else:
            print("❌ DETECTOR REPROBADO - Ajustar antes de soltar el freno")

if __name__ == "__main__":
    main()
