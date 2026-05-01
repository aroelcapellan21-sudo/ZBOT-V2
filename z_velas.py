#!/usr/bin/env python3
# =========================================
# z_velas.py - Escáner de Estructuras de Velas
# Detecta absorciones (pin bars) e inyecciones (marubozu)
# Basado en velas de 1 minuto o 5 minutos
# =========================================

import time
import os
import json
import urllib.request
from datetime import datetime

# Configuración
ACTIVOS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'AVAXUSDT']
INTERVALO = "5m"  # Velas de 5 minutos para detectar estructuras
UMBRAL_ABSORCION = 0.70  # 70% de mecha para considerar pin bar
UMBRAL_INYECCION = 0.90  # 90% de cuerpo para considerar marubozu

ARCHIVO_ESTADO = "estado/z_velas.json"
ARCHIVO_LOG = "velas_estructuras.log"

def obtener_ultima_vela(symbol):
    """Obtiene la última vela completada de Binance"""
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={INTERVALO}&limit=2"
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            datos = json.loads(response.read().decode())
            if len(datos) >= 2:
                # Tomar la penúltima vela (la última completada, no la actual)
                vela = datos[-2]
                return {
                    "open": float(vela[1]),
                    "high": float(vela[2]),
                    "low": float(vela[3]),
                    "close": float(vela[4]),
                    "timestamp": vela[0],
                    "time_str": datetime.fromtimestamp(vela[0]/1000).strftime('%Y-%m-%d %H:%M:%S')
                }
    except Exception as e:
        print(f"Error obteniendo vela de {symbol}: {e}")
    return None

def analizar_estructura(open_p, high, low, close):
    """Detecta la psicología de la vela actual"""
    cuerpo = abs(close - open_p)
    rango_total = high - low
    
    if rango_total == 0:
        return "NEUTRAL", 0, 0
    
    mecha_superior = high - max(open_p, close)
    mecha_inferior = min(open_p, close) - low
    
    # Calcular porcentajes
    pct_mecha_inf = (mecha_inferior / rango_total) * 100 if rango_total > 0 else 0
    pct_mecha_sup = (mecha_superior / rango_total) * 100 if rango_total > 0 else 0
    pct_cuerpo = (cuerpo / rango_total) * 100 if rango_total > 0 else 0
    
    # 1. Detección de Absorción (Pin Bar) - Mecha larga indica rechazo
    if mecha_inferior > (rango_total * UMBRAL_ABSORCION):
        return "ABSORCION_ALCISTA", pct_mecha_inf, pct_cuerpo
    if mecha_superior > (rango_total * UMBRAL_ABSORCION):
        return "ABSORCION_BAJISTA", pct_mecha_sup, pct_cuerpo
    
    # 2. Detección de Inyección (Marubozu) - Cuerpo muy grande indica fuerza
    if cuerpo > (rango_total * UMBRAL_INYECCION):
        if close > open_p:
            return "INYECCION_GAS", pct_cuerpo, 0
        else:
            return "PRESION_VENTA", pct_cuerpo, 0
    
    return "ESTABLE", pct_cuerpo, 0

def interpretar_senal(patron, symbol, precio):
    """Interpreta la señal para el bot"""
    if patron == "ABSORCION_ALCISTA":
        return f"🟢 {symbol} - Posible reversión alcista (pin bar inferior). Precio: ${precio:.2f}"
    elif patron == "ABSORCION_BAJISTA":
        return f"🔴 {symbol} - Posible reversión bajista (pin bar superior). Precio: ${precio:.2f}"
    elif patron == "INYECCION_GAS":
        return f"🔥 {symbol} - Inyección de capital (marubozu alcista). Tendencia fuerte. Precio: ${precio:.2f}"
    elif patron == "PRESION_VENTA":
        return f"💀 {symbol} - Presión de venta (marubozu bajista). Precio: ${precio:.2f}"
    else:
        return f"⚪ {symbol} - Estable. Sin señal clara. Precio: ${precio:.2f}"

def guardar_estado(resultados):
    """Guarda el estado en JSON para el auditor"""
    os.makedirs(os.path.dirname(ARCHIVO_ESTADO), exist_ok=True)
    with open(ARCHIVO_ESTADO, 'w') as f:
        json.dump({
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "intervalo": INTERVALO,
            "resultados": resultados
        }, f, indent=2)

if __name__ == "__main__":
    print("="*50)
    print("👁️ z_velas - Escáner de Estructuras de Velas")
    print(f"   Intervalo: {INTERVALO}")
    print(f"   Activos: {', '.join(ACTIVOS)}")
    print("="*50)
    
    # Crear archivo de log con encabezado
    if not os.path.exists(ARCHIVO_LOG):
        with open(ARCHIVO_LOG, 'w') as f:
            f.write("timestamp,symbol,patron,precio\n")
    
    ya_reportados = {}  # {symbol: timestamp_vela}

    while True:
        try:
            resultados = []
            for symbol in ACTIVOS:
                vela = obtener_ultima_vela(symbol)
                if not vela:
                    continue

                patron, _, _ = analizar_estructura(
                    vela["open"], vela["high"], vela["low"], vela["close"]
                )

                resultados.append({
                    "symbol": symbol,
                    "patron": patron,
                    "precio": vela["close"],
                    "timestamp": vela["time_str"]
                })

                # Solo reportar si es una vela nueva
                clave = f"{symbol}_{vela['timestamp']}"
                if patron != "ESTABLE" and ya_reportados.get(symbol) != clave:
                    print(interpretar_senal(patron, symbol, vela["close"]))
                    ya_reportados[symbol] = clave
                    # Guardar en log solo velas nuevas
                    with open(ARCHIVO_LOG, 'a') as f:
                        f.write(f"{vela['time_str']},{symbol},{patron},{vela['close']:.2f}\n")

            # Guardar estado para el auditor
            guardar_estado(resultados)

            time.sleep(30)  # Evaluar cada 30 segundos
            
        except KeyboardInterrupt:
            print("\n🛑 z_velas detenido")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(10)
