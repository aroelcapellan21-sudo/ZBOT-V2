# =========================================
# descargar_historico.py
# Descarga 1 año de velas horarias de
# ETH, SOL, BNB y AVAX desde Binance.
# Guarda cada una en data/
# =========================================

import urllib.request
import urllib.parse
import json
import csv
import os
import time
from datetime import datetime, timedelta

API_URL  = "https://api.binance.com/api/v3/klines"
MONEDAS  = ["ETHUSDT", "SOLUSDT", "BNBUSDT", "AVAXUSDT"]
INTERVAL = "1h"
LIMITE   = 1000  # Max por request

def fetch_candles(symbol, start_ms, end_ms):
    params = urllib.parse.urlencode({
        "symbol":    symbol,
        "interval":  INTERVAL,
        "startTime": start_ms,
        "endTime":   end_ms,
        "limit":     LIMITE
    })
    url = f"{API_URL}?{params}"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"[ERROR] {symbol}: {e}")
        return []

def descargar(symbol):
    print(f"[INFO] Descargando {symbol}...")
    ahora     = datetime.utcnow()
    hace_un_año = ahora - timedelta(days=365)
    start_ms  = int(hace_un_año.timestamp() * 1000)
    end_ms    = int(ahora.timestamp() * 1000)

    todas = []
    cursor = start_ms

    while cursor < end_ms:
        velas = fetch_candles(symbol, cursor, end_ms)
        if not velas:
            break
        todas.extend(velas)
        cursor = velas[-1][0] + 1  # siguiente vela
        print(f"  [{symbol}] Velas descargadas: {len(todas)}", end="\r")
        time.sleep(0.3)  # respetar rate limit

    print(f"\n  [{symbol}] Total: {len(todas)} velas")
    return todas

def guardar(symbol, velas):
    os.makedirs("data", exist_ok=True)
    nombre = f"data/{symbol.lower().replace('usdt','')}_1h.csv"
    with open(nombre, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
        for v in velas:
            ts = datetime.utcfromtimestamp(v[0] / 1000).strftime("%Y-%m-%d %H:%M:%S")
            writer.writerow([ts, v[1], v[2], v[3], v[4], v[5]])
    print(f"  [{symbol}] Guardado en: {nombre}")

if __name__ == "__main__":
    print("=" * 45)
    print("  DESCARGA DE HISTORICOS — QUINTETO")
    print("=" * 45)
    for moneda in MONEDAS:
        velas = descargar(moneda)
        if velas:
            guardar(moneda, velas)
        print()
    print("=" * 45)
    print("  Descarga completada.")
    print("=" * 45)

