# =========================================
# resumen_diario.py
# Resumen diario automatico por Telegram
# Se envia a las 8 AM cada dia
# Incluye contador de dias de demo
# Usa el mismo sistema que engine.py
# Constitucion RESPETADA
# =========================================

import os
import json
import urllib.request
import urllib.parse
from datetime import datetime, date
from resumen_capital import generar_bloque_capital
from utils import fetch_velas, calcular_rsi, calcular_ema

CONTADOR_FILE = os.path.expanduser("~/bot-padre-v2/datos_demo.json")
AUDITORIA = os.path.expanduser("~/bot-padre-v2/auditoria.csv")

ADMIN_YAYO = 6578945006
ADMIN_SOCIA = 6533031969
ADMIN_IDS = [ADMIN_YAYO, ADMIN_SOCIA]

NOMBRES = {
    "BTCUSDT": "Bitcoin",
    "ETHUSDT": "Ethereum",
    "SOLUSDT": "Solana",
    "BNBUSDT": "BNB",
    "AVAXUSDT": "Avalanche"
}

def cargar_token():
    ruta = os.path.expanduser("~/bot-padre-v2/keys.env")
    try:
        with open(ruta, "r") as f:
            for linea in f:
                if linea.startswith("TELEGRAM_TOKEN="):
                    return linea.strip().split("=", 1)[1]
    except:
        return None

def enviar_telegram(mensaje):
    token = cargar_token()
    if not token:
        print("[RESUMEN] Token no encontrado.")
        return
    for admin_id in ADMIN_IDS:
        try:
            params = urllib.parse.urlencode({
                "chat_id": admin_id,
                "text": mensaje
            })
            url = f"https://api.telegram.org/bot{token}/sendMessage?{params}"
            with urllib.request.urlopen(url, timeout=10) as resp:
                print(f"[RESUMEN] Enviado a {admin_id}")
        except Exception as e:
            print(f"[RESUMEN] Error: {e}")

def cargar_contador():
    try:
        with open(CONTADOR_FILE, "r") as f:
            return json.load(f)
    except:
        datos = {
            "fecha_inicio": date.today().isoformat(),
            "dias_activo": 0,
            "ultima_fecha": date.today().isoformat(),
            "meta_dias": 30
        }
        guardar_contador(datos)
        return datos

def guardar_contador(datos):
    with open(CONTADOR_FILE, "w") as f:
        json.dump(datos, f, indent=2)

def actualizar_contador():
    datos = cargar_contador()
    hoy = date.today().isoformat()
    if datos["ultima_fecha"] != hoy:
        datos["dias_activo"] += 1
        datos["ultima_fecha"] = hoy
        guardar_contador(datos)
    return datos

def barra_progreso(dias_activo, meta):
    porcentaje = min(int((dias_activo / meta) * 20), 20)
    barra = "█" * porcentaje + "░" * (20 - porcentaje)
    return barra

def obtener_datos_mercado():
    ACTIVOS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "AVAXUSDT"]
    datos = {}
    for symbol in ACTIVOS:
        cierres = fetch_velas(symbol)
        if cierres and len(cierres) >= 24:
            rsi = calcular_rsi(cierres)
            ema50 = calcular_ema(cierres, 50)
            precio_actual = cierres[-1]
            precio_apertura = cierres[-24]
            cambio_dia = round(((precio_actual - precio_apertura) / precio_apertura) * 100, 2)
            rsi_lista = [calcular_rsi(cierres[:i]) for i in range(len(cierres)-23, len(cierres)+1) if calcular_rsi(cierres[:i])]
            rsi_max = round(max(rsi_lista), 2) if rsi_lista else rsi
            rsi_min = round(min(rsi_lista), 2) if rsi_lista else rsi
            datos[symbol] = {
                "precio": precio_actual,
                "apertura": precio_apertura,
                "cambio": cambio_dia,
                "rsi": rsi,
                "rsi_max": rsi_max,
                "rsi_min": rsi_min,
                "ema50": ema50,
            }
    return datos

