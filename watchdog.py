# =========================================
# watchdog.py
# Vigila que main.py este vivo
# Si se cae lo reinicia y avisa por Telegram
# Corre como cron cada 5 minutos
# Constitucion RESPETADA
# =========================================

import glob
import os
import subprocess
import time
import urllib.request
import urllib.parse
from datetime import datetime

ADMIN_YAYO = 6578945006
ADMIN_SOCIA = 6533031969
ADMIN_IDS = [ADMIN_YAYO, ADMIN_SOCIA]

# Llave de confirmacion persistente para BOT_REAL_CONFIRMADO (fuera del repo,
# creada a mano por Ariel una sola vez). Mismo archivo que lee iniciar_bots.sh --
# ver CLAUDE.md, seccion "Modo de operacion". Su sola existencia no alcanza para
# operar en REAL: modo.json tambien tiene que decir "REAL" (segunda confirmacion
# independiente, sin cambios).
BOT_REAL_CONFIRMADO_FILE = os.path.expanduser("~/.bot_real_confirmado")

# Identidad EXACTA del proceso que este watchdog vigila. Todo lo que no sea
# este archivo, en este directorio, no es "el bot" -- ver bot_esta_vivo().
PROYECTO = os.path.realpath(os.path.expanduser("~/bot-padre-v2"))
SCRIPT_BOT = os.path.join(PROYECTO, "main.py")
SCREEN_BOT = "v2_main"

# Ventana de gracia tras un arranque del sistema. El crontab tiene
# `@reboot sleep 30 && iniciar_bots.sh`, e iniciar_bots.sh levanta v2_main
# recien al final (el 08-sep: boot 00:29:45, v2_main arriba ~00:30:07). Si el
# watchdog corre dentro de esa ventana, gana la carrera y levanta el bot por su
# cuenta; despues iniciar_bots.sh lo ve vivo, lo saltea con [SKIP] y la sesion
# screen nunca se crea. Con la guarda, dentro de esa ventana el watchdog no
# actua: el arranque es trabajo de iniciar_bots.sh. Si iniciar_bots.sh fallara,
# el watchdog igual actua en su corrida siguiente (5 min despues).
ESPERA_ARRANQUE_S = 90

def cargar_token():
    ruta = os.path.expanduser("~/bot-padre-v2/keys.env")
    try:
        with open(ruta, "r") as f:
            for linea in f:
                if linea.startswith("TELEGRAM_BOT_TOKEN="):
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

def pids_del_bot():
    """PIDs de los main.py DE ESTE PROYECTO.

    Reemplaza a `pgrep -f main.py`, que matchea por substring sobre la linea de
    comando entera y por lo tanto CRUZA PROYECTOS: el main.py de
    ~/motor-confluencia -- que iniciar_bots.sh levanta en cada arranque --
    contaba como "el bot". Verificado el 08-sep: con v2_main muerto y
    motor_confluencia vivo, pgrep devuelve 0 y el watchdog escribe
    "Bot vivo. Todo OK." sin reiniciar nada
    (reports/2026-09-08_watchdog-ciego-pgrep-cruzado.md).

    Criterio, las tres condiciones a la vez:
      1. el ejecutable es un python,
      2. su primer argumento no-flag resuelve a PROYECTO/main.py (resolviendo
         los relativos contra el cwd del propio proceso, para aceptar tanto
         `python3 main.py` como `python3 /ruta/main.py`),
      3. de ahi sale la identidad: mismo archivo, mismo directorio.

    Es el mismo criterio que ya usa proceso_activo() en iniciar_bots.sh (ancla
    el nombre y compara cwd), un escalon mas estricto: exigir que el proceso sea
    un python descarta el wrapper `SCREEN -dmS v2_main bash -c ... main.py`, que
    tiene el mismo cwd y sobrevive a la muerte de su hijo. Sin ese detalle, una
    screen viva con el python ya caido se leeria como bot vivo.
    """
    encontrados = []
    for ruta in glob.glob("/proc/[0-9]*"):
        try:
            with open(os.path.join(ruta, "cmdline"), "rb") as f:
                argv = [a.decode("utf-8", "replace")
                        for a in f.read().split(b"\0") if a]
            if len(argv) < 2 or "python" not in os.path.basename(argv[0]):
                continue
            script = next((a for a in argv[1:] if not a.startswith("-")), None)
            if script is None or os.path.basename(script) != "main.py":
                continue
            cwd = os.path.realpath(os.path.join(ruta, "cwd"))
            if not os.path.isabs(script):
                script = os.path.join(cwd, script)
            if os.path.realpath(script) == SCRIPT_BOT:
                encontrados.append(int(os.path.basename(ruta)))
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            # El proceso murio mientras se lo miraba, o es de otro usuario.
            # No es un error del watchdog: simplemente no es nuestro bot.
            continue
        except OSError as e:
            print(f"[watchdog] no se pudo inspeccionar {ruta}: {e}")
    return encontrados

