# =========================================
# brain/telegram_engine.py - Comunicador Actualizado
# FIX: Sleep agregado en escuchar() anti-flood
# FIX: URL fantasma eliminada en _monitor_precio
# FIX: Imports duplicados dentro de funciones eliminados
# FIX: capital_inicial leido de billetera real
# FIX: monto hardcodeado $10 eliminado
# NUEVO: /parar emergencia
# NUEVO: /pnl resumen dia
# MEJORA: Lenguaje llano en todos los comandos
# MEJORA: 3 secciones GENERAL / BOT / MANUAL separadas
# FIX: MANUAL legacy compatible con MANUAL_WIN/MANUAL_LOSS
# =========================================

import urllib.request
import urllib.parse
import json
import os
import fcntl
import threading
import time
from datetime import datetime, date

ADMIN_YAYO  = 6578945006
ADMIN_SOCIA = 6533031969
ADMIN_IDS   = [ADMIN_YAYO, ADMIN_SOCIA]

BITACORAS = {
    "EVENTOS":   ("🟢", "E", "Eventos",   "~/bot-padre-v2/memoria/eventos.log"),
    "CENTINELA": ("🔴", "C", "Centinela", "~/bot-padre-v2/memoria/centinela.log"),
    "CORECRO":   ("🔵", "C", "Corecro",   "~/bot-padre-v2/memoria/corecro.log"),
    "MATRIX":    ("🟡", "M", "Matrix",    "~/bot-padre-v2/memoria/matrix.log"),
}

BILLETERA_PATH = os.path.expanduser("~/bot-padre-v2/signals/billetera.json")
AUDITORIA_PATH = os.path.expanduser("~/bot-padre-v2/auditoria.csv")
AUDITORIA_LOCK = AUDITORIA_PATH + ".lock"
PARADA_PATH    = os.path.expanduser("~/bot-padre-v2/signals/PARADA_EMERGENCIA.txt")

_monitores_activos = {}
_monitores_stop    = {}

def _monitor_precio(symbol, precio_entrada, chat_id, intervalo_puntos=7):
    ultimo_nivel    = precio_entrada
    enviado_reverso = False
    enviar_mensaje(chat_id,
        f"👁 <b>MONITOR ACTIVO</b>\n"
        f"📍 {symbol}\n"
        f"💰 Entrada: ${precio_entrada}\n"
        f"📈 Avisaré cada +${intervalo_puntos} puntos\n"
        f"📉 Avisaré si regresa al precio de entrada\n"
        f"❌ Detener: /cancelar {symbol}"
    )
    while not _monitores_stop.get(symbol, False):
        try:
            params = urllib.parse.urlencode({"symbol": symbol, "interval": "1m", "limit": 1})
            url2   = f"https://api.binance.com/api/v3/klines?{params}"
            with urllib.request.urlopen(url2, timeout=10) as resp:
                data = json.loads(resp.read().decode())
            precio_actual = float(data[-1][4])
            ganancia = round(precio_actual - precio_entrada, 2)
            signo    = "+" if ganancia >= 0 else ""
            pct      = round(((precio_actual - precio_entrada) / precio_entrada) * 100, 2)
            if precio_actual >= ultimo_nivel + intervalo_puntos:
                enviar_mensaje(chat_id,
                    f"📈 <b>{symbol} SUBIÓ</b>\n"
                    f"💰 Entrada:  ${precio_entrada}\n"
                    f"📍 Ahora:    ${round(precio_actual, 2)}\n"
                    f"🚀 Ganancia: {signo}${ganancia} ({signo}{pct}%)\n"
                    f"⚡ ¿Salir o dejar correr?"
                )
                ultimo_nivel    = precio_actual
                enviado_reverso = False
            elif precio_actual <= precio_entrada and not enviado_reverso:
                enviar_mensaje(chat_id,
                    f"⚠️ <b>{symbol} REVERSO</b>\n"
                    f"💰 Entrada:  ${precio_entrada}\n"
                    f"📍 Ahora:    ${round(precio_actual, 2)}\n"
                    f"📉 Resultado: ${ganancia} ({pct}%)\n"
                    f"🛑 Considera salir manualmente"
                )
                enviado_reverso = True
            elif precio_actual > precio_entrada + 2:
                enviado_reverso = False
        except Exception as e:
            print(f"[MONITOR] Error {symbol}: {e}")
        time.sleep(30)
    enviar_mensaje(chat_id, f"❌ <b>Monitor {symbol} cancelado.</b>")
    _monitores_activos.pop(symbol, None)
    _monitores_stop.pop(symbol, None)

def cargar_token():
    ruta = os.path.expanduser("~/bot-padre-v2/keys.env")
    try:
        with open(ruta, "r") as f:
            for linea in f:
                if linea.startswith("TELEGRAM_TOKEN="):
                    return linea.strip().split("=", 1)[1]
    except Exception as e:
        print(f"[TELEGRAM] Error cargando token: {e}")
    return None

def get_api_url():
    token = cargar_token()
    if not token:
        return None
    return f"https://api.telegram.org/bot{token}"

def enviar_mensaje(chat_id, mensaje):
    api_url = get_api_url()
    if not api_url:
        print("[TELEGRAM] Token no encontrado.")
        return
    params = urllib.parse.urlencode({
        "chat_id":    chat_id,
        "text":       mensaje,
        "parse_mode": "HTML"
    })
    url = f"{api_url}/sendMessage?{params}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"[TELEGRAM] Error enviando mensaje: {e}")