def leer_operaciones():
    abiertas = []
    tp_hoy = []
    sl_hoy = []
    hoy = datetime.now().strftime("%Y-%m-%d")
    try:
        with open(AUDITORIA, "r") as f:
            lineas = f.readlines()
        for linea in lineas[1:]:
            p = linea.strip().split(",")
            if len(p) < 6:
                continue
            if p[5] == "ABIERTA":
                abiertas.append(p)
            elif p[5] == "TP" and p[0][:10] == hoy:
                tp_hoy.append(p)
            elif p[5] == "SL" and p[0][:10] == hoy:
                sl_hoy.append(p)
    except:
        pass
    return abiertas, tp_hoy, sl_hoy

def resumen_sencillo():
    abiertas, tp_hoy, sl_hoy = leer_operaciones()
    por_symbol = {}
    for op in abiertas:
        por_symbol[op[2]] = por_symbol.get(op[2], 0) + 1

    fecha = datetime.now().strftime("%d/%m/%Y %H:%M")
    msg = f"🍦 Z-BOT V2 | {fecha}\n"
    msg += "━━━━━━━━━━━━━━━━━━━\n"
    msg += generar_bloque_capital()
    msg += f"📂 Operaciones abiertas: {len(abiertas)}\n"
    msg += f"✅ Ganancias hoy: {len(tp_hoy)}\n"
    msg += f"🛑 Pérdidas hoy: {len(sl_hoy)}\n"
    msg += "━━━━━━━━━━━━━━━━━━━\n"

    if por_symbol:
        msg += "📌 Tengo abiertas:\n"
        for s, c in por_symbol.items():
            msg += f"  • {NOMBRES.get(s, s)}: {c} operacion{'es' if c > 1 else ''}\n"
    else:
        msg += "📌 Sin operaciones abiertas\n"

    if tp_hoy:
        msg += "━━━━━━━━━━━━━━━━━━━\n"
        msg += "✅ Cerradas con ganancia:\n"
        for op in tp_hoy:
            msg += f"  • {NOMBRES.get(op[2], op[2])} entrada ${op[3]}\n"

    if sl_hoy:
        msg += "━━━━━━━━━━━━━━━━━━━\n"
        msg += "🛑 Cerradas con pérdida:\n"
        for op in sl_hoy:
            msg += f"  • {NOMBRES.get(op[2], op[2])} entrada ${op[3]}\n"

    print(msg)
    enviar_telegram(msg)

def generar_resumen():
    datos = actualizar_contador()
    mercado = obtener_datos_mercado()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    dias = datos["dias_activo"]
    meta = datos["meta_dias"]
    fecha_inicio = datos["fecha_inicio"]
    barra = barra_progreso(dias, meta)
    dias_restantes = max(0, meta - dias)

    mensaje = f"""📅 RESUMEN DIARIO Z-BOT V2
🕐 {timestamp}

━━━━━━━━━━━━━━━━━━━━━
🏁 CONTADOR DEMO
━━━━━━━━━━━━━━━━━━━━━
📆 Inicio    : {fecha_inicio}
✅ Dias      : {dias} de {meta}
⏳ Restantes : {dias_restantes}
📊 Progreso  : {barra}
🎯 Meta      : {meta} dias → REAL

━━━━━━━━━━━━━━━━━━━━━
📊 MERCADO HOY
━━━━━━━━━━━━━━━━━━━━━"""

    for symbol, d in mercado.items():
        e = "🟢" if d["cambio"] > 0 else "🔴" if d["cambio"] < 0 else "⚪"
        mensaje += f"""
{e} {symbol}
   Precio  : ${d['precio']}
   Apertura: ${d['apertura']}
   Cambio  : {d['cambio']}%
   RSI     : {d['rsi']} (max:{d['rsi_max']} min:{d['rsi_min']})
   EMA50   : {d['ema50']}"""

    mensaje += f"""

━━━━━━━━━━━━━━━━━━━━━
💰 Capital  : $1000.0 USDT
🛡️ Drawdown : 0.0%
🟢 Sistema  : ACTIVO
━━━━━━━━━━━━━━━━━━━━━
CoreCro no ejecuta, no decide y no gobierna."""

    return mensaje

def enviar_resumen():
    resumen_sencillo()
    mensaje = generar_resumen()
    print(mensaje)
    enviar_telegram(mensaje)

if __name__ == "__main__":
    enviar_resumen()

