# =========================================
# consejero.py - Consejero Economico puro
# FIX: Capital total = USDT + valor monedas
# FIX: Umbrales comparados como porcentaje real
# FIX: Usa CAPITAL_BASE de config_cartera
# FIX: Notificaciones Telegram en cambios de estado
# NO decide. NO ejecuta.
# Constitucion RESPETADA
# =========================================

import json
import os
import urllib.request
import urllib.parse
from config_cartera import CAPITAL_BASE
from engine import enviar_aviso

BILLETERA        = os.path.expanduser("~/bot-padre-v2/signals/billetera.json")
ESTADO_CONSEJERO = os.path.expanduser("~/bot-padre-v2/signals/estado_consejero.json")
UMBRAL_SALUDABLE = 90.0
UMBRAL_RIESGO    = 80.0

MONEDAS_PRECIO = {
    "BTC":  "BTCUSDT",
    "ETH":  "ETHUSDT",
    "SOL":  "SOLUSDT",
    "BNB":  "BNBUSDT",
    "AVAX": "AVAXUSDT"
}

def _cargar_estado_previo():
    try:
        if os.path.exists(ESTADO_CONSEJERO):
            with open(ESTADO_CONSEJERO) as f:
                return json.load(f).get("estado", None)
    except Exception:
        pass
    return None

def _guardar_estado_actual(estado):
    try:
        os.makedirs(os.path.dirname(ESTADO_CONSEJERO), exist_ok=True)
        with open(ESTADO_CONSEJERO, "w") as f:
            json.dump({"estado": estado}, f)
    except Exception as e:
        print(f"[CONSEJERO] Error guardando estado: {e}")

def obtener_precio(symbol):
    try:
        params = urllib.parse.urlencode({"symbol": symbol, "interval": "1m", "limit": 1})
        url    = f"https://api.binance.com/api/v3/klines?{params}"
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode())
        return float(data[-1][4])
    except Exception as e:
        print(f"[CONSEJERO] Error precio {symbol}: {e}")
        return 0.0

def calcular_capital_total():
    """Suma USDT + valor actual de todas las monedas en posicion."""
    try:
        with open(BILLETERA, "r") as f:
            bill = json.load(f)
    except Exception as e:
        print(f"[CONSEJERO] Error leyendo billetera: {e}")
        return CAPITAL_BASE

    usdt          = float(bill.get("USDT", 0))
    valor_monedas = 0.0

    for moneda, symbol in MONEDAS_PRECIO.items():
        cantidad = float(bill.get(moneda, 0))
        if cantidad > 0:
            precio = obtener_precio(symbol)
            valor_monedas += cantidad * precio

    return round(usdt + valor_monedas, 2)

def consultar_consejero(capital_actual=None):
    """
    Evalua la salud financiera del sistema.
    FIX: Calcula capital real incluyendo monedas abiertas.
    """
    if capital_actual is None:
        capital_actual = calcular_capital_total()

    pct = (capital_actual / CAPITAL_BASE) * 100

    if pct >= UMBRAL_SALUDABLE:
        estado  = "SALUDABLE"
        mensaje = f"Capital en buen estado ({round(pct,1)}%). Sistema puede operar."
    elif pct >= UMBRAL_RIESGO:
        estado  = "EN RIESGO"
        mensaje = f"Capital reducido ({round(pct,1)}%). Operar con precaucion."
    else:
        estado  = "CRITICO"
        mensaje = f"Capital critico ({round(pct,1)}%). Sistema debe pausar operaciones."

    estado_previo = _cargar_estado_previo()
    _guardar_estado_actual(estado)

    if estado_previo is not None and estado_previo != estado:
        if estado == "CRITICO":
            enviar_aviso(
                f"🚨 CONSEJERO — CAPITAL CRÍTICO\n"
                f"Capital actual : ${capital_actual}\n"
                f"Capital inicial: ${CAPITAL_BASE}\n"
                f"Nivel          : {round(pct, 1)}% (mínimo 80%)\n"
                f"El sistema debe pausar operaciones."
            )
        elif estado == "EN RIESGO":
            enviar_aviso(
                f"⚠️ CONSEJERO — CAPITAL EN RIESGO\n"
                f"Capital actual : ${capital_actual}\n"
                f"Capital inicial: ${CAPITAL_BASE}\n"
                f"Nivel          : {round(pct, 1)}% (saludable ≥90%)\n"
                f"Operar con precaución."
            )
        elif estado == "SALUDABLE" and estado_previo in ("EN RIESGO", "CRITICO"):
            enviar_aviso(
                f"✅ CONSEJERO — CAPITAL RECUPERADO\n"
                f"Capital actual : ${capital_actual}\n"
                f"Capital inicial: ${CAPITAL_BASE}\n"
                f"Nivel          : {round(pct, 1)}% — Sistema operativo."
            )

    return {
        "estado":          estado,
        "capital_actual":  capital_actual,
        "capital_inicial": CAPITAL_BASE,
        "porcentaje":      round(pct, 1),
        "mensaje":         mensaje
    }

if __name__ == "__main__":
    capital = calcular_capital_total()
    resultado = consultar_consejero(capital)
    print(f"Capital total : ${resultado['capital_actual']}")
    print(f"Capital inicio: ${resultado['capital_inicial']}")
    print(f"Porcentaje    : {resultado['porcentaje']}%")
    print(f"Estado        : {resultado['estado']}")
    print(f"Mensaje       : {resultado['mensaje']}")
