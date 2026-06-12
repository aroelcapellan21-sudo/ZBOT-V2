#!/bin/bash
# ══════════════════════════════════════════════
#   LANZADOR MAESTRO — TODOS LOS BOTS
#   Corre con: ./arrancar_maestro.sh
#   Para ver un bot: screen -r NOMBRE
#   Para salir sin apagar: Ctrl+A luego D
# ══════════════════════════════════════════════

BASE="$HOME"
LOG="$BASE/arranque_maestro.log"
FECHA=$(date '+%Y-%m-%d %H:%M:%S')

echo "══════════════════════════════════════════════"
echo "   ZBOT MAESTRO — ARRANCANDO TODOS LOS BOTS"
echo "   $FECHA"
echo "══════════════════════════════════════════════"
echo "[$FECHA] Arranque maestro iniciado" >> "$LOG"

# ── ¿PROCESO PYTHON HIJO YA VIVO EN ESTE DIRECTORIO? ──
# Verifica el proceso real, no la sesión screen. Antes `lanzar` hacía
# `screen -X quit` incondicional, que mata la sesión pero deja el python hijo
# zombie poleando → doble notificación + error 409 en Telegram. El filtro por
# cwd distingue scripts homónimos de bots distintos (main.py de v2/v3/v4...).
proceso_activo() {
    local dir_abs archivo pid cwd
    dir_abs=$(readlink -f "$1")
    archivo=$(basename "$2")
    while read -r pid; do
        [ -z "$pid" ] && continue
        cwd=$(readlink -f "/proc/$pid/cwd" 2>/dev/null)
        [ "$cwd" = "$dir_abs" ] && return 0
    done < <(pgrep -f "python3 .*$archivo")
    return 1
}

# ── FUNCIÓN PARA LANZAR ────────────────────────
lanzar() {
    local NOMBRE=$1
    local DIRECTORIO=$2
    local ARCHIVO=$3

    if [ ! -f "$DIRECTORIO/$ARCHIVO" ]; then
        echo "  ⚠  $NOMBRE — no encontrado: $DIRECTORIO/$ARCHIVO"
        echo "[$FECHA] $NOMBRE NO ENCONTRADO" >> "$LOG"
        return
    fi

    # Guard primario: si el proceso ya corre desde este directorio, no duplicar.
    if proceso_activo "$DIRECTORIO" "$ARCHIVO"; then
        echo "  ⏭  $NOMBRE ya está corriendo (proceso vivo)"
        echo "[$FECHA] $NOMBRE SKIP (vivo)" >> "$LOG"
        return
    fi

    # No hay proceso vivo: limpiar sesión screen huérfana del mismo nombre y lanzar.
    if screen -list | grep -q "\.${NOMBRE}[[:space:]]"; then
        screen -S "$NOMBRE" -X quit 2>/dev/null
        screen -wipe >/dev/null 2>&1
    fi
    screen -dmS "$NOMBRE" bash -c "cd $DIRECTORIO && python3 $ARCHIVO >> $BASE/logs_maestro/${NOMBRE}.log 2>&1"
    echo "  ✅ $NOMBRE"
    echo "[$FECHA] $NOMBRE OK" >> "$LOG"
}

# Crear carpeta de logs
mkdir -p "$BASE/logs_maestro"

# ── Z-BOT V9 (PRINCIPAL) ───────────────────────
echo ""
echo "▶ Z-BOT V9..."
lanzar "v9_dashboard" "$BASE/zbot-v9"  "dashboard_v9.py"
lanzar "v9_launcher"  "$BASE/zbot-v9"  "launcher.py"
lanzar "v9_cerebro"   "$BASE/zbot-v9"  "cerebro_v9.py"
lanzar "v9_ejecutor"  "$BASE/zbot-v9"  "ejecutor_v9.py"

# ── TRIPLETA ───────────────────────────────────
echo ""
echo "▶ Tripleta (V5, V6, V8)..."
lanzar "v5_main"       "$BASE/bot-padre-v5"      "main.py"
lanzar "v6_main"       "$BASE/bot-padre-v6"      "main.py"
lanzar "v8_main"       "$BASE/bot-padre-v8"      "main.py"
lanzar "tripleta_dash" "$BASE"                    "dashboard_tripleta.py"

# ── REFERENCIA ─────────────────────────────────
echo ""
echo "▶ Bots referencia (V2, V3, V4)..."
lanzar "v2_main" "$BASE/bot-padre-v2"      "main.py"
lanzar "v3_main" "$BASE/bot-padre-v3-demo" "main.py"
lanzar "v4_main" "$BASE/bot-padre-v4"      "main.py"

# ── DIRECTOR ───────────────────────────────────
echo ""
echo "▶ Director orquesta..."
lanzar "orquesta" "$BASE/director-orquesta" "main.py"

# ── RESUMEN ────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════"
echo "   SISTEMA COMPLETO ACTIVO"
echo "   Puedes cerrar esta terminal."
echo "══════════════════════════════════════════════"
echo ""
echo "COMANDOS:"
echo "  screen -ls              → ver todos activos"
echo "  screen -r v9_dashboard  → Dashboard V9"
echo "  screen -r v9_launcher   → Observadores V9"
echo "  screen -r v9_cerebro    → Cerebro V9"
echo "  screen -r v9_ejecutor   → Ejecutor V9"
echo "  screen -r v5_main       → Bot V5"
echo "  screen -r v6_main       → Bot V6"
echo "  screen -r v8_main       → Bot V8"
echo "  screen -r tripleta_dash → Dashboard Tripleta"
echo "  screen -r v2_main       → Bot V2"
echo "  screen -r v3_main       → Bot V3 Demo"
echo "  screen -r v4_main       → Bot V4"
echo "  screen -r orquesta      → Director Orquesta"
echo ""
echo "  Salir sin apagar: Ctrl+A luego D"
echo "══════════════════════════════════════════════"
