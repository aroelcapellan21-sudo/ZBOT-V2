# =========================================
# centinela/modulos/conectividad.py
# Monitor de conectividad con el exchange
# Ping cada 5 minutos a Binance
# Alerta si falla 3 veces seguidas
# Constitucion RESPETADA
# =========================================

import sys
import os
import urllib.request
import json
from datetime import datetime
sys.path.insert(0, os.path.expanduser("~/bot-padre-v2"))

from centinela.estado import estado_global as estado
from centinela.config import FALLOS_CONECTIVIDAD_PARA_PAUSAR

NOMBRE = "conectividad"
URL_PING = "https://api.binance.com/api/v3/ping"
URL_PRECIO = "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"

def ping_exchange():
    try:
        with urllib.request.urlopen(URL_PING, timeout=5) as resp:
            if resp.status == 200:
                return True
    except:
        pass
    return False

def verificar_precio():
    try:
        with urllib.request.urlopen(URL_PRECIO, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            return float(data["price"]) > 0
    except:
        pass
    return False

def evaluar():
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ping_ok = ping_exchange()
    precio_ok = verificar_precio()
    exchange_online = ping_ok and precio_ok

    fallos = estado.get("fallos_conectividad")

    if exchange_online:
        estado.set("fallos_conectividad", 0)
        estado.set("exchange_online", True)
        estado.set("ultimo_ping", timestamp)
        nivel = "verde"
        motivo = f"Exchange online. Ping OK. Precio OK."
        accion = "ninguna"
    else:
        fallos += 1
        estado.set("fallos_conectividad", fallos)
        estado.set("exchange_online", False)

        if fallos >= FALLOS_CONECTIVIDAD_PARA_PAUSAR:
            nivel = "rojo"
            motivo = f"Exchange offline. {fallos} fallos seguidos. Pausando sistema."
            accion = "pausar_sistema"
        else:
            nivel = "naranja"
            motivo = f"Exchange offline. Fallo {fallos} de {FALLOS_CONECTIVIDAD_PARA_PAUSAR}."
            accion = "alerta_telegram"

    resultado = {
        "modulo": NOMBRE,
        "nivel": nivel,
        "motivo": motivo,
        "accion": accion,
        "datos": {
            "exchange_online": exchange_online,
            "ping_ok": ping_ok,
            "precio_ok": precio_ok,
            "fallos_consecutivos": estado.get("fallos_conectividad"),
            "ultimo_ping": timestamp,
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
