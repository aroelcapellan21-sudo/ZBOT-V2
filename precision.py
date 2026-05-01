#!/usr/bin/env python3
# =========================================
# z_precision.py - Motor de Precisión (Líder-Seguidor)
# Detecta retraso de correlación e igniciones
# =========================================

import json
import time
import urllib.request
from datetime import datetime
import os

LEADER = 'BTCUSDT'
ARSENAL = ['ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'AVAXUSDT']
ALL_SYMBOLS = [LEADER] + ARSENAL

ARCHIVO_IGNICION = "adn_mercado.csv"
ARCHIVO_LATENCIA = "latencia.log"
ARCHIVO_ESTADO = "estado/z_precision.json"

UMBRAL_IGNICION_BASE = 0.4
UMBRAL_RETRASO_BTC = 0.15
UMBRAL_RETRASO_ALT = 0.03

# FIX 2: Pisos por activo según su volatilidad real
UMBRAL_MINIMO = {
    'ETHUSDT': 0.20,
    'SOLUSDT': 0.25,
    'BNBUSDT': 0.20,
    'AVAXUSDT': 0.40,  # AVAX es más volátil, piso más alto
}
UMBRAL_MAXIMO = 1.5

volatilidad = {symbol: UMBRAL_IGNICION_BASE for symbol in ALL_SYMBOLS}
historial_cambios = {symbol: [] for symbol in ALL_SYMBOLS}
VENTANA_VOLATILIDAD = 20

def get_data():
    url = "https://api.binance.com/api/v3/ticker/24hr"
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            resp = json.loads(response.read().decode())
            return {item['symbol']: {
                'price': float(item['lastPrice']),
                'vol': float(item['quoteVolume']),
                'volume': float(item['volume'])
            } for item in resp if item['symbol'] in ALL_SYMBOLS}
    except Exception as e:
        print(f"Error de conexión: {e}")
        return None

def actualizar_volatilidad(symbol, cambio):
    historial_cambios[symbol].append(abs(cambio))
    if len(historial_cambios[symbol]) > VENTANA_VOLATILIDAD:
        historial_cambios[symbol].pop(0)

    if len(historial_cambios[symbol]) >= 10:
        media = sum(historial_cambios[symbol]) / len(historial_cambios[symbol])
        nuevo_umbral = round(media * 2, 2)
        # FIX 2: Usar piso específico por activo
        piso = UMBRAL_MINIMO.get(symbol, 0.20)
        volatilidad[symbol] = max(piso, min(UMBRAL_MAXIMO, nuevo_umbral))

def detectar_retraso(symbol, cambio_btc, cambio_alt):
    if abs(cambio_btc) > UMBRAL_RETRASO_BTC and abs(cambio_alt) < UMBRAL_RETRASO_ALT:
        with open(ARCHIVO_LATENCIA, 'a') as f:
            f.write(f"{datetime.now()}: {symbol} NO SIGUE a BTC (BTC:{cambio_btc:.2f}% | {symbol}:{cambio_alt:.2f}%)\n")
        return True
    return False

def detectar_ignicion(symbol, cambio, cambio_btc, umbral, precio_actual):
    if abs(cambio) > umbral:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        intensidad = "ALTA" if abs(cambio) > umbral * 1.5 else "MEDIA"

        # FIX 3: Verificar existencia antes de getsize
        escribir_header = not os.path.exists(ARCHIVO_IGNICION) or os.path.getsize(ARCHIVO_IGNICION) == 0
        with open(ARCHIVO_IGNICION, 'a') as f:
            if escribir_header:
                f.write("timestamp,symbol,precio,cambio,umbral,intensidad,btc_ref\n")
            # FIX 1: Campo precio incluido correctamente
            f.write(f"{timestamp},{symbol},{precio_actual:.4f},{cambio:.2f}%,{umbral:.2f}%,{intensidad},{cambio_btc:.2f}%\n")

        print(f"🎯 IGNICIÓN: {symbol} {cambio:+.2f}% (umbral {umbral:.2f}%) | BTC: {cambio_btc:+.2f}%")
        return True
    return False

def guardar_estado(estado):
    os.makedirs(os.path.dirname(ARCHIVO_ESTADO), exist_ok=True)
    with open(ARCHIVO_ESTADO, 'w') as f:
        json.dump(estado, f, indent=2)

# Inicialización
data_prev = get_data()
print(f"[{datetime.now().strftime('%H:%M:%S')}] 🎯 Motor de Precisión Activo")
print(f"   Líder: {LEADER}")
print(f"   Arsenal: {', '.join(ARSENAL)}")
print("=" * 50)

while True:
    try:
        time.sleep(5)
        data_act = get_data()
        if not data_act or not data_prev:
            continue

        btc_p_ant = data_prev[LEADER]['price']
        btc_p_act = data_act[LEADER]['price']
        btc_change = ((btc_p_act - btc_p_ant) / btc_p_ant) * 100

        igniciones = []
        retrasos = []

        for symbol in ARSENAL:
            if symbol not in data_act or symbol not in data_prev:
                continue

            p_act = data_act[symbol]['price']
            p_ant = data_prev[symbol]['price']
            change = ((p_act - p_ant) / p_ant) * 100

            actualizar_volatilidad(symbol, change)
            umbral_ignicion = volatilidad[symbol]

            if detectar_retraso(symbol, btc_change, change):
                retrasos.append(symbol)

            # FIX 1: Pasar precio_actual a la función
            if detectar_ignicion(symbol, change, btc_change, umbral_ignicion, p_act):
                igniciones.append({
                    "symbol": symbol,
                    "precio": round(p_act, 4),
                    "cambio": round(change, 2),
                    "umbral": umbral_ignicion,
                    "btc_ref": round(btc_change, 2)
                })

        guardar_estado({
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "btc_cambio": round(btc_change, 2),
            "igniciones": igniciones,
            "retrasos": retrasos,
            "volatilidad": {k: round(v, 2) for k, v in volatilidad.items()},
            "sugerencia": "Atención a igniciones" if igniciones else "Mercado sin igniciones"
        })

        data_prev = data_act

    except KeyboardInterrupt:
        print("\n🛑 Motor de Precisión detenido")
        break
    except Exception as e:
        print(f"Error: {e}")
        time.sleep(10)
