# =========================================
# centinela/modulos/drawdown.py
# Monitor de Drawdown en tiempo real
# Usa High Water Mark para calculo real
# Alerta escalonada: amarillo naranja rojo
# Constitucion RESPETADA
# =========================================

import sys
import os
sys.path.insert(0, os.path.expanduser("~/bot-padre-v2"))

from centinela.estado import estado_global as estado
from centinela.config import (
    DRAWDOWN_DIARIO_AMARILLO, DRAWDOWN_DIARIO_NARANJA, DRAWDOWN_DIARIO_ROJO,
    DRAWDOWN_SEMANAL_AMARILLO, DRAWDOWN_SEMANAL_NARANJA, DRAWDOWN_SEMANAL_ROJO,
    DRAWDOWN_POR_ACTIVO_MAX
)

NOMBRE = "drawdown"

def evaluar():
    capital_actual = estado.get("capital_actual")
    dd_diario = estado.get("drawdown_diario")
    dd_semanal = estado.get("drawdown_semanal")
    capital_max_dia = estado.get("capital_maximo_dia")

    nivel = "verde"
    motivo = ""
    accion = "ninguna"

    # Evaluar drawdown diario
    if dd_diario >= DRAWDOWN_DIARIO_ROJO:
        nivel = "rojo"
        motivo = f"Drawdown diario {dd_diario}% supera limite rojo {DRAWDOWN_DIARIO_ROJO}%"
        accion = "pausar_sistema"
    elif dd_diario >= DRAWDOWN_DIARIO_NARANJA:
        nivel = "naranja"
        motivo = f"Drawdown diario {dd_diario}% supera limite naranja {DRAWDOWN_DIARIO_NARANJA}%"
        accion = "alerta_telegram"
    elif dd_diario >= DRAWDOWN_DIARIO_AMARILLO:
        nivel = "amarillo"
        motivo = f"Drawdown diario {dd_diario}% supera limite amarillo {DRAWDOWN_DIARIO_AMARILLO}%"
        accion = "alerta_telegram"

    # Evaluar drawdown semanal si es mas grave
    if dd_semanal >= DRAWDOWN_SEMANAL_ROJO and nivel != "rojo":
        nivel = "rojo"
        motivo = f"Drawdown semanal {dd_semanal}% supera limite rojo {DRAWDOWN_SEMANAL_ROJO}%"
        accion = "pausar_sistema"
    elif dd_semanal >= DRAWDOWN_SEMANAL_NARANJA and nivel not in ["rojo"]:
        nivel = "naranja"
        motivo = f"Drawdown semanal {dd_semanal}% supera limite naranja {DRAWDOWN_SEMANAL_NARANJA}%"
        accion = "alerta_telegram"

    resultado = {
        "modulo": NOMBRE,
        "nivel": nivel,
        "motivo": motivo,
        "accion": accion,
        "datos": {
            "capital_actual": capital_actual,
            "capital_maximo_dia": capital_max_dia,
            "drawdown_diario": dd_diario,
            "drawdown_semanal": dd_semanal,
        }
    }

    return resultado

if __name__ == "__main__":
    # Simulacion de prueba
    estado.actualizar_capital(1000.0)
    estado.actualizar_capital(980.0)  # Simula caida de 2%
    resultado = evaluar()
    print(f"Modulo  : {resultado['modulo']}")
    print(f"Nivel   : {resultado['nivel']}")
    print(f"Motivo  : {resultado['motivo']}")
    print(f"Accion  : {resultado['accion']}")
    print(f"Datos   : {resultado['datos']}")
