# =========================================
# gestor_correlacion.py
# FIX: imports dentro de funciones eliminados
# FIX: Usa detectar_fase de utils (unico detector)
# FIX: Correlacion por direccion real
# Sin librerias externas. Constitucion RESPETADA
# =========================================

import json
import os
import urllib.request
import urllib.parse
from utils import fetch_velas, detectar_fase

AUDITORIA           = os.path.expanduser("~/bot-padre-v2/auditoria.csv")
MAX_TRADES_MISMA_DIR = 2

def cargar_operaciones_abiertas():
    try:
        with open(AUDITORIA, "r") as f:
            lineas = f.readlines()
        abiertas = []
        for linea in lineas[1:]:
            partes = linea.strip().split(",")
            if len(partes) >= 6 and partes[5] == "ABIERTA":
                abiertas.append({
                    "timestamp": partes[0],
                    "accion":    partes[1],
                    "symbol":    partes[2],
                    "precio":    float(partes[3]),
                })
        return abiertas
    except Exception as e:
        print(f"  [CORRELACION] Error leyendo auditoria: {e}")
        return []

def obtener_fase_btc():
    try:
        cierres = fetch_velas("BTCUSDT", limite=210)
        if not cierres:
            return "DESCONOCIDA"
        return detectar_fase(cierres, symbol="BTCUSDT")
    except Exception as e:
        print(f"  [CORRELACION] Error obteniendo fase BTC: {e}")
        return "DESCONOCIDA"

def puede_operar(accion_nueva, symbol_nuevo):
    abiertas = cargar_operaciones_abiertas()

    trades_misma_dir = [op for op in abiertas if op["accion"] == accion_nueva]
    count_misma_dir  = len(trades_misma_dir)

    print(f"  [CORRELACION] Accion: {accion_nueva} | Trades misma dir: {count_misma_dir}/{MAX_TRADES_MISMA_DIR}")

    if count_misma_dir >= MAX_TRADES_MISMA_DIR:
        print(f"  [CORRELACION] ❌ Limite {MAX_TRADES_MISMA_DIR} trades en direccion {accion_nueva}.")
        return False

    fase_btc = obtener_fase_btc()
    print(f"  [CORRELACION] Fase BTC macro: {fase_btc}")

    if accion_nueva == "ALCISTA" and fase_btc == "BAJISTA":
        print(f"  [CORRELACION] ❌ BTC bajista. No abrir LONG en {symbol_nuevo}.")
        return False

    if accion_nueva == "BAJISTA" and fase_btc == "ALCISTA":
        print(f"  [CORRELACION] ❌ BTC alcista. No abrir SHORT en {symbol_nuevo}.")
        return False

    print(f"  [CORRELACION] ✅ Correlacion OK. Puede operar {symbol_nuevo}.")
    return True

def estado_correlacion():
    abiertas  = cargar_operaciones_abiertas()
    alcistas  = len([op for op in abiertas if op["accion"] == "ALCISTA"])
    bajistas  = len([op for op in abiertas if op["accion"] == "BAJISTA"])
    laterales = len([op for op in abiertas if op["accion"] == "LATERAL"])
    fase_btc  = obtener_fase_btc()

    print(f"\n📊 ESTADO CORRELACION")
    print(f"  BTC macro     : {fase_btc}")
    print(f"  Trades ALCISTA: {alcistas}")
    print(f"  Trades BAJISTA: {bajistas}")
    print(f"  Trades LATERAL: {laterales}")
    print(f"  Total abiertos: {len(abiertas)}")

if __name__ == "__main__":
    estado_correlacion()
