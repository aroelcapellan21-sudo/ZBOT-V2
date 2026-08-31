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
from decimal import Decimal, ROUND_DOWN
from gestor_billetera import registrar_historial_billetera

BILLETERA            = os.path.expanduser("~/bot-padre-v2/signals/billetera.json")
LOCK_FILE            = os.path.expanduser("~/bot-padre-v2/signals/billetera.json.lock")
KEYS_FILE            = os.path.expanduser("~/bot-padre-v2/keys.env")
MODO_FILE            = os.path.expanduser("~/bot-padre-v2/signals/modo.json")
PARADA_EMERGENCIA_FILE = os.path.expanduser("~/bot-padre-v2/signals/PARADA_EMERGENCIA.txt")
MONTO_MINIMO_BINANCE = 5.0
BASE_URL             = "https://api.binance.com"

# Comision spot de Binance para el SIMULADOR: 0.1% por lado (taker VIP0), o sea
# 0.2% por operacion completa. En REAL no se usa: la comision se lee del array
# 'fills' de la respuesta. Si algun dia se paga con BNB, el descuento es 25%.
COMISION_SPOT        = 0.001

# Decimales de cantidad permitidos por símbolo (LOT_SIZE de Binance)
LOT_SIZE = {
    "BTCUSDT":  5,
    "ETHUSDT":  4,
    "SOLUSDT":  3,   # verificado contra /api/v3/exchangeInfo: stepSize 0.00100000
    "BNBUSDT":  3,
    "AVAXUSDT": 2,
}

def _leer_modo():
    # Fallback SIMULADOR: si modo.json falta, esta corrupto o se lee a medio
    # escribir, NUNCA asumir REAL. El default seguro es no tocar dinero.
    try:
        with open(MODO_FILE) as f:
            return json.load(f).get("modo", "SIMULADOR")
    except Exception as e:
        print(f"  [EJECUTOR] ⚠️ Error leyendo {MODO_FILE}: {e} — asumiendo SIMULADOR.")
        return "SIMULADOR"

def _confirmacion_real_activa():
    return os.environ.get("BOT_REAL_CONFIRMADO", "").strip().lower() == "true"

def _parada_emergencia_activa():
    # Kill switch de /parar (Telegram) y del asistente web. Antes de este fix
    # ningun modulo del camino real lo leia: era cosmetico (solo cambiaba el
    # dashboard). Se chequea aca porque ejecutor.py es el unico autorizado
    # para abrir/cerrar posiciones (CLAUDE.md) - cubre los 15 francotiradores
    # sin tocarlos. Solo bloquea APERTURAS (ejecutar_operacion); no toca
    # cerrar_posicion(), para que SL/TP sigan protegiendo posiciones abiertas.
    return os.path.exists(PARADA_EMERGENCIA_FILE)

def _truncar_cantidad(symbol, qty):
    """
    Trunca hacia abajo al LOT_SIZE del simbolo. NUNCA redondea hacia arriba:
    pedir mas cantidad de la que hay en la cuenta = rechazo -2010 de Binance
    = el cierre falla y la posicion queda ABIERTA sin stop.

    Se usa Decimal y no floor() sobre float porque el error binario se come un
    tick entero: 0.29 * 100 = 28.999999999999996 -> floor daria 0.28.
    """
    decimales = LOT_SIZE.get(symbol, 6)
    paso      = Decimal(1).scaleb(-decimales)
    return float(Decimal(str(qty)).quantize(paso, rounding=ROUND_DOWN))

def _formatear_qty(symbol, qty):
    """
    Devuelve la cantidad en notacion decimal fija para el parametro 'quantity'
    de Binance. NUNCA usar f"{qty}" con un float: Python convierte a notacion
    cientifica cualquier valor absoluto menor a 1e-4 (str(5.994e-05) ==
    '5.994e-05'), y Binance rechaza eso con -1100 "Illegal characters found
    in parameter 'quantity'" (regex de Binance para ese campo no acepta 'e').
    Pasa siempre con BTC: $5 de monto a ~$80.000 da qty~0.0000625,
    por debajo de 1e-4.
    """
    decimales = LOT_SIZE.get(symbol, 6)
    paso      = Decimal(1).scaleb(-decimales)
    return format(Decimal(str(qty)).quantize(paso, rounding=ROUND_DOWN), "f")