def enviar_aviso(mensaje):
    for admin_id in ADMIN_IDS:
        enviar_mensaje(admin_id, mensaje)

def obtener_updates(offset=None):
    api_url = get_api_url()
    if not api_url:
        return []
    params = {"timeout": 10, "allowed_updates": ["message", "callback_query"]}
    if offset:
        params["offset"] = offset
    url = f"{api_url}/getUpdates?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            return data.get("result", [])
    except Exception as e:
        print(f"[TELEGRAM] Error updates: {e}")
        return []

def obtener_capital_real():
    try:
        with open(BILLETERA_PATH, "r") as f:
            datos = json.load(f)
            return float(datos.get("USDT", 0))
    except Exception as e:
        print(f"[TELEGRAM] Error leyendo capital: {e}")
        return 0.0

def obtener_capital_inicial():
    try:
        from config_cartera import CAPITAL_BASE
        return CAPITAL_BASE
    except:
        return 1000.0

def obtener_senales():
    ruta = os.path.expanduser("~/bot-padre-v2/corecro/reports/corecro_signals_historico.txt")
    try:
        with open(ruta, "r") as f:
            lineas = f.readlines()
        return "".join(lineas[-10:])
    except:
        return "Sin señales disponibles."

def obtener_corecro():
    ruta = os.path.expanduser("~/bot-padre-v2/corecro/reports")
    try:
        archivos = [a for a in sorted(os.listdir(ruta)) if a.startswith("corecro_report_")]
        if not archivos:
            return "Sin reportes disponibles."
        ultimo = archivos[-1]
        with open(os.path.join(ruta, ultimo), "r") as f:
            return f.read()
    except:
        return "Sin reporte CoreCro disponible."

def obtener_bitacora(tipo="eventos", cantidad=10):
    tipo = tipo.upper()
    if tipo not in BITACORAS:
        tipo = "EVENTOS"
    emoji, inicial, nombre, ruta_rel = BITACORAS[tipo]
    ruta = os.path.expanduser(ruta_rel)
    try:
        with open(ruta, "r") as f:
            lineas = f.readlines()
        contenido = "".join(lineas[-cantidad:]) if lineas else "Sin registros aun."
        return emoji, inicial, nombre, contenido
    except:
        return emoji, inicial, nombre, "Sin registros aun."

def frase_wr(wr, total):
    if total == 0:
        return "Todavía no hay operaciones cerradas."
    de_cada_10 = round(wr / 10, 1)
    if wr >= 65:
        return f"De cada 10 trades ganas {de_cada_10} — excelente resultado. 🏆"
    elif wr >= 55:
        return f"De cada 10 trades ganas {de_cada_10} — vas bien. 👍"
    elif wr >= 45:
        return f"De cada 10 trades ganas {de_cada_10} — resultado normal. ⚖️"
    else:
        return f"De cada 10 trades ganas {de_cada_10} — el mercado está difícil. 💪"

def frase_capital(ganancia, pct):
    if ganancia > 0:
        return f"Estás ganando ${ganancia} desde que arrancaste — el bot está cumpliendo. 📈"
    elif ganancia == 0:
        return "Capital igual al inicio — el bot está en equilibrio. ⚖️"
    else:
        return f"Estás ${abs(ganancia)} abajo del inicio — el sistema trabaja para recuperarlo. 🔄"

def frase_trade(cambio_pct):
    if cambio_pct > 3:
        return f"Va muy bien, ya ganó {cambio_pct}% 🚀 Déjalo correr."
    elif cambio_pct > 0.8:
        return f"Va bien +{cambio_pct}% — el breakeven ya lo protege. 🛡️"
    elif cambio_pct > -0.5:
        return f"Está quieto {cambio_pct}% — el bot lo vigila. ⚖️"
    elif cambio_pct > -2:
        return f"Va un poco abajo {cambio_pct}% — dentro de lo normal. 📉"
    else:
        return f"Va mal {cambio_pct}% — se acerca al stop loss. ⚠️"

def leer_auditoria_stats():
    """
    Lee auditoria separando stats del bot vs manuales.
    Compatible con registros legacy MANUAL y nuevos MANUAL_WIN/MANUAL_LOSS.
    """
    stats = {
        "bot":    {"tp": 0, "sl": 0, "be": 0, "trailing": 0, "abiertas": 0},
        "manual": {"ganadas": 0, "perdidas": 0, "sin_dato": 0},
        "ultima_fecha": "Sin operaciones",
        "drawdown_max": 0.0,
    }
    capital_ini = obtener_capital_inicial()
    capital_sim = capital_ini
    capital_max = capital_ini

    try:
        with open(AUDITORIA_PATH, "r") as f:
            lineas = f.readlines()[1:]
        for linea in lineas:
            p = linea.strip().split(",")
            if len(p) < 6:
                continue
            estado = p[5].strip()

            if estado == "ABIERTA":
                stats["bot"]["abiertas"] += 1

            elif estado == "TP":
                stats["bot"]["tp"] += 1
                stats["ultima_fecha"] = p[0][:10]
                capital_sim = round(capital_sim * 1.012, 2)

            elif estado == "SL":
                stats["bot"]["sl"] += 1
                stats["ultima_fecha"] = p[0][:10]
                capital_sim = round(capital_sim * 0.988, 2)

            elif estado == "BE":
                stats["bot"]["be"] += 1
                stats["ultima_fecha"] = p[0][:10]

            elif estado == "TRAILING_SL":
                stats["bot"]["trailing"] += 1
                stats["ultima_fecha"] = p[0][:10]
                capital_sim = round(capital_sim * 1.005, 2)

            elif estado == "MANUAL_WIN":
                stats["manual"]["ganadas"] += 1
                stats["ultima_fecha"] = p[0][:10]
                capital_sim = round(capital_sim * 1.008, 2)

            elif estado == "MANUAL_LOSS":
                stats["manual"]["perdidas"] += 1
                stats["ultima_fecha"] = p[0][:10]
                capital_sim = round(capital_sim * 0.992, 2)

            elif estado == "MANUAL":
                # Legacy — no sabemos si fue ganancia o pérdida
                # Los contamos separados para no distorsionar WR
                stats["manual"]["sin_dato"] += 1
                stats["ultima_fecha"] = p[0][:10]

            if capital_sim > capital_max:
                capital_max = capital_sim
            elif capital_max > 0:
                dd = ((capital_max - capital_sim) / capital_max) * 100
                if dd > stats["drawdown_max"]:
                    stats["drawdown_max"] = round(dd, 2)

    except Exception as e:
        print(f"[TELEGRAM] Error leyendo auditoria: {e}")

    return stats

