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
import db

BILLETERA = os.path.expanduser("~/bot-padre-v2/signals/billetera.json")

DRAWDOWN_MAXIMO_PCT      = 0.10
PERDIDA_DIARIA_MAXIMA_PCT = 0.05

MONEDAS_PRECIO = {
    "BTC": "BTCUSDT",
    "ETH": "ETHUSDT",
    "SOL": "SOLUSDT",
    "BNB": "BNBUSDT",
    "AVAX": "AVAXUSDT"
}

class DatosIncompletos(RuntimeError):
    """
    No se pudo calcular el capital con certeza (falta algun precio).
    Es RuntimeError a proposito: esta_bloqueado() ya lo captura y pausa el
    ciclo. Lo importante es que NUNCA se persiste bloqueo por esta causa.
    """

def _obtener_precio(symbol):
    """Devuelve None si no se pudo obtener. NUNCA 0.0: valorizar en cero una
    moneda con saldo hunde el capital y dispara un drawdown que no existe."""
    try:
        params = urllib.parse.urlencode({"symbol": symbol, "interval": "1m", "limit": 1})
        url    = f"https://api.binance.com/api/v3/klines?{params}"
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode())
        return float(data[-1][4])
    except Exception as e:
        print(f"[GUARDIAN] Error precio {symbol}: {e}")
        return None

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
    sin_precio    = []

    for moneda, symbol in MONEDAS_PRECIO.items():
        cantidad = float(data.get(moneda, 0))
        if cantidad > 0:
            precio = _obtener_precio(symbol)
            if precio is None:
                sin_precio.append(moneda)
                continue
            valor_monedas += cantidad * precio

    if sin_precio:
        # Preferimos no evaluar el riesgo antes que evaluarlo con la cripto
        # valorizada en cero. El llamador pausa el ciclo, sin persistir nada.
        raise DatosIncompletos(
            f"[GUARDIAN] Sin precio para {', '.join(sin_precio)} — "
            f"no se evalua el riesgo este ciclo (no se bloquea de forma permanente)."
        )

    return round(usdt + valor_monedas, 2)

def cargar_estado_riesgo(capital_actual):
    data = db.json_get("estado_riesgo")
    if data is not None:
        return data
    return {
        "capital_maximo_historico": capital_actual,
        "capital_inicio_dia":       capital_actual,
        "fecha":                    datetime.now().strftime("%Y-%m-%d"),
        "bloqueado":                False,
        "bloqueado_dia":            False,
    }

