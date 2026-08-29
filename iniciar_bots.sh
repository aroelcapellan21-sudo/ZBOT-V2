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
iniciar claude_code "$DIR" "claude"

echo "================================================"
echo " Todos los procesos iniciados."
echo " Ver con: screen -ls"
echo "================================================"
