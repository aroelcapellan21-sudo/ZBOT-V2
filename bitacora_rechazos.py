import csv
import os
from datetime import datetime

ARCHIVO = os.path.expanduser("~/bot-padre-v2/memoria/rechazos.csv")

def registrar_rechazo(symbol, tipo_senal, precio, rsi, diff_ema, fase, filtro, motivo):
    """Registra una señal rechazada para análisis posterior."""
    # Asegurar que existe el directorio memoria
    os.makedirs(os.path.dirname(ARCHIVO), exist_ok=True)
    es_nuevo = not os.path.exists(ARCHIVO)
    with open(ARCHIVO, "a", newline='') as f:
        writer = csv.writer(f)
        if es_nuevo:
            writer.writerow(["timestamp", "symbol", "tipo", "precio", "rsi", "diff_ema", "fase", "filtro", "motivo"])
        writer.writerow([datetime.now(), symbol, tipo_senal, precio, rsi, diff_ema, fase, filtro, motivo])
