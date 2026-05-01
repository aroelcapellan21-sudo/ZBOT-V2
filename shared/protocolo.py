# El Quinteto Sagrado de Yayo
MONEDAS_PERMITIDAS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "ADAUSDT", "DOTUSDT"]

# Reglas de validación para el Padre
def validar_datos(datos):
    if datos.get("symbol") in MONEDAS_PERMITIDAS:
        return True
    return False
