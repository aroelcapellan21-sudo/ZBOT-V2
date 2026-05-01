# =========================================
# brain/telegram_engine.py - Comunicador Actualizado
# Rol: Envia alertas y responde comandos.
# UNIFICADO: Capital real en todos los reportes.
# =========================================

import urllib.request
import urllib.parse
import json
import os
import threading
import time
from datetime import datetime

# --- Administradores ---
ADMIN_YAYO = 6578945006
ADMIN_SOCIA = 6533031969
ADMIN_IDS = [ADMIN_YAYO, ADMIN_SOCIA]

BITACORAS = {
    "EVENTOS":   ("🟢", "E", "Eventos",   "~/bot-padre-v2/memoria/eventos.log"),
    "CENTINELA": ("🔴", "C", "Centinela", "~/bot-padre-v2/memoria/centinela.log"),
    "CORECRO":   ("🔵", "C", "Corecro",   "~/bot-padre-v2/memoria/corecro.log"),
    "MATRIX":    ("🟡", "M", "Matrix",    "~/bot-padre-v2/memoria/matrix.log"),
}

# ─── MONITOR DE PRECIOS ───────────────────────────────────────────────────────
_monitores_activos = {}
_monitores_stop    = {}

def _monitor_precio(symbol, precio_entrada, chat_id, intervalo_puntos=7):
    ultimo_nivel  = precio_entrada
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
            url = f"https://api.telegram.org/bot{cargar_token()}"
            url2 = f"https://api.binance.com/api/v3/klines?{params}"
            with urllib.request.urlopen(url2, timeout=10) as resp:
                data = json.loads(resp.read().decode())
            precio_actual = float(data[-1][4])
            ganancia = round(precio_actual - precio_entrada, 2)
            signo = "+" if ganancia >= 0 else ""
            pct = round(((precio_actual - precio_entrada) / precio_entrada) * 100, 2)

            # Subida de N puntos
            if precio_actual >= ultimo_nivel + intervalo_puntos:
                enviar_mensaje(chat_id,
                    f"📈 <b>{symbol} SUBIÓ</b>\n"
                    f"💰 Entrada:  ${precio_entrada}\n"
                    f"📍 Ahora:    ${round(precio_actual, 2)}\n"
                    f"🚀 Ganancia: {signo}${ganancia} ({signo}{pct}%)\n"
                    f"⚡ ¿Salir o dejar correr?"
                )
                ultimo_nivel  = precio_actual
                enviado_reverso = False

            # Reverso al precio de entrada
            elif precio_actual <= precio_entrada and not enviado_reverso:
                enviar_mensaje(chat_id,
                    f"⚠️ <b>{symbol} REVERSO</b>\n"
                    f"💰 Entrada:  ${precio_entrada}\n"
                    f"📍 Ahora:    ${round(precio_actual, 2)}\n"
                    f"📉 Resultado: ${ganancia} ({pct}%)\n"
                    f"🛑 Considera salir manualmente"
                )
                enviado_reverso = True

            # Si recupera, resetea el flag
            elif precio_actual > precio_entrada + 2:
                enviado_reverso = False

        except Exception as e:
            print(f"[MONITOR] Error {symbol}: {e}")

        time.sleep(30)

    enviar_mensaje(chat_id, f"❌ <b>Monitor {symbol} cancelado.</b>")
    _monitores_activos.pop(symbol, None)
    _monitores_stop.pop(symbol, None)
# ─────────────────────────────────────────────────────────────────────────────

def cargar_token():
    ruta = os.path.expanduser("~/bot-padre-v2/keys.env")
    try:
        with open(ruta, "r") as f:
            for linea in f:
                if linea.startswith("TELEGRAM_TOKEN="):
                    return linea.strip().split("=", 1)[1]
    except:
        return None

TOKEN = cargar_token()
API_URL = f"https://api.telegram.org/bot{TOKEN}"

def enviar_mensaje(chat_id, mensaje):
    if not TOKEN:
        print("[TELEGRAM] Token no encontrado.")
        return
    params = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": mensaje,
        "parse_mode": "HTML"
    })
    url = f"{API_URL}/sendMessage?{params}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"[TELEGRAM] Error: {e}")

def enviar_aviso(mensaje):
    for admin_id in ADMIN_IDS:
        enviar_mensaje(admin_id, mensaje)

def obtener_updates(offset=None):
    params = {"timeout": 10, "allowed_updates": ["message", "callback_query"]}
    if offset:
        params["offset"] = offset
    url = f"{API_URL}/getUpdates?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            return data.get("result", [])
    except Exception as e:
        print(f"[TELEGRAM] Error updates: {e}")
        return []

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

def obtener_capital_real():
    ruta = os.path.expanduser("~/bot-padre-v2/signals/billetera.json")
    capital_inicial = 1000.0
    try:
        with open(ruta, "r") as f:
            datos = json.load(f)
            return float(datos.get("USDT", capital_inicial))
    except:
        return capital_inicial

def obtener_bitacora(tipo="eventos", cantidad=10):
    tipo = tipo.upper()
    if tipo not in BITACORAS:
        tipo = "eventos"
    emoji, inicial, nombre, ruta_rel = BITACORAS[tipo]
    ruta = os.path.expanduser(ruta_rel)
    try:
        with open(ruta, "r") as f:
            lineas = f.readlines()
        contenido = "".join(lineas[-cantidad:]) if lineas else "Sin registros aun."
        return emoji, inicial, nombre, contenido
    except:
        return emoji, inicial, nombre, "Sin registros aun."

def obtener_resumen_personal():
    import urllib.request, urllib.parse, json as _json
    ruta_billetera = os.path.expanduser("~/bot-padre-v2/signals/billetera.json")
    ruta_auditoria = os.path.expanduser("~/bot-padre-v2/auditoria.csv")
    capital_inicial = 1000.0

    try:
        with open(ruta_billetera) as f:
            bill = _json.load(f)
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
                url = f"https://api.binance.com/api/v3/klines?{params}"
                with urllib.request.urlopen(url, timeout=10) as resp:
                    data = _json.loads(resp.read().decode())
                precio = float(data[-1][4])
                valor_monedas += cantidad * precio
            except:
                pass

    capital_actual = round(usdt + valor_monedas, 2)
    ganancia = round(capital_actual - capital_inicial, 2)
    porcentaje = round((ganancia / capital_inicial) * 100, 2)
    signo = "+" if ganancia >= 0 else ""

    total = tp = sl = abiertas = 0
    ultima_fecha = "Sin operaciones"

    try:
        with open(ruta_auditoria, "r") as f:
            lineas = f.readlines()[1:]
        for linea in lineas:
            p = linea.strip().split(",")
            if len(p) < 6: continue
            if p[5] == "ABIERTA": abiertas += 1
            elif p[5] == "TP":
                tp += 1; total += 1; ultima_fecha = p[0][:10]
            elif p[5] == "SL":
                sl += 1; total += 1; ultima_fecha = p[0][:10]
    except: pass

    winrate = round((tp / total * 100), 1) if total > 0 else 0.0
    emoji_ganancia = "📈" if ganancia >= 0 else "📉"

    msg = (
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 <b>Z-BOT | MI RESUMEN</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 <b>Capital inicial:</b>  ${capital_inicial:,.2f}\n"
        f"💵 <b>Capital actual:</b>   ${capital_actual:,.2f}\n"
        f"{emoji_ganancia} <b>Ganancia:</b>        {signo}${ganancia} ({signo}{porcentaje}%)\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>OPERACIONES</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📁 Total cerradas:   {total}\n"
        f"✅ Ganadas (TP):      {tp}\n"
        f"🛑 Perdidas (SL):     {sl}\n"
        f"🎯 Win Rate:          {winrate}%\n"
        f"📂 Abiertas ahora:   {abiertas}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🕐 Última operación: {ultima_fecha}\n"
        f"⚡ Estado:            🟢 ACTIVO\n"
        f"━━━━━━━━━━━━━━━━━━━━━"
    )
    return msg

