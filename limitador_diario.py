# =========================================
# limitador_diario.py
# FIX: guardar_estado_diario error visible
# FIX: contar_operaciones_hoy solo cuenta entradas
# FIX: except pass eliminados
# FIX: Notificaciones Telegram en bloqueos (sin spam)
# Sin librerias externas. Constitucion RESPETADA
# =========================================

import os
from datetime import datetime
from engine import enviar_aviso
import db

AUDITORIA = os.path.expanduser("~/bot-padre-v2/auditoria.csv")

MAX_OPERACIONES_DIA      = 8
MAX_PERDIDAS_CONSECUTIVAS = 4

def _default_diario(hoy):
    return {"fecha": hoy, "operaciones_hoy": 0, "perdidas_consecutivas": 0, "pausado": False}

def cargar_estado_diario():
    hoy  = datetime.now().strftime("%Y-%m-%d")
    data = db.json_get("estado_diario")
    if data is None or data.get("fecha") != hoy:
        data = _default_diario(hoy)
        guardar_estado_diario(data)
    return data

def guardar_estado_diario(data):
    db.json_set("estado_diario", data)

def contar_operaciones_hoy():
    """
    Cuenta solo cierres reales del dia (TP/SL/TRAILING_SL).
    Excluye MANUAL_LEGACY, RECONCILE y cualquier otro estado no operativo.
    Deduplica por (timestamp, symbol) para evitar doble conteo si un cierre
    queda escrito dos veces por procesos solapados.
    """
    try:
        hoy = datetime.now().strftime("%Y-%m-%d")
        with open(AUDITORIA, "r") as f:
            lineas = f.readlines()
        count = 0
        vistos = set()
        for linea in lineas[1:]:
            partes = linea.strip().split(",")
            if (len(partes) >= 6
                    and partes[0].startswith(hoy)
                    and partes[5] in ("TP", "SL", "TRAILING_SL")):
                clave = (partes[0], partes[2])  # (timestamp, symbol)
                if clave not in vistos:
                    vistos.add(clave)
                    count += 1
        return count
    except Exception as e:
        print(f"  [LIMITADOR] Error contando operaciones: {e}")
        return 0

def contar_perdidas_consecutivas():
    try:
        hoy = datetime.now().strftime("%Y-%m-%d")
        with open(AUDITORIA, "r") as f:
            lineas = f.readlines()
        ops = []
        for linea in lineas[1:]:
            partes = linea.strip().split(",")
            if len(partes) >= 6 and partes[5] in ("TP", "SL", "TRAILING_SL") and partes[0].startswith(hoy):
                ops.append(partes[5])
        if not ops:
            return 0
        consecutivas = 0
        for op in reversed(ops):
            if op == "SL":
                consecutivas += 1
            else:
                break
        return consecutivas
    except Exception as e:
        print(f"  [LIMITADOR] Error contando perdidas: {e}")
        return 0

def puede_operar_hoy():
    estado       = cargar_estado_diario()
    ops_hoy      = contar_operaciones_hoy()
    perdidas_consec = contar_perdidas_consecutivas()

    print(f"  [LIMITADOR] Operaciones hoy    : {ops_hoy}/{MAX_OPERACIONES_DIA}")
    print(f"  [LIMITADOR] Perdidas seguidas  : {perdidas_consec}/{MAX_PERDIDAS_CONSECUTIVAS}")

    if estado.get("pausado"):
        print(f"  [LIMITADOR] ❌ Bot pausado por perdidas consecutivas.")
        return False

    if ops_hoy >= MAX_OPERACIONES_DIA:
        print(f"  [LIMITADOR] ❌ Limite diario alcanzado ({MAX_OPERACIONES_DIA} ops).")
        if not estado.get("notificado_limite"):
            estado["notificado_limite"] = True
            guardar_estado_diario(estado)
            enviar_aviso(
                f"📊 LÍMITE DIARIO ALCANZADO\n"
                f"Operaciones hoy: {ops_hoy}/{MAX_OPERACIONES_DIA}\n"
                f"Bot en pausa hasta mañana."
            )
        return False

    if perdidas_consec >= MAX_PERDIDAS_CONSECUTIVAS:
        estado["pausado"] = True
        guardar_estado_diario(estado)
        print(f"  [LIMITADOR] ❌ {MAX_PERDIDAS_CONSECUTIVAS} perdidas seguidas. Bot pausado hoy.")
        enviar_aviso(
            f"🔴 BOT PAUSADO — {MAX_PERDIDAS_CONSECUTIVAS} PÉRDIDAS SEGUIDAS\n"
            f"Pérdidas consecutivas hoy: {perdidas_consec}\n"
            f"El sistema no abrirá nuevas operaciones hasta mañana."
        )
        return False

    print(f"  [LIMITADOR] ✅ Puede operar hoy.")
    return True

if __name__ == "__main__":
    print("📅 Limitador Diario Inteligente\n")
    print(f"  Max operaciones por dia     : {MAX_OPERACIONES_DIA}")
    print(f"  Max perdidas consecutivas   : {MAX_PERDIDAS_CONSECUTIVAS}\n")
    resultado = puede_operar_hoy()
    print(f"\n  Resultado: {'✅ Puede operar' if resultado else '❌ No operar hoy'}")
