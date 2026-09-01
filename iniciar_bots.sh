#!/bin/bash
# =========================================
# iniciar_bots.sh — Z-Bot Padre v2
# Inicia todos los procesos en screen.
# Seguro: no duplica sesiones existentes.
# Llamado por @reboot en crontab.
# =========================================

DIR=~/bot-padre-v2
KEYS="$DIR/keys.env"

# Llave de confirmacion persistente para BOT_REAL_CONFIRMADO (fuera del repo).
# La crea Ariel a mano una sola vez -- ver CLAUDE.md, seccion "Modo de operacion".
# Su sola existencia no alcanza para operar en REAL: modo.json tambien tiene
# que decir "REAL" (segunda confirmacion independiente, sin cambios).
BOT_REAL_CONFIRMADO_FILE="$HOME/.bot_real_confirmado"

# Lee una variable de keys.env
leer_key() {
    grep "^$1=" "$KEYS" | cut -d= -f2
}

# ¿Ya hay un proceso python VIVO de este script lanzado desde ESTE directorio?
# Guard de fondo: la detección por nombre de screen falla bajo cron (el socket dir
# de screen difiere y no ve las sesiones), por eso duplicaba. Verificar el proceso
# hijo real es robusto e independiente del entorno. El filtro por cwd evita confundir
# scripts homónimos de otros bots (main.py de v4, heatmap.py de zbot/radar, etc.).
proceso_activo() {
    local dir_abs comando archivo pid cwd
    dir_abs=$(readlink -f "$1")
    comando=$2
    archivo=$(echo "$comando" | grep -oE '[A-Za-z0-9_./-]+\.py' | head -1)
    [ -z "$archivo" ] && return 1
    archivo=$(basename "$archivo")
    # FIX: pgrep -f hace match por substring — "python3 .*asistente.py" matcheaba
    # tambien "tunnel_asistente.py" (false positive: SKIP de un proceso que no
    # esta corriendo). Anclar el nombre de archivo a un limite real (inicio de
    # linea o "/" antes, fin de linea o espacio despues).
    local archivo_regex
    archivo_regex=$(printf '%s' "$archivo" | sed 's/\./\\./g')
    while read -r pid; do
        [ -z "$pid" ] && continue
        cwd=$(readlink -f "/proc/$pid/cwd" 2>/dev/null)
        [ "$cwd" = "$dir_abs" ] && return 0
    done < <(pgrep -f "(^|[ /])${archivo_regex}(\$| )")
    return 1
}

# Inicia una sesión screen solo si el proceso no está ya corriendo
iniciar() {
    local nombre=$1
    local directorio=$2
    local comando=$3

    # Guard primario: proceso hijo vivo en este directorio -> no duplicar.
    if proceso_activo "$directorio" "$comando"; then
        echo "[SKIP] $nombre ya está corriendo (proceso vivo)"
        return
    fi

    # No hay proceso vivo. Si quedó una sesión screen huérfana o muerta con ese
    # nombre (p.ej. screen vivo con su python ya caído, o un `-X quit` previo que
    # dejó la sesión a medias), limpiarla antes de relanzar para no acumular.
    if screen -list | grep -q "\.${nombre}[[:space:]]"; then
        echo "[WIPE] $nombre: sesión sin proceso vivo — limpiando"
        screen -S "$nombre" -X quit 2>/dev/null
        screen -wipe >/dev/null 2>&1
    fi

    screen -dmS "$nombre" bash -c "cd $directorio && $comando"
    echo "[OK]   $nombre iniciado"
}

# =========================================
# Claude Code — arranque propio (no usa iniciar())
# =========================================
# iniciar()/proceso_activo() solo saben reconocer comandos "python3 archivo.py":
# con "claude" el nombre de archivo sale vacio, proceso_activo() da SIEMPRE falso,
# y la rama de limpieza mata la sesion de Claude que estaba viva. Ya ocurrio:
# ver "[WIPE] claude_code" en memoria/arranque.log. Por eso Claude Code lleva su
# propio guard aca abajo y NO se toca iniciar(), que es la que usa el bot.