def obtener_resumen_personal():
    capital_inicial = obtener_capital_inicial()

    try:
        with open(BILLETERA_PATH) as f:
            bill = json.load(f)
    except:
        bill = {}

    usdt = bill.get("USDT", 0)
    MONEDAS = {"BTC": "BTCUSDT", "ETH": "ETHUSDT", "SOL": "SOLUSDT", "BNB": "BNBUSDT", "AVAX": "AVAXUSDT"}
    valor_monedas = 0.0
    for moneda, symbol in MONEDAS.items():
        cantidad = bill.get(moneda, 0)
        if cantidad > 0:
            try:
                params = urllib.parse.urlencode({"symbol": symbol, "interval": "1m", "limit": 1})
                url    = f"https://api.binance.com/api/v3/klines?{params}"
                with urllib.request.urlopen(url, timeout=10) as resp:
                    data = json.loads(resp.read().decode())
                precio = float(data[-1][4])
                valor_monedas += cantidad * precio
            except:
                pass

    capital_actual = round(usdt + valor_monedas, 2)
    ganancia_total = round(capital_actual - capital_inicial, 2)
    porcentaje     = round((ganancia_total / capital_inicial) * 100, 2) if capital_inicial > 0 else 0
    signo_gen      = "+" if ganancia_total >= 0 else ""
    emoji_gen      = "📈" if ganancia_total >= 0 else "📉"

    stats    = leer_auditoria_stats()
    tp       = stats["bot"]["tp"]
    sl       = stats["bot"]["sl"]
    be       = stats["bot"]["be"]
    trailing = stats["bot"]["trailing"]
    abiertas = stats["bot"]["abiertas"]

    total_bot = tp + sl
    wr_bot    = round((tp / total_bot * 100), 1) if total_bot > 0 else 0.0

    man_gan   = stats["manual"]["ganadas"]
    man_per   = stats["manual"]["perdidas"]
    man_sin   = stats["manual"]["sin_dato"]
    total_man = man_gan + man_per + man_sin

    # WR manual solo con datos conocidos
    man_conocidas = man_gan + man_per
    wr_man = round((man_gan / man_conocidas * 100), 1) if man_conocidas > 0 else 0.0

    ultima_fecha = stats["ultima_fecha"]
    drawdown_max = stats["drawdown_max"]

    # WR general — solo operaciones con resultado conocido
    total_conocido = total_bot + man_conocidas
    wins_conocidos = tp + be + trailing + man_gan
    wr_general = round((wins_conocidos / total_conocido * 100), 1) if total_conocido > 0 else 0.0

    # Frase manual
    if total_man == 0:
        frase_man = "No has cerrado ningún trade manualmente todavía."
    elif man_sin > 0 and man_conocidas == 0:
        frase_man = f"Tienes {man_sin} cierres manuales sin datos de resultado (registros anteriores)."
    elif wr_man >= 60:
        frase_man = f"Tus cierres manuales van bien. 👍"
    elif wr_man >= 40:
        frase_man = f"Tus cierres manuales están parejos."
    else:
        frase_man = f"Tus cierres manuales generaron más pérdidas — considera dejar que el bot decida."

    parado    = os.path.exists(PARADA_PATH)
    estado_bot = "⛔ PAUSADO" if parado else "🟢 ACTIVO"

    # Nota legacy si hay manuales sin dato
    nota_legacy = ""
    if man_sin > 0:
        nota_legacy = f"\n   ⚠️ {man_sin} cierres sin resultado registrado (histórico)\n"

    return (
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 <b>Z-BOT | MI RESUMEN</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"

        f"💰 <b>GENERAL</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Capital inicial:   ${capital_inicial:,.2f}\n"
        f"💵 Capital actual:    ${capital_actual:,.2f}\n"
        f"{emoji_gen} Ganancia total:  {signo_gen}${ganancia_total} ({signo_gen}{porcentaje}%)\n"
        f"📉 Drawdown máx:      {drawdown_max}%\n"
        f"📁 Total ops:         {total_bot + total_man}\n"
        f"🎯 WR general:        {wr_general}%\n"
        f"💬 {frase_capital(ganancia_total, porcentaje)}\n\n"

        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 <b>OPERACIONES DEL BOT</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📁 Total cerradas:    {total_bot}\n"
        f"✅ Ganadas (TP):       {tp}\n"
        f"🛑 Perdidas (SL):      {sl}\n"
        f"🛡️ Breakeven:          {be}\n"
        f"🎯 Trailing:           {trailing}\n"
        f"🎯 Win Rate bot:       {wr_bot}%\n"
        f"💬 {frase_wr(wr_bot, total_bot)}\n\n"

        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🤚 <b>OPERACIONES MANUALES</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📁 Total manuales:    {total_man}\n"
        f"✅ Ganadas man.:       {man_gan}\n"
        f"🛑 Perdidas man.:      {man_per}\n"
        f"🎯 WR manual:          {wr_man}%\n"
        f"{nota_legacy}"
        f"💬 {frase_man}\n\n"

        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 <b>ESTADO ACTUAL</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📂 Abiertas ahora:    {abiertas}\n"
        f"🕐 Última op.:        {ultima_fecha}\n"
        f"⚡ Estado:             {estado_bot}\n"
        f"━━━━━━━━━━━━━━━━━━━━━"
    )

