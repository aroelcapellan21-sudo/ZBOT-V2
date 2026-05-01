import os
import requests
import os
import csv
from datetime import datetime

ARCHIVO_HISTORIAL = os.path.expanduser("~/bot-padre-v2/noticias_historial.csv")

def obtener_precio_binance(symbol="BTCUSDT"):
    try:
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
        data = requests.get(url, timeout=10).json()
        return float(data['price'])
    except Exception as e:
        print(f"Error precio: {e}")
        return 0.0

def registrar_evento(noticia, impacto="MEDIO"):
    precio = obtener_precio_binance()
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    file_exists = os.path.isfile(ARCHIVO_HISTORIAL)
    
    with open(ARCHIVO_HISTORIAL, mode='a', newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Fecha", "Evento", "Impacto", "Precio_Inicial", "Var_1h", "Resultado"])
        
        writer.writerow([fecha, noticia, impacto, precio, "PND", "OBSERVANDO"])
    print(f"✅ Registro exitoso: [{noticia}] a ${precio}")

if __name__ == "__main__":
    print("🕵️ Periodista activado...")
    # Forzamos un registro inicial para crear el archivo
    registrar_evento("SISTEMA DE MONITOREO ACTIVADO", "INFO")