# Resuelve el binario de claude sin depender del PATH: bajo cron el PATH es
# /usr/bin:/bin y "claude" NO se encuentra (ni el de nvm ni el de /usr/local/bin).
resolver_claude() {
    local nvm_claude
    if command -v claude >/dev/null 2>&1; then
        command -v claude
        return 0
    fi
    # Instalacion via nvm (la vigente hoy). Se toma la version mas alta presente.
    nvm_claude=$(ls -1d "$HOME"/.nvm/versions/node/*/bin/claude 2>/dev/null | sort -V | tail -1)
    if [ -x "$nvm_claude" ]; then
        echo "$nvm_claude"
        return 0
    fi
    if [ -x /usr/local/bin/claude ]; then
        echo /usr/local/bin/claude
        return 0
    fi
    return 1
}

# ¿Hay un proceso 'claude' vivo, con cwd en el proyecto y colgando de un SCREEN?
# Mira /proc y no el socket dir de screen (que bajo cron no ve las sesiones).
# El chequeo del padre SCREEN evita confundirse con un claude que Ariel tenga
# abierto a mano en una terminal: ese no cuelga de un SCREEN.
claude_en_screen_activo() {
    local dir_abs pid cwd ppid pcomm
    dir_abs=$(readlink -f "$1")
    while read -r pid; do
        [ -z "$pid" ] && continue
        cwd=$(readlink -f "/proc/$pid/cwd" 2>/dev/null)
        [ "$cwd" = "$dir_abs" ] || continue
        ppid=$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ')
        [ -z "$ppid" ] && continue
        # OJO: /proc/<pid>/comm devuelve "screen" en minuscula; el "SCREEN" en
        # mayuscula que se ve en `pgrep -af` es solo el argv[0]. Comparar en
        # minuscula, si no el guard nunca detecta la sesion viva.
        pcomm=$(tr '[:upper:]' '[:lower:]' < "/proc/$ppid/comm" 2>/dev/null)
        [ "$pcomm" = "screen" ] && return 0
    done < <(pgrep -x claude)
    return 1
}

iniciar_claude() {
    local nombre=$1
    local directorio=$2
    local bin

    # Guard primario: sesion de Claude viva en este directorio -> no tocarla.
    if claude_en_screen_activo "$directorio"; then
        echo "[SKIP] $nombre ya está corriendo (sesión Claude Code viva)"
        return
    fi

    bin=$(resolver_claude)
    if [ -z "$bin" ]; then
        echo "[ERR]  $nombre: no se encontró el binario 'claude' — sesión NO iniciada"
        return
    fi

    # Sin Claude vivo: limpiar una screen huerfana con ese nombre antes de relanzar.
    if screen -list | grep -q "\.${nombre}[[:space:]]"; then
        echo "[WIPE] $nombre: sesión sin Claude vivo — limpiando"
        screen -S "$nombre" -X quit 2>/dev/null
        screen -wipe >/dev/null 2>&1
    fi

    # TERM explicito: bajo cron viene vacio y la TUI de Claude Code lo necesita.
    # --remote-control deja la sesion accesible desde el celular sin escanear QR.
    screen -dmS "$nombre" bash -c "cd $directorio && export TERM=xterm-256color && exec '$bin' --remote-control $nombre"
    echo "[OK]   $nombre iniciado ($bin, Remote Control activo)"
}

echo "================================================"
echo " Z-Bot Padre v2 — Iniciando procesos"
echo " $(date)"
echo "================================================"

# --- Módulos de datos e inteligencia ---
iniciar z_velas      "$DIR" "python3 z_velas.py"
iniciar z_volumen    "$DIR" "python3 volumen_real.py"
iniciar z_precision  "$DIR" "python3 precision.py"
iniciar z_fugas      "$DIR" "python3 picos_fuga.py"
iniciar z_fuerza     "$DIR" "python3 fuerza_sector.py"
iniciar z_liquidez   "$DIR" "python3 liquidez_libro.py"
iniciar z_heatmap    "$DIR" "python3 heatmap.py"
iniciar z_correlation "$DIR" "python3 correlation.py"

# --- Inteligencia y análisis técnico (bot-padre-v2) ---
iniciar z_radar      "$DIR" "python3 radar_noticias.py"
iniciar z_intel      "$DIR" "python3 servidor_intel.py"

# --- Motores de análisis (zbot/radar) ---
iniciar z_squeeze      ~/zbot/radar "python3 squeeze_detector.py"
iniciar z_macd         ~/zbot/radar "python3 macd_engine.py"
iniciar z_rsi_adv      ~/zbot/radar "python3 rsi_advanced.py"
iniciar z_vol_engine   ~/zbot/radar "python3 volumen_engine.py"
iniciar z_sentiment    ~/zbot/radar "python3 z_sentiment.py"
iniciar z_orderblocks  ~/zbot/radar "python3 orderblock_engine.py"
iniciar z_timeframes   ~/zbot/radar "python3 timeframe_engine.py"
iniciar z_ignition     ~/zbot/radar "python3 ignition.py"
iniciar z_heatmap_radar ~/zbot/radar "python3 heatmap.py"
iniciar z_wicks        ~/zbot/radar "python3 wick_analyzer.py"

# --- Radar (zbot) ---
iniciar z_auditor    ~/zbot/radar "python3 auditor_supremo.py"
iniciar z_webserver  ~/zbot/radar "python3 z_webserver.py"
iniciar z_executor   ~/zbot/radar "python3 radar_executor.py"

# --- Core del bot ---
iniciar z_diagnostico  "$DIR" "python3 auto_diagnostico.py"
iniciar z_dashboard_v2 "$DIR" "python3 z_webserver_v2.py"
iniciar z_asistente    "$DIR" "python3 asistente.py"

# --- Túnel cloudflared ---
iniciar z_tunnel "$DIR" "python3 tunnel_asistente.py"

# --- Bot principal (último, depende de los anteriores) ---
sleep 5
CMD_V2_MAIN="python3 main.py"
if [ -f "$BOT_REAL_CONFIRMADO_FILE" ]; then
    echo "[REAL] $BOT_REAL_CONFIRMADO_FILE presente — exportando BOT_REAL_CONFIRMADO=true para v2_main"
    CMD_V2_MAIN="export BOT_REAL_CONFIRMADO=true && $CMD_V2_MAIN"
fi
iniciar v2_main "$DIR" "$CMD_V2_MAIN"

# --- Rescatados de la copia vieja en $HOME (jun 2026), antes de borrarla ---
iniciar motor_confluencia ~/motor-confluencia "python3 main.py"

# --- Claude Code — sesion accesible desde el celular (Remote Control) ---
# Reemplaza a la vieja linea `iniciar claude_code "$DIR" "claude"`, que no tenia
# guard real (mataba la sesion viva) y bajo cron no encontraba el binario.
iniciar_claude z_code "$DIR"

echo "================================================"
echo " Todos los procesos iniciados."
echo " Ver con: screen -ls"
echo "================================================"