def enviar_mensaje_con_botones(chat_id, mensaje, botones):
    api_url = get_api_url()
    if not api_url:
        return
    keyboard = {"inline_keyboard": [[{"text": b["text"], "callback_data": b["data"]}] for b in botones]}
    data = json.dumps({
        "chat_id":      chat_id,
        "text":         mensaje,
        "parse_mode":   "HTML",
        "reply_markup": json.dumps(keyboard)
    }).encode()
    req = urllib.request.Request(
        f"{api_url}/sendMessage",
        data=data,
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"[TELEGRAM] Error botones: {e}")

def responder_callback(callback_query_id, texto):
    api_url = get_api_url()
    if not api_url:
        return
    params = urllib.parse.urlencode({
        "callback_query_id": callback_query_id,
        "text":              texto
    })
    url = f"{api_url}/answerCallbackQuery?{params}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            pass
    except Exception as e:
        print(f"[TELEGRAM] Error callback: {e}")

def obtener_operaciones_abiertas():
    try:
        with open(AUDITORIA_PATH, "r") as f:
            lineas = f.readlines()
        abiertas = []
        for linea in lineas[1:]:
            p = linea.strip().split(",")
            if len(p) >= 6 and p[5] == "ABIERTA":
                try:
                    monto = float(p[6]) if len(p) > 6 else 10.0
                except:
                    monto = 10.0
                abiertas.append({
                    "timestamp":      p[0],
                    "symbol":         p[2],
                    "accion":         p[1],
                    "precio_entrada": float(p[3]),
                    "monto":          monto
                })
        if not abiertas:
            return "📭 <b>No hay trades abiertos ahora mismo.</b>\n\n💬 El bot está esperando una buena oportunidad para entrar.", []

        TAKE_PROFIT    = 6.0
        lineas_msg     = ["📊 <b>TRADES ABIERTOS</b>\n"]
        total_ganancia = 0.0
        botones        = []

        for op in abiertas:
            sym    = op["symbol"]
            entrada = op["precio_entrada"]
            monto  = op["monto"]
            accion = op["accion"]
            ts     = op["timestamp"]

            try:
                dt_entr = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
                horas   = round((datetime.now() - dt_entr).total_seconds() / 3600, 1)
            except:
                horas = 0

            try:
                params = urllib.parse.urlencode({"symbol": sym, "interval": "1m", "limit": 1})
                url    = f"https://api.binance.com/api/v3/klines?{params}"
                with urllib.request.urlopen(url, timeout=10) as resp:
                    data = json.loads(resp.read().decode())
                precio_ahora = float(data[-1][4])
            except:
                precio_ahora = entrada

            if accion == "BAJISTA":
                cambio_pct = round(((entrada - precio_ahora) / entrada) * 100, 2)
            else:
                cambio_pct = round(((precio_ahora - entrada) / entrada) * 100, 2)

            ganancia_usd   = round((cambio_pct / 100) * monto, 3)
            total_ganancia += ganancia_usd
            busca_usd      = round(monto * (1 + TAKE_PROFIT / 100), 2)
            emoji          = "✅" if cambio_pct >= 0 else "🔴"
            signo          = "+" if cambio_pct >= 0 else ""
            moneda         = sym.replace("USDT", "")

            lineas_msg.append(f"{emoji} <b>{moneda}</b> — {accion}")
            lineas_msg.append(f"   Entró a: ${entrada} | Ahora: ${round(precio_ahora, 4)}")
            lineas_msg.append(f"   {signo}{cambio_pct}%  ({signo}${ganancia_usd} USDT)")
            lineas_msg.append(f"   💵 Invertido: ${monto} | 🎯 Busca: ${busca_usd}")
            lineas_msg.append(f"   ⏱ Lleva: {horas}h abierto")
            lineas_msg.append(f"   💬 {frase_trade(cambio_pct)}\n")
            botones.append({"text": f"🚪 Salir {moneda}", "data": f"salir_{sym}"})

        signo_total = "+" if total_ganancia >= 0 else ""
        lineas_msg.append(f"💰 <b>Total neto ahora: {signo_total}${round(total_ganancia,3)} USDT</b>")
        return "\n".join(lineas_msg), botones

    except Exception as e:
        return f"⚠️ Error: {e}", []

