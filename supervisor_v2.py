#!/usr/bin/env python3
# =========================================
# supervisor_v2.py — Supervisor Z-Bot V2
# FIX: Eliminado requests y dotenv
# FIX: Ruta log corregida
# FIX: Ruta billetera corregida
# FIX: Sistema de prioridades — no spam
# FIX: Memoria de estado — no repite alertas
# Sin librerias externas. Constitucion RESPETADA
# =========================================

import os
import json
import subprocess
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path

BOT_DIR       = "/home/ariel/bot-padre-v2"
LOG_FILE      = f"{BOT_DIR}/memoria/eventos.log"
KEYS_FILE     = f"{BOT_DIR}/keys.env"
BILLETERA     = f"{BOT_DIR}/signals/billetera.json"
ESTADO_SUP    = f"{BOT_DIR}/signals/estado_supervisor.json"
AUDITORIA     = f"{BOT_DIR}/auditoria.csv"

MONEDAS       = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "AVAXUSDT"]
MAX_SILENCIO  = 30   # minutos antes de considerar log congelado
REENVIO_MIN   = 60   # minutos antes de reenviar mismo problema critico

ADMIN_YAYO    = 6578945006
ADMIN_SOCIA   = 6533031969
ADMIN_IDS     = [ADMIN_YAYO, ADMIN_SOCIA]

# ─── Token ───────────────────────────────────────────────────────────────────
def cargar_token():
    try:
        with open(KEYS_FILE, "r") as f:
            for linea in f:
                if linea.startswith("TELEGRAM_TOKEN="):
                    return linea.strip().split("=", 1)[1]
    except Exception as e:
        print(f"[SUPERVISOR] Error cargando token: {e}")
    return None

# ─── Telegram ────────────────────────────────────────────────────────────────
def enviar_alerta(mensaje):
    token = cargar_token()
    if not token:
        print("[SUPERVISOR] Sin token. Solo consola.")
        return
    for admin_id in ADMIN_IDS:
        try:
            data = json.dumps({
                "chat_id":    admin_id,
                "text":       mensaje,
                "parse_mode": "HTML"
            }).encode()
            req = urllib.request.Request(
                f"https://api.telegram.org/bot{token}/sendMessage",
                data=data,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=10):
                pass
        except Exception as e:
            print(f"[SUPERVISOR] Error Telegram {admin_id}: {e}")

# ─── Estado supervisor ───────────────────────────────────────────────────────
def cargar_estado():
    try:
        with open(ESTADO_SUP, "r") as f:
            return json.load(f)
    except:
        return {}

def guardar_estado(estado):
    try:
        os.makedirs(os.path.dirname(ESTADO_SUP), exist_ok=True)
        with open(ESTADO_SUP, "w") as f:
            json.dump(estado, f, indent=2)
    except Exception as e:
        print(f"[SUPERVISOR] Error guardando estado: {e}")

def debe_alertar(estado, clave, prioridad):
    """
    Decide si debe enviar alerta segun prioridad y tiempo.
    CRITICO: alerta inmediata, reenvio cada 60 min
    IMPORTANTE: solo si persiste 30+ min
    INFORMATIVO: nunca por Telegram
    """
    if prioridad == "INFORMATIVO":
        return False

    ahora     = datetime.now().timestamp()
    ultimo    = estado.get(clave, {}).get("ultimo_envio", 0)
    primera   = estado.get(clave, {}).get("primera_vez", ahora)
    mins_desde_ultimo  = (ahora - ultimo) / 60
    mins_desde_primera = (ahora - primera) / 60

    if prioridad == "CRITICO":
        # Primera vez → alertar siempre
        if ultimo == 0:
            return True
        # Repetido → solo cada 60 min
        return mins_desde_ultimo >= REENVIO_MIN

    if prioridad == "IMPORTANTE":
        # Solo alertar si persiste 30+ min Y han pasado 60 min desde ultimo envio
        if mins_desde_primera >= 30:
            if ultimo == 0 or mins_desde_ultimo >= REENVIO_MIN:
                return True
        return False

    return False

def registrar_alerta(estado, clave):
    ahora = datetime.now().timestamp()
    if clave not in estado:
        estado[clave] = {"primera_vez": ahora, "ultimo_envio": 0}
    estado[clave]["ultimo_envio"] = ahora

def limpiar_resuelto(estado, clave):
    """Limpia el estado cuando un problema se resuelve."""
    if clave in estado:
        del estado[clave]

# ─── Checks ──────────────────────────────────────────────────────────────────
def check_proceso_vivo():
    """Verifica que el screen v2_main existe y tiene proceso activo."""
    r = subprocess.run(["screen", "-list"], capture_output=True, text=True)
    return "v2_main" in r.stdout

def check_silencio_log():
    """Retorna minutos desde ultima escritura al log."""
    path = Path(LOG_FILE)
    if not path.exists():
        return 9999
    mtime = path.stat().st_mtime
    return int((datetime.now().timestamp() - mtime) / 60)

