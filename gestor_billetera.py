# =========================================
# gestor_billetera.py
# Actualiza el capital despues de TP o SL
# FIX: Fallback silencioso eliminado
# FIX: Error critico si no se puede guardar
# FIX: Validacion de monto minimo Binance
# Sin librerias externas. Constitucion RESPETADA
# =========================================

import json
import os

BILLETERA = os.path.expanduser("~/bot-padre-v2/signals/billetera.json")
MONTO_MINIMO_BINANCE = 5.0

def cargar_billetera():
    try:
        with open(BILLETERA, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        raise RuntimeError("[BILLETERA] ERROR CRITICO: billetera.json no encontrada. No operar.")
    except Exception as e:
        raise RuntimeError(f"[BILLETERA] ERROR CRITICO leyendo billetera: {e}")

def guardar_billetera(billetera):
    try:
        os.makedirs(os.path.dirname(BILLETERA), exist_ok=True)
        with open(BILLETERA, "w") as f:
            json.dump(billetera, f, indent=2)
    except Exception as e:
        print(f"[BILLETERA] ERROR CRITICO guardando: {e}")
        raise RuntimeError(f"[BILLETERA] No se pudo guardar. Capital en riesgo: {e}")

def registrar_tp(precio_entrada, precio_salida, monto, moneda, tipo="ALCISTA"):
    if precio_entrada <= 0 or monto < MONTO_MINIMO_BINANCE:
        print(f"[BILLETERA] ⚠️ Datos invalidos para TP. monto=${monto}, entrada=${precio_entrada}")
        return 0
    billetera = cargar_billetera()
    cantidad = round(monto / precio_entrada, 8)
    if tipo == "BAJISTA":
        # Short cerrado en ganancia: recompramos crypto mas barato
        costo_recompra = round(cantidad * precio_salida, 4)
        billetera["USDT"] = round(billetera.get("USDT", 0) - costo_recompra, 4)
        billetera[moneda] = round(billetera.get(moneda, 0) + cantidad, 8)
        ganancia = round(monto - costo_recompra, 4)
    else:
        # Long cerrado en ganancia: vendemos crypto y recuperamos USDT
        usdt_recibido = round(cantidad * precio_salida, 4)
        billetera["USDT"] = round(billetera.get("USDT", 0) + usdt_recibido, 4)
        billetera[moneda] = max(0.0, round(billetera.get(moneda, 0) - cantidad, 8))
        ganancia = round(usdt_recibido - monto, 4)
    guardar_billetera(billetera)
    print(f"  💰 TP {tipo}: ${precio_entrada} → ${precio_salida} | Ganancia: +${ganancia}")
    return ganancia

def registrar_sl(precio_entrada, precio_salida, monto, moneda, tipo="ALCISTA"):
    if precio_entrada <= 0 or monto < MONTO_MINIMO_BINANCE:
        print(f"[BILLETERA] ⚠️ Datos invalidos para SL. monto=${monto}, entrada=${precio_entrada}")
        return 0
    billetera = cargar_billetera()
    cantidad = round(monto / precio_entrada, 8)
    if tipo == "BAJISTA":
        # Short cerrado en perdida: recompramos crypto mas caro
        costo_recompra = round(cantidad * precio_salida, 4)
        billetera["USDT"] = round(billetera.get("USDT", 0) - costo_recompra, 4)
        billetera[moneda] = round(billetera.get(moneda, 0) + cantidad, 8)
        perdida = round(costo_recompra - monto, 4)
    else:
        # Long cerrado en perdida: vendemos crypto y recuperamos menos USDT
        usdt_recibido = round(cantidad * precio_salida, 4)
        billetera["USDT"] = round(billetera.get("USDT", 0) + usdt_recibido, 4)
        billetera[moneda] = max(0.0, round(billetera.get(moneda, 0) - cantidad, 8))
        perdida = round(monto - usdt_recibido, 4)
    guardar_billetera(billetera)
    print(f"  🛑 SL {tipo}: ${precio_entrada} → ${precio_salida} | Perdida: -${perdida}")
    return perdida
