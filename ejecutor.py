# =========================================
# ejecutor.py
# Ejecuta operaciones de compra y venta
# FIX: Eliminado fallback $10 silencioso
# FIX: VENTA solo vende cantidad de la op
# FIX: Validacion monto minimo Binance
# FIX: Registro atomico en billetera
# FIX: Lock file contra condicion de carrera
# Sin librerias externas. Constitucion RESPETADA
# =========================================

import json
import os
import fcntl
from gestor_billetera import registrar_historial_billetera

BILLETERA  = os.path.expanduser("~/bot-padre-v2/signals/billetera.json")
LOCK_FILE  = os.path.expanduser("~/bot-padre-v2/signals/ejecutor.lock")
MONTO_MINIMO_BINANCE = 5.0

def ejecutar_operacion(moneda, tipo, precio, monto=None):
    if not monto or monto <= 0:
        return f"❌ RECHAZADO: Monto invalido (${monto})"

    if monto < MONTO_MINIMO_BINANCE:
        return f"❌ RECHAZADO: Monto ${monto:.2f} bajo minimo Binance (${MONTO_MINIMO_BINANCE})"

    os.makedirs(os.path.dirname(LOCK_FILE), exist_ok=True)

    try:
        lock_fd = open(LOCK_FILE, "w")
    except Exception as e:
        return f"❌ ERROR abriendo lock file: {e}"

    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
    except Exception as e:
        lock_fd.close()
        return f"❌ ERROR adquiriendo lock de billetera: {e}"

    try:
        try:
            with open(BILLETERA, "r") as f:
                billetera = json.load(f)
        except Exception as e:
            return f"❌ ERROR leyendo billetera: {e}"

        if tipo == "COMPRA":
            usdt_disponible = billetera.get("USDT", 0)
            if usdt_disponible >= monto:
                billetera["USDT"] = round(usdt_disponible - monto, 4)
                cantidad = monto / precio
                billetera[moneda] = round(billetera.get(moneda, 0) + cantidad, 8)
                resultado = f"✅ EJECUTADO: Compra {moneda} a ${precio} por ${monto:.2f} USDT"
            else:
                return f"❌ RECHAZADO: Fondos insuficientes (necesita ${monto:.2f}, tiene ${usdt_disponible:.2f})"

        elif tipo == "VENTA":
            cantidad_a_vender = monto / precio
            cantidad_disponible = billetera.get(moneda, 0)
            if cantidad_disponible >= cantidad_a_vender:
                billetera[moneda] = round(cantidad_disponible - cantidad_a_vender, 8)
                billetera["USDT"] = round(billetera.get("USDT", 0) + monto, 4)
                resultado = f"✅ EJECUTADO: Venta {moneda} a ${precio} recuperando ${monto:.2f} USDT"
            else:
                return f"❌ RECHAZADO: No tienes suficiente {moneda} (necesita {cantidad_a_vender:.6f}, tiene {cantidad_disponible:.6f})"

        else:
            return f"❌ Tipo desconocido: {tipo}"

        try:
            with open(BILLETERA, "w") as f:
                json.dump(billetera, f, indent=2)
            registrar_historial_billetera(billetera, tipo)
        except Exception as e:
            return f"❌ ERROR CRITICO guardando billetera: {e}"

        return resultado

    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()