def _valor_estimado_al_stop(symbol, monto, precio, sl_pct):
    """
    Valor en USDT que tendria la posicion al tocar su STOP_LOSS, modelando el
    camino real del dinero -- no monto*(1-sl), que es lo que parece a simple
    vista y da un numero optimista de mas.

    Tres mordiscos, en este orden:
      1. al COMPRAR se trunca al LOT_SIZE (no se compra el monto exacto)
      2. Binance cobra la comision de la COMPRA en el activo base -> qty neta
      3. al CERRAR se vuelve a truncar esa qty neta al LOT_SIZE

    El truncamiento pega fuerte donde el step vale mucho: en BTC un step son
    ~$0.78 al precio de hoy, el 15% de una entrada de $5.
    """
    qty_comprada = _truncar_cantidad(symbol, monto / precio)
    qty_neta     = _truncar_cantidad(symbol, qty_comprada * (1 - COMISION_SPOT))
    return qty_neta * precio * (1 - sl_pct / 100.0)

def _monto_minimo_viable(symbol, precio, sl_pct):
    """
    Menor monto de entrada (en centavos) cuyo SL sigue siendo ejecutable al
    precio actual. Solo para el mensaje de rechazo: que diga cuanto haria
    falta, en vez de dejar a Ariel calculandolo a mano. Devuelve None si ni
    con $30 alcanza (no deberia pasar; es un tope de cordura del bucle).
    """
    centavos = int(MONTO_MINIMO_BINANCE * 100)
    while centavos <= 3000:
        if _valor_estimado_al_stop(symbol, centavos / 100.0, precio, sl_pct) >= MONTO_MINIMO_BINANCE:
            return centavos / 100.0
        centavos += 1
    return None

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
    """
    Simula un fill con la MISMA forma que devuelve Binance, incluido el array
    'fills' con la comision. Asi _extraer_fill() no distingue simulado de real
    y el SIMULADOR deja de sobreestimar las ganancias.
    """
    precio = _precio_ticker(symbol)
    if side == "BUY":
        if quote_qty is not None:
            qty  = _truncar_cantidad(symbol, quote_qty / precio)
            # El USDT gastado se recalcula sobre la cantidad ya truncada. Dejarlo
            # en quote_qty inventaba un precio implicito (usdt/qty) distinto del
            # de mercado: con BTC a 5 decimales, un ticket de $20 tiene ~3% de
            # granularidad, y desde el fix #4 ese precio es el que fija SL y TP.
            usdt = round(qty * precio, 8)
        else:
            qty  = base_qty
            usdt = round(base_qty * precio, 2)
    else:
        qty  = base_qty
        usdt = round(base_qty * precio, 2)

    # Binance cobra en el activo BASE al comprar y en el QUOTE al vender.
    if side == "BUY":
        comision, activo = round(qty * COMISION_SPOT, 8), symbol.replace("USDT", "")
    else:
        comision, activo = round(usdt * COMISION_SPOT, 8), "USDT"

    return {"executedQty": str(qty), "cummulativeQuoteQty": str(usdt), "price": str(precio),
            "fills": [{"commission": str(comision), "commissionAsset": activo}]}

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
        params["quantity"] = _formatear_qty(symbol, base_qty)
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

def _saldo_libre(moneda):
    """Saldo real disponible de un activo en Binance ahora mismo, con la key
    de trading (la misma que ya coloca ordenes) -- para saber cuanto hay de
    margen real antes de ajustar una cantidad de cierre."""
    api_key, secret = _cargar_keys()
    params = {"timestamp": int(time.time() * 1000)}
    query  = urllib.parse.urlencode(params)
    firma  = hmac.new(secret.encode(), query.encode(), hashlib.sha256).hexdigest()
    url    = f"{BASE_URL}/api/v3/account?{query}&signature={firma}"
    req    = urllib.request.Request(url, headers={"X-MBX-APIKEY": api_key})
    with urllib.request.urlopen(req, timeout=10) as resp:
        cuenta = json.loads(resp.read())
    for b in cuenta.get("balances", []):
        if b["asset"] == moneda:
            return float(b["free"])
    return 0.0

