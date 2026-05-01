# =========================================
# brain/data_engine.py - Sin librerias externas
# Constitucion RESPETADA
# RSI calculado desde utils.py - Una sola fuente
# =========================================

import csv
from utils import fetch_velas, calcular_rsi, calcular_ema, detectar_fase

QUINTETO = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "AVAXUSDT"]
EMA_LONG = 200
EMA_SHORT = 50

def fetch_candles(symbol, interval="4h", limit=200):
    return fetch_velas(symbol, intervalo=interval, limite=limit)

def preparar_datos_mercado(symbol, velas_raw):
    if not velas_raw:
        return []
    try:
        if isinstance(velas_raw[0], float):
            cierres = velas_raw
        else:
            cierres = [float(k[4]) for k in velas_raw]
        rsi = calcular_rsi(cierres[-100:])
        ema50 = calcular_ema(cierres, EMA_SHORT)
        ema200 = calcular_ema(cierres, EMA_LONG)
        velas = []
        for cierre in cierres:
            velas.append({
                "close": cierre,
                "ema_50": ema50,
                "ema_200": ema200,
                "rsi": rsi
            })
        guardar_memoria(symbol, velas)
        return velas
    except Exception as e:
        print(f"Error procesando {symbol}: {e}")
        return []

def guardar_memoria(symbol, velas):
    nombre = f"memory_{symbol}.csv"
    campos = ["close", "ema_50", "ema_200", "rsi"]
    try:
        with open(nombre, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=campos)
            writer.writeheader()
            writer.writerows(velas)
    except Exception as e:
        print(f"Error guardando memoria {symbol}: {e}")
