# =========================================
# ejecutor.py
# Ejecuta operaciones de compra y venta en Binance real
# FIX: Eliminado fallback $10 silencioso
# FIX: VENTA solo vende cantidad de la op
# FIX: Validacion monto minimo Binance
# FIX: Registro atomico en billetera
# FIX: Lock file contra condicion de carrera
# FIX: Conectado a api.binance.com con keys de keys.env
# FIX: Lot size por simbolo (precision Binance)
# FIX: Modo Simulador Activo via signals/modo.json
# Sin librerias externas. Constitucion RESPETADA
# =========================================

import json
import os
import fcntl
import hmac
import hashlib
import time
import urllib.request
import urllib.parse
import urllib.error
from gestor_billetera import registrar_historial_billetera

BILLETERA            = os.path.expanduser("~/bot-padre-v2/signals/billetera.json")
LOCK_FILE            = os.path.expanduser("~/bot-padre-v2/signals/ejecutor.lock")
KEYS_FILE            = os.path.expanduser("~/bot-padre-v2/keys.env")
MODO_FILE            = os.path.expanduser("~/bot-padre-v2/signals/modo.json")
MONTO_MINIMO_BINANCE = 5.0
BASE_URL             = "https://api.binance.com"

# Decimales de cantidad permitidos por símbolo (LOT_SIZE de Binance)
LOT_SIZE = {
    "BTCUSDT":  5,
    "ETHUSDT":  4,
    "SOLUSDT":  2,
    "BNBUSDT":  3,
    "AVAXUSDT": 2,
}

def _leer_modo():
    try:
        with open(MODO_FILE) as f:
            return json.load(f).get("modo", "REAL")
    except Exception:
        return "REAL"

def _redondear_cantidad(symbol, qty):
    decimales = LOT_SIZE.get(symbol, 6)
    return round(qty, decimales)

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
        raise RuntimeError("BINANCE_API_KEY o BINANCE_SECRET_KEY no encontradas en keys.env")
    return api_key, secret

def _firmar(params, secret):
    query = urllib.parse.urlencode(params)
    signature = hmac.new(secret.encode(), query.encode(), hashlib.sha256).hexdigest()
    return query + "&signature=" + signature

def _precio_ticker(symbol):
    url = f"{BASE_URL}/api/v3/ticker/price?symbol={symbol}"
    with urllib.request.urlopen(url, timeout=5) as resp:
        return float(json.loads(resp.read())["price"])

def _simular_fill(symbol, side, quote_qty=None, base_qty=None):
    precio = _precio_ticker(symbol)
    if side == "BUY":
        if quote_qty is not None:
            qty  = round(quote_qty / precio, LOT_SIZE.get(symbol, 6))
            usdt = quote_qty
        else:
            qty  = base_qty
            usdt = round(base_qty * precio, 2)
    else:
        qty  = base_qty
        usdt = round(base_qty * precio, 2)
    return {"executedQty": str(qty), "cummulativeQuoteQty": str(usdt), "price": str(precio)}