def check_posiciones_riesgo(silencio):
    """Verifica si hay posiciones abiertas con bot sin vigilancia."""
    if silencio < MAX_SILENCIO:
        return []
    try:
        with open(AUDITORIA, "r") as f:
            lineas = f.readlines()
        abiertas = [
            l.strip().split(",")[2]
            for l in lineas[1:]
            if len(l.strip().split(",")) >= 6 and
            l.strip().split(",")[5] == "ABIERTA"
        ]
        return abiertas
    except:
        return []

def check_errores_criticos():
    """Busca errores criticos en el log reciente."""
    if not Path(LOG_FILE).exists():
        return []
    try:
        r = subprocess.run(["tail", "-n", "200", LOG_FILE],
                           capture_output=True, text=True)
        keywords_criticos = [
            "ERROR CRITICO", "RuntimeError", "Traceback",
            "billetera no encontrada", "No se pudo guardar"
        ]
        encontrados = []
        vistos      = set()
        for linea in r.stdout.splitlines():
            for kw in keywords_criticos:
                if kw in linea:
                    corta = linea.strip()[:100]
                    if corta not in vistos:
                        vistos.add(corta)
                        encontrados.append(corta)
                    break
        return encontrados[-3:]
    except:
        return []

# ─── Supervisor principal ─────────────────────────────────────────────────────
def supervisar():
    ahora  = datetime.now().strftime("%d/%m/%Y %H:%M")
    estado = cargar_estado()

    alertas_enviar = []  # (clave, prioridad, mensaje)
    resueltos      = []  # claves resueltas

    # --- CHECK 1: Proceso vivo (CRITICO) ---
    if not check_proceso_vivo():
        clave = "proceso_muerto"
        if debe_alertar(estado, clave, "CRITICO"):
            alertas_enviar.append((
                clave, "CRITICO",
                "🔴 <b>PROCESO MUERTO</b>\nLa screen v2_main no existe o está muerta.\n🔧 Revisar: <code>screen -r v2_main</code>"
            ))
            registrar_alerta(estado, clave)
    else:
        if "proceso_muerto" in estado:
            resueltos.append("proceso_muerto")
            alertas_enviar.append((
                "proceso_resuelto", "CRITICO",
                "✅ <b>PROCESO RECUPERADO</b>\nLa screen v2_main está activa nuevamente."
            ))

    # --- CHECK 2: Log congelado (IMPORTANTE) ---
    silencio = check_silencio_log()
    if silencio >= MAX_SILENCIO:
        clave = "log_congelado"
        if debe_alertar(estado, clave, "IMPORTANTE"):
            alertas_enviar.append((
                clave, "IMPORTANTE",
                f"⚠️ <b>LOG SIN ACTIVIDAD</b>\nSin registros hace <b>{silencio} minutos</b>.\n🔧 Revisar: <code>screen -r v2_main</code>"
            ))
            registrar_alerta(estado, clave)
    else:
        if "log_congelado" in estado:
            resueltos.append("log_congelado")

    # --- CHECK 3: Posiciones en riesgo (CRITICO) ---
    posiciones = check_posiciones_riesgo(silencio)
    if posiciones:
        clave = "posiciones_riesgo"
        if debe_alertar(estado, clave, "CRITICO"):
            symbols = ", ".join(set(posiciones))
            alertas_enviar.append((
                clave, "CRITICO",
                f"🚨 <b>POSICIONES SIN VIGILANCIA</b>\n{symbols} tienen trades abiertos y el bot lleva {silencio} min sin actividad."
            ))
            registrar_alerta(estado, clave)
    else:
        if "posiciones_riesgo" in estado:
            resueltos.append("posiciones_riesgo")

    # --- CHECK 4: Errores criticos en log (IMPORTANTE) ---
    errores = check_errores_criticos()
    if errores:
        clave = "errores_criticos"
        if debe_alertar(estado, clave, "IMPORTANTE"):
            texto_errores = "\n".join(f"<code>{e}</code>" for e in errores)
            alertas_enviar.append((
                clave, "IMPORTANTE",
                f"⚠️ <b>ERRORES EN LOG</b>\n{texto_errores}"
            ))
            registrar_alerta(estado, clave)
    else:
        if "errores_criticos" in estado:
            resueltos.append("errores_criticos")

    # --- CHECK 5: Posiciones huerfanas (auto-reconciliacion) ---
    try:
        from reconciliar import auto_reconciliar
        n = auto_reconciliar()
        if n > 0:
            print(f"[SUPERVISOR] Auto-reconciliacion: {n} posicion(es) huerfana(s) resueltas.")
    except Exception as e:
        print(f"[SUPERVISOR] Error en auto_reconciliar: {e}")

    # --- Limpiar resueltos ---
    for clave in resueltos:
        limpiar_resuelto(estado, clave)

    # --- Enviar alertas ---
    for clave, prioridad, mensaje in alertas_enviar:
        msg_completo = (
            f"🤖 <b>SUPERVISOR Z-BOT V2</b>\n"
            f"🕐 {ahora}\n\n"
            f"{mensaje}"
        )
        print(msg_completo)
        if clave != "proceso_resuelto" or resueltos:
            enviar_alerta(msg_completo)

    guardar_estado(estado)

    if not alertas_enviar:
        print(f"[SUPERVISOR] {ahora} — Todo OK ✅")

if __name__ == "__main__":
    supervisar()
