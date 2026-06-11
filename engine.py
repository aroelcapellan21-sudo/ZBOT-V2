# =========================================
# engine.py - Motor de avisos
# FIX: Token recargado en cada envio
# FIX: parse_mode HTML agregado
# NO ejecuta. NO decide. NO toca capital.
# Constitucion RESPETADA
# =========================================

import urllib.request
import urllib.parse
import json
import os
from datetime import datetime

ADMIN_YAYO  = 6578945006
ADMIN_SOCIA = 6533031969
ADMIN_IDS   = [ADMIN_YAYO, ADMIN_SOCIA]

LOG_TELEGRAM = os.path.expanduser("~/bot-padre-v2/memoria/telegram.log")

def _log_telegram(linea):
    """Persiste fallos de envio a Telegram. Antes solo se imprimian al stdout
    del screen y se perdian (causa de fallos invisibles durante dias)."""
    try:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_TELEGRAM, "a") as f:
            f.write(f"{ts} - {linea}\n")
    except Exception as e:
        print(f"[ENGINE] No se pudo escribir telegram.log: {e}")

def cargar_token():
    ruta = os.path.expanduser("~/bot-padre-v2/keys.env")
    try:
        with open(ruta, "r") as f:
            for linea in f:
                if linea.startswith("TELEGRAM_BOT_TOKEN="):
                    return linea.strip().split("=", 1)[1]
    except Exception as e:
        print(f"[ENGINE] Error cargando token: {e}")
        _log_telegram(f"ERROR cargando token: {e}")
    return None

def enviar_aviso(mensaje):
    """
    Envia aviso critico a los administradores.
    FIX: Token recargado en cada llamada.
    FIX: parse_mode HTML incluido.
    """
    print(f"[AVISO] {mensaje}")
    token = cargar_token()
    if not token:
        print("[ENGINE] Token no disponible. Aviso solo en consola.")
        _log_telegram("Token no disponible. Aviso solo en consola.")
        return
    for admin_id in ADMIN_IDS:
        try:
            params = urllib.parse.urlencode({
                "chat_id":    admin_id,
                "text":       f"🚨 Z-BOT AVISO:\n{mensaje}",
                "parse_mode": "HTML"
            })
            url = f"https://api.telegram.org/bot{token}/sendMessage?{params}"
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                if not data.get("ok"):
                    print(f"[ENGINE] Telegram rechazo admin {admin_id}: {data}")
                    _log_telegram(f"Rechazo admin {admin_id}: {data}")
        except Exception as e:
            print(f"[ENGINE] Error Telegram admin {admin_id}: {e}")
            _log_telegram(f"Error envio admin {admin_id}: {e}")