def _ajustar_qty_bajo_notional(symbol, moneda, cantidad, precio):
    """
    Si vender 'cantidad' exacta no alcanza el minNotional de Binance (la
    posicion perdio valor de mercado desde la entrada -- caso SOL 30-ago-2026,
    ver reports/2026-08-30_diagnostico-sol-zombie-notional-1013.md), calcula
    la MINIMA cantidad extra necesaria para superarlo, tomada del saldo real
    disponible -- nunca mas de lo que hay en la cuenta.

    Devuelve (cantidad_final, se_ajusto: bool) si se puede cerrar, o
    (None, motivo) si ni con todo el saldo disponible alcanza el minimo.
    """
    valor = cantidad * precio
    if valor >= MONTO_MINIMO_BINANCE:
        return cantidad, False

    # 3% de margen: cubre el pequeño movimiento de precio entre este chequeo
    # y la ejecucion real, y lo que se pierde al truncar al LOT_SIZE despues.
    objetivo      = (MONTO_MINIMO_BINANCE * 1.03) / precio
    qty_necesaria = _truncar_cantidad(symbol, objetivo)

    try:
        saldo_libre = _saldo_libre(moneda)
    except Exception as e:
        return None, f"no se pudo consultar el saldo real para ajustar: {e}"

    qty_final = min(qty_necesaria, _truncar_cantidad(symbol, saldo_libre))
    if qty_final * precio < MONTO_MINIMO_BINANCE:
        # El mensaje viejo describia el sintoma y se quedaba ahi, y el aviso que
        # lo envuelve dice "reintentando proximo ciclo" -- lo cual es falso: se
        # repite identico cada 4 minutos y no se destraba solo. Se agrega lo
        # unico accionable: que NO es transitorio, y a que precio deja de serlo.
        qty_vendible = _truncar_cantidad(symbol, saldo_libre)
        precio_destrabe = (MONTO_MINIMO_BINANCE / qty_vendible) if qty_vendible > 0 else None
        if precio_destrabe:
            subida_pct = (precio_destrabe / precio - 1) * 100
            detalle_destrabe = (f" NO es transitorio: se repite igual cada ciclo hasta que "
                                f"{moneda} suba a ~${round(precio_destrabe, 4)} "
                                f"(+{subida_pct:.2f}% desde ${round(precio, 4)}). "
                                f"Mientras tanto la posicion queda SIN STOP EFECTIVO: "
                                f"cerrarla a mano si no se quiere esperar ese precio.")
        else:
            detalle_destrabe = (" NO es transitorio, y no hay saldo vendible: la posicion no "
                                "puede cerrarse por esta via a ningun precio.")
        return None, (f"ni con todo el saldo disponible ({saldo_libre} {moneda}, "
                       f"${round(saldo_libre * precio, 2)}) se alcanza el minimo "
                       f"de ${MONTO_MINIMO_BINANCE}.{detalle_destrabe}")
    return qty_final, qty_final > cantidad

