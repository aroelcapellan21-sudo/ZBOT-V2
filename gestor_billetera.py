# =========================================
# gestor_billetera.py
# Actualiza el capital despues de TP o SL
# FIX: Fallback silencioso eliminado
# FIX: Error critico si no se puede guardar
# FIX: Validacion de monto minimo Binance
# FIX: Historial CSV para reconstruccion de capital
# Sin librerias externas. Constitucion RESPETADA
# =========================================

import csv
import fcntl
import json
import os
from contextlib import contextmanager
from datetime import datetime

BILLETERA           = os.path.expanduser("~/bot-padre-v2/signals/billetera.json")
HISTORIAL_BILLETERA = os.path.expanduser("~/bot-padre-v2/historial_billetera.csv")
MONEDAS_HISTORIAL   = ["BTC", "ETH", "SOL", "BNB", "AVAX"]
MONTO_MINIMO_BINANCE = 5.0

_LOCK_PATH = BILLETERA + ".lock"

@contextmanager
def _billetera_lock():
    with open(_LOCK_PATH, "w") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)

def registrar_historial_billetera(billetera, evento):
    """Appenda una fila al CSV de historial tras cada escritura exitosa de billetera.json."""
    try:
        escribir_cabecera = not os.path.exists(HISTORIAL_BILLETERA)
        with open(HISTORIAL_BILLETERA, "a", newline="") as f:
            writer = csv.writer(f)
            if escribir_cabecera:
                writer.writerow(["timestamp", "evento", "USDT"] + MONEDAS_HISTORIAL)
            writer.writerow(
                [datetime.now().strftime("%Y-%m-%d %H:%M:%S"), evento,
                 billetera.get("USDT", 0)]
                + [billetera.get(m, 0) for m in MONEDAS_HISTORIAL]
            )
    except Exception as e:
        print(f"[BILLETERA] ⚠️ Error escribiendo historial_billetera.csv: {e}")

def cargar_billetera():
    try:
        with open(BILLETERA, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        raise RuntimeError("[BILLETERA] ERROR CRITICO: billetera.json no encontrada. No operar.")
    except Exception as e:
        raise RuntimeError(f"[BILLETERA] ERROR CRITICO leyendo billetera: {e}")

def guardar_billetera(billetera):
    tmp = BILLETERA + ".tmp"
    try:
        os.makedirs(os.path.dirname(BILLETERA), exist_ok=True)
        with open(tmp, "w") as f:
            json.dump(billetera, f, indent=2)
        os.replace(tmp, BILLETERA)
    except Exception as e:
        raise RuntimeError(f"[BILLETERA] No se pudo guardar. Capital en riesgo: {e}")

def registrar_tp(precio_entrada, precio_salida, monto, moneda, tipo="ALCISTA"):
    if precio_entrada <= 0 or monto < MONTO_MINIMO_BINANCE:
        print(f"[BILLETERA] ⚠️ Datos invalidos para TP. monto=${monto}, entrada=${precio_entrada}")
        return 0
    with _billetera_lock():
        billetera = cargar_billetera()
        cantidad = round(monto / precio_entrada, 8)
        if tipo == "BAJISTA":
            costo_recompra = round(cantidad * precio_salida, 4)
            billetera["USDT"] = round(billetera.get("USDT", 0) - costo_recompra, 4)
            billetera[moneda] = round(billetera.get(moneda, 0) + cantidad, 8)
            ganancia = round(monto - costo_recompra, 4)
        else:
            usdt_recibido = round(cantidad * precio_salida, 4)
            billetera["USDT"] = round(billetera.get("USDT", 0) + usdt_recibido, 4)
            billetera[moneda] = max(0.0, round(billetera.get(moneda, 0) - cantidad, 8))
            ganancia = round(usdt_recibido - monto, 4)
        guardar_billetera(billetera)
    registrar_historial_billetera(billetera, "TP")
    print(f"  💰 TP {tipo}: ${precio_entrada} → ${precio_salida} | Ganancia: +${ganancia}")
    return ganancia

def registrar_sl(precio_entrada, precio_salida, monto, moneda, tipo="ALCISTA"):
    if precio_entrada <= 0 or monto < MONTO_MINIMO_BINANCE:
        print(f"[BILLETERA] ⚠️ Datos invalidos para SL. monto=${monto}, entrada=${precio_entrada}")
        return 0
    with _billetera_lock():
        billetera = cargar_billetera()
        cantidad = round(monto / precio_entrada, 8)
        if tipo == "BAJISTA":
            costo_recompra = round(cantidad * precio_salida, 4)
            billetera["USDT"] = round(billetera.get("USDT", 0) - costo_recompra, 4)
            billetera[moneda] = round(billetera.get(moneda, 0) + cantidad, 8)
            perdida = round(costo_recompra - monto, 4)
        else:
            usdt_recibido = round(cantidad * precio_salida, 4)
            billetera["USDT"] = round(billetera.get("USDT", 0) + usdt_recibido, 4)
            billetera[moneda] = max(0.0, round(billetera.get(moneda, 0) - cantidad, 8))
            perdida = round(monto - usdt_recibido, 4)
        guardar_billetera(billetera)
    registrar_historial_billetera(billetera, "SL")
    print(f"  🛑 SL {tipo}: ${precio_entrada} → ${precio_salida} | Perdida: -${perdida}")
    return perdida
