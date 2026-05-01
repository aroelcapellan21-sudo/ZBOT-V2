# =========================================
# HIJO: SAR + RSI TENDENCIAL
# Rol: Confirmador de señal (NO decide)
# =========================================

def evaluar(datos):
    close = datos["close"]
    rsi = datos["rsi"]
    ema200 = datos["ema200"]
    sar = datos["sar"]

    if not close or not rsi or not ema200 or not sar:
        return {"accion": "esperar", "confianza": 0}

    precio = close[-1]
    rsi_actual = rsi[-1]
    ema200_actual = ema200[-1]
    sar_actual = sar[-1]

    # --- CONDICION COMPRA ---
    if (
        precio > ema200_actual and
        sar_actual < precio and
        40 <= rsi_actual <= 55
    ):
        return {"accion": "confirmar_compra", "confianza": 7}

    # --- CONDICION VENTA ---
    if (
        precio < ema200_actual and
        sar_actual > precio and
        45 <= rsi_actual <= 60
    ):
        return {"accion": "confirmar_venta", "confianza": 7}

    return {"accion": "esperar", "confianza": 0}
