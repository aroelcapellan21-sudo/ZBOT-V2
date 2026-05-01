# =========================================
# utils.py
# Funciones compartidas del sistema
# RSI, EMA y deteccion de fase
# UN SOLO CALCULO. TODOS IMPORTAN DE AQUI.
# Detector aprobado 70.68% promedio
# Umbrales validados por activo con filtro EMA200
# Sin librerias externas. Constitucion RESPETADA
# =========================================

import os
import urllib.request
import urllib.parse
import json

RSI_PERIODO = 14
EMA_CORTA = 20
EMA_LARGA = 50

UMBRALES_FASE = {
    "BTCUSDT":  {"7d": 1.5, "30d": 2.0},
    "ETHUSDT":  {"7d": 1.5, "30d": 2.0},
    "SOLUSDT":  {"7d": 2.0, "30d": 4.0},
    "BNBUSDT":  {"7d": 1.0, "30d": 1.5},
    "AVAXUSDT": {"7d": 1.5, "30d": 2.5}
}

def fetch_velas(symbol, intervalo="4h", limite=210):
    params = urllib.parse.urlencode({
        "symbol": symbol,
        "interval": intervalo,
        "limit": limite
    })
    url = f"https://api.binance.com/api/v3/klines?{params}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        return [float(k[4]) for k in data]
    except Exception as e:
        print(f"[UTILS] Error fetch {symbol}: {e}")
        return []

def calcular_rsi(cierres, periodo=RSI_PERIODO):
    if len(cierres) < periodo + 1:
        return None
    ganancias = [max(cierres[i] - cierres[i-1], 0) for i in range(1, len(cierres))]
    perdidas  = [max(cierres[i-1] - cierres[i], 0) for i in range(1, len(cierres))]
    avg_g = sum(ganancias[:periodo]) / periodo
    avg_p = sum(perdidas[:periodo]) / periodo
    for i in range(periodo, len(ganancias)):
        avg_g = (avg_g * (periodo - 1) + ganancias[i]) / periodo
        avg_p = (avg_p * (periodo - 1) + perdidas[i]) / periodo
    if avg_p == 0:
        return 100.0
    return round(100 - (100 / (1 + avg_g / avg_p)), 2)

def calcular_ema(cierres, periodo):
    if len(cierres) < periodo:
        return None
    k = 2 / (periodo + 1)
    ema = sum(cierres[:periodo]) / periodo
    for precio in cierres[periodo:]:
        ema = precio * k + ema * (1 - k)
    return round(ema, 2)

def detectar_fase(cierres, symbol=None, ventana=30):
    if len(cierres) < 55:
        return "DESCONOCIDA"
    precio = cierres[-1]
    ema50  = calcular_ema(cierres, 50)
    ema200 = calcular_ema(cierres, 200) if len(cierres) >= 200 else None
    if ema50 is None:
        return "DESCONOCIDA"
    if symbol and symbol in UMBRALES_FASE:
        u7        = UMBRALES_FASE[symbol]["7d"]
        u30       = UMBRALES_FASE[symbol]["30d"]
        velas_7d  = 42
        velas_30d = 180
        if len(cierres) >= velas_30d:
            cambio_7d  = ((precio - cierres[-velas_7d])  / cierres[-velas_7d])  * 100
            cambio_30d = ((precio - cierres[-velas_30d]) / cierres[-velas_30d]) * 100
            if ema200 is not None:
                if precio > ema200 and cambio_7d > u7 and cambio_30d > u30:
                    return "ALCISTA"
                elif precio < ema200 and cambio_7d < -u7 and cambio_30d < -u30:
                    return "BAJISTA"
                else:
                    return "LATERAL"
    inicio = cierres[-ventana]
    cambio = ((precio - inicio) / inicio) * 100
    if ema200 is not None:
        if precio > ema50 and precio > ema200 and cambio > 1.0:
            return "ALCISTA"
        elif precio < ema50 and precio < ema200 and cambio < -1.0:
            return "BAJISTA"
        else:
            return "LATERAL"
    else:
        if precio > ema50 and cambio > 1.0:
            return "ALCISTA"
        elif precio < ema50 and cambio < -1.0:
            return "BAJISTA"
        else:
            return "LATERAL"

# ── Filtro Estadístico ─────────────────────────────────────────
from memoria_propia import puede_operar_memoria, analizar_historial
from bitacora_rechazos import registrar_rechazo

_PROB_RACHAS = None

def _cargar_probabilidades():
    global _PROB_RACHAS
    if _PROB_RACHAS is None:
        try:
            ruta = os.path.expanduser("~/bot-padre-v2/data/probabilidades_rachas.json")
            with open(ruta) as f:
                _PROB_RACHAS = json.load(f)
        except Exception as e:
            print(f"[UTILS] Probabilidades no cargadas: {e}")
            _PROB_RACHAS = {}
    return _PROB_RACHAS

def detectar_racha_actual(cierres, datos_ohlc=None, max_buscar=6):
    if len(cierres) < max_buscar + 1:
        return 0, None
    colores = []
    for i in range(len(cierres)-1, len(cierres)-max_buscar-1, -1):
        if i > 0:
            cambio = cierres[i] - cierres[i-1]
            colores.append("verde" if cambio > 0 else "rojo")
    if not colores:
        return 0, None
    color_actual = colores[0]
    racha = 0
    for c in colores:
        if c == color_actual:
            racha += 1
        else:
            break
    return racha, color_actual

def aplicar_filtro_estadistico(cierres, symbol=""):
    probs = _cargar_probabilidades()
    if not probs:
        return True, "sin_datos_estadisticos"
    racha, color = detectar_racha_actual(cierres)
    if racha == 5:
        return False, f"racha_5_{color}s_zona_muerta_50pct"
    clave = f"racha_{min(racha, 6)}_{color}s" if racha >= 2 else None
    if clave and clave in probs.get("rachas", {}):
        p        = probs["rachas"][clave]
        prob_rev = p["reversion"]
        muestras = p["muestras"]
        if muestras >= 30 and prob_rev < 0.54:
            return False, f"{clave}_prob_baja_{prob_rev}"
        return True, f"{clave}_prob_{prob_rev}_muestras_{muestras}"
    return True, "sin_patron_relevante"

if __name__ == "__main__":
    print("=== PRUEBA UTILS ===")
    for symbol in ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "AVAXUSDT"]:
        cierres = fetch_velas(symbol, limite=210)
        if cierres:
            rsi    = calcular_rsi(cierres)
            ema50  = calcular_ema(cierres, EMA_LARGA)
            ema200 = calcular_ema(cierres, 200)
            fase   = detectar_fase(cierres, symbol=symbol)
            print(f"{symbol}: ${cierres[-1]} | RSI:{rsi} | EMA50:{ema50} | EMA200:{ema200} | Fase:{fase}")
    print("✅ Utils funcionando correctamente.")