def _extraer_fill(respuesta, moneda, qty_fallback, usdt_fallback, precio_fallback):
    """
    Normaliza la respuesta de Binance a (qty_neta, usdt_neto, precio_real).

    'executedQty' es BRUTO, antes de comision. Binance cobra:
      - en COMPRA : la comision en el activo BASE  -> recibis menos cripto
      - en VENTA  : la comision en el activo QUOTE -> recibis menos USDT
    El detalle viene en respuesta["fills"][i]["commission"/"commissionAsset"].
    Persistir executedQty sin restar la comision hace que despues intentes
    vender ~0.1% mas de lo que realmente tenes.

    _simular_fill no devuelve 'fills', asi que en SIMULADOR la comision es 0.
    Modelar fees simuladas es otro cambio (punto 5 del plan de auditoria).
    """
    qty  = float(respuesta.get("executedQty") or qty_fallback)
    usdt = float(respuesta.get("cummulativeQuoteQty") or usdt_fallback)

    com_base = com_quote = 0.0
    for f in respuesta.get("fills") or []:
        try:
            c = float(f.get("commission") or 0)
        except (TypeError, ValueError) as e:
            print(f"  [EJECUTOR] ⚠️ Comision ilegible en fill: {e}")
            continue
        activo = f.get("commissionAsset")
        if activo == moneda:
            com_base += c
        elif activo == "USDT":
            com_quote += c

    precio_real = round(usdt / qty, 4) if qty > 0 else precio_fallback
    return round(qty - com_base, 8), round(usdt - com_quote, 8), precio_real


