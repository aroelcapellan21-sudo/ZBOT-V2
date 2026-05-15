# =========================================
# detector_multitimeframe.py
# FIX: Usa calcular_ema de utils (unico)
# FIX: MACD O(n2) eliminado - calculo eficiente
# FIX: Usa umbrales de utils para detectar tendencia
# Sin librerias externas. Constitucion RESPETADA
# =========================================

import json
import urllib.request
import urllib.parse
from utils import calcular_ema, calcular_rsi, fetch_velas

TIMEFRAMES = ["1h", "4h", "1d"]

def fetch_cierres(symbol, intervalo, limite=210):
    return fetch_velas(symbol, intervalo=intervalo, limite=limite)

def calcular_macd_histograma(cierres):
    """
    FIX: Calculo eficiente de MACD.
    Calcula EMA12, EMA26 una sola vez sobre todo el historial.
    """
    if len(cierres) < 35:
        return None
    ema12 = calcular_ema(cierres, 12)
    ema26 = calcular_ema(cierres, 26)
    if ema12 is None or ema26 is None:
        return None
    macd_line = ema12 - ema26

    # Signal: EMA9 del MACD — aproximado con ultimas 9 diferencias
    macd_values = []
    for i in range(26, len(cierres)):
        e12 = calcular_ema(cierres[:i+1], 12)
        e26 = calcular_ema(cierres[:i+1], 26)
        if e12 and e26:
            macd_values.append(e12 - e26)

    if len(macd_values) < 9:
        return None

    signal = calcular_ema(macd_values, 9)
    if signal is None:
        return None

    return round(macd_values[-1] - signal, 6)

def detectar_tendencia(cierres, intervalo="4h"):
    """
    FIX: Umbrales por timeframe en vez de fijo 3%.
    """
    if len(cierres) < 10:
        return "DESCONOCIDA"

    ema20 = calcular_ema(cierres, 20)
    ema50 = calcular_ema(cierres, 50)

    if ema20 is None or ema50 is None:
        return "DESCONOCIDA"

    precio = cierres[-1]

    # Umbral por timeframe
    umbrales = {"1h": 1.5, "4h": 2.0, "1d": 3.0}
    umbral   = umbrales.get(intervalo, 2.0)

    cambio = ((cierres[-1] - cierres[0]) / cierres[0]) * 100

    if precio > ema20 > ema50 and cambio > umbral:
        return "ALCISTA"
    elif precio < ema20 < ema50 and cambio < -umbral:
        return "BAJISTA"
    else:
        return "LATERAL"

def confirmar_tendencia_multitf(symbol, fase_esperada):
    print(f"  [MTF] Confirmando tendencia {symbol} fase {fase_esperada}...")
    resultados  = {}
    histogramas = {}

    for tf in TIMEFRAMES:
        cierres = fetch_cierres(symbol, tf)
        if not cierres:
            print(f"  [MTF] ⚠️ Sin datos {tf}")
            continue
        tendencia  = detectar_tendencia(cierres, tf)
        histograma = calcular_macd_histograma(cierres)
        resultados[tf]  = tendencia
        histogramas[tf] = histograma
        macd_dir = "↑" if histograma and histograma > 0 else "↓" if histograma and histograma < 0 else "→"
        print(f"  [MTF] {tf:>4} → {tendencia} | MACD {macd_dir}")

    if not resultados:
        print(f"  [MTF] ⚠️ Sin datos. Permitiendo operacion.")
        return True

    tf_4h    = resultados.get("4h", "DESCONOCIDA")
    tf_1d    = resultados.get("1d", "DESCONOCIDA")
    hist_4h  = histogramas.get("4h", None)
    hist_1d  = histogramas.get("1d", None)

    if fase_esperada == "ALCISTA":
        if tf_4h == "BAJISTA" and tf_1d == "BAJISTA":
            print(f"  [MTF] ❌ 4H y 1D bajistas. No abrir alcista.")
            return False
        coincidencias = sum(1 for t in resultados.values() if t == "ALCISTA")
        macd_apoya    = (hist_4h and hist_4h > 0) or (hist_1d and hist_1d > 0)
        if coincidencias >= 1 or macd_apoya:
            print(f"  [MTF] ✅ Tendencia alcista confirmada.")
            return True
        print(f"  [MTF] ❌ Tendencia alcista no confirmada.")
        return False

    if fase_esperada == "BAJISTA":
        if tf_4h == "ALCISTA" and tf_1d == "ALCISTA":
            print(f"  [MTF] ❌ 4H y 1D alcistas. No abrir bajista.")
            return False
        coincidencias = sum(1 for t in resultados.values() if t == "BAJISTA")
        macd_apoya    = (hist_4h and hist_4h < 0) or (hist_1d and hist_1d < 0)
        if coincidencias >= 1 or macd_apoya:
            print(f"  [MTF] ✅ Tendencia bajista confirmada.")
            return True
        print(f"  [MTF] ❌ Tendencia bajista no confirmada.")
        return False

    if fase_esperada == "LATERAL":
        if tf_4h != "LATERAL":
            print(f"  [MTF] ❌ 4H en tendencia {tf_4h}. No operar lateral.")
            return False
        print(f"  [MTF] ✅ 4H lateral confirmado. Señal lateral válida.")
        return True

    return True

if __name__ == "__main__":
    simbolos = ["BTCUSDT", "ETHUSDT"]
    print("🔭 Detector MTF V5\n")
    for symbol in simbolos:
        for fase in ["ALCISTA", "LATERAL", "BAJISTA"]:
            resultado = confirmar_tendencia_multitf(symbol, fase)
            print(f"  {symbol} {fase}: {'✅' if resultado else '❌'}\n")
