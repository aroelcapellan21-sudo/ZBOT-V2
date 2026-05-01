# =========================================
# watchdog.py
# Vigila que main.py este vivo
# Si se cae lo reinicia y avisa por Telegram
# Corre como cron cada 5 minutos
# Constitucion RESPETADA
# =========================================

import os
import subprocess
import urllib.request
import urllib.parse
from datetime import datetime

ADMIN_YAYO = 6578945006
ADMIN_SOCIA = 6533031969
ADMIN_IDS = [ADMIN_YAYO, ADMIN_SOCIA]

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
        return
    for admin_id in ADMIN_IDS:
        try:
            params = urllib.parse.urlencode({
                "chat_id": admin_id,
                "text": mensaje
            })
            url = f"https://api.telegram.org/bot{token}/sendMessage?{params}"
            with urllib.request.urlopen(url, timeout=10) as resp:
                pass
        except:
            pass

def bot_esta_vivo():
    try:
        result = subprocess.run(
            ["pgrep", "-f", "main.py"],
            capture_output=True, text=True
        )
        return result.returncode == 0
    except:
        return False

def reiniciar_bot():
    try:
        os.chdir(os.path.expanduser("~/bot-padre-v2"))
        subprocess.Popen(
            ["python3", "main.py"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return True
    except:
        return False

def main():
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if bot_esta_vivo():
        print(f"[{timestamp}] Watchdog: Bot vivo. Todo OK.")
        return

    print(f"[{timestamp}] Watchdog: Bot caido. Reiniciando...")

    enviar_telegram(
        f"⚠️ WATCHDOG Z-BOT\n"
        f"🕐 {timestamp}\n\n"
        f"❌ Bot caido detectado.\n"
        f"🔄 Reiniciando automaticamente..."
    )

    if reiniciar_bot():
        enviar_telegram(
            f"✅ WATCHDOG Z-BOT\n"
            f"🕐 {timestamp}\n\n"
            f"Bot reiniciado correctamente.\n"
            f"Sistema activo nuevamente."
        )
        print(f"[{timestamp}] Watchdog: Bot reiniciado correctamente.")
    else:
        enviar_telegram(
            f"🚨 WATCHDOG Z-BOT\n"
            f"🕐 {timestamp}\n\n"
            f"ERROR: No se pudo reiniciar el bot.\n"
            f"Revision manual requerida."
        )
        print(f"[{timestamp}] Watchdog: Error al reiniciar.")

if __name__ == "__main__":
    main()
