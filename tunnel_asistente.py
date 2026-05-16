#!/usr/bin/env python3
# =========================================
# tunnel_asistente.py
# Inicia cloudflared apuntando al asistente (puerto 5050).
# Captura la URL publica, la envia por Telegram y la guarda.
# Ejecutar en screen z_tunnel: python3 tunnel_asistente.py
# Sin librerias externas. Constitucion RESPETADA
# =========================================

import subprocess
import threading
import re
import os
import json
import urllib.request
import urllib.parse
import sys
import time

PUERTO       = 5050
KEYS_FILE    = os.path.expanduser("~/bot-padre-v2/keys.env")
URL_FILE     = os.path.expanduser("~/bot-padre-v2/signals/tunnel_url.txt")
PATRON_URL   = re.compile(r"https://[a-zA-Z0-9._-]+\.trycloudflare\.com")
PATRON_FIJA  = re.compile(r"https://[a-zA-Z0-9._-]+\.[a-z]{2,}")


def cargar_token():
    try:
        with open(KEYS_FILE) as f:
            for linea in f:
                if linea.startswith("TELEGRAM_TOKEN="):
                    return linea.strip().split("=", 1)[1]
    except Exception:
        pass
    return None

def cargar_admins():
    ids = []
    try:
        with open(KEYS_FILE) as f:
            for linea in f:
                if linea.startswith("TELEGRAM_CHAT_ID="):
                    ids.append(linea.strip().split("=", 1)[1])
                elif linea.startswith("ID_SOCIA="):
                    ids.append(linea.strip().split("=", 1)[1])
    except Exception:
        pass
    return ids

def enviar_telegram(mensaje):
    token = cargar_token()
    if not token:
        return
    for chat_id in cargar_admins():
        try:
            data = json.dumps({"chat_id": chat_id, "text": mensaje}).encode()
            req  = urllib.request.Request(
                f"https://api.telegram.org/bot{token}/sendMessage",
                data=data,
                headers={"Content-Type": "application/json"}
            )
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass

def guardar_url(url):
    try:
        os.makedirs(os.path.dirname(URL_FILE), exist_ok=True)
        with open(URL_FILE, "w") as f:
            f.write(url)
    except Exception as e:
        print(f"[TUNNEL] Error guardando URL: {e}")

def url_ya_notificada(url):
    try:
        with open(URL_FILE) as f:
            return f.read().strip() == url
    except Exception:
        return False

def procesar_linea(linea, url_encontrada):
    """Busca la URL publica en la salida de cloudflared."""
    if url_encontrada[0]:
        return

    # Quick tunnel (trycloudflare.com)
    m = PATRON_URL.search(linea)
    if m:
        url = m.group()
        url_encontrada[0] = url
        print(f"\n[TUNNEL] ✅ URL publica: {url}\n")
        ya_guardada = url_ya_notificada(url)
        guardar_url(url)
        if not ya_guardada:
            enviar_telegram(
                f"🌐 ASISTENTE DISPONIBLE\n"
                f"URL: {url}\n"
                f"Esta URL cambia al reiniciar el tunel.\n"
                f"Para URL fija: ver instrucciones en tunnel_asistente.py"
            )
        return

    # Named tunnel (URL fija con dominio propio)
    if "INF" in linea and ("Registered" in linea or "hostname" in linea.lower()):
        m2 = PATRON_FIJA.search(linea)
        if m2 and "trycloudflare" not in m2.group():
            url = m2.group()
            url_encontrada[0] = url
            print(f"\n[TUNNEL] ✅ URL FIJA: {url}\n")
            ya_guardada = url_ya_notificada(url)
            guardar_url(url)
            if not ya_guardada:
                enviar_telegram(
                    f"🔒 ASISTENTE — URL FIJA\n"
                    f"URL: {url}\n"
                    f"Esta URL no cambia al reiniciar."
                )

def leer_salida(proc, url_encontrada):
    """Lee stderr de cloudflared en un hilo separado."""
    for linea in iter(proc.stderr.readline, b""):
        linea_str = linea.decode("utf-8", errors="replace").rstrip()
        print(linea_str, flush=True)
        procesar_linea(linea_str, url_encontrada)

def intentar_tunnel_nombrado():
    """
    Intenta usar el tunel nombrado de ~/.cloudflared/config.yml.
    Retorna True si arranca OK, False si falla (sin credenciales).
    """
    config = os.path.expanduser("~/.cloudflared/config.yml")
    if not os.path.exists(config):
        return False
    creds_path = None
    try:
        with open(config) as f:
            for linea in f:
                if "credentials-file:" in linea:
                    creds_path = linea.split(":", 1)[1].strip()
    except Exception:
        pass

    if creds_path and os.path.exists(creds_path):
        return True   # Credenciales presentes, usar named tunnel
    return False      # Sin credenciales, usar quick tunnel

def main():
    print(f"[TUNNEL] Iniciando tunel para asistente en puerto {PUERTO}...")

    usa_nombrado = intentar_tunnel_nombrado()

    if usa_nombrado:
        print("[TUNNEL] Usando tunel nombrado (URL fija)...")
        cmd = ["cloudflared", "tunnel", "run"]
    else:
        print("[TUNNEL] Usando quick tunnel (URL cambia al reiniciar)...")
        print("[TUNNEL] Para URL fija: ejecuta 'cloudflared tunnel login' una sola vez.")
        cmd = ["cloudflared", "tunnel", "--url", f"http://localhost:{PUERTO}"]

    url_encontrada = [None]

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=1
        )
    except FileNotFoundError:
        print("[TUNNEL] ERROR: cloudflared no instalado.")
        print("[TUNNEL]   Instalar con: curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o /usr/local/bin/cloudflared && chmod +x /usr/local/bin/cloudflared")
        sys.exit(1)

    hilo = threading.Thread(target=leer_salida, args=(proc, url_encontrada), daemon=True)
    hilo.start()

    # Tambien leer stdout
    def leer_stdout(p):
        for l in iter(p.stdout.readline, b""):
            print(l.decode("utf-8", errors="replace").rstrip(), flush=True)

    hilo_out = threading.Thread(target=leer_stdout, args=(proc,), daemon=True)
    hilo_out.start()

    try:
        proc.wait()
    except KeyboardInterrupt:
        print("\n[TUNNEL] Detenido por el usuario.")
        proc.terminate()

    rc = proc.returncode
    if rc and rc != -15:
        print(f"[TUNNEL] Tunel terminado con codigo {rc}. Reiniciando en 60s...")
        time.sleep(60)
        os.execv(sys.executable, [sys.executable] + sys.argv)


if __name__ == "__main__":
    main()
