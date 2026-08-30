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
import urllib.error
import hmac
import hashlib
import time
from datetime import datetime, timezone, timedelta
from config_cartera import CAPITAL_BASE
from engine import enviar_aviso
import db

BILLETERA = os.path.expanduser("~/bot-padre-v2/signals/billetera.json")
AUDITORIA = os.path.expanduser("~/bot-padre-v2/auditoria.csv")
KEYS_FILE = os.path.expanduser("~/bot-padre-v2/keys.env")
UMBRAL_SALUDABLE = 90.0
UMBRAL_RIESGO    = 80.0

MONEDAS_ACTIVAS         = ["BTC", "ETH", "SOL", "AVAX"]
VERIFICACION_KEY        = "estado_verificacion_binance"
UMBRAL_DISCREPANCIA_USD = 1.0

# Resumen diario adicional (no reemplaza el aviso de transicion de estado)
RESUMEN_DIARIO_KEY   = "estado_consejero_resumen"
RESUMEN_DIARIO_HORAS = 24

MONEDAS_PRECIO = {
    "BTC":  "BTCUSDT",
    "ETH":  "ETHUSDT",
    "SOL":  "SOLUSDT",
    "BNB":  "BNBUSDT",
    "AVAX": "AVAXUSDT"
}

def _cargar_keys_lectura():
    api_key = secret = None
    with open(KEYS_FILE) as f:
        for linea in f:
            if linea.startswith("BINANCE_API_KEY_LECTURA="):
                api_key = linea.strip().split("=", 1)[1]
            elif linea.startswith("BINANCE_API_SECRET_LECTURA="):
                secret = linea.strip().split("=", 1)[1]
    if not api_key or not secret:
        raise RuntimeError("BINANCE_API_KEY_LECTURA/SECRET no encontradas en keys.env")
    return api_key, secret

def _binance_account_lectura():
    """Un unico GET firmado a /api/v3/account: sirve de prueba de conexion
    (si falla, la key de lectura no esta funcionando) Y trae los saldos
    reales para la deteccion de discrepancias, sin duplicar la llamada."""
    api_key, secret = _cargar_keys_lectura()
    params = {"timestamp": int(time.time() * 1000), "recvWindow": 5000}
    query  = urllib.parse.urlencode(params)
    firma  = hmac.new(secret.encode(), query.encode(), hashlib.sha256).hexdigest()
    url    = f"https://api.binance.com/api/v3/account?{query}&signature={firma}"
    req    = urllib.request.Request(url, headers={"X-MBX-APIKEY": api_key})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())

def _posiciones_abiertas():
    """Qty real (no solo presencia) de cada moneda activa con fila ABIERTA
    o RESERVADA en auditoria.csv ahora mismo."""
    posiciones = {}
    try:
        with open(AUDITORIA) as f:
            for linea in f:
                partes = linea.strip().split(",")
                if len(partes) < 6 or partes[5] not in ("ABIERTA", "RESERVADA"):
                    continue
                activo = partes[2].replace("USDT", "")
                if activo in MONEDAS_ACTIVAS:
                    qty = float(partes[7]) if len(partes) >= 8 and partes[7] else 0.0
                    posiciones[activo] = posiciones.get(activo, 0.0) + qty
    except Exception as e:
        print(f"[CONSEJERO] Error leyendo auditoria.csv: {e}")
    return posiciones

def _detectar_discrepancias(cuenta):
    """
    Compara auditoria.csv contra los saldos reales de Binance para las 4
    monedas activas. Este es el mismo tipo de bug que ya encontramos y
    reconciliamos a mano en BTC y ETH (venta real sin reflejar en el CSV) --
    esto lo detecta solo, el mismo dia.
    """
    saldos     = {b["asset"]: float(b["free"]) + float(b["locked"]) for b in cuenta.get("balances", [])}
    posiciones = _posiciones_abiertas()
    discrepancias = []
    for moneda in MONEDAS_ACTIVAS:
        saldo_real   = saldos.get(moneda, 0.0)
        qty_esperada = posiciones.get(moneda, 0.0)
        precio       = obtener_precio(MONEDAS_PRECIO[moneda])
        valor_saldo  = saldo_real * precio if precio else 0.0

        if qty_esperada > 0 and saldo_real < qty_esperada * 0.5:
            discrepancias.append(
                f"{moneda}: auditoria.csv dice ABIERTA {qty_esperada}, Binance tiene solo "
                f"{saldo_real} — posible venta fuera del bot sin reconciliar"
            )
        elif qty_esperada == 0 and valor_saldo >= UMBRAL_DISCREPANCIA_USD:
            discrepancias.append(
                f"{moneda}: Binance tiene {saldo_real} (~${round(valor_saldo, 2)}) pero "
                f"auditoria.csv no tiene ninguna fila ABIERTA — posible compra fuera del bot sin registrar"
            )
    return discrepancias

