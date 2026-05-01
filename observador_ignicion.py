# =========================================
# observador_ignicion.py
# Detecta movimientos bruscos en 10 segundos
# FIX: requests eliminado (violaba Constitucion)
# FIX: Rutas absolutas
# FIX: except pass eliminados
# Sin librerias externas. Constitucion RESPETADA
# =========================================

import time
import json
import csv
import os
import urllib.request
import urllib.parse
from datetime import datetime

MONEDAS = [
    'BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'AVAXUSDT',
    'MATICUSDT', 'LINKUSDT', 'DOTUSDT', 'RNDRUSDT', 'NEARUSDT'
]

ADN_CSV       = os.path.expanduser("~/bot-padre-v2/data/adn_mercado.csv")
ESTADO_JSON   = os.path.expanduser("~/bot-padre-v2/signals/estado_ignicion.json")
UMBRAL_PCT    = 0.5   # % de movimiento en 10s para considerar ignicion
INTERVALO     = 10    # segundos entre escaneos

def obtener_precios():
    url = "https://api.binance.com/api/v3/ticker/price"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            datos = json.loads(resp.read().decode())
        return {
            item['symbol']: float(item['price'])
            for item in datos
            if item['symbol'] in MONEDAS
        }
    except Exception as e:
        print(f"[IGNICION] Error obteniendo precios: {e}")
        return None

def guardar_adn(timestamp, moneda, precio, variacion, tipo):
    try:
        os.makedirs(os.path.dirname(ADN_CSV), exist_ok=True)
        escribir_header = not os.path.exists(ADN_CSV) or os.path.getsize(ADN_CSV) == 0
        with open(ADN_CSV, 'a', newline='') as f:
            writer = csv.writer(f)
            if escribir_header:
                writer.writerow(["timestamp", "symbol", "precio", "variacion_pct", "tipo"])
            writer.writerow([timestamp, moneda, precio, round(variacion, 4), tipo])
    except Exception as e:
        print(f"[IGNICION] Error guardando ADN: {e}")

def guardar_estado(igniciones):
    try:
        os.makedirs(os.path.dirname(ESTADO_JSON), exist_ok=True)
        with open(ESTADO_JSON, 'w') as f:
            json.dump({
                "timestamp":  datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "igniciones": igniciones,
                "total":      len(igniciones)
            }, f, indent=2)
    except Exception as e:
        print(f"[IGNICION] Error guardando estado: {e}")

def escanear(precios_anteriores, precios_actuales):
    igniciones = []
    for moneda in MONEDAS:
        p_ant = precios_anteriores.get(moneda)
        p_act = precios_actuales.get(moneda)
        if not p_ant or not p_act or p_ant == 0:
            continue
        variacion = ((p_act - p_ant) / p_ant) * 100
        if abs(variacion) >= UMBRAL_PCT:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            tipo      = "SUBIDA" if variacion > 0 else "BAJADA"
            guardar_adn(timestamp, moneda, p_act, variacion, tipo)
            igniciones.append({
                "symbol":    moneda,
                "precio":    p_act,
                "variacion": round(variacion, 4),
                "tipo":      tipo
            })
            emoji = "🚀" if variacion > 0 else "💥"
            print(f"[{timestamp}] {emoji} IGNICION {tipo}: {moneda} {variacion:+.2f}%")
    return igniciones

if __name__ == "__main__":
    print("=" * 50)
    print("🔥 observador_ignicion - Detector de Movimientos Bruscos")
    print(f"   Umbral  : {UMBRAL_PCT}% en {INTERVALO} segundos")
    print(f"   Monedas : {len(MONEDAS)}")
    print("=" * 50)

    precios_anteriores = obtener_precios()
    if not precios_anteriores:
        print("[IGNICION] Error obteniendo precios iniciales. Reintentando...")
        time.sleep(5)
        precios_anteriores = obtener_precios()

    while True:
        try:
            time.sleep(INTERVALO)
            precios_actuales = obtener_precios()
            if not precios_actuales:
                continue

            igniciones = escanear(precios_anteriores, precios_actuales)
            guardar_estado(igniciones)
            precios_anteriores = precios_actuales

        except KeyboardInterrupt:
            print("\n🛑 observador_ignicion detenido")
            break
        except Exception as e:
            print(f"[IGNICION] Error en ciclo: {e}")
            time.sleep(5)