def enviar_mensaje_con_botones(chat_id, mensaje, botones):
    if not TOKEN:
        return
    import json as _json
    keyboard = {"inline_keyboard": [[{"text": b["text"], "callback_data": b["data"]}] for b in botones]}
    data = _json.dumps({
        "chat_id": chat_id,
        "text": mensaje,
        "parse_mode": "HTML",
        "reply_markup": _json.dumps(keyboard)
    }).encode()
    req = urllib.request.Request(
        f"{API_URL}/sendMessage",
        data=data,
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return _json.loads(resp.read().decode())
    except Exception as e:
        print(f"[TELEGRAM] Error botones: {e}")

def responder_callback(callback_query_id, texto):
    params = urllib.parse.urlencode({
        "callback_query_id": callback_query_id,
        "text": texto
    })
    url = f"{API_URL}/answerCallbackQuery?{params}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            pass
    except:
        pass

def obtener_operaciones_abiertas():
    ruta_audit = os.path.expanduser("~/bot-padre-v2/auditoria.csv")
    try:
        with open(ruta_audit, "r") as f:
            lineas = f.readlines()
        abiertas = []
        for linea in lineas[1:]:
            p = linea.strip().split(",")
            if len(p) >= 6 and p[5] == "ABIERTA":
                abiertas.append({"symbol": p[2], "precio_entrada": float(p[3]), "monto": 10.0})
        if not abiertas:
            return "📭 No hay operaciones abiertas ahora mismo.", []
        import urllib.request, urllib.parse, json as _json
        TAKE_PROFIT = 6.0
        lineas_msg = ["📊 <b>OPERACIONES ABIERTAS</b>\n"]
        total_ganancia = 0.0
        botones = []
        for op in abiertas:
            sym = op["symbol"]
            entrada = op["precio_entrada"]
            monto = op["monto"]
            try:
                params = urllib.parse.urlencode({"symbol": sym, "interval": "1m", "limit": 1})
                url = f"https://api.binance.com/api/v3/klines?{params}"
                with urllib.request.urlopen(url, timeout=10) as resp:
                    data = _json.loads(resp.read().decode())
                precio_actual = float(data[-1][4])
            except:
                precio_actual = entrada
            cambio_pct = ((precio_actual - entrada) / entrada) * 100
            ganancia_usd = round((cambio_pct / 100) * monto, 3)
            total_ganancia += ganancia_usd
            busca_usd = round(monto * (1 + TAKE_PROFIT / 100), 2)
            emoji = "✅" if cambio_pct >= 0 else "🔴"
            emoji_gp = "📈" if cambio_pct >= 0 else "📉"
            signo = "+" if cambio_pct >= 0 else ""
            lineas_msg.append(f"{emoji} <b>{sym}</b>")
            lineas_msg.append(f"   Entrada:      ${entrada}")
            lineas_msg.append(f"   Ahora:        ${precio_actual}")
            lineas_msg.append(f"   {signo}{round(cambio_pct,2)}%  ({signo}${ganancia_usd} USDT)")
            lineas_msg.append(f"   💵 Invertido: ${monto} USDT")
            lineas_msg.append(f"   🎯 Busca:     ${busca_usd} USDT (+{TAKE_PROFIT}%)")
            lineas_msg.append(f"   {emoji_gp} Resultado:  {signo}${ganancia_usd} USDT\n")
            botones.append({"text": f"🚪 Salir {sym}", "data": f"salir_{sym}"})
        signo_total = "+" if total_ganancia >= 0 else ""
        lineas_msg.append(f"💰 <b>Total neto: {signo_total}${round(total_ganancia,3)} USDT</b>")
        return "\n".join(lineas_msg), botones
    except Exception as e:
        return f"⚠️ Error: {e}", []

def cerrar_operacion_manual(symbol):
    ruta_audit = os.path.expanduser("~/bot-padre-v2/auditoria.csv")
    import urllib.request, urllib.parse, json as _json
    try:
        params = urllib.parse.urlencode({"symbol": symbol, "interval": "1m", "limit": 1})
        url = f"https://api.binance.com/api/v3/klines?{params}"
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = _json.loads(resp.read().decode())
        precio_actual = float(data[-1][4])
    except:
        return f"⚠️ No pude obtener precio de {symbol}"
    try:
        with open(ruta_audit, "r") as f:
            lineas = f.readlines()
        header = lineas[0]
        nuevas = [header]
        cerradas = 0
        ganancia_total = 0.0
        for linea in lineas[1:]:
            p = linea.strip().split(",")
            if len(p) >= 6 and p[2] == symbol and p[5] == "ABIERTA":
                precio_entrada = float(p[3])
                cambio = ((precio_actual - precio_entrada) / precio_entrada) * 100
                ganancia_total += round((cambio / 100) * 10.0, 3)
                p[5] = "MANUAL"
                cerradas += 1
            nuevas.append(",".join(p) + "\n")
        with open(ruta_audit, "w") as f:
            f.writelines(nuevas)
        if cerradas == 0:
            return f"⚠️ No hay operaciones abiertas de {symbol}"
        signo = "+" if ganancia_total >= 0 else ""
        emoji = "✅" if ganancia_total >= 0 else "🔴"
        return (f"{emoji} <b>SALIDA MANUAL {symbol}</b>\n"
                f"Precio salida: ${precio_actual}\n"
                f"Ops cerradas: {cerradas}\n"
                f"Resultado: {signo}${ganancia_total} USDT")
    except Exception as e:
        return f"⚠️ Error cerrando {symbol}: {e}"

def obtener_disparos():
    import urllib.request, urllib.parse, json as _json

    QUINTETO = [
        ("BTCUSDT", "BTC"), ("ETHUSDT", "ETH"), ("SOLUSDT", "SOL"),
        ("BNBUSDT", "BNB"), ("AVAXUSDT", "AVAX"),
    ]
    RSI_MIN = 45; RSI_MAX = 55
    EMA_CORTA = 20; EMA_LARGA = 50
    DIFF_EMA_MAX = 2.0
    VENTANA_FASE = 30; UMBRAL_FASE = 2.5

    def fetch_velas(symbol):
        try:
            params = urllib.parse.urlencode({"symbol": symbol, "interval": "4h", "limit": 210})
            url = f"https://api.binance.com/api/v3/klines?{params}"
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = _json.loads(resp.read().decode())
            return [float(k[4]) for k in data]
        except:
            return []

    def calcular_rsi(cierres, periodo=14):
        if len(cierres) < periodo + 1: return None
        g = [max(cierres[i]-cierres[i-1], 0) for i in range(1, periodo+1)]
        p = [max(cierres[i-1]-cierres[i], 0) for i in range(1, periodo+1)]
        ag = sum(g)/periodo; ap = sum(p)/periodo
        if ap == 0: return 100.0
        return round(100 - (100/(1+ag/ap)), 2)

    def calcular_ema(cierres, periodo):
        if len(cierres) < periodo: return None
        k = 2/(periodo+1)
        ema = sum(cierres[:periodo])/periodo
        for p in cierres[periodo:]:
            ema = p*k + ema*(1-k)
        return round(ema, 2)

    def detectar_fase(cierres):
        if len(cierres) < VENTANA_FASE: return "?"
        cambio = ((cierres[-1]-cierres[-VENTANA_FASE])/cierres[-VENTANA_FASE])*100
        if cambio > UMBRAL_FASE: return "ALCISTA"
        elif cambio < -UMBRAL_FASE: return "BAJISTA"
        return "LATERAL"

    def barra(pct, largo=10):
        pct = max(0, min(100, pct))
        llenos = int(pct / 100 * largo)
        return "█" * llenos + "░" * (largo - llenos)

    def pct_rsi(rsi):
        if rsi is None: return 0
        if RSI_MIN <= rsi <= RSI_MAX: return 100
        if rsi < RSI_MIN:
            return max(0, round(100 - ((RSI_MIN - rsi) / RSI_MIN * 100), 1))
        return max(0, round(100 - ((rsi - RSI_MAX) / (100-RSI_MAX) * 100), 1))

    def pct_ema(diff):
        if diff is None: return 0
        if diff >= DIFF_EMA_MAX: return max(0, round(100 - ((diff - DIFF_EMA_MAX) / DIFF_EMA_MAX * 100), 1))
        return round((1 - diff / DIFF_EMA_MAX) * 100, 1)

    lineas = ["🎯 <b>DISPAROS</b>\n"]

    for symbol, nombre in QUINTETO:
        cierres = fetch_velas(symbol)
        if not cierres:
            lineas.append(f"⚖️ <b>{nombre}</b>\n❌ Sin datos\n──────────────")
            continue

        precio   = cierres[-1]
        rsi      = calcular_rsi(cierres[-15:])
        ema_c    = calcular_ema(cierres, EMA_CORTA)
        ema_l    = calcular_ema(cierres, EMA_LARGA)
        fase     = detectar_fase(cierres)
        diff_ema = round(abs(ema_c - ema_l) / ema_l * 100, 2) if ema_c and ema_l else None

        p_rsi   = pct_rsi(rsi)
        p_ema   = pct_ema(diff_ema) if diff_ema is not None else 0
        p_fase  = 100 if fase == "LATERAL" else 0
        p_total = round(p_rsi * 0.4 + p_ema * 0.4 + p_fase * 0.2, 1)
        falta   = round(100 - p_total, 1)

        rsi_ok  = RSI_MIN <= (rsi or 0) <= RSI_MAX
        ema_ok  = (diff_ema or 999) < DIFF_EMA_MAX
        fase_ok = fase == "LATERAL"

        if rsi_ok:
            rsi_txt = f"{rsi}% ✅ +0%"
        elif rsi and rsi < RSI_MIN:
            rsi_txt = f"{rsi}% ❌ falta +{round(RSI_MIN-rsi,1)}%"
        else:
            rsi_txt = f"{rsi}% ❌ +{round((rsi or 0)-RSI_MAX,1)}% fuera"

        if ema_ok:
            ema_txt = f"{diff_ema}% ✅ falta {round(100-p_ema,1)}%"
        else:
            ema_txt = f"{diff_ema}% ❌ +{round((diff_ema or 0)-DIFF_EMA_MAX,2)}% fuera"

        todas_ok = rsi_ok and ema_ok and fase_ok
        if todas_ok and p_total >= 90:
            estado_emoji = "🟢 LISTO"
        elif p_total >= 60:
            estado_emoji = "🟡 CERCA"
        else:
            estado_emoji = "🔴 NO LISTO"

        motivos = []
        if not rsi_ok: motivos.append("RSI")
        if not ema_ok: motivos.append("EMA")
        if not fase_ok: motivos.append(f"Fase {fase}")
        motivo_txt = " + ".join(motivos) if motivos else ""

        lineas.append(
            f"⚖️ <b>{nombre}</b> ${precio}\n"
            f"RSI [{barra(p_rsi)}] {rsi_txt}\n"
            f"EMA [{barra(p_ema)}] {ema_txt}\n"
            f"🎯 [{barra(p_total)}] {p_total}% listo — falta {falta}%\n"
            f"📍 {fase} | {estado_emoji}{' — '+motivo_txt if motivo_txt else ''}\n"
            f"──────────────"
        )

    return "\n".join(lineas)

def obtener_memoria():
    import json as _json
    ruta = os.path.expanduser("~/bot-padre-v2/data/memoria_propia.json")
    try:
        with open(ruta) as f:
            mem = _json.load(f)
    except:
        return "📭 Sin memoria acumulada aún."

    lineas = ["🧠 <b>MEMORIA DEL BOT</b>\n"]
    lineas.append(f"📊 Total trades: {mem.get('total_trades', 0)}")
    lineas.append(f"🎯 WR Global: {mem.get('wr_global', 0)}%\n")
    lineas.append("📈 <b>POR MONEDA:</b>")
    for sym in ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "AVAXUSDT"]:
        wr  = mem.get(f"{sym}_wr", None)
        ops = mem.get(f"{sym}_trades", 0)
        if wr is not None:
            emoji = "✅" if wr >= 60 else "⚠️" if wr >= 50 else "🔴"
            lineas.append(f"  {emoji} {sym}: {wr}% WR ({ops} trades)")

    lineas.append("\n⏰ <b>POR HORARIO UTC:</b>")
    for h in range(0, 24, 4):
        key = f"hora_{h}_{h+4}_wr"
        if key in mem:
            emoji = "✅" if mem[key] >= 60 else "⚠️" if mem[key] >= 50 else "🔴"
            lineas.append(f"  {emoji} {h:02d}-{h+4:02d}h: {mem[key]}% WR")

    if mem.get("perdidas_ultimos_5", 0) >= 3:
        lineas.append("\n⚠️ Racha mala reciente — precaución")

    lineas.append(f"\n🕐 Actualizado: {mem.get('actualizado', 'N/A')}")
    return "\n".join(lineas)

