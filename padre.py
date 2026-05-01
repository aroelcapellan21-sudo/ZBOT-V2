# =========================================
# padre.py - Executor puro
# Rol: Recibe orden limpia y ejecuta.
# NO decide. NO valida. NO calcula.
# Constitucion RESPETADA
# =========================================

from ejecutor import ejecutar_operacion

def ejecutar_orden(moneda, accion, precio):
    """
    Recibe orden limpia de la Matrix.
    Solo ejecuta. Nada mas.
    """
    confirmacion = ejecutar_operacion(moneda, accion, precio)
    print(f"[PADRE] Orden ejecutada: {accion} {moneda} a ${precio}")
    print(f"[PADRE] Confirmacion: {confirmacion}")
    return confirmacion

if __name__ == "__main__":
    print("[PADRE] En espera de ordenes de la Matrix.")