def cerrar_operacion_manual(symbol):
    try:
        params = urllib.parse.urlencode({"symbol": symbol, "interval": "1m", "limit": 1})
        url    = f"https://api.binance.com/api/v3/klines?{params}"
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        precio_ahora = float(data[-1][4])
    except:
        return f"⚠️ No pude obtener precio de {symbol}"

    try:
        _lk = open(AUDITORIA_LOCK, "w")
        fcntl.flock(_lk, fcntl.LOCK_EX)
        with open(AUDITORIA_PATH, "r") as f:
            lineas = f.readlines()
        header         = lineas[0]
        nuevas         = [header]
        cerradas       = 0
        ganancia_total = 0.0
        for linea in lineas[1:]:
            p = linea.strip().split(",")
            if len(p) >= 6 and p[2] == symbol and p[5] == "ABIERTA":
                precio_entrada = float(p[3])
                cambio         = ((precio_ahora - precio_entrada) / precio_entrada) * 100
                monto          = float(p[6]) if len(p) > 6 else 10.0
                ganancia_total += round((cambio / 100) * monto, 3)
                p[5] = "MANUAL_WIN" if cambio >= 0 else "MANUAL_LOSS"
                cerradas += 1
            nuevas.append(",".join(p) + "\n")
        _tmp = AUDITORIA_PATH + ".tmp"
        with open(_tmp, "w") as f:
            f.writelines(nuevas)
        os.replace(_tmp, AUDITORIA_PATH)
        _lk.close()
        if cerradas == 0:
            return f"⚠️ No hay operaciones abiertas de {symbol}"
        signo  = "+" if ganancia_total >= 0 else ""
        emoji  = "✅" if ganancia_total >= 0 else "🔴"
        moneda = symbol.replace("USDT","")
        if ganancia_total >= 0:
            resultado_texto = f"Saliste ganando ${ganancia_total} USDT. Buena decisión. ✅"
        else:
            resultado_texto = f"Saliste perdiendo ${abs(ganancia_total)} USDT. A veces hay que cortar. 💪"
        return (
            f"{emoji} <b>SALIDA MANUAL {moneda}</b>\n"
            f"Precio de salida: ${precio_ahora}\n"
            f"Resultado: {signo}${ganancia_total} USDT\n\n"
            f"💬 {resultado_texto}"
        )
    except Exception as e:
        return f"⚠️ Error cerrando {symbol}: {e}"

def obtener_pnl_dia():
    hoy    = date.today().strftime("%Y-%m-%d")
    tp_hoy = sl_hoy = be_hoy = 0
    try:
        with open(AUDITORIA_PATH, "r") as f:
            lineas = f.readlines()
        for linea in lineas[1:]:
            p = linea.strip().split(",")
            if len(p) >= 6 and p[0].startswith(hoy):
                if p[5] == "TP":      tp_hoy += 1
                elif p[5] == "SL":    sl_hoy += 1
                elif p[5] == "BE":    be_hoy += 1
    except:
        pass

    total_hoy = tp_hoy + sl_hoy + be_hoy
    wr_hoy    = round(tp_hoy / total_hoy * 100, 1) if total_hoy > 0 else 0

    capital_ini = obtener_capital_inicial()
    try:
        with open(BILLETERA_PATH) as f:
            bill = json.load(f)
        usdt = bill.get("USDT", 0)
    except:
        usdt = 0
        bill = {}

    MONEDAS = {"BTC": "BTCUSDT", "ETH": "ETHUSDT", "SOL": "SOLUSDT", "BNB": "BNBUSDT", "AVAX": "AVAXUSDT"}
    valor_monedas = 0.0
    for moneda, symbol in MONEDAS.items():
        cantidad = bill.get(moneda, 0)
        if cantidad > 0:
            try:
                params = urllib.parse.urlencode({"symbol": symbol, "interval": "1m", "limit": 1})
                url    = f"https://api.binance.com/api/v3/klines?{params}"
                with urllib.request.urlopen(url, timeout=10) as resp:
                    data = json.loads(resp.read().decode())
                valor_monedas += cantidad * float(data[-1][4])
            except:
                pass

    capital_actual = round(usdt + valor_monedas, 2)
    ganancia_total = round(capital_actual - capital_ini, 2)
    signo_total    = "+" if ganancia_total >= 0 else ""

    if total_hoy == 0:
        eval_dia = "Hoy no hubo operaciones cerradas todavía. El bot está buscando señales."
    elif wr_hoy >= 65:
        eval_dia = f"Excelente día — ganaste {tp_hoy} de {total_hoy} trades. 🏆"
    elif wr_hoy >= 50:
        eval_dia = f"Buen día — más victorias que derrotas ({tp_hoy} ganadas, {sl_hoy} perdidas). 👍"
    elif wr_hoy >= 35:
        eval_dia = f"Día regular — {tp_hoy} ganadas y {sl_hoy} perdidas. El mercado estuvo difícil. ⚖️"
    else:
        eval_dia = f"Día difícil — {sl_hoy} perdidas y {tp_hoy} ganadas. Forma parte del proceso. 💪"

    if ganancia_total > 0:
        eval_capital = f"En total desde el inicio estás ganando ${ganancia_total}. Vas por buen camino. 📈"
    elif ganancia_total == 0:
        eval_capital = "El capital está igual al inicio. El bot está en equilibrio."
    else:
        eval_capital = f"En total estás ${abs(ganancia_total)} abajo del inicio. El sistema trabaja para recuperarlo. 🔄"

    return (
        f"📊 <b>CÓMO FUE EL DÍA HOY</b>\n"
        f"🕐 {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n"
        f"✅ Trades ganados:   {tp_hoy}\n"
        f"❌ Trades perdidos:  {sl_hoy}\n"
        f"🛡️ Breakeven:        {be_hoy}\n"
        f"📈 Win rate hoy:     {wr_hoy}%\n\n"
        f"💰 Capital ahora:    ${capital_actual}\n"
        f"🏦 Capital inicial:  ${capital_ini}\n"
        f"📊 Diferencia:       {signo_total}${ganancia_total}\n\n"
        f"💬 <b>{eval_dia}</b>\n\n"
        f"💬 <b>{eval_capital}</b>"
    )

