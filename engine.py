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

ADMIN_YAYO  = 6578945006
ADMIN_SOCIA = 6533031969
ADMIN_IDS   = [ADMIN_YAYO, ADMIN_SOCIA]

def cargar_token():
    ruta = os.path.expanduser("~/bot-padre-v2/keys.env")
    try:
        with open(ruta, "r") as f:
            for linea in f:
                if linea.startswith("TELEGRAM_TOKEN="):
                    return linea.strip().split("=", 1)[1]
    except Exception as e:
        print(f"[ENGINE] Error cargando token: {e}")
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
                pass
        except Exception as e:
            print(f"[ENGINE] Error Telegram admin {admin_id}: {e}")
