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
CAPITAL_MAX_POR_OP = 0.02
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

def registrar_tp(precio_entrada, precio_salida, take_profit_pct):
    billetera = cargar_billetera()
    capital = billetera.get("USDT", 0)
    if capital <= 0:
        print("[BILLETERA] ⚠️ Capital cero o negativo. No se registra TP.")
        return 0
    monto_operacion = capital * CAPITAL_MAX_POR_OP
    if monto_operacion < MONTO_MINIMO_BINANCE:
        print(f"[BILLETERA] ⚠️ Monto ${monto_operacion:.2f} bajo minimo Binance.")
        return 0
    ganancia = monto_operacion * (take_profit_pct / 100)
    billetera["USDT"] = round(capital + ganancia, 4)
    guardar_billetera(billetera)
    print(f"  💰 Billetera: ${capital} → ${billetera['USDT']} (+${round(ganancia, 4)})")
    return ganancia

def registrar_sl(precio_entrada, precio_salida, stop_loss_pct):
    billetera = cargar_billetera()
    capital = billetera.get("USDT", 0)
    if capital <= 0:
        print("[BILLETERA] ⚠️ Capital cero o negativo. No se registra SL.")
        return 0
    monto_operacion = capital * CAPITAL_MAX_POR_OP
    if monto_operacion < MONTO_MINIMO_BINANCE:
        print(f"[BILLETERA] ⚠️ Monto ${monto_operacion:.2f} bajo minimo Binance.")
        return 0
    perdida = monto_operacion * (stop_loss_pct / 100)
    billetera["USDT"] = round(capital - perdida, 4)
    guardar_billetera(billetera)
    print(f"  🛑 Billetera: ${capital} → ${billetera['USDT']} (-${round(perdida, 4)})")
    return perdida