def activar_parada_emergencia(chat_id):
    try:
        with open(PARADA_PATH, "w") as f:
            f.write(f"PARADA solicitada por admin {chat_id} a las {datetime.now()}")
        return (
            "🛑 <b>PARADA DE EMERGENCIA ACTIVADA</b>\n\n"
            "El bot dejará de abrir nuevas operaciones en el próximo ciclo.\n\n"
            "⚠️ Los trades ya abiertos siguen bajo vigilancia hasta que cierren solos.\n\n"
            "Para reactivar el bot escribe /reactivar"
        )
    except Exception as e:
        return f"❌ Error activando parada: {e}"

def reactivar_bot(chat_id):
    try:
        if os.path.exists(PARADA_PATH):
            os.remove(PARADA_PATH)
            return (
                "✅ <b>BOT REACTIVADO</b>\n\n"
                "El bot vuelve a buscar oportunidades en el próximo ciclo.\n"
                "Todo funciona con normalidad."
            )
        else:
            return "ℹ️ El bot no estaba pausado. Sigue funcionando con normalidad."
    except Exception as e:
        return f"❌ Error reactivando: {e}"

def obtener_disparos():
    QUINTETO     = [("BTCUSDT","BTC"),("ETHUSDT","ETH"),("SOLUSDT","SOL"),("BNBUSDT","BNB"),("AVAXUSDT","AVAX")]
    RSI_MIN      = 45; RSI_MAX = 55
    EMA_CORTA    = 20; EMA_LARGA = 50
    DIFF_EMA_MAX = 2.0
    VENTANA_FASE = 30; UMBRAL_FASE = 2.5
    from utils import calcular_rsi, calcular_ema, fetch_velas

    def detectar_fase(cierres):
        if len(cierres) < VENTANA_FASE: return "?"
        cambio = ((cierres[-1]-cierres[-VENTANA_FASE])/cierres[-VENTANA_FASE])*100
        if cambio > UMBRAL_FASE: return "ALCISTA"
        elif cambio < -UMBRAL_FASE: return "BAJISTA"
        return "LATERAL"

    def barra(pct, largo=10):
        pct = max(0, min(100, pct))
        return "█" * int(pct/100*largo) + "░" * (largo - int(pct/100*largo))

    def pct_rsi(rsi):
        if rsi is None: return 0
        if RSI_MIN <= rsi <= RSI_MAX: return 100
        if rsi < RSI_MIN: return max(0, round(100-((RSI_MIN-rsi)/RSI_MIN*100),1))
        return max(0, round(100-((rsi-RSI_MAX)/(100-RSI_MAX)*100),1))

    def pct_ema(diff):
        if diff is None: return 0
        if diff >= DIFF_EMA_MAX: return max(0, round(100-((diff-DIFF_EMA_MAX)/DIFF_EMA_MAX*100),1))
        return round((1-diff/DIFF_EMA_MAX)*100,1)

    lineas = ["🎯 <b>ESTADO DE CADA MONEDA</b>\n"]
    for symbol, nombre in QUINTETO:
        cierres = fetch_velas(symbol, limite=210)
        if not cierres:
            lineas.append(f"💱 <b>{nombre}</b>\n❌ Sin datos\n──────────────")
            continue
        precio   = cierres[-1]
        rsi      = calcular_rsi(cierres)
        ema_c    = calcular_ema(cierres, EMA_CORTA)
        ema_l    = calcular_ema(cierres, EMA_LARGA)
        fase     = detectar_fase(cierres)
        diff_ema = round(abs(ema_c-ema_l)/ema_l*100,2) if ema_c and ema_l else None
        p_rsi    = pct_rsi(rsi)
        p_ema    = pct_ema(diff_ema) if diff_ema is not None else 0
        p_fase   = 100 if fase == "LATERAL" else 0
        p_total  = round(p_rsi*0.4 + p_ema*0.4 + p_fase*0.2, 1)
        rsi_ok   = RSI_MIN <= (rsi or 0) <= RSI_MAX
        ema_ok   = (diff_ema or 999) < DIFF_EMA_MAX
        fase_ok  = fase == "LATERAL"
        if rsi_ok and ema_ok and fase_ok and p_total >= 90:
            estado_emoji = "🟢 LISTO PARA OPERAR"
            consejo      = "El bot puede entrar en cualquier momento."
        elif p_total >= 60:
            estado_emoji = "🟡 CASI LISTO"
            consejo      = "Le falta poco para tener señal."
        else:
            estado_emoji = "🔴 NO LISTO"
            consejo      = "El mercado no da señal todavía."
        motivos = []
        if not rsi_ok:  motivos.append("RSI fuera de rango")
        if not ema_ok:  motivos.append("Medias muy separadas")
        if not fase_ok: motivos.append(f"Mercado en {fase}")
        lineas.append(
            f"💱 <b>{nombre}</b> — ${precio}\n"
            f"[{barra(p_total)}] {p_total}% listo\n"
            f"📍 {fase} | {estado_emoji}\n"
            f"⚙️ {' | '.join(motivos) if motivos else 'Todo en orden'}\n"
            f"💬 {consejo}\n──────────────"
        )
    return "\n".join(lineas)

