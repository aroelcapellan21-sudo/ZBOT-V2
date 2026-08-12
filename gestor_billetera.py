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
from engine import enviar_aviso

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

def _alertar_cierre_sin_registrar(clase, precio_entrada, monto, moneda):
    """
    Los datos no permiten contabilizar, pero la orden de cierre YA salio a
    Binance. Antes esto solo imprimia una linea que se perdia en el stdout del
    screen; ahora avisa, porque la billetera queda descuadrada.
    """
    msg = (f"[BILLETERA] ⚠️ {clase} NO REGISTRADO en {moneda}: datos invalidos "
           f"(monto=${monto}, entrada=${precio_entrada}). La orden ya se ejecuto "
           f"en Binance — billetera.json quedo descuadrada.")
    print(msg)
    try:
        enviar_aviso(f"⚠️ DESCUADRE {moneda}\n{msg}")
    except Exception as e:
        print(f"[BILLETERA] No se pudo avisar del descuadre: {e}")


def _aplicar_cierre(billetera, precio_entrada, precio_salida, monto, moneda, tipo, qty, usdt):
    """
    Mueve la billetera por un cierre y devuelve el resultado en USDT
    (positivo = ganancia, en TP; el llamador de SL lo invierte de signo).

    qty/usdt vienen del fill REAL que devolvio cerrar_posicion:
      qty  = cripto efectivamente entregada (SELL) o recibida neta (BUY)
      usdt = USDT NETO de comision recibido (SELL) o pagado (BUY)
    Si son None se cae al calculo teorico de siempre (filas escritas antes de
    este cambio, o cierres que no pasaron por cerrar_posicion).
    """
    teorico = qty is None or usdt is None
    if teorico:
        qty  = round(monto / precio_entrada, 8)
        usdt = round(qty * precio_salida, 4)

    if tipo == "BAJISTA":
        billetera["USDT"] = round(billetera.get("USDT", 0) - usdt, 4)
        billetera[moneda] = round(billetera.get(moneda, 0) + qty, 8)
        resultado = round(monto - usdt, 4)
    else:
        billetera["USDT"] = round(billetera.get("USDT", 0) + usdt, 4)
        billetera[moneda] = max(0.0, round(billetera.get(moneda, 0) - qty, 8))
        resultado = round(usdt - monto, 4)
    return resultado, teorico


def registrar_tp(precio_entrada, precio_salida, monto, moneda, tipo="ALCISTA", qty=None, usdt=None):
    if precio_entrada <= 0 or monto < MONTO_MINIMO_BINANCE:
        # Se llega aca DESPUES de que la orden se ejecuto en Binance: salir en
        # silencio deja la billetera sin registrar una venta que si ocurrio.
        _alertar_cierre_sin_registrar("TP", precio_entrada, monto, moneda)
        return 0
    with _billetera_lock():
        billetera = cargar_billetera()
        ganancia, teorico = _aplicar_cierre(
            billetera, precio_entrada, precio_salida, monto, moneda, tipo, qty, usdt)
        guardar_billetera(billetera)
    registrar_historial_billetera(billetera, "TP")
    origen = " (calculo teorico, sin fill real)" if teorico else ""
    print(f"  💰 TP {tipo}: ${precio_entrada} → ${precio_salida} | Ganancia: +${ganancia}{origen}")
    return ganancia

def registrar_sl(precio_entrada, precio_salida, monto, moneda, tipo="ALCISTA", qty=None, usdt=None):
    if precio_entrada <= 0 or monto < MONTO_MINIMO_BINANCE:
        _alertar_cierre_sin_registrar("SL", precio_entrada, monto, moneda)
        return 0
    with _billetera_lock():
        billetera = cargar_billetera()
        resultado, teorico = _aplicar_cierre(
            billetera, precio_entrada, precio_salida, monto, moneda, tipo, qty, usdt)
        guardar_billetera(billetera)
    perdida = round(-resultado, 4)
    registrar_historial_billetera(billetera, "SL")
    origen = " (calculo teorico, sin fill real)" if teorico else ""
    print(f"  🛑 SL {tipo}: ${precio_entrada} → ${precio_salida} | Perdida: -${perdida}{origen}")
    return perdida