def obtener_registros():
    ruta = os.path.expanduser("~/bot-padre-v2/auditoria.csv")
    try:
        with open(ruta) as f:
            lineas = f.readlines()
        if len(lineas) <= 1:
            return "📭 Sin registros aún."
        ops = lineas[1:][-10:]
        msg = ["📋 <b>ÚLTIMOS REGISTROS</b>\n"]
        for l in ops:
            p = l.strip().split(",")
            if len(p) >= 6:
                fecha = p[0][:10]
                sym   = p[2].replace("USDT","")
                estado= p[5]
                emoji = "✅" if estado == "TP" else "🔴" if estado == "SL" else "🎯" if estado == "TRAILING_SL" else "📂"
                msg.append(f"{emoji} {fecha} | {sym} | {estado}")
        return "\n".join(msg)
    except Exception as e:
        return f"⚠️ Error: {e}"

def obtener_estadisticas():
    ruta = os.path.expanduser("~/bot-padre-v2/auditoria.csv")
    try:
        with open(ruta) as f:
            lineas = f.readlines()
        stats = {}
        for l in lineas[1:]:
            p = l.strip().split(",")
            if len(p) >= 6 and p[5] in ("TP", "SL", "MANUAL", "TRAILING_SL"):
                sym = p[2]
                if sym not in stats:
                    stats[sym] = {"tp": 0, "sl": 0}
                if p[5] == "TP":
                    stats[sym]["tp"] += 1
                else:
                    stats[sym]["sl"] += 1
        if not stats:
            return "📭 Sin estadísticas aún."
        msg = ["📊 <b>ESTADÍSTICAS POR MONEDA</b>\n"]
        for sym, s in sorted(stats.items()):
            total = s["tp"] + s["sl"]
            wr = round((s["tp"] / total) * 100, 1) if total > 0 else 0
            emoji = "✅" if wr >= 60 else "⚠️" if wr >= 50 else "🔴"
            msg.append(f"{emoji} {sym.replace('USDT','')}: {wr}% WR ({s['tp']}✅ {s['sl']}🔴 / {total} ops)")
        return "\n".join(msg)
    except Exception as e:
        return f"⚠️ Error: {e}"

def procesar_comando(mensaje, chat_id):
    if chat_id not in ADMIN_IDS:
        enviar_mensaje(chat_id, "⛔ No autorizado.")
        return

    if mensaje == "/start" or mensaje == "/ping":
        enviar_mensaje(chat_id, "🟢 Z-Bot V2 activo y respondiendo.")

    elif mensaje == "/status":
        enviar_mensaje(chat_id, "🟢 Sistema operativo.")

    elif mensaje == "/capital":
        capital = obtener_capital_real()
        enviar_mensaje(chat_id, f"💰 Capital actual: ${capital} USDT")

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

    elif mensaje == "/disparos":
        enviar_mensaje(chat_id, obtener_disparos())

    elif mensaje.startswith("/salir"):
        partes = mensaje.split()
        if len(partes) < 2:
            enviar_mensaje(chat_id, "⚠️ Uso: /salir BTCUSDT")
        else:
            resultado = cerrar_operacion_manual(partes[1].upper())
            enviar_mensaje(chat_id, resultado)

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
                    t = threading.Thread(
                        target=_monitor_precio,
                        args=(symbol, precio_entrada, chat_id),
                        daemon=True
                    )
                    _monitores_activos[symbol] = t
                    t.start()
            except ValueError:
                enviar_mensaje(chat_id, "⚠️ Precio inválido. Ejemplo: /alertar BNBUSDT 603.3")

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
        tipo = partes[1] if len(partes) > 1 else "eventos"
        emoji, inicial, nombre, contenido = obtener_bitacora(tipo)
        enviar_mensaje(chat_id, f"{emoji} <b>Bitácora {inicial} - {nombre}</b>\n\n{contenido}")

    elif mensaje == "/ayuda":
        ayuda = (
            "📋 <b>Comandos disponibles:</b>\n\n"
            "/status - Estado del sistema\n"
            "/capital - Capital actual\n"
            "/senales - Señales recientes\n"
            "/corecro - Ultimo reporte CoreCro\n"
            "/resumen - Mi resumen personal\n"
            "/operaciones - Trades abiertos (ganando/perdiendo)\n"
            "/disparos - Estado de cada moneda hacia el disparo\n"
            "/salir SYMBOL - Cerrar trade manualmente\n"
            "/alertar SYMBOL PRECIO - Vigilar precio cada 7 puntos\n"
            "/cancelar SYMBOL - Detener monitor de precio\n"
            "/memoria - Lo que el bot aprendió\n"
            "/registros - Últimas operaciones\n"
            "/estadisticas - WR por moneda\n"
            "/bitacora - 🟢 Bitácora E - EVENTOS\n"
            "/bitacora corecro - 🔵 Bitácora C - CORECRO\n"
            "/bitacora matrix - 🟡 Bitácora M - MATRIX\n"
            "/bitacora centinela - 🔴 Bitácora C - CENTINELA\n"
            "/ping - Verificar si el sistema responde\n"
            "/ayuda - Lista de comandos"
        )
        enviar_mensaje(chat_id, ayuda)

