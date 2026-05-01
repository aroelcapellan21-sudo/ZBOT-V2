import os
import time
import json
import urllib.request

# Configuración
ALTS = ['ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'AVAXUSDT']
BTC_SYMBOL = 'BTCUSDT'
ARCHIVO = "fuerza_sector.csv"

def obtener_precio(symbol):
    """Obtiene el precio actual de un símbolo desde Binance"""
    url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            return float(data['price'])
    except Exception as e:
        print(f"Error obteniendo precio de {symbol}: {e}")
        return None

def obtener_variacion_24h(symbol):
    """Obtiene la variación porcentual en 24h de un símbolo"""
    url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            return float(data['priceChangePercent'])
    except Exception as e:
        print(f"Error obteniendo variación de {symbol}: {e}")
        return None

def calcular_fuerza_sector():
    """
    Calcula la fuerza relativa del sector de altcoins frente a BTC.
    Retorna: (fuerza_promedio, estado, confianza)
    """
    btc_variacion = obtener_variacion_24h(BTC_SYMBOL)
    if btc_variacion is None:
        return None, "ERROR", 0
    
    # Calcular variación promedio de las altcoins
    alt_variaciones = []
    for alt in ALTS:
        var = obtener_variacion_24h(alt)
        if var is not None:
            alt_variaciones.append(var)
    
    if not alt_variaciones:
        return None, "ERROR", 0
    
    alt_promedio = sum(alt_variaciones) / len(alt_variaciones)
    
    # Calcular fuerza relativa (diferencia entre altcoins y BTC)
    fuerza = alt_promedio - btc_variacion
    
    # Interpretar fuerza
    if fuerza > 2.0:
        estado = "MUY_FUERTE"
        confianza = "Alta"
    elif fuerza > 0.5:
        estado = "FUERTE"
        confianza = "Media"
    elif fuerza > -0.5:
        estado = "SINCRONIZADO"
        confianza = "Media"
    elif fuerza > -2.0:
        estado = "DEBIL"
        confianza = "Media"
    else:
        estado = "MUY_DEBIL"
        confianza = "Alta"
    
    return round(fuerza, 2), estado, confianza

def analizar_sector():
    """Analiza el sector y guarda resultados"""
    fuerza, estado, confianza = calcular_fuerza_sector()
    
    if fuerza is None:
        print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Error obteniendo datos")
        return
    
    with open(ARCHIVO, "a") as f:
        linea = f"{time.strftime('%Y-%m-%d %H:%M:%S')},SECTOR_ALTS,Fuerza:{fuerza},Estado:{estado},Confianza:{confianza}\n"
        f.write(linea)
        print(linea.strip())

if __name__ == "__main__":
    # Crear archivo con encabezado si no existe
    if not os.path.exists(ARCHIVO):
        with open(ARCHIVO, "w") as f:
            f.write("timestamp,sector,fuerza,estado,confianza\n")
    
    print("🚀 Iniciando monitoreo de fuerza del sector")
    print("   Comparando altcoins vs BTC cada 10 minutos...\n")
    
    while True:
        analizar_sector()
        time.sleep(600)  # 10 minutos