def _verificar_binance():
    """
    Corre cada ciclo (60s via main.py). Avisa por Telegram DE INMEDIATO ante
    caida de la key de lectura o discrepancia nueva -- no espera al resumen
    diario. Usa db.py para no repetir el mismo aviso en cada ciclo mientras
    el problema sigue igual (solo avisa en cambios de estado).
    """
    previo                = db.json_get(VERIFICACION_KEY) or {}
    conexion_ok_previa    = previo.get("conexion_ok", True)
    discrepancias_previas = set(previo.get("discrepancias", []))

    try:
        cuenta        = _binance_account_lectura()
        conexion_ok   = True
        discrepancias = _detectar_discrepancias(cuenta)
    except Exception as e:
        conexion_ok   = False
        discrepancias = []
        if conexion_ok_previa:
            enviar_aviso(
                f"🚨 CONSEJERO — Conexión a Binance (key de lectura) caída\n"
                f"Error: {e}\n"
                f"Probable causa: cambio de IP pública (sin IP fija).\n"
                f"El bot de trading sigue operando — usa una key distinta, de escritura."
            )

    if conexion_ok and not conexion_ok_previa:
        enviar_aviso("✅ CONSEJERO — Conexión a Binance (key de lectura) recuperada.")

    for d in set(discrepancias) - discrepancias_previas:
        enviar_aviso(f"⚠️ CONSEJERO — Discrepancia detectada\n{d}")

    resultado = {"conexion_ok": conexion_ok, "discrepancias": discrepancias}
    db.json_set(VERIFICACION_KEY, resultado)
    return resultado

def _cargar_estado_previo():
    data = db.json_get("estado_consejero")
    return data.get("estado") if data else None

def _guardar_estado_actual(estado):
    db.json_set("estado_consejero", {"estado": estado})

def _debe_enviar_resumen_diario():
    """Gate de 24h -- mismo patron que historial_precios.py::registrar_snapshot()."""
    data   = db.json_get(RESUMEN_DIARIO_KEY)
    ultimo = data.get("ultimo_envio") if data else None
    if ultimo is None:
        return True
    try:
        ahora = datetime.now(timezone.utc)
        return ahora - datetime.fromisoformat(ultimo) >= timedelta(hours=RESUMEN_DIARIO_HORAS)
    except Exception as e:
        print(f"[CONSEJERO] Error leyendo fecha de resumen previo: {e}")
        return True

def _enviar_resumen_diario(resultado):
    """
    Resumen de estado una vez cada 24h, independiente de si hubo transicion.
    Cubre el silencio prolongado cuando el estado queda trabado (ej. CRITICO
    varios dias) -- el aviso de transicion de mas abajo no se toca.
    """
    if not _debe_enviar_resumen_diario():
        return
    estado_bin = db.json_get(VERIFICACION_KEY) or {}
    todo_bien  = estado_bin.get("conexion_ok", True) and not estado_bin.get("discrepancias")
    frase      = "✅ Todo bien." if todo_bien else "⚠️ Esto está raro, revísalo."
    detalle    = ""
    if estado_bin.get("discrepancias"):
        detalle = "\n" + "\n".join(f"- {d}" for d in estado_bin["discrepancias"])
    enviar_aviso(
        f"📊 CONSEJERO — Resumen diario\n"
        f"{frase}\n\n"
        f"Capital actual : ${resultado['capital_actual']}\n"
        f"Capital inicial: ${resultado['capital_inicial']}\n"
        f"Nivel          : {resultado['porcentaje']}%\n"
        f"Estado         : {resultado['estado']}\n"
        f"Conexión Binance (lectura): {'OK' if estado_bin.get('conexion_ok', True) else 'CAÍDA'}"
        f"{detalle}"
    )
    db.json_set(RESUMEN_DIARIO_KEY, {"ultimo_envio": datetime.now(timezone.utc).isoformat()})

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
    _verificar_binance()

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

    resultado = {
        "estado":          estado,
        "capital_actual":  capital_actual,
        "capital_inicial": CAPITAL_BASE,
        "porcentaje":      round(pct, 1),
        "mensaje":         mensaje
    }

    try:
        _enviar_resumen_diario(resultado)
    except Exception as e:
        print(f"[CONSEJERO] Error enviando resumen diario: {e}")

    return resultado

if __name__ == "__main__":
    capital = calcular_capital_total()
    resultado = consultar_consejero(capital)
    print(f"Capital total : ${resultado['capital_actual']}")
    print(f"Capital inicio: ${resultado['capital_inicial']}")
    print(f"Porcentaje    : {resultado['porcentaje']}%")
    print(f"Estado        : {resultado['estado']}")
    print(f"Mensaje       : {resultado['mensaje']}")