def escuchar():
    print("[TELEGRAM] Escuchando comandos...")
    offset = None
    while True:
        updates = obtener_updates(offset)
        for update in updates:
            offset = update["update_id"] + 1
            if "callback_query" in update:
                cb = update["callback_query"]
                cb_id = cb["id"]
                cb_data = cb.get("data", "")
                cb_chat = cb["message"]["chat"]["id"]
                if cb_chat in ADMIN_IDS:
                    if cb_data.startswith("salir_"):
                        symbol = cb_data.replace("salir_", "")
                        responder_callback(cb_id, f"Cerrando {symbol}...")
                        resultado = cerrar_operacion_manual(symbol)
                        enviar_mensaje(cb_chat, resultado)
                continue
            msg_obj = update.get("message", {})
            texto = msg_obj.get("text", "")
            chat_id = msg_obj.get("chat", {}).get("id")
            if texto and chat_id:
                procesar_comando(texto, chat_id)

if __name__ == "__main__":
    escuchar()
#!/usr/bin/env python3
"""
supervisor_v2.py — Supervisor completo Z-Bot V2
"""

import os
import json
import subprocess
import requests
from datetime import datetime
from pathlib import Path
from dotenv import dotenv_values

BOT_DIR      = "/home/ariel/bot-padre-v2"
LOG_FILE     = "/home/ariel/bot-padre-v2/eventos.log"
KEYS_FILE    = f"{BOT_DIR}/keys.env"
MONEDAS      = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "AVAXUSDT"]
MAX_SILENCIO = 15

ADMIN_YAYO   = 6578945006
ADMIN_SOCIA  = 6533031969
ADMIN_IDS    = [ADMIN_YAYO, ADMIN_SOCIA]

def cargar_token():
    config = dotenv_values(KEYS_FILE)
    return (config.get("TELEGRAM_TOKEN") or "").strip()

def enviar_alerta(mensaje):
    token = cargar_token()
    if not token:
        print("⚠️  Sin TELEGRAM_TOKEN en keys.env")
        return
    for admin_id in ADMIN_IDS:
        try:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            requests.post(url, json={
                "chat_id": admin_id,
                "text": mensaje,
                "parse_mode": "HTML"
            }, timeout=10)
        except Exception as e:
            print(f"Error enviando Telegram a {admin_id}: {e}")

def check_proceso_vivo():
    r = subprocess.run(["pgrep", "-f", "v2_main"],
                       capture_output=True, text=True)
    return r.returncode == 0

def check_screen_viva():
    r = subprocess.run(["screen", "-list"], capture_output=True, text=True)
    return "v2_main" in r.stdout

def check_silencio_log():
    path = Path(LOG_FILE)
    if not path.exists():
        return 9999
    mtime = path.stat().st_mtime
    return int((datetime.now().timestamp() - mtime) / 60)

def check_posiciones_abiertas():
    candidatos = [
        f"{BOT_DIR}/tesoro/billetera.json",
        f"{BOT_DIR}/billetera.json",
        f"{BOT_DIR}/data/billetera.json",
    ]
    for ruta in candidatos:
        if os.path.exists(ruta):
            try:
                with open(ruta) as f:
                    data = json.load(f)
                abiertas = []
                for moneda, info in data.items():
                    if isinstance(info, dict):
                        pos = info.get("posiciones", [])
                        if pos:
                            abiertas.append((moneda, len(pos)))
                return abiertas
            except Exception as e:
                return [("ERROR_LEYENDO_BILLETERA", str(e))]
    return []

def check_errores_log(lineas=300):
    if not Path(LOG_FILE).exists():
        return []
    try:
        r = subprocess.run(["tail", "-n", str(lineas), LOG_FILE],
                           capture_output=True, text=True)
        keywords = [
            "ERROR", "Exception", "Traceback", "SyntaxError",
            "NameError", "KeyError", "AttributeError", "IndexError",
            "ConnectionError", "TimeoutError", "JSONDecodeError",
            "ZeroDivisionError", "TypeError", "ValueError"
        ]
        encontrados = []
        vistos = set()
        for linea in r.stdout.splitlines():
            for kw in keywords:
                if kw in linea:
                    corta = linea.strip()[:120]
                    if corta not in vistos:
                        vistos.add(corta)
                        encontrados.append(corta)
                    break
        return encontrados[-5:]
    except:
        return []

def check_actividad_monedas():
    if not Path(LOG_FILE).exists():
        return {m: False for m in MONEDAS}
    try:
        r = subprocess.run(["tail", "-n", "600", LOG_FILE],
                           capture_output=True, text=True)
        lineas = r.stdout.splitlines()
        actividad = {m: False for m in MONEDAS}
        for linea in lineas:
            for moneda in MONEDAS:
                simbolo = moneda.replace("USDT", "")
                if simbolo in linea or moneda in linea:
                    actividad[moneda] = True
        return actividad
    except:
        return {m: False for m in MONEDAS}

def supervisar():
    ahora    = datetime.now().strftime("%d/%m/%Y %H:%M")
    criticos = []
    alertas  = []

    if not check_proceso_vivo():
        criticos.append("🔴 <b>PROCESO MUERTO:</b> main.py de V2 no está corriendo")

    if not check_screen_viva():
        criticos.append("🔴 <b>SCREEN MUERTA:</b> La sesión v2_main no existe")

    silencio = check_silencio_log()
    if silencio >= MAX_SILENCIO:
        criticos.append(f"🔴 <b>LOG CONGELADO:</b> Sin actividad hace <b>{silencio} minutos</b>")

    posiciones = check_posiciones_abiertas()
    if posiciones and silencio >= MAX_SILENCIO:
        for moneda, cant in posiciones:
            criticos.append(
                f"🚨 <b>PELIGRO:</b> {moneda} tiene {cant} posición(es) abierta(s) "
                f"y el bot lleva {silencio} min sin vigilar"
            )

    errores = check_errores_log()
    if errores:
        alertas.append("⚠️ <b>ERRORES EN LOG:</b>")
        for err in errores:
            alertas.append(f"  <code>{err}</code>")

    actividad = check_actividad_monedas()
    dormidas = [m for m, activa in actividad.items() if not activa]
    if dormidas:
        alertas.append(f"😴 <b>SIN ACTIVIDAD:</b> {', '.join(dormidas)}")

    if not criticos and not alertas:
        return

    msg = [f"🤖 <b>SUPERVISOR Z-BOT V2</b>", f"🕐 {ahora}", ""]

    if criticos:
        msg.append("━━━ 🚨 CRÍTICO ━━━")
        msg.extend(criticos)
        msg.append("")

    if alertas:
        msg.append("━━━ ⚠️ ALERTAS ━━━")
        msg.extend(alertas)
        msg.append("")

    msg.append("🔧 Revisar: <code>screen -r v2_main</code>")

    texto = "\n".join(msg)
    enviar_alerta(texto)
    print(texto)

