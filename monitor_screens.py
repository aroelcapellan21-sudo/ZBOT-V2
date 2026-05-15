import subprocess
import json
import os
from datetime import datetime

SCREENS_ESPERADOS = [
    "z_intel", "v2_main", "z_precision", "z_volumen",
    "z_fugas", "z_radar", "z_fuerza", "z_liquidez", "z_velas",
    "z_heatmap", "z_correlation", "z_squeeze", "z_macd", "z_rsi_adv",
    "z_vol_engine", "z_sentiment", "z_orderblocks", "z_timeframes",
    "z_ignition", "z_heatmap_radar", "z_wicks", "z_auditor",
    "z_webserver", "z_tunnel", "z_executor", "z_dashboard_v2",
    "z_diagnostico", "z_asistente"
]

REPORTE = os.path.expanduser("~/bot-padre-v2/estado_screens.json")

def verificar_screens():
    resultado = subprocess.run(["screen", "-ls"], capture_output=True, text=True)
    salida = resultado.stdout + resultado.stderr

    activos = []
    for linea in salida.splitlines():
        for nombre in SCREENS_ESPERADOS:
            if nombre in linea:
                activos.append(nombre)

    caidos = [s for s in SCREENS_ESPERADOS if s not in activos]

    reporte = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_esperados": len(SCREENS_ESPERADOS),
        "total_activos": len(activos),
        "total_caidos": len(caidos),
        "activos": activos,
        "caidos": caidos
    }

    with open(REPORTE, "w") as f:
        json.dump(reporte, f, indent=2)

    return reporte

if __name__ == "__main__":
    r = verificar_screens()
    print(f"✅ Activos: {len(r['activos'])}")
    print(f"❌ Caídos: {r['caidos']}")
