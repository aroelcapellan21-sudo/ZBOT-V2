# =========================================
# termometro.py
# Clasifica el estado del mercado global
# Ajusta TP, SL y frecuencia de trades
# Nivel institucional. Constitucion RESPETADA
# =========================================

import json
import os
import urllib.request
import urllib.parse
from datetime import datetime
from engine import enviar_aviso

ESTADO_TERMOMETRO = os.path.expanduser("~/bot-padre-v2/signals/estado_termometro.json")

SIMBOLOS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "AVAXUSDT"]

def fetch_velas(symbol, limite=20):
    try:
        params = urllib.parse.urlencode({
            "symbol": symbol,
            "interval": "1h",
            "limit": limite
        })
        url = f"https://api.binance.com/api/v3/klines?{params}"
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        return [float(k[4]) for k in data]
    except:
        return []

def calcular_volatilidad(cierres):
    if len(cierres) < 2:
        return 0
    cambios = [abs((cierres[i] - cierres[i-1]) / cierres[i-1]) * 100 for i in range(1, len(cierres))]
    return round(sum(cambios) / len(cambios), 4)

def calcular_tendencia(cierres):
    if len(cierres) < 10:
        return 0
    cambio = ((cierres[-1] - cierres[0]) / cierres[0]) * 100
    return round(cambio, 2)

def clasificar_mercado():
    volatilidades = []
    tendencias = []

    for symbol in SIMBOLOS:
        cierres = fetch_velas(symbol, limite=50)
        if not cierres:
            continue
        volatilidades.append(calcular_volatilidad(cierres))
        tendencias.append(calcular_tendencia(cierres))

    if not volatilidades:
        return "DESCONOCIDO", 0, 0, obtener_parametros("DESCONOCIDO")

    vol_promedio = round(sum(volatilidades) / len(volatilidades), 4)
    tend_promedio = round(sum(tendencias) / len(tendencias), 2)

    if vol_promedio > 2.0:
        estado = "VOLATILIDAD_EXTREMA"
    elif vol_promedio > 1.0 and abs(tend_promedio) > 3:
        estado = "TENDENCIA_FUERTE"
    elif vol_promedio > 0.5 and abs(tend_promedio) > 1:
        estado = "TENDENCIA_DEBIL"
    elif vol_promedio < 0.3:
        estado = "MERCADO_MUERTO"
    else:
        estado = "TENDENCIA_DEBIL"

    parametros = obtener_parametros(estado)
    guardar_estado(estado, vol_promedio, tend_promedio, parametros)

    return estado, vol_promedio, tend_promedio, parametros

def obtener_parametros(estado):
    if estado == "TENDENCIA_FUERTE":
        return {"tp_mult": 1.5, "sl_mult": 1.2, "operar": True, "descripcion": "Mercado con tendencia fuerte"}
    elif estado == "TENDENCIA_DEBIL":
        return {"tp_mult": 1.0, "sl_mult": 1.0, "operar": True, "descripcion": "Mercado con tendencia debil"}
    elif estado == "VOLATILIDAD_EXTREMA":
        return {"tp_mult": 0.0, "sl_mult": 0.0, "operar": False, "descripcion": "Volatilidad extrema - operacion suspendida"}
    elif estado == "MERCADO_MUERTO":
        return {"tp_mult": 0, "sl_mult": 0, "operar": False, "descripcion": "Mercado sin movimiento - no operar"}
    else:
        return {"tp_mult": 1.0, "sl_mult": 1.0, "operar": True, "descripcion": "Estado desconocido"}

def guardar_estado(estado, volatilidad, tendencia, parametros):
    estado_previo = None
    try:
        if os.path.exists(ESTADO_TERMOMETRO):
            with open(ESTADO_TERMOMETRO) as f:
                estado_previo = json.load(f).get("estado")
    except Exception:
        pass

    try:
        os.makedirs(os.path.dirname(ESTADO_TERMOMETRO), exist_ok=True)
        data = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "estado": estado,
            "volatilidad_promedio": volatilidad,
            "tendencia_promedio": tendencia,
            "parametros": parametros
        }
        with open(ESTADO_TERMOMETRO, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

    if estado_previo is not None and estado_previo != estado:
        if not parametros["operar"]:
            enviar_aviso(
                f"💀 TERMÓMETRO — MERCADO MUERTO\n"
                f"Estado anterior: {estado_previo}\n"
                f"Volatilidad: {volatilidad}% | Tendencia: {tendencia}%\n"
                f"Bot suspendido hasta que el mercado reactive."
            )
        elif estado == "VOLATILIDAD_EXTREMA":
            enviar_aviso(
                f"⚡ TERMÓMETRO — VOLATILIDAD EXTREMA\n"
                f"Estado anterior: {estado_previo}\n"
                f"Volatilidad: {volatilidad}% | Tendencia: {tendencia}%\n"
                f"Bot suspendido hasta que la volatilidad baje."
            )
        elif estado == "TENDENCIA_FUERTE":
            enviar_aviso(
                f"🚀 TERMÓMETRO — TENDENCIA FUERTE\n"
                f"Estado anterior: {estado_previo}\n"
                f"Volatilidad: {volatilidad}% | Tendencia: {tendencia}%\n"
                f"TP/SL ampliados x1.5. Condiciones favorables."
            )
        elif estado_previo == "MERCADO_MUERTO":
            enviar_aviso(
                f"✅ TERMÓMETRO — MERCADO ACTIVO\n"
                f"Estado nuevo: {estado}\n"
                f"Volatilidad: {volatilidad}% | Tendencia: {tendencia}%\n"
                f"Bot reanudando operaciones normales."
            )

def cargar_estado():
    try:
        with open(ESTADO_TERMOMETRO, "r") as f:
            return json.load(f)
    except:
        return {"estado": "TENDENCIA_DEBIL", "parametros": obtener_parametros("TENDENCIA_DEBIL")}

def puede_operar_termometro():
    estado = cargar_estado()
    if not estado["parametros"]["operar"]:
        print(f"  [TERMOMETRO] ❌ {estado['parametros']['descripcion']}")
        return False
    print(f"  [TERMOMETRO] ✅ {estado['estado']} - {estado['parametros']['descripcion']}")
    return True

def obtener_multiplicadores():
    estado = cargar_estado()
    return estado["parametros"]["tp_mult"], estado["parametros"]["sl_mult"]

if __name__ == "__main__":
    print("🌡️ Midiendo temperatura del mercado...")
    estado, vol, tend, params = clasificar_mercado()
    print(f"\n  Estado      : {estado}")
    print(f"  Volatilidad : {vol}%")
    print(f"  Tendencia   : {tend}%")
    print(f"  TP mult     : x{params['tp_mult']}")
    print(f"  SL mult     : x{params['sl_mult']}")
    print(f"  Operar      : {'✅ Si' if params['operar'] else '❌ No'}")
    print(f"  Descripcion : {params['descripcion']}")
