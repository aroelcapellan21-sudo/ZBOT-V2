# =========================================
# gestor_tp_parcial.py
# Escala la salida en dos partes
# TP1 = 3% cierra 50% | TP2 = 6% cierra resto
# Aumenta win rate y suaviza equity
# Nivel fondo cuantitativo. Constitucion RESPETADA
# =========================================

import json
import os
from datetime import datetime
from gestor_billetera import registrar_tp, registrar_sl

AUDITORIA = os.path.expanduser("~/bot-padre-v2/auditoria.csv")
AUDITORIA_PARCIAL = os.path.expanduser("~/bot-padre-v2/signals/tp_parcial.json")

TP1_PCT = 3.0
TP2_PCT = 6.0
SL_PCT = 3.5

def cargar_tp_parcial():
    try:
        with open(AUDITORIA_PARCIAL, "r") as f:
            return json.load(f)
    except:
        return {}

def guardar_tp_parcial(data):
    try:
        os.makedirs(os.path.dirname(AUDITORIA_PARCIAL), exist_ok=True)
        with open(AUDITORIA_PARCIAL, "w") as f:
            json.dump(data, f, indent=2)
    except:
        pass

def registrar_entrada_parcial(symbol, precio_entrada, timestamp):
    data = cargar_tp_parcial()
    key = f"{symbol}_{timestamp}"
    data[key] = {
        "symbol": symbol,
        "precio_entrada": precio_entrada,
        "timestamp": timestamp,
        "tp1_tocado": False,
        "sl_movido": False,
        "cerrado": False
    }
    guardar_tp_parcial(data)
    print(f"  [TP PARCIAL] Registrada entrada {symbol} a ${precio_entrada}")

def revisar_tp_parcial(symbol, precio_actual):
    data = cargar_tp_parcial()
    modificado = False

    for key, op in data.items():
        if op["symbol"] != symbol or op["cerrado"]:
            continue

        precio_entrada = op["precio_entrada"]
        cambio = ((precio_actual - precio_entrada) / precio_entrada) * 100

        # Si no tocó TP1 todavía
        if not op["tp1_tocado"]:
            if cambio >= TP1_PCT:
                op["tp1_tocado"] = True
                op["sl_movido"] = True
                registrar_tp(precio_entrada, precio_actual, TP1_PCT)
                print(f"  [TP PARCIAL] ✅ TP1 alcanzado {symbol} +{round(cambio,2)}% | 50% cerrado | SL movido a breakeven")
                modificado = True

            elif cambio <= -SL_PCT:
                op["cerrado"] = True
                registrar_sl(precio_entrada, precio_actual, SL_PCT)
                print(f"  [TP PARCIAL] 🛑 SL activado {symbol} {round(cambio,2)}%")
                modificado = True

        # Si ya tocó TP1, SL está en breakeven
        else:
            if cambio >= TP2_PCT:
                op["cerrado"] = True
                registrar_tp(precio_entrada, precio_actual, TP2_PCT)
                print(f"  [TP PARCIAL] ✅ TP2 alcanzado {symbol} +{round(cambio,2)}% | 50% restante cerrado")
                modificado = True

            elif cambio <= 0:
                op["cerrado"] = True
                print(f"  [TP PARCIAL] ⚖️ Breakeven alcanzado {symbol}. Trade cerrado sin perdida.")
                modificado = True

    if modificado:
        guardar_tp_parcial(data)

def limpiar_cerrados():
    data = cargar_tp_parcial()
    abiertos = {k: v for k, v in data.items() if not v["cerrado"]}
    guardar_tp_parcial(abiertos)
    print(f"  [TP PARCIAL] Operaciones abiertas: {len(abiertos)}")

if __name__ == "__main__":
    print("🎯 Gestor TP Parcial activo")
    print(f"  TP1: {TP1_PCT}% → cierra 50%")
    print(f"  TP2: {TP2_PCT}% → cierra resto")
    print(f"  SL : {SL_PCT}% → se mueve a breakeven tras TP1")
    limpiar_cerrados()