if __name__ == "__main__":
    supervisar()
# =========================================
# brain/telegram_engine.py - Comunicador Actualizado
# Rol: Envia alertas y responde comandos.
# UNIFICADO: Capital real en todos los reportes.
# =========================================

import urllib.request
import urllib.parse
import json
import os
import threading
import time
from datetime import datetime

# --- Administradores ---
ADMIN_YAYO = 6578945006
ADMIN_SOCIA = 6533031969
ADMIN_IDS = [ADMIN_YAYO, ADMIN_SOCIA]

BITACORAS = {
    "EVENTOS":   ("🟢", "E", "Eventos",   "~/bot-padre-v2/memoria/eventos.log"),
    "CENTINELA": ("🔴", "C", "Centinela", "~/bot-padre-v2/memoria/centinela.log"),
    "CORECRO":   ("🔵", "C", "Corecro",   "~/bot-padre-v2/memoria/corecro.log"),
    "MATRIX":    ("🟡", "M", "Matrix",    "~/bot-padre-v2/memoria/matrix.log"),
}

# ─── MONITOR DE PRECIOS ───────────────────────────────────────────────────────
_monitores_activos = {}
_monitores_stop    = {}

def _monitor_precio(symbol, precio_entrada, chat_id, intervalo_puntos=7):
    ultimo_nivel  = precio_entrada
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
            url = f"https://api.telegram.org/bot{cargar_token()}"
            url2 = f"https://api.binance.com/api/v3/klines?{params}"
            with urllib.request.urlopen(url2, timeout=10) as resp:
                data = json.loads(resp.read().decode())
            precio_actual = float(data[-1][4])
            ganancia = round(precio_actual - precio_entrada, 2)
            signo = "+" if ganancia >= 0 else ""
            pct = round(((precio_actual - precio_entrada) / precio_entrada) * 100, 2)

            # Subida de N puntos
            if precio_actual >= ultimo_nivel + intervalo_puntos:
                enviar_mensaje(chat_id,
                    f"📈 <b>{symbol} SUBIÓ</b>\n"
                    f"💰 Entrada:  ${precio_entrada}\n"
                    f"📍 Ahora:    ${round(precio_actual, 2)}\n"
                    f"🚀 Ganancia: {signo}${ganancia} ({signo}{pct}%)\n"
                    f"⚡ ¿Salir o dejar correr?"
                )
                ultimo_nivel  = precio_actual
                enviado_reverso = False

            # Reverso al precio de entrada
            elif precio_actual <= precio_entrada and not enviado_reverso:
                enviar_mensaje(chat_id,
                    f"⚠️ <b>{symbol} REVERSO</b>\n"
                    f"💰 Entrada:  ${precio_entrada}\n"
                    f"📍 Ahora:    ${round(precio_actual, 2)}\n"
                    f"📉 Resultado: ${ganancia} ({pct}%)\n"
                    f"🛑 Considera salir manualmente"
                )
                enviado_reverso = True

            # Si recupera, resetea el flag
            elif precio_actual > precio_entrada + 2:
                enviado_reverso = False

        except Exception as e:
            print(f"[MONITOR] Error {symbol}: {e}")

        time.sleep(30)

    enviar_mensaje(chat_id, f"❌ <b>Monitor {symbol} cancelado.</b>")
    _monitores_activos.pop(symbol, None)
    _monitores_stop.pop(symbol, None)
# ─────────────────────────────────────────────────────────────────────────────

def cargar_token():
    ruta = os.path.expanduser("~/bot-padre-v2/keys.env")
    try:
        with open(ruta, "r") as f:
            for linea in f:
                if linea.startswith("TELEGRAM_TOKEN="):
                    return linea.strip().split("=", 1)[1]
    except:
        return None

TOKEN = cargar_token()
API_URL = f"https://api.telegram.org/bot{TOKEN}"

def enviar_mensaje(chat_id, mensaje):
    if not TOKEN:
        print("[TELEGRAM] Token no encontrado.")
        return
    params = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": mensaje,
        "parse_mode": "HTML"
    })
    url = f"{API_URL}/sendMessage?{params}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"[TELEGRAM] Error: {e}")

def enviar_aviso(mensaje):
    for admin_id in ADMIN_IDS:
        enviar_mensaje(admin_id, mensaje)

def obtener_updates(offset=None):
    params = {"timeout": 10, "allowed_updates": ["message", "callback_query"]}
    if offset:
        params["offset"] = offset
    url = f"{API_URL}/getUpdates?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            return data.get("result", [])
    except Exception as e:
        print(f"[TELEGRAM] Error updates: {e}")
        return []

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

def obtener_capital_real():
    ruta = os.path.expanduser("~/bot-padre-v2/signals/billetera.json")
    capital_inicial = 1000.0
    try:
        with open(ruta, "r") as f:
            datos = json.load(f)
            return float(datos.get("USDT", capital_inicial))
    except:
        return capital_inicial

def obtener_bitacora(tipo="eventos", cantidad=10):
    tipo = tipo.upper()
    if tipo not in BITACORAS:
        tipo = "eventos"
    emoji, inicial, nombre, ruta_rel = BITACORAS[tipo]
    ruta = os.path.expanduser(ruta_rel)
    try:
        with open(ruta, "r") as f:
            lineas = f.readlines()
        contenido = "".join(lineas[-cantidad:]) if lineas else "Sin registros aun."
        return emoji, inicial, nombre, contenido
    except:
        return emoji, inicial, nombre, "Sin registros aun."

def obtener_resumen_personal():
    import urllib.request, urllib.parse, json as _json
    ruta_billetera = os.path.expanduser("~/bot-padre-v2/signals/billetera.json")
    ruta_auditoria = os.path.expanduser("~/bot-padre-v2/auditoria.csv")
    capital_inicial = 1000.0

    try:
        with open(ruta_billetera) as f:
            bill = _json.load(f)
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
                url = f"https://api.binance.com/api/v3/klines?{params}"
                with urllib.request.urlopen(url, timeout=10) as resp:
                    data = _json.loads(resp.read().decode())
                precio = float(data[-1][4])
                valor_monedas += cantidad * precio
            except:
                pass

    capital_actual = round(usdt + valor_monedas, 2)
    ganancia = round(capital_actual - capital_inicial, 2)
    porcentaje = round((ganancia / capital_inicial) * 100, 2)
    signo = "+" if ganancia >= 0 else ""

    total = tp = sl = abiertas = 0
    ultima_fecha = "Sin operaciones"

    try:
        with open(ruta_auditoria, "r") as f:
            lineas = f.readlines()[1:]
        for linea in lineas:
            p = linea.strip().split(",")
            if len(p) < 6: continue
            if p[5] == "ABIERTA": abiertas += 1
            elif p[5] == "TP":
                tp += 1; total += 1; ultima_fecha = p[0][:10]
            elif p[5] == "SL":
                sl += 1; total += 1; ultima_fecha = p[0][:10]
    except: pass

    winrate = round((tp / total * 100), 1) if total > 0 else 0.0
    emoji_ganancia = "📈" if ganancia >= 0 else "📉"

    msg = (
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 <b>Z-BOT | MI RESUMEN</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 <b>Capital inicial:</b>  ${capital_inicial:,.2f}\n"
        f"💵 <b>Capital actual:</b>   ${capital_actual:,.2f}\n"
        f"{emoji_ganancia} <b>Ganancia:</b>        {signo}${ganancia} ({signo}{porcentaje}%)\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>OPERACIONES</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📁 Total cerradas:   {total}\n"
        f"✅ Ganadas (TP):      {tp}\n"
        f"🛑 Perdidas (SL):     {sl}\n"
        f"🎯 Win Rate:          {winrate}%\n"
        f"📂 Abiertas ahora:   {abiertas}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🕐 Última operación: {ultima_fecha}\n"
        f"⚡ Estado:            🟢 ACTIVO\n"
        f"━━━━━━━━━━━━━━━━━━━━━"
    )
    return msg

