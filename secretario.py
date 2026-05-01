# =========================================
# secretario.py - Notario perpetuo
# Rol: Solo registra eventos del sistema.
# NO opina. NO analiza. NO decide.
# Constitucion RESPETADA
# =========================================

import csv
import os
from datetime import datetime

REGISTRO = "secretario_log.txt"
AUDITORIA = "secretario_auditoria.csv"

def registrar_evento(modulo, evento):
    """
    Registra cualquier evento del sistema.
    Solo escribe. Nada mas.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    linea = f"[{timestamp}] [{modulo}] {evento}"
    with open(REGISTRO, "a", encoding="utf-8") as f:
        f.write(linea + "\n")

def registrar_operacion(symbol, accion, entrada, salida, motivo, ganancia, capital):
    """
    Registra operacion cerrada en auditoria.
    Solo escribe. Nada mas.
    """
    existe = os.path.exists(AUDITORIA)
    with open(AUDITORIA, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not existe:
            writer.writerow(["fecha", "symbol", "accion", "entrada", "salida", "motivo", "ganancia", "capital"])
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            symbol, accion, entrada, salida, motivo,
            round(ganancia, 2), round(capital, 2)
        ])

if __name__ == "__main__":
    print("[SECRETARIO] En espera de eventos para registrar.")
