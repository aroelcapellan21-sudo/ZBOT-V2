# =========================================
# centinela/modulos/alertas.py
# Sistema de alertas escalonadas
# Coordina mensajes a Telegram
# Verde / Amarillo / Naranja / Rojo
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
from centinela.config import TELEGRAM_TOKEN_ALERTAS, TELEGRAM_CHAT_ID_ALERTAS

NOMBRE = "alertas"

EMOJIS = {
    "verde": "🟢",
    "amarillo": "🟡",
    "naranja": "🟠",
    "rojo": "🔴"
}

def enviar_alerta_telegram(mensaje):
    if not TELEGRAM_TOKEN_ALERTAS or not TELEGRAM_CHAT_ID_ALERTAS:
        print(f"[CENTINELA] {mensaje}")
        return
    try:
        params = urllib.parse.urlencode({
            "chat_id": TELEGRAM_CHAT_ID_ALERTAS,
            "text": mensaje,
            "parse_mode": "HTML"
        })
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN_ALERTAS}/sendMessage?{params}"
        with urllib.request.urlopen(url, timeout=10) as resp:
            pass
    except Exception as e:
        print(f"[CENTINELA] Error enviando alerta: {e}")

def procesar_resultado(resultado):
    nivel = resultado.get("nivel", "verde")
    motivo = resultado.get("motivo", "")
    accion = resultado.get("accion", "ninguna")
    modulo = resultado.get("modulo", "desconocido")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    emoji = EMOJIS.get(nivel, "⚪")

    if nivel == "verde":
        return

    mensaje = (
        f"{emoji} CENTINELA GUARDIAN - ALERTA {nivel.upper()}\n"
        f"Modulo : {modulo}\n"
        f"Hora   : {timestamp}\n"
        f"Motivo : {motivo}\n"
        f"Accion : {accion}"
    )

    enviar_alerta_telegram(mensaje)

    if accion == "pausar_sistema":
        estado.set("sistema_pausado", True)
        estado.set("nivel_alerta", nivel)
        estado.set("motivo_alerta", motivo)
        print(f"[CENTINELA] 🔴 SISTEMA PAUSADO: {motivo}")

    elif accion == "bloquear_entradas":
        estado.set("nivel_alerta", nivel)
        estado.set("motivo_alerta", motivo)
        print(f"[CENTINELA] 🔴 ENTRADAS BLOQUEADAS: {motivo}")

    elif accion == "alerta_telegram":
        estado.set("nivel_alerta", nivel)
        estado.set("motivo_alerta", motivo)
        print(f"[CENTINELA] {emoji} ALERTA: {motivo}")

def evaluar(resultados):
    nivel_global = "verde"
    for r in resultados:
        nivel = r.get("nivel", "verde")
        if nivel == "rojo":
            nivel_global = "rojo"
            break
        elif nivel == "naranja" and nivel_global != "rojo":
            nivel_global = "naranja"
        elif nivel == "amarillo" and nivel_global not in ["rojo", "naranja"]:
            nivel_global = "amarillo"

    estado.set("nivel_alerta", nivel_global)

    for r in resultados:
        procesar_resultado(r)

    return {
        "modulo": NOMBRE,
        "nivel": nivel_global,
        "motivo": f"Nivel global del sistema: {nivel_global}",
        "accion": "ninguna",
        "datos": {"nivel_global": nivel_global}
    }

if __name__ == "__main__":
    resultados_prueba = [
        {"modulo": "drawdown", "nivel": "amarillo", "motivo": "Drawdown 2.1%", "accion": "alerta_telegram"},
        {"modulo": "conectividad", "nivel": "verde", "motivo": "Online", "accion": "ninguna"},
    ]
    resultado = evaluar(resultados_prueba)
    print(f"Modulo  : {resultado['modulo']}")
    print(f"Nivel   : {resultado['nivel']}")
    print(f"Motivo  : {resultado['motivo']}")