def ejecutar_operacion(moneda, tipo, precio, monto=None, sl_pct=None):
    """
    Devuelve (mensaje, fill).
      fill = {"qty": <cripto NETA de comision>, "usdt": <USDT NETO>, "precio": <fill real>}
      fill = None  si la orden fue rechazada o fallo.
    El mensaje mantiene el formato "✅ ..."/"❌ ..." de siempre.

    sl_pct: STOP_LOSS del francotirador que llama, en porcentaje (ej. 3.5).
    Si se pasa, se rechaza la entrada cuando el SL dejaria la posicion bajo el
    minNotional -- ver el guardian de entrada mas abajo. Default None (no
    chequea) para no romper a los 11 francotiradores que hoy no lo pasan; al
    reactivar cualquiera de ellos hay que pasarle su STOP_LOSS.
    """
    if not monto or monto <= 0:
        return f"❌ RECHAZADO: Monto invalido (${monto})", None

    if monto < MONTO_MINIMO_BINANCE:
        return f"❌ RECHAZADO: Monto ${monto:.2f} bajo minimo Binance (${MONTO_MINIMO_BINANCE})", None

    if _parada_emergencia_activa():
        return "❌ RECHAZADO: Parada de emergencia activa (signals/PARADA_EMERGENCIA.txt)", None

    symbol     = moneda + "USDT"

    # ---- Guardian de entrada: no abrir una posicion cuyo SL sera inejecutable ----
    # Motivo (reports/2026-08-30_fix-dos-bugs-de-fondo.md): con entradas de $5 y
    # minNotional de $5, al tocar el SL la posicion vale menos del minimo y
    # Binance rechaza la venta con -1013. Resultado: 15 dias operando en REAL
    # sin stop-loss efectivo, con las 3 perdidas cerradas a mano.
    # Que NO se abra es el resultado correcto: una posicion que no puede parar
    # la perdida no es una posicion, es una apuesta abierta.
    if sl_pct:
        valor_sl = _valor_estimado_al_stop(symbol, monto, precio, sl_pct)
        if valor_sl < MONTO_MINIMO_BINANCE:
            minimo = _monto_minimo_viable(symbol, precio, sl_pct)
            sugerencia = (f" Monto minimo viable hoy para {symbol}: ${minimo:.2f}."
                          if minimo else "")
            return (f"❌ RECHAZADO: SL inejecutable — con ${monto:.2f} de entrada y SL "
                    f"{sl_pct}%, la posicion valdria ${valor_sl:.2f} al tocar el stop, "
                    f"bajo el minimo de Binance (${MONTO_MINIMO_BINANCE}). Abrirla seria "
                    f"quedarse sin stop.{sugerencia}"), None
    # -----------------------------------------------------------------------------

    modo       = _leer_modo()
    simulador  = not (modo == "REAL" and _confirmacion_real_activa())

    if simulador:
        print(f"  [EJECUTOR] Modo SIMULADOR — sin orden real a Binance.")

    os.makedirs(os.path.dirname(LOCK_FILE), exist_ok=True)

    try:
        lock_fd = open(LOCK_FILE, "w")
    except Exception as e:
        return f"❌ ERROR abriendo lock file: {e}", None

    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
    except Exception as e:
        lock_fd.close()
        return f"❌ ERROR adquiriendo lock de billetera: {e}", None

    try:
        try:
            with open(BILLETERA, "r") as f:
                billetera = json.load(f)
        except Exception as e:
            return f"❌ ERROR leyendo billetera: {e}", None

        if tipo == "COMPRA":
            usdt_disponible = billetera.get("USDT", 0)
            if usdt_disponible < monto:
                return f"❌ RECHAZADO: Fondos insuficientes (necesita ${monto:.2f}, tiene ${usdt_disponible:.2f})", None

            try:
                if simulador:
                    respuesta = _simular_fill(symbol, "BUY", quote_qty=monto)
                else:
                    respuesta = _orden_mercado(symbol, "BUY", quote_qty=monto)
            except Exception as e:
                return f"❌ ERROR {'simulando' if simulador else 'Binance'} COMPRA: {e}", None

            qty_neta, usdt_neto, precio_real = _extraer_fill(
                respuesta, moneda, monto / precio, monto, precio)
            # En COMPRA se gasta el USDT bruto; la comision se descuenta de la cripto.
            usdt_gastado = float(respuesta.get("cummulativeQuoteQty") or monto)

            billetera["USDT"] = round(billetera.get("USDT", 0) - usdt_gastado, 4)
            billetera[moneda] = round(billetera.get(moneda, 0) + qty_neta, 8)
            fill      = {"qty": qty_neta, "usdt": usdt_gastado, "precio": precio_real}
            resultado = f"✅ {'[SIM] ' if simulador else ''}EJECUTADO: Compra {moneda} a ${precio_real} por ${usdt_gastado:.2f} USDT"

        elif tipo == "VENTA":
            cantidad_a_vender = _truncar_cantidad(symbol, monto / precio)
            if not simulador:
                cantidad_disponible = billetera.get(moneda, 0)
                if cantidad_disponible < cantidad_a_vender:
                    return f"❌ RECHAZADO: No tienes suficiente {moneda} (necesita {cantidad_a_vender}, tiene {cantidad_disponible:.6f})", None

            try:
                if simulador:
                    respuesta = _simular_fill(symbol, "SELL", base_qty=cantidad_a_vender)
                else:
                    respuesta = _orden_mercado(symbol, "SELL", base_qty=cantidad_a_vender)
            except Exception as e:
                return f"❌ ERROR {'simulando' if simulador else 'Binance'} VENTA: {e}", None

            _, usdt_neto, precio_real = _extraer_fill(
                respuesta, moneda, cantidad_a_vender, monto, precio)
            # En VENTA se entrega la cripto bruta; la comision se descuenta del USDT.
            qty_entregada = float(respuesta.get("executedQty") or cantidad_a_vender)

            billetera[moneda] = round(billetera.get(moneda, 0) - qty_entregada, 8)
            billetera["USDT"] = round(billetera.get("USDT", 0) + usdt_neto, 4)
            fill      = {"qty": qty_entregada, "usdt": usdt_neto, "precio": precio_real}
            resultado = f"✅ {'[SIM] ' if simulador else ''}EJECUTADO: Venta {moneda} a ${precio_real} recuperando ${usdt_neto:.2f} USDT"

        else:
            return f"❌ Tipo desconocido: {tipo}", None

        try:
            tmp = BILLETERA + ".tmp"
            with open(tmp, "w") as f:
                json.dump(billetera, f, indent=2)
            os.replace(tmp, BILLETERA)
            registrar_historial_billetera(billetera, tipo)
        except Exception as e:
            return f"❌ ERROR CRITICO guardando billetera: {e}", None

        return resultado, fill

    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()