def obtener_memoria():
    ruta = os.path.expanduser("~/bot-padre-v2/data/memoria_propia.json")
    try:
        with open(ruta) as f:
            mem = json.load(f)
    except:
        return "📭 Sin memoria acumulada aún."
    lineas = ["🧠 <b>LO QUE EL BOT APRENDIÓ</b>\n"]
    total  = mem.get('total_trades', 0)
    wr     = mem.get('wr_global', 0)
    lineas.append(f"📊 Total trades: {total}")
    lineas.append(f"🎯 WR Global: {wr}%")
    lineas.append(f"💬 {frase_wr(wr, total)}\n")
    lineas.append("📈 <b>POR MONEDA:</b>")
    for sym in ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","AVAXUSDT"]:
        wr_sym  = mem.get(f"{sym}_wr", None)
        ops_sym = mem.get(f"{sym}_trades", 0)
        if wr_sym is not None:
            emoji  = "✅" if wr_sym >= 60 else "⚠️" if wr_sym >= 50 else "🔴"
            moneda = sym.replace("USDT","")
            lineas.append(f"  {emoji} {moneda}: {wr_sym}% WR ({ops_sym} trades) — {frase_wr(wr_sym, ops_sym)}")
    lineas.append(f"\n🕐 Actualizado: {mem.get('actualizado', 'N/A')}")
    return "\n".join(lineas)

def obtener_registros():
    try:
        with open(AUDITORIA_PATH) as f:
            lineas = f.readlines()
        if len(lineas) <= 1:
            return "📭 Sin registros aún."
        ops = lineas[1:][-10:]
        msg = ["📋 <b>ÚLTIMAS OPERACIONES</b>\n"]
        for l in ops:
            p = l.strip().split(",")
            if len(p) >= 6:
                fecha  = p[0][:10]
                sym    = p[2].replace("USDT","")
                estado = p[5]
                if estado == "TP":           emoji = "✅"; texto = "Ganada"
                elif estado == "SL":         emoji = "🔴"; texto = "Perdida"
                elif estado == "BE":         emoji = "🛡️"; texto = "Salió en cero"
                elif estado == "TRAILING_SL":emoji = "🎯"; texto = "Salió con trailing"
                elif estado == "MANUAL_WIN": emoji = "🤚✅"; texto = "Manual — ganada"
                elif estado == "MANUAL_LOSS":emoji = "🤚🔴"; texto = "Manual — perdida"
                elif estado == "MANUAL":     emoji = "🤚"; texto = "Manual (histórico)"
                else:                        emoji = "📂"; texto = estado
                msg.append(f"{emoji} {fecha} | {sym} | {texto}")
        return "\n".join(msg)
    except Exception as e:
        return f"⚠️ Error: {e}"

def obtener_estadisticas():
    try:
        with open(AUDITORIA_PATH) as f:
            lineas = f.readlines()
        stats = {}
        for l in lineas[1:]:
            p = l.strip().split(",")
            if len(p) >= 6 and p[5] in ("TP","SL","MANUAL_WIN","MANUAL_LOSS","TRAILING_SL"):
                sym = p[2]
                if sym not in stats:
                    stats[sym] = {"tp": 0, "sl": 0}
                if p[5] in ("TP", "MANUAL_WIN"):
                    stats[sym]["tp"] += 1
                else:
                    stats[sym]["sl"] += 1
        if not stats:
            return "📭 Sin estadísticas aún."
        msg = ["📊 <b>RENDIMIENTO POR MONEDA</b>\n"]
        for sym, s in sorted(stats.items()):
            total  = s["tp"] + s["sl"]
            wr     = round((s["tp"]/total*100),1) if total > 0 else 0
            emoji  = "✅" if wr >= 60 else "⚠️" if wr >= 50 else "🔴"
            moneda = sym.replace('USDT','')
            msg.append(f"{emoji} <b>{moneda}</b>: {wr}% WR ({s['tp']} ganadas / {s['sl']} perdidas / {total} total)")
            msg.append(f"   💬 {frase_wr(wr, total)}")
        return "\n".join(msg)
    except Exception as e:
        return f"⚠️ Error: {e}"

