# =========================================
# memoria/memoria.py
# Registro de eventos del sistema
# FIX: Logs separados por tipo
# FIX: Eliminada reescritura de __init__.py
# FIX: Funciones duplicadas eliminadas
# FIX: try/except en escritura de logs
# Sin librerias externas. Constitucion RESPETADA
# =========================================

import os
from datetime import datetime

LOG_EVENTOS   = os.path.expanduser("~/bot-padre-v2/memoria/eventos.log")
LOG_CORECRO   = os.path.expanduser("~/bot-padre-v2/memoria/corecro.log")
LOG_MATRIX    = os.path.expanduser("~/bot-padre-v2/memoria/matrix.log")
LOG_CENTINELA = os.path.expanduser("~/bot-padre-v2/memoria/centinela.log")

def _escribir_log(ruta, mensaje):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with open(ruta, "a") as f:
            f.write(f"{timestamp} - {mensaje}\n")
    except Exception as e:
        print(f"[MEMORIA] Error escribiendo log {ruta}: {e}")

def registrar_evento(mensaje):
    _escribir_log(LOG_EVENTOS, mensaje)
    print(f"[EVENTO] {mensaje}")

def registrar_corecro(mensaje):
    _escribir_log(LOG_CORECRO, f"[CORECRO] {mensaje}")
    print(f"[CORECRO] {mensaje}")

def registrar_matrix(mensaje):
    _escribir_log(LOG_MATRIX, f"[MATRIX] {mensaje}")
    print(f"[MATRIX] {mensaje}")

def registrar_centinela(mensaje):
    _escribir_log(LOG_CENTINELA, f"[CENTINELA] {mensaje}")
    print(f"[CENTINELA] {mensaje}")
