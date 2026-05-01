import os
import time

# Rutas de los reportes de los analistas
ARCHIVOS = {
    "Liquidez": "muros_liquidez.csv",
    "Fuerza": "fuerza_sector.csv",
    "Fugas": "picos_fuga.csv",
    "Volumen": "volumen_real.csv",
    "Precision": "precision.csv",      # Si existe
    "Radar": "radar_noticias.csv"      # Si existe
}

def leer_ultima_linea(archivo):
    if not os.path.exists(archivo):
        return "SIN DATOS"
    try:
        with open(archivo, "r") as f:
            lineas = f.readlines()
            if len(lineas) <= 1:
                return "ESPERANDO DATOS..."
            ultima = lineas[-1].strip()
            # Extraer solo la parte relevante (ej. "OBI:0.1234,COMPRA")
            partes = ultima.split(',')
            if len(partes) >= 3:
                return f"{partes[1]} | {partes[2]}"  # Ajusta según tu formato
            return ultima
    except:
        return "ERROR"

def interpretar_estado(data):
    """Devuelve emoji y color según el contenido"""
    if "FUERTE" in data or "COMPRA" in data or "MURO" in data:
        return "🟢"
    elif "DEBIL" in data or "VENTA" in data:
        return "🔴"
    elif "SINCRONIZADO" in data or "NEUTRAL" in data:
        return "🟡"
    else:
        return "⚪"

def generar_auditoria():
    os.system('clear')
    print("="*55)
    print(f"       🧠 AUDITOR SUPREMO - Z-BOT")
    print(f"       📅 {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*55)
    print("")
    
    for nombre, archivo in ARCHIVOS.items():
        data = leer_ultima_linea(archivo)
        emoji = interpretar_estado(data)
        print(f"   {emoji} {nombre:12} : {data}")
    
    print("")
    print("="*55)
    print("   💡 Sugerencia:")
    
    # Lógica simple de recomendación
    liquidez = leer_ultima_linea(ARCHIVOS.get("Liquidez", ""))
    fuerza = leer_ultima_linea(ARCHIVOS.get("Fuerza", ""))
    
    if "FUERTE" in fuerza and "COMPRA" in liquidez:
        print("   ✅ Liquidez y Fuerza positivas. Mercado con potencial alcista.")
    elif "DEBIL" in fuerza and "VENTA" in liquidez:
        print("   ⚠️  Liquidez y Fuerza negativas. Precaución, posible bajista.")
    else:
        print("   🔍 Observa consistencia entre Liquidez y Fuerza antes de operar.")
    
    print("="*55)
    print("   🔄 Actualiza cada 30s | Ctrl+C para salir")

if __name__ == "__main__":
    try:
        while True:
            generar_auditoria()
            time.sleep(30)
    except KeyboardInterrupt:
        print("\n👋 Auditoría finalizada.")