def guardar_estado_riesgo(estado):
    db.json_set("estado_riesgo", estado)

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

    max_hist    = estado.get("capital_maximo_historico") or 0
    inicio_dia  = estado.get("capital_inicio_dia") or 0

    # Sin una base valida no hay porcentaje que calcular. Antes esto era un
    # ZeroDivisionError que ni siquiera capturaba esta_bloqueado(), asi que
    # mataba el ciclo entero del francotirador. Mismo criterio que
    # DatosIncompletos por falta de precio: se pausa, no se persiste bloqueo.
    if max_hist <= 0 or inicio_dia <= 0:
        raise DatosIncompletos(
            f"[GUARDIAN] Base de riesgo invalida (max_hist=${max_hist}, "
            f"inicio_dia=${inicio_dia}) — no se evalua el riesgo este ciclo."
        )

    limite_drawdown = max_hist  * (1 - DRAWDOWN_MAXIMO_PCT)
    limite_diario   = inicio_dia * (1 - PERDIDA_DIARIA_MAXIMA_PCT)

    drawdown_actual = ((max_hist - capital_actual) / max_hist) * 100
    perdida_dia     = ((inicio_dia - capital_actual) / inicio_dia) * 100

    print(f"\n--- AUDITORIA DE RIESGO V2.14 ---")
    print(f"  🛡️ Límites activos  : DD máx {DRAWDOWN_MAXIMO_PCT*100:.0f}% | Pérdida día {PERDIDA_DIARIA_MAXIMA_PCT*100:.0f}%")
    print(f"  💰 Capital Actual   : ${round(capital_actual, 2)}")
    print(f"  📈 Maximo Historico : ${round(max_hist, 2)}")
    print(f"  📉 Drawdown Total   : {round(drawdown_actual, 2)}% (Max {DRAWDOWN_MAXIMO_PCT*100:.0f}%)")
    print(f"  📅 Perdida Hoy      : {round(perdida_dia, 2)}% (Max {PERDIDA_DIARIA_MAXIMA_PCT*100:.0f}%)")

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
    Verifica el capital actual contra los límites en cada llamada.
    Los flags cacheados no son suficientes: si el capital cae durante el día
    el guardián no lo detectaría hasta el día siguiente.

    Fail-safe: ante CUALQUIER fallo devuelve True (no operar). Antes capturaba
    solo RuntimeError y ademas dejaba verificar_riesgo() FUERA del try, asi que
    un ZeroDivisionError o un KeyError se propagaban y mataban el ciclo del
    francotirador en vez de limitarse a bloquear.
    """
    try:
        capital_actual = cargar_billetera()
        return not verificar_riesgo(capital_actual)
    except DatosIncompletos as e:
        print(f"[GUARDIAN] {e}")
        return True   # pausa transitoria: nada se persiste, se reintenta solo
    except Exception as e:
        print(f"[GUARDIAN] {type(e).__name__}: {e}")
        return True   # sin datos confiables, no operar

def estado_bloqueo():
    """
    Foto del guardian, sin tocar nada. La usa /desbloquear sin argumento.
    Devuelve (bloqueado, texto).
    """
    try:
        capital_actual = cargar_billetera()
    except RuntimeError as e:
        return None, f"⚠️ No se pudo leer el capital: {e}"

    estado = cargar_estado_riesgo(capital_actual)
    dd_bloq  = estado.get("bloqueado", False)
    dia_bloq = estado.get("bloqueado_dia", False)
    max_hist = estado.get("capital_maximo_historico") or 0

    if not dd_bloq and not dia_bloq:
        return False, (f"✅ <b>GUARDIÁN ACTIVO</b>\n\n"
                       f"No está bloqueado. Nada que desbloquear.\n"
                       f"Capital actual : ${capital_actual}\n"
                       f"Máximo histórico: ${max_hist}")

    dd = ((max_hist - capital_actual) / max_hist * 100) if max_hist > 0 else 0
    return True, (
        f"🔒 <b>GUARDIÁN BLOQUEADO</b>\n\n"
        f"Drawdown permanente : {'sí' if dd_bloq else 'no'}\n"
        f"Límite diario       : {'sí' if dia_bloq else 'no'}\n"
        f"Capital actual      : ${capital_actual}\n"
        f"Máximo histórico    : ${max_hist}\n"
        f"Caída desde el pico : {round(dd, 2)}%\n\n"
        f"⚠️ Desbloquear <b>rebasea el máximo histórico</b> a ${capital_actual}.\n"
        f"El drawdown vuelve a contarse desde ahí: se pierde la referencia\n"
        f"del pico anterior. Sin eso el bloqueo se re-dispara solo en el\n"
        f"ciclo siguiente.\n\n"
        f"Para confirmar: <code>/desbloquear confirmar</code>"
    )


def desbloquear(motivo="manual"):
    """
    Levanta el bloqueo del guardian. Unica salida documentada: antes habia que
    editar bot.db a mano.

    Rebasea capital_maximo_historico al capital actual a proposito. Si solo se
    apagara el flag, verificar_riesgo() compararia contra el mismo pico, veria
    la misma caida y volveria a bloquear en el ciclo siguiente.

    Devuelve (ok, mensaje).
    """
    try:
        capital_actual = cargar_billetera()
    except RuntimeError as e:
        return False, f"⚠️ No se pudo leer el capital: {e}"

    estado = cargar_estado_riesgo(capital_actual)
    if not estado.get("bloqueado") and not estado.get("bloqueado_dia"):
        return False, "El guardián no está bloqueado. No se cambió nada."

    previo = {
        "capital_maximo_historico": estado.get("capital_maximo_historico"),
        "capital_inicio_dia":       estado.get("capital_inicio_dia"),
        "bloqueado":                estado.get("bloqueado"),
        "bloqueado_dia":            estado.get("bloqueado_dia"),
    }
    estado["bloqueado"]                = False
    estado["bloqueado_dia"]            = False
    estado["capital_maximo_historico"] = capital_actual
    estado["capital_inicio_dia"]       = capital_actual
    # Huella del desbloqueo: quien lo levanto, cuando y desde que estado.
    estado["desbloqueo"] = {
        "timestamp":     datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "motivo":        motivo,
        "estado_previo": previo,
    }
    guardar_estado_riesgo(estado)

    msg = (f"🔓 <b>GUARDIÁN DESBLOQUEADO</b>\n\n"
           f"Motivo : {motivo}\n"
           f"Capital: ${capital_actual}\n"
           f"Máximo histórico rebaseado: ${previo['capital_maximo_historico']} → ${capital_actual}\n"
           f"El drawdown se cuenta desde acá. El bot vuelve a operar.")
    print(f"[GUARDIAN] Desbloqueo manual ({motivo}). "
          f"max_hist {previo['capital_maximo_historico']} -> {capital_actual}")
    try:
        enviar_aviso(msg)
    except Exception as e:
        print(f"[GUARDIAN] No se pudo avisar del desbloqueo: {e}")
    return True, msg


if __name__ == "__main__":
    if verificar_riesgo():
        print("\n  ✅ RESULTADO: El Guardian autoriza operacion.")
    else:
        print("\n  ❌ RESULTADO: El Guardian BLOQUEA el sistema.")
