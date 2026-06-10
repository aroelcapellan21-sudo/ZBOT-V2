#!/bin/bash
# =========================================
# iniciar_bots.sh — Z-Bot Padre v2
# Inicia todos los procesos en screen.
# Seguro: no duplica sesiones existentes.
# Llamado por @reboot en crontab.
# =========================================

DIR=~/bot-padre-v2
KEYS="$DIR/keys.env"

# Lee una variable de keys.env
leer_key() {
    grep "^$1=" "$KEYS" | cut -d= -f2
}

ANTHROPIC_API_KEY=$(leer_key "ANTHROPIC_API_KEY")

# Inicia una sesión screen solo si no existe ya
iniciar() {
    local nombre=$1
    local directorio=$2
    local comando=$3

    if screen -list | grep -q "\.${nombre}[[:space:]]"; then
        echo "[SKIP] $nombre ya está corriendo"
    else
        screen -dmS "$nombre" bash -c "cd $directorio && $comando"
        echo "[OK]   $nombre iniciado"
    fi
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

# --- Radar (zbot) ---
iniciar z_auditor    ~/zbot/radar "python3 auditor_supremo.py"
iniciar z_webserver  ~/zbot/radar "python3 z_webserver.py"
iniciar z_executor   ~/zbot/radar "python3 radar_executor.py"

# --- Core del bot ---
iniciar z_diagnostico  "$DIR" "python3 auto_diagnostico.py"
iniciar z_dashboard_v2 "$DIR" "python3 z_webserver_v2.py"
iniciar z_asistente    "$DIR" "ANTHROPIC_API_KEY='$ANTHROPIC_API_KEY' python3 asistente.py"

# --- Túnel cloudflared ---
iniciar z_tunnel "$DIR" "python3 tunnel_asistente.py"

# --- Bot principal (último, depende de los anteriores) ---
sleep 5
iniciar v2_main "$DIR" "python3 main.py"

echo "================================================"
echo " Todos los procesos iniciados."
echo " Ver con: screen -ls"
echo "================================================"