def cerrar_posicion(moneda, tipo_trade, precio_entrada, monto_op, qty=None):
    """
    Envía la orden de cierre a Binance para una posición abierta.
    ALCISTA/LATERAL → SELL base_qty (vende la crypto comprada)
    BAJISTA         → BUY  base_qty (recompra la crypto vendida)
    No actualiza billetera: eso sigue siendo responsabilidad de registrar_tp/sl.

    qty: cantidad REAL de la posicion (columna 'qty' de auditoria.csv, que
         guarda el executedQty neto de comision del fill de entrada).
         Si es None se cae al calculo teorico monto_op/precio_entrada, que es
         lo que hacian las filas escritas antes de este cambio.

    Devuelve (mensaje, fill) igual que ejecutar_operacion:
      fill = {"qty": ..., "usdt": <USDT NETO recibido>, "precio": <fill real>}
      fill = None si el cierre fallo.
    """
    symbol    = moneda + "USDT"
    modo      = _leer_modo()
    simulador = not (modo == "REAL" and _confirmacion_real_activa())

    if qty is None:
        cantidad = _truncar_cantidad(symbol, monto_op / precio_entrada)
        print(f"  [EJECUTOR] {symbol} sin qty persistida — cierre por calculo teorico.")
    else:
        cantidad = _truncar_cantidad(symbol, qty)

    if cantidad <= 0:
        return f"❌ Cantidad de cierre inválida: {cantidad}", None

    if tipo_trade in ("ALCISTA", "LATERAL"):
        lado, verbo = "SELL", "vendido"
        etiqueta    = "CIERRE LONG"
    elif tipo_trade == "BAJISTA":
        lado, verbo = "BUY", "recomprado"
        etiqueta    = "CIERRE SHORT"
    else:
        return f"❌ tipo_trade desconocido para cierre: {tipo_trade}", None

    ajuste_notional = ""
    if lado == "SELL" and not simulador:
        try:
            precio_actual = _precio_ticker(symbol)
        except Exception as e:
            return f"❌ ERROR obteniendo precio para chequeo NOTIONAL {symbol}: {e}", None
        cantidad_ajustada, detalle = _ajustar_qty_bajo_notional(symbol, moneda, cantidad, precio_actual)
        if cantidad_ajustada is None:
            # 'detalle' ya explica que no es transitorio y a que precio se
            # destraba (ver _ajustar_qty_bajo_notional). Se marca ademas como
            # CIERRE BLOQUEADO y no como un error de orden cualquiera: no hay
            # nada que reintentar, es una condicion de mercado.
            return (f"❌ CIERRE BLOQUEADO: {symbol} bajo minimo Binance "
                    f"(${MONTO_MINIMO_BINANCE}) incluso ajustando qty — {detalle}"), None
        if detalle:
            ajuste_notional = (f" [qty ajustada de {cantidad} a {cantidad_ajustada} {moneda} "
                                f"para superar el minimo NOTIONAL de Binance]")
            print(f"  [EJECUTOR] {symbol}: {ajuste_notional.strip()}")
        cantidad = cantidad_ajustada

    try:
        if simulador:
            respuesta = _simular_fill(symbol, lado, base_qty=cantidad)
        else:
            respuesta = _orden_mercado(symbol, lado, base_qty=cantidad)

        qty_neta, usdt_neto, precio_r = _extraer_fill(
            respuesta, moneda, cantidad, 0.0, precio_entrada)
        qty_ej = float(respuesta.get("executedQty") or cantidad)
        # SELL: se entrega la cripto bruta y se recibe USDT neto de comision.
        # BUY (cierre de short): se recibe cripto neta y se paga USDT bruto.
        fill = {"qty": qty_neta if lado == "BUY" else qty_ej,
                "usdt": usdt_neto,
                "precio": precio_r}
        tag = "[SIM] " if simulador else ""
        return f"✅ {tag}{etiqueta} {moneda}: {verbo} {qty_ej} a ${precio_r}{ajuste_notional}", fill

    except urllib.error.HTTPError as e:
        cuerpo = e.read().decode()
        return f"❌ Binance {e.code} en cierre {moneda}: {cuerpo}", None
    except Exception as e:
        return f"❌ ERROR cierre Binance {moneda}: {e}", None
