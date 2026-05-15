# =========================================
# guardian_riesgo.py - VERSION V2.14
# FIX: Imports dentro de funciones eliminados
# FIX: Fallback $1000 silencioso eliminado
# FIX: esta_bloqueado() sin doble HTTP
# FIX: guardar_estado_riesgo con error visible
# FIX: Notificaciones Telegram en transiciones de bloqueo
# Sin librerias externas. Constitucion RESPETADA
# =========================================

import json
import os
import urllib.request
import urllib.parse
from datetime import datetime
from engine import enviar_aviso

BILLETERA     = os.path.expanduser("~/bot-padre-v2/signals/billetera.json")
ESTADO_RIESGO = os.path.expanduser("~/bot-padre-v2/signals/estado_riesgo.json")

DRAWDOWN_MAXIMO_PCT      = 0.10
PERDIDA_DIARIA_MAXIMA_PCT = 0.05

MONEDAS_PRECIO = {
    "BTC": "BTCUSDT",
    "ETH": "ETHUSDT",
    "SOL": "SOLUSDT",
    "BNB": "BNBUSDT",
    "AVAX": "AVAXUSDT"
}

def _obtener_precio(symbol):
    try:
        params = urllib.parse.urlencode({"symbol": symbol, "interval": "1m", "limit": 1})
        url    = f"https://api.binance.com/api/v3/klines?{params}"
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode())
        return float(data[-1][4])
    except Exception as e:
        print(f"[GUARDIAN] Error precio {symbol}: {e}")
        return 0.0

def cargar_billetera():
    try:
        with open(BILLETERA, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        raise RuntimeError("[GUARDIAN] ERROR CRITICO: billetera.json no encontrada.")
    except Exception as e:
        raise RuntimeError(f"[GUARDIAN] ERROR CRITICO leyendo billetera: {e}")

    usdt          = float(data.get("USDT", 0))
    valor_monedas = 0.0

    for moneda, symbol in MONEDAS_PRECIO.items():
        cantidad = float(data.get(moneda, 0))
        if cantidad > 0:
            precio = _obtener_precio(symbol)
            valor_monedas += cantidad * precio

    return round(usdt + valor_monedas, 2)

def cargar_estado_riesgo(capital_actual):
    try:
        if os.path.exists(ESTADO_RIESGO):
            with open(ESTADO_RIESGO, "r") as f:
                return json.load(f)
    except Exception as e:
        print(f"[GUARDIAN] Error cargando estado_riesgo: {e}")

    return {
        "capital_maximo_historico": capital_actual,
        "capital_inicio_dia":       capital_actual,
        "fecha":                    datetime.now().strftime("%Y-%m-%d"),
        "bloqueado":                False,
        "bloqueado_dia":            False
    }

def guardar_estado_riesgo(estado):
    try:
        os.makedirs(os.path.dirname(ESTADO_RIESGO), exist_ok=True)
        with open(ESTADO_RIESGO, "w") as f:
            json.dump(estado, f, indent=2)
    except Exception as e:
        print(f"[GUARDIAN] ERROR CRITICO guardando estado_riesgo: {e}")

def verificar_riesgo(capital_actual=None):
    if capital_actual is None:
        capital_actual = cargar_billetera()

    estado = cargar_estado_riesgo(capital_actual)
    hoy    = datetime.now().strftime("%Y-%m-%d")

    if estado["fecha"] != hoy:
        estaba_bloqueado = estado.get("bloqueado_dia", False)
        estado["fecha"]              = hoy
        estado["capital_inicio_dia"] = capital_actual
        estado["bloqueado_dia"]      = False
        print(f"[GUARDIAN] Nuevo dia. Capital base: ${capital_actual}")
        if estaba_bloqueado:
            enviar_aviso(
                f"✅ GUARDIAN DESBLOQUEADO — Nuevo día\n"
                f"Capital base hoy: ${capital_actual}"
            )

    if capital_actual > estado.get("capital_maximo_historico", 0):
        estado["capital_maximo_historico"] = capital_actual

    max_hist    = estado["capital_maximo_historico"]
    inicio_dia  = estado["capital_inicio_dia"]

    limite_drawdown = max_hist  * (1 - DRAWDOWN_MAXIMO_PCT)
    limite_diario   = inicio_dia * (1 - PERDIDA_DIARIA_MAXIMA_PCT)

    drawdown_actual = ((max_hist - capital_actual) / max_hist) * 100
    perdida_dia     = ((inicio_dia - capital_actual) / inicio_dia) * 100

    print(f"\n--- AUDITORIA DE RIESGO V2.13 ---")
    print(f"  💰 Capital Actual   : ${round(capital_actual, 2)}")
    print(f"  📈 Maximo Historico : ${round(max_hist, 2)}")
    print(f"  📉 Drawdown Total   : {round(drawdown_actual, 2)}% (Max 10%)")
    print(f"  📅 Perdida Hoy      : {round(perdida_dia, 2)}% (Max 5%)")

    if capital_actual <= limite_drawdown:
        ya_bloqueado = estado.get("bloqueado", False)
        estado["bloqueado"] = True
        guardar_estado_riesgo(estado)
        print(f"  🚨 ALERTA: DRAWDOWN MAXIMO VIOLADO")
        if not ya_bloqueado:
            enviar_aviso(
                f"🚨 GUARDIAN — DRAWDOWN MÁXIMO VIOLADO\n"
                f"Capital actual : ${round(capital_actual, 2)}\n"
                f"Máximo histórico: ${round(max_hist, 2)}\n"
                f"Drawdown       : {round(drawdown_actual, 2)}% (límite 10%)\n"
                f"SISTEMA BLOQUEADO indefinidamente."
            )
        return False

    if capital_actual <= limite_diario:
        ya_bloqueado_dia = estado.get("bloqueado_dia", False)
        estado["bloqueado_dia"] = True
        guardar_estado_riesgo(estado)
        print(f"  🛑 ALERTA: LIMITE DIARIO ALCANZADO")
        if not ya_bloqueado_dia:
            enviar_aviso(
                f"🛑 GUARDIAN — LÍMITE DIARIO ALCANZADO\n"
                f"Capital actual : ${round(capital_actual, 2)}\n"
                f"Capital inicio : ${round(inicio_dia, 2)}\n"
                f"Pérdida hoy    : {round(perdida_dia, 2)}% (límite 5%)\n"
                f"BLOQUEADO hasta mañana."
            )
        return False

    guardar_estado_riesgo(estado)
    return True

def esta_bloqueado():
    """
    FIX: Una sola llamada a cargar_billetera().
    Capital pasado como parametro a verificar_riesgo().
    """
    try:
        capital_actual = cargar_billetera()
    except RuntimeError as e:
        print(f"[GUARDIAN] {e}")
        return True  # Si no hay billetera, bloquear por seguridad

    estado = cargar_estado_riesgo(capital_actual)
    hoy    = datetime.now().strftime("%Y-%m-%d")

    if estado["fecha"] != hoy:
        return not verificar_riesgo(capital_actual)

    return estado.get("bloqueado", False) or estado.get("bloqueado_dia", False)

if __name__ == "__main__":
    if verificar_riesgo():
        print("\n  ✅ RESULTADO: El Guardian autoriza operacion.")
    else:
        print("\n  ❌ RESULTADO: El Guardian BLOQUEA el sistema.")