def bot_esta_vivo():
    return len(pids_del_bot()) > 0

def uptime_segundos():
    try:
        with open("/proc/uptime") as f:
            return float(f.read().split()[0])
    except (OSError, ValueError) as e:
        # Sin uptime no se puede saber si estamos en el arranque. Se devuelve
        # None y main() sigue como antes: mejor actuar de mas que no actuar.
        print(f"[watchdog] no se pudo leer /proc/uptime: {e}")
        return None

def reiniciar_bot():
    """Levanta el bot DENTRO de su screen, igual que iniciar_bots.sh.

    Antes se lanzaba con subprocess.Popen y stdout/stderr a DEVNULL: el bot
    quedaba huerfano (ppid=1), `screen -r v2_main` no existia, monitor_screens.py
    lo reportaba caido y el log del bot no quedaba en ningun lado. Pasa
    exactamente eso el 08-sep 00:30. Levantar en screen no evita la carrera con
    iniciar_bots.sh, pero la vuelve inofensiva: gane quien gane, el bot queda
    observable y con el log a la vista.

    Ademas ahora se VERIFICA: antes devolvia True porque Popen no habia lanzado
    excepcion, aunque el proceso muriera al instante -- y el aviso de Telegram
    decia "Bot reiniciado correctamente" igual.
    """
    comando = "python3 main.py"
    if os.path.isfile(BOT_REAL_CONFIRMADO_FILE):
        comando = f"export BOT_REAL_CONFIRMADO=true && {comando}"
    try:
        # Llegamos aca solo si NO hay proceso vivo, asi que una sesion con ese
        # nombre es basura de un arranque anterior: limpiarla antes de crear la
        # nueva evita quedar con dos sesiones v2_main (monitor_screens.py las
        # reportaria como duplicadas). Mismo orden que iniciar_bots.sh.
        subprocess.run(["screen", "-S", SCREEN_BOT, "-X", "quit"],
                       capture_output=True, timeout=15)
        subprocess.run(["screen", "-wipe"], capture_output=True, timeout=15)
        subprocess.run(["screen", "-dmS", SCREEN_BOT, "bash", "-c",
                        f"cd {PROYECTO} && {comando}"],
                       capture_output=True, timeout=15, check=True)
    except (OSError, subprocess.SubprocessError) as e:
        print(f"[watchdog] fallo al lanzar la screen {SCREEN_BOT}: {e}")
        return False

    # main.py tarda unos segundos en arrancar (importa modulos y lee la DB).
    for _ in range(10):
        time.sleep(1)
        if bot_esta_vivo():
            return True
    print(f"[watchdog] la screen {SCREEN_BOT} se creo pero el bot no aparecio vivo")
    return False

def main():
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    up = uptime_segundos()
    if up is not None and up < ESPERA_ARRANQUE_S:
        print(f"[{timestamp}] Watchdog: arranque reciente ({up:.0f}s) — "
              f"le toca a iniciar_bots.sh. No se actua.")
        return

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
