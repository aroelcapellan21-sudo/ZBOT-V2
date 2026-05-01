# =========================================
# descargar_historico.py
# Rol: Descarga velas historicas de BTC/USDT
# desde Binance (sin API key, datos publicos)
# Guarda el resultado en: data/btc_1h.csv
# NO ejecuta. NO opera. Solo descarga datos.
# =========================================

import urllib.request
import json
import csv
import os
from datetime import datetime

os.makedirs("data", exist_ok=True)

SYMBOL = "BTCUSDT"
INTERVAL = "1h"
LIMIT = 1000
TOTAL_VELAS = 8760
ARCHIVO = "data/btc_1h.csv"

def descargar_velas(symbol, interval, limit, end_time=None):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    if end_time:
        url += f"&endTime={end_time}"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"[ERROR] No se pudo conectar: {e}")
        return []

def descargar_historico_completo():
    print(f"[INFO] Descargando {TOTAL_VELAS} velas de {SYMBOL} ({INTERVAL})...")
    todas_las_velas = []
    end_time = None

    while len(todas_las_velas) < TOTAL_VELAS:
        velas = descargar_velas(SYMBOL, INTERVAL, LIMIT, end_time)
        if not velas:
            print("[ERROR] Sin datos. Revisa tu conexion a internet.")
            break
        todas_las_velas = velas + todas_las_velas
        end_time = velas[0][0] - 1
        print(f"[INFO] Velas descargadas: {len(todas_las_velas)}")
        if len(todas_las_velas) >= TOTAL_VELAS:
            break

    todas_las_velas = todas_las_velas[-TOTAL_VELAS:]

    with open(ARCHIVO, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
        for v in todas_las_velas:
            ts = datetime.utcfromtimestamp(v[0] / 1000).strftime("%Y-%m-%d %H:%M:%S")
            writer.writerow([ts, v[1], v[2], v[3], v[4], v[5]])

    print(f"\n[OK] Descarga completa.")
    print(f"[OK] Total de velas guardadas: {len(todas_las_velas)}")
    print(f"[OK] Archivo: {ARCHIVO}")

if __name__ == "__main__":
    descargar_historico_completo()
