import subprocess
import json
import os
import re
from collections import Counter
from datetime import datetime

# Lista completa historica. NO se edita para apagar un screen: para eso esta
# SCREENS_PAUSADOS de abajo, asi queda a la vista que el screen existe y esta
# apagado a proposito, y revertir es vaciar una lista.
SCREENS_TODOS = [
    "z_intel", "v2_main", "z_precision", "z_volumen",
    "z_fugas", "z_radar", "z_fuerza", "z_liquidez", "z_velas",
    "z_heatmap", "z_correlation", "z_squeeze", "z_macd", "z_rsi_adv",
    "z_vol_engine", "z_sentiment", "z_orderblocks", "z_timeframes",
    "z_ignition", "z_heatmap_radar", "z_wicks", "z_auditor",
    # z_executor sacado el 2026-09-06: el proceso se apago a proposito (score del
    # radar sin valor predictivo) y dejarlo aca lo reportaria como caido para siempre.
    "z_webserver", "z_tunnel", "z_dashboard_v2",
    "z_diagnostico", "z_asistente"
]

# Apagados a proposito el 2026-09-19 (20 radares + z_auditor) para liberar RAM y
# peso de API durante la ventana de captura de order book. Sin esto, este monitor
# los reportaria caidos cada 60 s y el asistente mostraria 21 caidos permanentes.
# Ninguno alimenta a v2_main: ver reports/2026-09-19_paso1-inventario-radares.md
# PARA REVERTIR: dejar SCREENS_PAUSADOS = [] y descomentar las lineas
# correspondientes en iniciar_bots.sh.
SCREENS_PAUSADOS = [
    "z_velas", "z_volumen", "z_precision", "z_fugas", "z_fuerza",
    "z_liquidez", "z_heatmap", "z_correlation", "z_radar", "z_intel",
    "z_squeeze", "z_macd", "z_rsi_adv", "z_vol_engine", "z_sentiment",
    "z_orderblocks", "z_timeframes", "z_ignition", "z_heatmap_radar",
    "z_wicks", "z_auditor"
]

SCREENS_ESPERADOS = [s for s in SCREENS_TODOS if s not in SCREENS_PAUSADOS]

REPORTE = os.path.expanduser("~/bot-padre-v2/estado_screens.json")

def verificar_screens():
    resultado = subprocess.run(["screen", "-ls"], capture_output=True, text=True)
    salida = resultado.stdout + resultado.stderr

    # Nombre REAL de cada sesión: lineas tipo "\t12345.nombre\t(fecha)\t(estado)".
    # Match exacto sobre el nombre, no substring: antes "z_heatmap" matcheaba la
    # linea de "z_heatmap_radar" y lo contaba dos veces (falso duplicado).
    sesiones = re.findall(r"^\s*\d+\.(\S+)\s", salida, re.MULTILINE)

    conteo = Counter(s for s in sesiones if s in SCREENS_ESPERADOS)
    activos = [s for s in SCREENS_ESPERADOS if conteo.get(s, 0) >= 1]
    caidos = [s for s in SCREENS_ESPERADOS if conteo.get(s, 0) == 0]
    # Duplicados REALES: un nombre esperado con más de una sesión viva.
    duplicados = {s: conteo[s] for s in SCREENS_ESPERADOS if conteo.get(s, 0) > 1}

    reporte = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_esperados": len(SCREENS_ESPERADOS),
        "total_activos": len(activos),
        "total_caidos": len(caidos),
        "total_duplicados": len(duplicados),
        "activos": activos,
        "caidos": caidos,
        "duplicados": duplicados
    }

    with open(REPORTE, "w") as f:
        json.dump(reporte, f, indent=2)

    return reporte

if __name__ == "__main__":
    r = verificar_screens()
    print(f"✅ Activos: {len(r['activos'])}")
    print(f"❌ Caídos: {r['caidos']}")
    if r["duplicados"]:
        print(f"⚠️  Duplicados: {r['duplicados']}")