def enviar_mensaje_con_botones(chat_id, mensaje, botones):
    if not TOKEN:
        return
    import json as _json
    keyboard = {"inline_keyboard": [[{"text": b["text"], "callback_data": b["data"]}] for b in botones]}
    data = _json.dumps({
        "chat_id": chat_id,
        "text": mensaje,
        "parse_mode": "HTML",
        "reply_markup": _json.dumps(keyboard)
    }).encode()
    req = urllib.request.Request(
        f"{API_URL}/sendMessage",
        data=data,
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return _json.loads(resp.read().decode())
    except Exception as e:
        print(f"[TELEGRAM] Error botones: {e}")

def responder_callback(callback_query_id, texto):
    params = urllib.parse.urlencode({
        "callback_query_id": callback_query_id,
        "text": texto
    })
    url = f"{API_URL}/answerCallbackQuery?{params}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            pass
    except:
        pass

def obtener_operaciones_abiertas():
    ruta_audit = os.path.expanduser("~/bot-padre-v2/auditoria.csv")
    try:
        with open(ruta_audit, "r") as f:
            lineas = f.readlines()
        abiertas = []
        for linea in lineas[1:]:
            p = linea.strip().split(",")
            if len(p) >= 6 and p[5] == "ABIERTA":
                abiertas.append({"symbol": p[2], "precio_entrada": float(p[3]), "monto": 10.0})
        if not abiertas:
            return "📭 No hay operaciones abiertas ahora mismo.", []
        import urllib.request, urllib.parse, json as _json
        TAKE_PROFIT = 6.0
        lineas_msg = ["📊 <b>OPERACIONES ABIERTAS</b>\n"]
        total_ganancia = 0.0
        botones = []
        for op in abiertas:
            sym = op["symbol"]
            entrada = op["precio_entrada"]
            monto = op["monto"]
            try:
                params = urllib.parse.urlencode({"symbol": sym, "interval": "1m", "limit": 1})
                url = f"https://api.binance.com/api/v3/klines?{params}"
                with urllib.request.urlopen(url, timeout=10) as resp:
                    data = _json.loads(resp.read().decode())
                precio_actual = float(data[-1][4])
            except:
                precio_actual = entrada
            cambio_pct = ((precio_actual - entrada) / entrada) * 100
            ganancia_usd = round((cambio_pct / 100) * monto, 3)
            total_ganancia += ganancia_usd
            busca_usd = round(monto * (1 + TAKE_PROFIT / 100), 2)
            emoji = "✅" if cambio_pct >= 0 else "🔴"
            emoji_gp = "📈" if cambio_pct >= 0 else "📉"
            signo = "+" if cambio_pct >= 0 else ""
            lineas_msg.append(f"{emoji} <b>{sym}</b>")
            lineas_msg.append(f"   Entrada:      ${entrada}")
            lineas_msg.append(f"   Ahora:        ${precio_actual}")
            lineas_msg.append(f"   {signo}{round(cambio_pct,2)}%  ({signo}${ganancia_usd} USDT)")
            lineas_msg.append(f"   💵 Invertido: ${monto} USDT")
            lineas_msg.append(f"   🎯 Busca:     ${busca_usd} USDT (+{TAKE_PROFIT}%)")
            lineas_msg.append(f"   {emoji_gp} Resultado:  {signo}${ganancia_usd} USDT\n")
            botones.append({"text": f"🚪 Salir {sym}", "data": f"salir_{sym}"})
        signo_total = "+" if total_ganancia >= 0 else ""
        lineas_msg.append(f"💰 <b>Total neto: {signo_total}${round(total_ganancia,3)} USDT</b>")
        return "\n".join(lineas_msg), botones
    except Exception as e:
        return f"⚠️ Error: {e}", []

def cerrar_operacion_manual(symbol):
    ruta_audit = os.path.expanduser("~/bot-padre-v2/auditoria.csv")
    import urllib.request, urllib.parse, json as _json
    try:
        params = urllib.parse.urlencode({"symbol": symbol, "interval": "1m", "limit": 1})
        url = f"https://api.binance.com/api/v3/klines?{params}"
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = _json.loads(resp.read().decode())
        precio_actual = float(data[-1][4])
    except:
        return f"⚠️ No pude obtener precio de {symbol}"
    try:
        with open(ruta_audit, "r") as f:
            lineas = f.readlines()
        header = lineas[0]
        nuevas = [header]
        cerradas = 0
        ganancia_total = 0.0
        for linea in lineas[1:]:
            p = linea.strip().split(",")
            if len(p) >= 6 and p[2] == symbol and p[5] == "ABIERTA":
                precio_entrada = float(p[3])
                cambio = ((precio_actual - precio_entrada) / precio_entrada) * 100
                ganancia_total += round((cambio / 100) * 10.0, 3)
                p[5] = "MANUAL"
                cerradas += 1
            nuevas.append(",".join(p) + "\n")
        with open(ruta_audit, "w") as f:
            f.writelines(nuevas)
        if cerradas == 0:
            return f"⚠️ No hay operaciones abiertas de {symbol}"
        signo = "+" if ganancia_total >= 0 else ""
        emoji = "✅" if ganancia_total >= 0 else "🔴"
        return (f"{emoji} <b>SALIDA MANUAL {symbol}</b>\n"
                f"Precio salida: ${precio_actual}\n"
                f"Ops cerradas: {cerradas}\n"
                f"Resultado: {signo}${ganancia_total} USDT")
    except Exception as e:
        return f"⚠️ Error cerrando {symbol}: {e}"

def obtener_disparos():
    import urllib.request, urllib.parse, json as _json

    QUINTETO = [
        ("BTCUSDT", "BTC"), ("ETHUSDT", "ETH"), ("SOLUSDT", "SOL"),
        ("BNBUSDT", "BNB"), ("AVAXUSDT", "AVAX"),
    ]
    RSI_MIN = 45; RSI_MAX = 55
    EMA_CORTA = 20; EMA_LARGA = 50
    DIFF_EMA_MAX = 2.0
    VENTANA_FASE = 30; UMBRAL_FASE = 2.5

    def fetch_velas(symbol):
        try:
            params = urllib.parse.urlencode({"symbol": symbol, "interval": "4h", "limit": 210})
            url = f"https://api.binance.com/api/v3/klines?{params}"
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = _json.loads(resp.read().decode())
            return [float(k[4]) for k in data]
        except:
            return []

    def calcular_rsi(cierres, periodo=14):
        if len(cierres) < periodo + 1: return None
        g = [max(cierres[i]-cierres[i-1], 0) for i in range(1, periodo+1)]
        p = [max(cierres[i-1]-cierres[i], 0) for i in range(1, periodo+1)]
        ag = sum(g)/periodo; ap = sum(p)/periodo
        if ap == 0: return 100.0
        return round(100 - (100/(1+ag/ap)), 2)

    def calcular_ema(cierres, periodo):
        if len(cierres) < periodo: return None
        k = 2/(periodo+1)
        ema = sum(cierres[:periodo])/periodo
        for p in cierres[periodo:]:
            ema = p*k + ema*(1-k)
        return round(ema, 2)

    def detectar_fase(cierres):
        if len(cierres) < VENTANA_FASE: return "?"
        cambio = ((cierres[-1]-cierres[-VENTANA_FASE])/cierres[-VENTANA_FASE])*100
        if cambio > UMBRAL_FASE: return "ALCISTA"
        elif cambio < -UMBRAL_FASE: return "BAJISTA"
        return "LATERAL"

    def barra(pct, largo=10):
        pct = max(0, min(100, pct))
        llenos = int(pct / 100 * largo)
        return "█" * llenos + "░" * (largo - llenos)

    def pct_rsi(rsi):
        if rsi is None: return 0
        if RSI_MIN <= rsi <= RSI_MAX: return 100
        if rsi < RSI_MIN:
            return max(0, round(100 - ((RSI_MIN - rsi) / RSI_MIN * 100), 1))
        return max(0, round(100 - ((rsi - RSI_MAX) / (100-RSI_MAX) * 100), 1))

    def pct_ema(diff):
        if diff is None: return 0
        if diff >= DIFF_EMA_MAX: return max(0, round(100 - ((diff - DIFF_EMA_MAX) / DIFF_EMA_MAX * 100), 1))
        return round((1 - diff / DIFF_EMA_MAX) * 100, 1)

    lineas = ["🎯 <b>DISPAROS</b>\n"]

    for symbol, nombre in QUINTETO:
        cierres = fetch_velas(symbol)
        if not cierres:
            lineas.append(f"⚖️ <b>{nombre}</b>\n❌ Sin datos\n──────────────")
            continue

        precio   = cierres[-1]
        rsi      = calcular_rsi(cierres[-15:])
        ema_c    = calcular_ema(cierres, EMA_CORTA)
        ema_l    = calcular_ema(cierres, EMA_LARGA)
        fase     = detectar_fase(cierres)
        diff_ema = round(abs(ema_c - ema_l) / ema_l * 100, 2) if ema_c and ema_l else None

        p_rsi   = pct_rsi(rsi)
        p_ema   = pct_ema(diff_ema) if diff_ema is not None else 0
        p_fase  = 100 if fase == "LATERAL" else 0
        p_total = round(p_rsi * 0.4 + p_ema * 0.4 + p_fase * 0.2, 1)
        falta   = round(100 - p_total, 1)

        rsi_ok  = RSI_MIN <= (rsi or 0) <= RSI_MAX
        ema_ok  = (diff_ema or 999) < DIFF_EMA_MAX
        fase_ok = fase == "LATERAL"

        if rsi_ok:
            rsi_txt = f"{rsi}% ✅ +0%"
        elif rsi and rsi < RSI_MIN:
            rsi_txt = f"{rsi}% ❌ falta +{round(RSI_MIN-rsi,1)}%"
        else:
            rsi_txt = f"{rsi}% ❌ +{round((rsi or 0)-RSI_MAX,1)}% fuera"

        if ema_ok:
            ema_txt = f"{diff_ema}% ✅ falta {round(100-p_ema,1)}%"
        else:
            ema_txt = f"{diff_ema}% ❌ +{round((diff_ema or 0)-DIFF_EMA_MAX,2)}% fuera"

        todas_ok = rsi_ok and ema_ok and fase_ok
        if todas_ok and p_total >= 90:
            estado_emoji = "🟢 LISTO"
        elif p_total >= 60:
            estado_emoji = "🟡 CERCA"
        else:
            estado_emoji = "🔴 NO LISTO"

        motivos = []
        if not rsi_ok: motivos.append("RSI")
        if not ema_ok: motivos.append("EMA")
        if not fase_ok: motivos.append(f"Fase {fase}")
        motivo_txt = " + ".join(motivos) if motivos else ""

        lineas.append(
            f"⚖️ <b>{nombre}</b> ${precio}\n"
            f"RSI [{barra(p_rsi)}] {rsi_txt}\n"
            f"EMA [{barra(p_ema)}] {ema_txt}\n"
            f"🎯 [{barra(p_total)}] {p_total}% listo — falta {falta}%\n"
            f"📍 {fase} | {estado_emoji}{' — '+motivo_txt if motivo_txt else ''}\n"
            f"──────────────"
        )

    return "\n".join(lineas)

def obtener_memoria():
    import json as _json
    ruta = os.path.expanduser("~/bot-padre-v2/data/memoria_propia.json")
    try:
        with open(ruta) as f:
            mem = _json.load(f)
    except:
        return "📭 Sin memoria acumulada aún."

    lineas = ["🧠 <b>MEMORIA DEL BOT</b>\n"]
    lineas.append(f"📊 Total trades: {mem.get('total_trades', 0)}")
    lineas.append(f"🎯 WR Global: {mem.get('wr_global', 0)}%\n")
    lineas.append("📈 <b>POR MONEDA:</b>")
    for sym in ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "AVAXUSDT"]:
        wr  = mem.get(f"{sym}_wr", None)
        ops = mem.get(f"{sym}_trades", 0)
        if wr is not None:
            emoji = "✅" if wr >= 60 else "⚠️" if wr >= 50 else "🔴"
            lineas.append(f"  {emoji} {sym}: {wr}% WR ({ops} trades)")

    lineas.append("\n⏰ <b>POR HORARIO UTC:</b>")
    for h in range(0, 24, 4):
        key = f"hora_{h}_{h+4}_wr"
        if key in mem:
            emoji = "✅" if mem[key] >= 60 else "⚠️" if mem[key] >= 50 else "🔴"
            lineas.append(f"  {emoji} {h:02d}-{h+4:02d}h: {mem[key]}% WR")

    if mem.get("perdidas_ultimos_5", 0) >= 3:
        lineas.append("\n⚠️ Racha mala reciente — precaución")

    lineas.append(f"\n🕐 Actualizado: {mem.get('actualizado', 'N/A')}")
    return "\n".join(lineas)

