# =========================================
# centinela/modulos/operaciones.py
# Monitor de operaciones simultaneas
# Limite maximo segun Constitucion
# Bloquea nuevas entradas si se supera
# Constitucion RESPETADA
# =========================================

import sys
import os
sys.path.insert(0, os.path.expanduser("~/bot-padre-v2"))

from centinela.estado import estado_global as estado
from centinela.config import MAX_OPERACIONES_SIMULTANEAS, ACTIVOS

NOMBRE = "operaciones"

def contar_operaciones_abiertas():
    try:
        auditoria = os.path.expanduser("~/bot-padre-v2/auditoria.csv")
        if not os.path.exists(auditoria):
            return 0, {}
        abiertas = 0
        por_activo = {s: 0 for s in ACTIVOS}
        with open(auditoria, "r") as f:
            for linea in f:
                partes = linea.strip().split(",")
                if len(partes) >= 6 and partes[5] == "ABIERTA":
                    abiertas += 1
                    symbol = partes[2] if len(partes) > 2 else "DESCONOCIDO"
                    if symbol in por_activo:
                        por_activo[symbol] += 1
        return abiertas, por_activo
    except:
        return 0, {}

def evaluar():
    total, por_activo = contar_operaciones_abiertas()

    estado.set("operaciones_abiertas", total)
    estado.set("operaciones_por_activo", por_activo)

    nivel = "verde"
    motivo = ""
    accion = "ninguna"

    if total >= MAX_OPERACIONES_SIMULTANEAS:
        nivel = "rojo"
        motivo = f"Operaciones abiertas {total} alcanza limite maximo {MAX_OPERACIONES_SIMULTANEAS}. Bloqueando nuevas entradas."
        accion = "bloquear_entradas"
    elif total >= MAX_OPERACIONES_SIMULTANEAS * 0.8:
        nivel = "amarillo"
        motivo = f"Operaciones abiertas {total} cerca del limite {MAX_OPERACIONES_SIMULTANEAS}."
        accion = "alerta_telegram"

    resultado = {
        "modulo": NOMBRE,
        "nivel": nivel,
        "motivo": motivo,
        "accion": accion,
        "datos": {
            "operaciones_abiertas": total,
            "limite_maximo": MAX_OPERACIONES_SIMULTANEAS,
            "por_activo": por_activo,
        }
    }

    return resultado

if __name__ == "__main__":
    resultado = evaluar()
    print(f"Modulo  : {resultado['modulo']}")
    print(f"Nivel   : {resultado['nivel']}")
    print(f"Motivo  : {resultado['motivo']}")
    print(f"Accion  : {resultado['accion']}")
    print(f"Datos   : {resultado['datos']}")
