# =========================================
# centinela/modulos/volatilidad.py
# Monitor de volatilidad anomala
# Detecta movimientos >5% en 1 hora
# Activa modo panico por 30 minutos
# Constitucion RESPETADA
# =========================================

import sys
import os
import urllib.request
import urllib.parse
import json
from datetime import datetime
sys.path.insert(0, os.path.expanduser("~/bot-padre-v2"))

from centinela.estado import estado_global as estado
from centinela.config import (
    ACTIVOS,
    VOLATILIDAD_ANOMALA_PORCENTAJE,
    DURACION_MODO_PANICO
)

NOMBRE = "volatilidad"

def fetch_velas_1h(symbol):
    params = urllib.parse.urlencode({
        "symbol": symbol,
        "interval": "1h",
        "limit": 2
    })
    url = f"https://api.binance.com/api/v3/klines?{params}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        return [float(k[4]) for k in data]
    except:
        return []

def calcular_cambio_1h(symbol):
    velas = fetch_velas_1h(symbol)
    if len(velas) < 2:
        return 0
    cambio = ((velas[-1] - velas[-2]) / velas[-2]) * 100
    return round(abs(cambio), 4)

def verificar_modo_panico():
    if not estado.get("modo_panico"):
        return False
    timestamp_panico = estado.get("timestamp_panico")
    if timestamp_panico is None:
        return False
    ahora = datetime.now().timestamp()
    if ahora - timestamp_panico > DURACION_MODO_PANICO:
        estado.set("modo_panico", False)
        estado.set("timestamp_panico", None)
        return False
    return True

def evaluar():
    if verificar_modo_panico():
        timestamp_panico = estado.get("timestamp_panico")
        tiempo_restante = int(DURACION_MODO_PANICO - (datetime.now().timestamp() - timestamp_panico))
        return {
            "modulo": NOMBRE,
            "nivel": "rojo",
            "motivo": f"MODO PANICO ACTIVO. Tiempo restante: {tiempo_restante} segundos.",
            "accion": "pausar_sistema",
            "datos": {"modo_panico": True, "tiempo_restante": tiempo_restante}
        }

    activos_anomalos = []
    cambios = {}

    for symbol in ACTIVOS:
        cambio = calcular_cambio_1h(symbol)
        cambios[symbol] = cambio
        if cambio >= VOLATILIDAD_ANOMALA_PORCENTAJE:
            activos_anomalos.append(symbol)

    if activos_anomalos:
        estado.set("modo_panico", True)
        estado.set("timestamp_panico", datetime.now().timestamp())
        nivel = "rojo"
        motivo = f"Volatilidad anomala detectada en {activos_anomalos}. Modo panico activado por {DURACION_MODO_PANICO//60} minutos."
        accion = "pausar_sistema"
    else:
        nivel = "verde"
        motivo = "Volatilidad normal en todos los activos."
        accion = "ninguna"

    resultado = {
        "modulo": NOMBRE,
        "nivel": nivel,
        "motivo": motivo,
        "accion": accion,
        "datos": {
            "cambios_1h": cambios,
            "activos_anomalos": activos_anomalos,
            "umbral": VOLATILIDAD_ANOMALA_PORCENTAJE,
            "modo_panico": estado.get("modo_panico"),
        }
    }

    return resultado

if __name__ == "__main__":
    resultado = evaluar()
    print(f"Modulo  : {resultado['modulo']}")
    print(f"Nivel   : {resultado['nivel']}")
    print(f"Motivo  : {resultado['motivo']}")
    print(f"Accion  : {resultado['accion']}")
    print(f"Datos   : {resultado['datos']}")