def obtener_registros():
    ruta = os.path.expanduser("~/bot-padre-v2/auditoria.csv")
    try:
        with open(ruta) as f:
            lineas = f.readlines()
        if len(lineas) <= 1:
            return "📭 Sin registros aún."
        ops = lineas[1:][-10:]
        msg = ["📋 <b>ÚLTIMOS REGISTROS</b>\n"]
        for l in ops:
            p = l.strip().split(",")
            if len(p) >= 6:
                fecha = p[0][:10]
                sym   = p[2].replace("USDT","")
                estado= p[5]
                emoji = "✅" if estado == "TP" else "🔴" if estado == "SL" else "🎯" if estado == "TRAILING_SL" else "📂"
                msg.append(f"{emoji} {fecha} | {sym} | {estado}")
        return "\n".join(msg)
    except Exception as e:
        return f"⚠️ Error: {e}"

def obtener_estadisticas():
    ruta = os.path.expanduser("~/bot-padre-v2/auditoria.csv")
    try:
        with open(ruta) as f:
            lineas = f.readlines()
        stats = {}
        for l in lineas[1:]:
            p = l.strip().split(",")
            if len(p) >= 6 and p[5] in ("TP", "SL", "MANUAL", "TRAILING_SL"):
                sym = p[2]
                if sym not in stats:
                    stats[sym] = {"tp": 0, "sl": 0}
                if p[5] == "TP":
                    stats[sym]["tp"] += 1
                else:
                    stats[sym]["sl"] += 1
        if not stats:
            return "📭 Sin estadísticas aún."
        msg = ["📊 <b>ESTADÍSTICAS POR MONEDA</b>\n"]
        for sym, s in sorted(stats.items()):
            total = s["tp"] + s["sl"]
            wr = round((s["tp"] / total) * 100, 1) if total > 0 else 0
            emoji = "✅" if wr >= 60 else "⚠️" if wr >= 50 else "🔴"
            msg.append(f"{emoji} {sym.replace('USDT','')}: {wr}% WR ({s['tp']}✅ {s['sl']}🔴 / {total} ops)")
        return "\n".join(msg)
    except Exception as e:
        return f"⚠️ Error: {e}"

def procesar_comando(mensaje, chat_id):
    if chat_id not in ADMIN_IDS:
        enviar_mensaje(chat_id, "⛔ No autorizado.")
        return

    if mensaje == "/start" or mensaje == "/ping":
        enviar_mensaje(chat_id, "🟢 Z-Bot V2 activo y respondiendo.")

    elif mensaje == "/status":
        enviar_mensaje(chat_id, "🟢 Sistema operativo.")

    elif mensaje == "/capital":
        capital = obtener_capital_real()
        enviar_mensaje(chat_id, f"💰 Capital actual: ${capital} USDT")

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

    elif mensaje == "/disparos":
        enviar_mensaje(chat_id, obtener_disparos())

    elif mensaje.startswith("/salir"):
        partes = mensaje.split()
        if len(partes) < 2:
            enviar_mensaje(chat_id, "⚠️ Uso: /salir BTCUSDT")
        else:
            resultado = cerrar_operacion_manual(partes[1].upper())
            enviar_mensaje(chat_id, resultado)

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
                    t = threading.Thread(
                        target=_monitor_precio,
                        args=(symbol, precio_entrada, chat_id),
                        daemon=True
                    )
                    _monitores_activos[symbol] = t
                    t.start()
            except ValueError:
                enviar_mensaje(chat_id, "⚠️ Precio inválido. Ejemplo: /alertar BNBUSDT 603.3")

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
        tipo = partes[1] if len(partes) > 1 else "eventos"
        emoji, inicial, nombre, contenido = obtener_bitacora(tipo)
        enviar_mensaje(chat_id, f"{emoji} <b>Bitácora {inicial} - {nombre}</b>\n\n{contenido}")

    elif mensaje == "/ayuda":
        ayuda = (
            "📋 <b>Comandos disponibles:</b>\n\n"
            "/status - Estado del sistema\n"
            "/capital - Capital actual\n"
            "/senales - Señales recientes\n"
            "/corecro - Ultimo reporte CoreCro\n"
            "/resumen - Mi resumen personal\n"
            "/operaciones - Trades abiertos (ganando/perdiendo)\n"
            "/disparos - Estado de cada moneda hacia el disparo\n"
            "/salir SYMBOL - Cerrar trade manualmente\n"
            "/alertar SYMBOL PRECIO - Vigilar precio cada 7 puntos\n"
            "/cancelar SYMBOL - Detener monitor de precio\n"
            "/memoria - Lo que el bot aprendió\n"
            "/registros - Últimas operaciones\n"
            "/estadisticas - WR por moneda\n"
            "/bitacora - 🟢 Bitácora E - EVENTOS\n"
            "/bitacora corecro - 🔵 Bitácora C - CORECRO\n"
            "/bitacora matrix - 🟡 Bitácora M - MATRIX\n"
            "/bitacora centinela - 🔴 Bitácora C - CENTINELA\n"
            "/ping - Verificar si el sistema responde\n"
            "/ayuda - Lista de comandos"
        )
        enviar_mensaje(chat_id, ayuda)