def _orden_mercado(symbol, side, quote_qty=None, base_qty=None):
    api_key, secret = _cargar_keys()
    params = {
        "symbol":    symbol,
        "side":      side,
        "type":      "MARKET",
        "timestamp": int(time.time() * 1000),
    }
    if quote_qty is not None:
        params["quoteOrderQty"] = f"{quote_qty:.2f}"
    elif base_qty is not None:
        params["quantity"] = f"{base_qty}"
    else:
        raise ValueError("Debe especificarse quote_qty o base_qty")

    body = _firmar(params, secret).encode()
    req  = urllib.request.Request(
        f"{BASE_URL}/api/v3/order",
        data=body,
        method="POST",
        headers={
            "X-MBX-APIKEY": api_key,
            "Content-Type": "application/x-www-form-urlencoded",
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        cuerpo = e.read().decode()
        raise RuntimeError(f"Binance {e.code}: {cuerpo}")

def ejecutar_operacion(moneda, tipo, precio, monto=None):
    if not monto or monto <= 0:
        return f"❌ RECHAZADO: Monto invalido (${monto})"

    if monto < MONTO_MINIMO_BINANCE:
        return f"❌ RECHAZADO: Monto ${monto:.2f} bajo minimo Binance (${MONTO_MINIMO_BINANCE})"

    symbol     = moneda + "USDT"
    modo       = _leer_modo()
    simulador  = (modo == "SIMULADOR")

    if simulador:
        print(f"  [EJECUTOR] Modo SIMULADOR — sin orden real a Binance.")

    os.makedirs(os.path.dirname(LOCK_FILE), exist_ok=True)

    try:
        lock_fd = open(LOCK_FILE, "w")
    except Exception as e:
        return f"❌ ERROR abriendo lock file: {e}"

    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
    except Exception as e:
        lock_fd.close()
        return f"❌ ERROR adquiriendo lock de billetera: {e}"

    try:
        try:
            with open(BILLETERA, "r") as f:
                billetera = json.load(f)
        except Exception as e:
            return f"❌ ERROR leyendo billetera: {e}"

        if tipo == "COMPRA":
            usdt_disponible = billetera.get("USDT", 0)
            if usdt_disponible < monto:
                return f"❌ RECHAZADO: Fondos insuficientes (necesita ${monto:.2f}, tiene ${usdt_disponible:.2f})"

            try:
                if simulador:
                    respuesta = _simular_fill(symbol, "BUY", quote_qty=monto)
                else:
                    respuesta = _orden_mercado(symbol, "BUY", quote_qty=monto)
            except Exception as e:
                return f"❌ ERROR {'simulando' if simulador else 'Binance'} COMPRA: {e}"

            ejecutado_usdt = float(respuesta.get("cummulativeQuoteQty", monto))
            ejecutado_qty  = float(respuesta.get("executedQty", monto / precio))
            precio_real    = round(ejecutado_usdt / ejecutado_qty, 4) if ejecutado_qty > 0 else precio

            billetera["USDT"] = round(billetera.get("USDT", 0) - ejecutado_usdt, 4)
            billetera[moneda] = round(billetera.get(moneda, 0) + ejecutado_qty, 8)
            resultado = f"✅ {'[SIM] ' if simulador else ''}EJECUTADO: Compra {moneda} a ${precio_real} por ${ejecutado_usdt:.2f} USDT"

        elif tipo == "VENTA":
            cantidad_a_vender   = _redondear_cantidad(symbol, monto / precio)
            cantidad_disponible = billetera.get(moneda, 0)
            if cantidad_disponible < cantidad_a_vender:
                return f"❌ RECHAZADO: No tienes suficiente {moneda} (necesita {cantidad_a_vender}, tiene {cantidad_disponible:.6f})"

            try:
                if simulador:
                    respuesta = _simular_fill(symbol, "SELL", base_qty=cantidad_a_vender)
                else:
                    respuesta = _orden_mercado(symbol, "SELL", base_qty=cantidad_a_vender)
            except Exception as e:
                return f"❌ ERROR {'simulando' if simulador else 'Binance'} VENTA: {e}"

            ejecutado_qty  = float(respuesta.get("executedQty", cantidad_a_vender))
            ejecutado_usdt = float(respuesta.get("cummulativeQuoteQty", monto))
            precio_real    = round(ejecutado_usdt / ejecutado_qty, 4) if ejecutado_qty > 0 else precio

            billetera[moneda] = round(billetera.get(moneda, 0) - ejecutado_qty, 8)
            billetera["USDT"] = round(billetera.get("USDT", 0) + ejecutado_usdt, 4)
            resultado = f"✅ {'[SIM] ' if simulador else ''}EJECUTADO: Venta {moneda} a ${precio_real} recuperando ${ejecutado_usdt:.2f} USDT"

        else:
            return f"❌ Tipo desconocido: {tipo}"

        try:
            with open(BILLETERA, "w") as f:
                json.dump(billetera, f, indent=2)
            registrar_historial_billetera(billetera, tipo)
        except Exception as e:
            return f"❌ ERROR CRITICO guardando billetera: {e}"

        return resultado

    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()

def cerrar_posicion(moneda, tipo_trade, precio_entrada, monto_op):
    """
    Envía la orden de cierre a Binance para una posición abierta.
    ALCISTA/LATERAL → SELL base_qty (vende la crypto comprada)
    BAJISTA         → BUY  base_qty (recompra la crypto vendida)
    No actualiza billetera: eso sigue siendo responsabilidad de registrar_tp/sl.
    """
    symbol    = moneda + "USDT"
    modo      = _leer_modo()
    simulador = (modo == "SIMULADOR")

    cantidad = _redondear_cantidad(symbol, monto_op / precio_entrada)
    if cantidad <= 0:
        return f"❌ Cantidad de cierre inválida: {cantidad}"

    try:
        if tipo_trade in ("ALCISTA", "LATERAL"):
            if simulador:
                respuesta = _simular_fill(symbol, "SELL", base_qty=cantidad)
            else:
                respuesta = _orden_mercado(symbol, "SELL", base_qty=cantidad)
            tag      = "[SIM] " if simulador else ""
            qty_ej   = float(respuesta.get("executedQty", cantidad))
            usdt_ej  = float(respuesta.get("cummulativeQuoteQty", 0))
            precio_r = round(usdt_ej / qty_ej, 4) if qty_ej > 0 else precio_entrada
            return f"✅ {tag}CIERRE LONG {moneda}: vendido {qty_ej} a ${precio_r}"

        elif tipo_trade == "BAJISTA":
            if simulador:
                respuesta = _simular_fill(symbol, "BUY", base_qty=cantidad)
            else:
                respuesta = _orden_mercado(symbol, "BUY", base_qty=cantidad)
            tag      = "[SIM] " if simulador else ""
            qty_ej   = float(respuesta.get("executedQty", cantidad))
            usdt_ej  = float(respuesta.get("cummulativeQuoteQty", 0))
            precio_r = round(usdt_ej / qty_ej, 4) if qty_ej > 0 else precio_entrada
            return f"✅ {tag}CIERRE SHORT {moneda}: recomprado {qty_ej} a ${precio_r}"

        else:
            return f"❌ tipo_trade desconocido para cierre: {tipo_trade}"

    except urllib.error.HTTPError as e:
        cuerpo = e.read().decode()
        return f"❌ Binance {e.code} en cierre {moneda}: {cuerpo}"
    except Exception as e:
        return f"❌ ERROR cierre Binance {moneda}: {e}"