def procesar_comando(mensaje, chat_id):
    if chat_id not in ADMIN_IDS:
        enviar_mensaje(chat_id, "⛔ No autorizado.")
        return

    if mensaje in ("/start", "/ping"):
        enviar_mensaje(chat_id, "🟢 Z-Bot V2 activo y respondiendo.")
    elif mensaje == "/status":
        parado = os.path.exists(PARADA_PATH)
        estado = "⛔ PAUSADO — escribe /reactivar para volver" if parado else "🟢 ACTIVO — operando con normalidad"
        enviar_mensaje(chat_id, f"🤖 Estado del bot: {estado}")
    elif mensaje == "/capital":
        capital = obtener_capital_real()
        enviar_mensaje(chat_id, f"💰 Capital disponible en USDT: ${capital}")
    elif mensaje == "/senales":
        enviar_mensaje(chat_id, obtener_senales())
    elif mensaje == "/corecro":
        enviar_mensaje(chat_id, obtener_corecro())
    elif mensaje == "/resumen":
        enviar_mensaje(chat_id, obtener_resumen_personal())
    elif mensaje == "/operaciones":
        texto, botones = obtener_operaciones_abiertas()
        if botones:
            enviar_mensaje_con_botones(chat_id, texto, botones)
        else:
            enviar_mensaje(chat_id, texto)
    elif mensaje == "/pnl":
        enviar_mensaje(chat_id, obtener_pnl_dia())
    elif mensaje == "/parar":
        enviar_mensaje(chat_id, activar_parada_emergencia(chat_id))
    elif mensaje == "/reactivar":
        enviar_mensaje(chat_id, reactivar_bot(chat_id))
    elif mensaje == "/disparos":
        enviar_mensaje(chat_id, obtener_disparos())
    elif mensaje.startswith("/salir"):
        partes = mensaje.split()
        if len(partes) < 2:
            enviar_mensaje(chat_id, "⚠️ Uso: /salir BTCUSDT")
        else:
            enviar_mensaje(chat_id, cerrar_operacion_manual(partes[1].upper()))
    elif mensaje == "/memoria":
        enviar_mensaje(chat_id, obtener_memoria())
    elif mensaje == "/registros":
        enviar_mensaje(chat_id, obtener_registros())
    elif mensaje == "/estadisticas":
        enviar_mensaje(chat_id, obtener_estadisticas())
    elif mensaje.startswith("/alertar"):
        partes = mensaje.split()
        if len(partes) < 3:
            enviar_mensaje(chat_id, "⚠️ Uso: /alertar BNBUSDT 603.3")
        else:
            symbol = partes[1].upper()
            try:
                precio_entrada = float(partes[2])
                if symbol in _monitores_activos:
                    enviar_mensaje(chat_id, f"⚠️ Ya hay monitor activo para {symbol}\nUsa /cancelar {symbol} primero.")
                else:
                    _monitores_stop[symbol] = False
                    t = threading.Thread(target=_monitor_precio, args=(symbol, precio_entrada, chat_id), daemon=True)
                    _monitores_activos[symbol] = t
                    t.start()
            except ValueError:
                enviar_mensaje(chat_id, "⚠️ Precio inválido.")
    elif mensaje.startswith("/cancelar"):
        partes = mensaje.split()
        if len(partes) < 2:
            enviar_mensaje(chat_id, "⚠️ Uso: /cancelar BNBUSDT")
        else:
            symbol = partes[1].upper()
            if symbol in _monitores_activos:
                _monitores_stop[symbol] = True
                enviar_mensaje(chat_id, f"⏳ Cancelando monitor de {symbol}...")
            else:
                enviar_mensaje(chat_id, f"⚠️ No hay monitor activo para {symbol}")
    elif mensaje.startswith("/bitacora"):
        partes = mensaje.split()
        tipo   = partes[1] if len(partes) > 1 else "eventos"
        emoji, inicial, nombre, contenido = obtener_bitacora(tipo)
        enviar_mensaje(chat_id, f"{emoji} <b>Bitácora {inicial} - {nombre}</b>\n\n{contenido}")
    elif mensaje == "/ayuda":
        enviar_mensaje(chat_id,
            "📋 <b>COMANDOS DISPONIBLES</b>\n\n"
            "📊 <b>VER INFORMACIÓN:</b>\n"
            "/resumen — Mi resumen completo\n"
            "/pnl — Cómo fue el día hoy\n"
            "/operaciones — Trades abiertos ahora\n"
            "/estadisticas — Rendimiento por moneda\n"
            "/registros — Últimas operaciones\n"
            "/capital — Cuánto USDT hay disponible\n"
            "/memoria — Lo que el bot aprendió\n"
            "/disparos — Estado de cada moneda\n\n"
            "⚙️ <b>CONTROLAR EL BOT:</b>\n"
            "/parar — Detener el bot de emergencia\n"
            "/reactivar — Volver a activar el bot\n"
            "/status — Ver si el bot está activo\n"
            "/salir SYMBOL — Cerrar un trade manualmente\n\n"
            "📡 <b>MONITOREAR PRECIOS:</b>\n"
            "/alertar SYMBOL PRECIO — Vigilar un precio\n"
            "/cancelar SYMBOL — Dejar de vigilar\n\n"
            "📋 <b>OTROS:</b>\n"
            "/bitacora — Ver log de eventos\n"
            "/ping — Verificar que responde\n"
            "/ayuda — Esta lista"
        )
    else:
        enviar_mensaje(chat_id, "❓ No reconozco ese comando.\nEscribe /ayuda para ver qué puedo hacer.")

def escuchar():
    print("[TELEGRAM] Escuchando comandos...")
    offset = None
    while True:
        try:
            updates = obtener_updates(offset)
            for update in updates:
                offset = update["update_id"] + 1
                if "callback_query" in update:
                    cb      = update["callback_query"]
                    cb_id   = cb["id"]
                    cb_data = cb.get("data", "")
                    cb_chat = cb["message"]["chat"]["id"]
                    if cb_chat in ADMIN_IDS:
                        if cb_data.startswith("salir_"):
                            symbol = cb_data.replace("salir_", "")
                            responder_callback(cb_id, f"Cerrando {symbol}...")
                            enviar_mensaje(cb_chat, cerrar_operacion_manual(symbol))
                    continue
                msg_obj = update.get("message", {})
                texto   = msg_obj.get("text", "")
                chat_id = msg_obj.get("chat", {}).get("id")
                if texto and chat_id:
                    procesar_comando(texto, chat_id)
        except Exception as e:
            print(f"[TELEGRAM] Error en escuchar: {e}")
        time.sleep(1)

if __name__ == "__main__":
    escuchar()