def escuchar():
    print("[TELEGRAM] Escuchando comandos...")
    offset = None
    while True:
        updates = obtener_updates(offset)
        for update in updates:
            offset = update["update_id"] + 1
            if "callback_query" in update:
                cb = update["callback_query"]
                cb_id = cb["id"]
                cb_data = cb.get("data", "")
                cb_chat = cb["message"]["chat"]["id"]
                if cb_chat in ADMIN_IDS:
                    if cb_data.startswith("salir_"):
                        symbol = cb_data.replace("salir_", "")
                        responder_callback(cb_id, f"Cerrando {symbol}...")
                        resultado = cerrar_operacion_manual(symbol)
                        enviar_mensaje(cb_chat, resultado)
                continue
            msg_obj = update.get("message", {})
            texto = msg_obj.get("text", "")
            chat_id = msg_obj.get("chat", {}).get("id")
            if texto and chat_id:
                procesar_comando(texto, chat_id)

if __name__ == "__main__":
    escuchar()
#!/usr/bin/env python3
"""
supervisor_v2.py — Supervisor completo Z-Bot V2
"""

import os
import json
import subprocess
import requests
from datetime import datetime
from pathlib import Path
from dotenv import dotenv_values

BOT_DIR      = "/home/ariel/bot-padre-v2"
LOG_FILE     = "/home/ariel/bot-padre-v2/eventos.log"
KEYS_FILE    = f"{BOT_DIR}/keys.env"
MONEDAS      = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "AVAXUSDT"]
MAX_SILENCIO = 15

ADMIN_YAYO   = 6578945006
ADMIN_SOCIA  = 6533031969
ADMIN_IDS    = [ADMIN_YAYO, ADMIN_SOCIA]

def cargar_token():
    config = dotenv_values(KEYS_FILE)
    return (config.get("TELEGRAM_TOKEN") or "").strip()

def enviar_alerta(mensaje):
    token = cargar_token()
    if not token:
        print("⚠️  Sin TELEGRAM_TOKEN en keys.env")
        return
    for admin_id in ADMIN_IDS:
        try:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            requests.post(url, json={
                "chat_id": admin_id,
                "text": mensaje,
                "parse_mode": "HTML"
            }, timeout=10)
        except Exception as e:
            print(f"Error enviando Telegram a {admin_id}: {e}")

def check_proceso_vivo():
    r = subprocess.run(["pgrep", "-f", "v2_main"],
                       capture_output=True, text=True)
    return r.returncode == 0

def check_screen_viva():
    r = subprocess.run(["screen", "-list"], capture_output=True, text=True)
    return "v2_main" in r.stdout

def check_silencio_log():
    path = Path(LOG_FILE)
    if not path.exists():
        return 9999
    mtime = path.stat().st_mtime
    return int((datetime.now().timestamp() - mtime) / 60)

def check_posiciones_abiertas():
    candidatos = [
        f"{BOT_DIR}/tesoro/billetera.json",
        f"{BOT_DIR}/billetera.json",
        f"{BOT_DIR}/data/billetera.json",
    ]
    for ruta in candidatos:
        if os.path.exists(ruta):
            try:
                with open(ruta) as f:
                    data = json.load(f)
                abiertas = []
                for moneda, info in data.items():
                    if isinstance(info, dict):
                        pos = info.get("posiciones", [])
                        if pos:
                            abiertas.append((moneda, len(pos)))
                return abiertas
            except Exception as e:
                return [("ERROR_LEYENDO_BILLETERA", str(e))]
    return []

def check_errores_log(lineas=300):
    if not Path(LOG_FILE).exists():
        return []
    try:
        r = subprocess.run(["tail", "-n", str(lineas), LOG_FILE],
                           capture_output=True, text=True)
        keywords = [
            "ERROR", "Exception", "Traceback", "SyntaxError",
            "NameError", "KeyError", "AttributeError", "IndexError",
            "ConnectionError", "TimeoutError", "JSONDecodeError",
            "ZeroDivisionError", "TypeError", "ValueError"
        ]
        encontrados = []
        vistos = set()
        for linea in r.stdout.splitlines():
            for kw in keywords:
                if kw in linea:
                    corta = linea.strip()[:120]
                    if corta not in vistos:
                        vistos.add(corta)
                        encontrados.append(corta)
                    break
        return encontrados[-5:]
    except:
        return []

def check_actividad_monedas():
    if not Path(LOG_FILE).exists():
        return {m: False for m in MONEDAS}
    try:
        r = subprocess.run(["tail", "-n", "600", LOG_FILE],
                           capture_output=True, text=True)
        lineas = r.stdout.splitlines()
        actividad = {m: False for m in MONEDAS}
        for linea in lineas:
            for moneda in MONEDAS:
                simbolo = moneda.replace("USDT", "")
                if simbolo in linea or moneda in linea:
                    actividad[moneda] = True
        return actividad
    except:
        return {m: False for m in MONEDAS}

def supervisar():
    ahora    = datetime.now().strftime("%d/%m/%Y %H:%M")
    criticos = []
    alertas  = []

    if not check_proceso_vivo():
        criticos.append("🔴 <b>PROCESO MUERTO:</b> main.py de V2 no está corriendo")

    if not check_screen_viva():
        criticos.append("🔴 <b>SCREEN MUERTA:</b> La sesión v2_main no existe")

    silencio = check_silencio_log()
    if silencio >= MAX_SILENCIO:
        criticos.append(f"🔴 <b>LOG CONGELADO:</b> Sin actividad hace <b>{silencio} minutos</b>")

    posiciones = check_posiciones_abiertas()
    if posiciones and silencio >= MAX_SILENCIO:
        for moneda, cant in posiciones:
            criticos.append(
                f"🚨 <b>PELIGRO:</b> {moneda} tiene {cant} posición(es) abierta(s) "
                f"y el bot lleva {silencio} min sin vigilar"
            )

    errores = check_errores_log()
    if errores:
        alertas.append("⚠️ <b>ERRORES EN LOG:</b>")
        for err in errores:
            alertas.append(f"  <code>{err}</code>")

    actividad = check_actividad_monedas()
    dormidas = [m for m, activa in actividad.items() if not activa]
    if dormidas:
        alertas.append(f"😴 <b>SIN ACTIVIDAD:</b> {', '.join(dormidas)}")

    if not criticos and not alertas:
        return

    msg = [f"🤖 <b>SUPERVISOR Z-BOT V2</b>", f"🕐 {ahora}", ""]

    if criticos:
        msg.append("━━━ 🚨 CRÍTICO ━━━")
        msg.extend(criticos)
        msg.append("")

    if alertas:
        msg.append("━━━ ⚠️ ALERTAS ━━━")
        msg.extend(alertas)
        msg.append("")

    msg.append("🔧 Revisar: <code>screen -r v2_main</code>")

    texto = "\n".join(msg)
    enviar_alerta(texto)
    print(texto)

if __name__ == "__main__":
    supervisar()
