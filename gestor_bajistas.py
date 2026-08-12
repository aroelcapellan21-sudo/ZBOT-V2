# =========================================
# gestor_bajistas.py
# Gate central de francotiradores BAJISTAS (SHORT).
# Los shorts son imposibles en cuenta SPOT. Permanecen DESACTIVADOS.
#
# Reactivacion MANUAL (desde 2026-08-12): exige DOS condiciones
#   1. BOT_BAJISTAS_CONFIRMADO=true en el entorno del proceso, y
#   2. saldo suficiente en Futuros USDT-M.
# Antes bastaba (2): fondear futuros por cualquier motivo reactivaba solos a
# los 5 francotiradores bajistas. Eso es peligroso porque la ruta de ejecucion
# sigue siendo SPOT: ejecutar_operacion(..., "VENTA", ...) y
# cerrar_posicion(..., "BAJISTA") operan contra spot, donde un short no existe.
# Fondear futuros NO habilita shorts reales — hay que reescribir el ejecutor.
# Ante cualquier error de API -> DESACTIVADO (seguro).
# Sin librerias externas. Constitucion RESPETADA
# =========================================

import json
import os
import time
import hmac
import hashlib
import urllib.request
import urllib.parse
import urllib.error

KEYS_FILE    = os.path.expanduser("~/bot-padre-v2/keys.env")
ESTADO_FILE  = os.path.expanduser("~/bot-padre-v2/signals/estado_bajistas.json")
FUTURES_BASE = "https://fapi.binance.com"

# Saldo minimo de futuros (USDT) para reactivar los bajistas.
# Binance Futures exige ~5 USDT de notional minimo por orden.
SALDO_MINIMO_FUTUROS = 5.0

# Cache para no consultar Binance en cada ciclo (5 directores cada 60s).
_CACHE_TTL = 300  # segundos
_cache = {"ts": 0.0, "activos": False, "saldo": 0.0}


def _cargar_keys():
    api_key = secret = None
    try:
        with open(KEYS_FILE) as f:
            for linea in f:
                if linea.startswith("BINANCE_API_KEY="):
                    api_key = linea.strip().split("=", 1)[1]
                elif linea.startswith("BINANCE_SECRET_KEY="):
                    secret = linea.strip().split("=", 1)[1]
    except Exception as e:
        raise RuntimeError(f"Error leyendo {KEYS_FILE}: {e}")
    if not api_key or not secret:
        raise RuntimeError("BINANCE_API_KEY o BINANCE_SECRET_KEY no encontradas")
    return api_key, secret


def _saldo_futuros_usdt():
    """
    Consulta el saldo disponible de USDT en Futuros USDT-M.
    Devuelve availableBalance de USDT, o lanza excepcion si falla.
    """
    api_key, secret = _cargar_keys()
    params = {"timestamp": int(time.time() * 1000), "recvWindow": 5000}
    query  = urllib.parse.urlencode(params)
    sig    = hmac.new(secret.encode(), query.encode(), hashlib.sha256).hexdigest()
    url    = f"{FUTURES_BASE}/fapi/v2/balance?{query}&signature={sig}"
    req    = urllib.request.Request(url, headers={"X-MBX-APIKEY": api_key})
    with urllib.request.urlopen(req, timeout=8) as resp:
        data = json.loads(resp.read().decode())
    for activo in data:
        if activo.get("asset") == "USDT":
            return float(activo.get("availableBalance", 0))
    return 0.0


def _leer_estado_previo():
    try:
        with open(ESTADO_FILE) as f:
            return json.load(f).get("activos")
    except Exception:
        return None


def _guardar_estado(activos, saldo, motivo):
    estado = {
        "activos":       activos,
        "saldo_futuros": round(saldo, 2),
        "umbral":        SALDO_MINIMO_FUTUROS,
        "motivo":        motivo,
        "actualizado":   time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    try:
        tmp = ESTADO_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(estado, f, indent=2)
        os.replace(tmp, ESTADO_FILE)
    except Exception as e:
        print(f"  [BAJISTAS] Error guardando estado: {e}")


def _notificar_transicion(previo, activos_nuevo, saldo):
    """Avisa por Telegram + log SOLO cuando cambia el estado."""
    if previo == activos_nuevo:
        return  # sin cambio, no spamear

    # imports diferidos para evitar ciclos al cargar el modulo
    try:
        from memoria.memoria import registrar_evento
        from engine import enviar_aviso
        if activos_nuevo:
            registrar_evento(
                f"BAJISTAS REACTIVADOS: saldo futuros ${round(saldo,2)} >= ${SALDO_MINIMO_FUTUROS}"
            )
            enviar_aviso(
                f"🟢 FRANCOTIRADORES BAJISTAS REACTIVADOS\n"
                f"Saldo Futuros USDT-M: ${round(saldo,2)}\n"
                f"Los shorts vuelven a operar."
            )
        else:
            registrar_evento(
                f"BAJISTAS EN PAUSA: sin saldo en futuros (${round(saldo,2)})"
            )
            enviar_aviso(
                f"⏸️ FRANCOTIRADORES BAJISTAS EN PAUSA\n"
                f"Sin fondos en Futuros USDT-M (${round(saldo,2)}).\n"
                f"El bot opera solo ALCISTA y LATERAL."
            )
    except Exception as e:
        print(f"  [BAJISTAS] Error notificando transicion: {e}")


def _autorizacion_manual():
    """
    Segunda llave, deliberada y fuera del repo. Mismo patron que
    BOT_REAL_CONFIRMADO para el paso a REAL: no vive en ningun archivo
    versionado, se exporta a mano en la sesion screen el dia que se decida
    reactivar los shorts — despues de reescribir el ejecutor para futuros.
    """
    return os.environ.get("BOT_BAJISTAS_CONFIRMADO", "").strip().lower() == "true"


def bajistas_activos():
    """
    True solo si hay autorizacion manual explicita Y saldo suficiente en
    Futuros USDT-M. Cachea 5 min. Ante cualquier error -> DESACTIVADO.
    """
    ahora = time.time()
    if ahora - _cache["ts"] < _CACHE_TTL:
        return _cache["activos"]

    if not _autorizacion_manual():
        # Corta antes de consultar la API: sin la llave manual el saldo de
        # futuros es irrelevante, y ademas evita una llamada por ciclo.
        saldo   = 0.0
        activos = False
        motivo  = "sin_autorizacion_manual"
        print("  [BAJISTAS] Sin BOT_BAJISTAS_CONFIRMADO=true — desactivados (gate manual).")
    else:
        try:
            saldo   = _saldo_futuros_usdt()
            activos = saldo >= SALDO_MINIMO_FUTUROS
            motivo  = "saldo_suficiente" if activos else "saldo_insuficiente"
        except Exception as e:
            # Cuenta solo spot, sin permiso de futuros, o API caida -> desactivado.
            saldo   = 0.0
            activos = False
            motivo  = f"error_api: {e}"
            print(f"  [BAJISTAS] Sin acceso a futuros, desactivados: {e}")

    previo = _leer_estado_previo()
    _notificar_transicion(previo, activos, saldo)
    _cache.update({"ts": ahora, "activos": activos, "saldo": saldo})
    _guardar_estado(activos, saldo, motivo)
    return activos


if __name__ == "__main__":
    activo = bajistas_activos()
    print(f"Bajistas activos: {activo} | saldo futuros: ${_cache['saldo']}")
