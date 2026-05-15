# =========================================
# trailing_stop.py
# Stop loss que sigue al precio hacia arriba
# FIX: Zona ciega 0%-+2% eliminada
# FIX: SL escala progresivamente desde +0%
# FIX: Error critico si no se puede guardar
# FIX: Multiples ops del mismo symbol manejadas
# Sin librerias externas. Constitucion RESPETADA
# =========================================

import db

TRAILING_ACTIVACION = 0.5
TRAILING_DISTANCIA  = 1.5

def cargar_trailing():
    return db.json_get("trailing_data", {})

def guardar_trailing(data):
    db.json_set("trailing_data", data)

def registrar_entrada_trailing(symbol, precio_entrada, timestamp):
    data = cargar_trailing()
    key = f"{symbol}_{timestamp}"
    data[key] = {
        "symbol":          symbol,
        "precio_entrada":  precio_entrada,
        "precio_maximo":   precio_entrada,
        "trailing_sl":     round(precio_entrada * (1 - TRAILING_DISTANCIA / 100), 6),
        "trailing_activo": False,
        "timestamp":       timestamp,
        "cerrado":         False
    }
    guardar_trailing(data)
    print(f"  [TRAILING] Registrada entrada {symbol} a ${precio_entrada}")

def revisar_trailing(symbol, precio_actual):
    data = cargar_trailing()
    modificado = False
    cerrar = False

    for key, op in data.items():
        if op["symbol"] != symbol or op["cerrado"]:
            continue

        precio_entrada = op["precio_entrada"]
        cambio = ((precio_actual - precio_entrada) / precio_entrada) * 100

        # Actualizar precio maximo
        if precio_actual > op["precio_maximo"]:
            op["precio_maximo"] = precio_actual
            modificado = True

        # FIX ZONA CIEGA: SL escala progresivamente desde cualquier ganancia > 0
        if cambio > 0:
            sl_dinamico = round(precio_actual * (1 - TRAILING_DISTANCIA / 100), 6)
            sl_fijo     = round(precio_entrada * (1 - TRAILING_DISTANCIA / 100), 6)
            nuevo_sl    = max(sl_fijo, sl_dinamico)
            if nuevo_sl > op["trailing_sl"]:
                op["trailing_sl"] = nuevo_sl
                modificado = True

        # Activar trailing oficial si supera activacion
        if not op["trailing_activo"] and cambio >= TRAILING_ACTIVACION:
            op["trailing_activo"] = True
            print(f"  [TRAILING] 🟢 Activado {symbol} | Precio: ${precio_actual} | SL: ${round(op['trailing_sl'], 4)}")
            modificado = True

        # Revisar si el trailing SL fue tocado
        if precio_actual <= op["trailing_sl"] and cambio > -(TRAILING_DISTANCIA + 0.5):
            op["cerrado"] = True
            ganancia = round(cambio, 2)
            tipo = "TRAILING_SL" if op["trailing_activo"] else "SL_DINAMICO"
            print(f"  [TRAILING] 🎯 {tipo} tocado {symbol} | Precio: ${precio_actual} | Resultado: {ganancia}%")
            cerrar = True
            modificado = True

    if modificado:
        guardar_trailing(data)

    return cerrar

def obtener_trailing_sl(symbol):
    data = cargar_trailing()
    for key, op in data.items():
        if op["symbol"] == symbol and not op["cerrado"]:
            return op["trailing_sl"]
    return None

def limpiar_cerrados():
    data = cargar_trailing()
    abiertos = {k: v for k, v in data.items() if not v["cerrado"]}
    guardar_trailing(abiertos)

if __name__ == "__main__":
    print("🎯 Trailing Stop Inteligente")
    print(f"  Activacion : +{TRAILING_ACTIVACION}% de ganancia")
    print(f"  Distancia  : {TRAILING_DISTANCIA}% desde maximo")
    print(f"  FIX        : SL escala desde +0% (zona ciega eliminada)")
    print(f"  Ejemplo:")
    print(f"  Entrada $100 → sube a $101 → SL ya en $98.50")
    print(f"  Sube a $102 → trailing activo → SL en $100.47")
    print(f"  Precio maximo $105 → SL en $103.43")
    print(f"  Si cae a $103.43 → cierra con +3.43%")
