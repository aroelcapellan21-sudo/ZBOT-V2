# =========================================
# padre_corecro.py
# FIX: Ruta absoluta para REPORTS_DIR
# FIX: No registra reporte completo en eventos.log
# Sin librerias externas. Constitucion RESPETADA
# =========================================

import os
from corecro.corecro import generar_reporte
from memoria.memoria import registrar_corecro

REPORTS_DIR = os.path.expanduser("~/bot-padre-v2/corecro/reports")

def ejecutar_corecro():
    """
    Ejecuta CoreCro de forma silenciosa.
    FIX: Solo registra resumen, no el reporte completo.
    """
    try:
        generar_reporte()
    except Exception as e:
        registrar_corecro(f"Error generando reporte: {e}")
        print(f"[CORECRO] Error: {e}")
        return

    try:
        archivos = [
            a for a in sorted(os.listdir(REPORTS_DIR))
            if a.startswith("corecro_report_")
        ]
        if archivos:
            ultimo = archivos[-1]
            registrar_corecro(f"Reporte generado: {ultimo}")
        else:
            registrar_corecro("Reporte generado correctamente.")
    except Exception as e:
        registrar_corecro(f"Error leyendo reporte: {e}")

    print("✔ CoreCro: reporte generado silenciosamente")

if __name__ == "__main__":
    ejecutar_corecro()
