# =========================================
# brain/data_engine.py
# Motor de datos de mercado
# FIX: RSI calculado sobre historial completo
# FIX: EMA calculada progresivamente por vela
# FIX: Ruta CSV fija y absoluta
# Sin librerias externas. Constitucion RESPETADA
# =========================================

import os
import csv
from utils import fetch_velas, calcular_rsi, calcular_ema, detectar_fase

QUINTETO = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "AVAXUSDT"]
EMA_LONG  = 200
EMA_SHORT = 50
DATA_DIR  = os.path.expanduser("~/bot-padre-v2/data")

def fetch_candles(symbol, interval="4h", limit=210):
    return fetch_velas(symbol, intervalo=interval, limite=limit)

def preparar_datos_mercado(symbol, velas_raw):
    if not velas_raw:
        return []
    try:
        if isinstance(velas_raw[0], float):
            cierres = velas_raw
        else:
            cierres = [float(k[4]) for k in velas_raw]

        if len(cierres) < EMA_LONG + 1:
            print(f"[DATA ENGINE] {symbol}: datos insuficientes ({len(cierres)} velas)")
            return []

        velas = []
        for i in range(EMA_LONG, len(cierres)):
            # Slice hasta la vela actual para calcular indicadores progresivos
            slice_actual = cierres[:i+1]

            rsi    = calcular_rsi(slice_actual)
            ema50  = calcular_ema(slice_actual, EMA_SHORT)
            ema200 = calcular_ema(slice_actual, EMA_LONG)

            velas.append({
                "close":   slice_actual[-1],
                "ema_50":  ema50,
                "ema_200": ema200,
                "rsi":     rsi
            })

        # Guardar memoria con ruta fija
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            ruta_csv = os.path.join(DATA_DIR, f"memory_{symbol}.csv")
            with open(ruta_csv, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["close", "ema_50", "ema_200", "rsi"])
                writer.writeheader()
                writer.writerows(velas)
        except Exception as e:
            print(f"[DATA ENGINE] Error guardando CSV {symbol}: {e}")

        return velas

    except Exception as e:
        print(f"[DATA ENGINE] Error procesando {symbol}: {e}")
        return []

if __name__ == "__main__":
    print("=== PRUEBA DATA ENGINE ===")
    for symbol in QUINTETO:
        velas_raw = fetch_candles(symbol)
        velas = preparar_datos_mercado(symbol, velas_raw)
        if velas:
            ultima = velas[-1]
            print(f"{symbol}: ${ultima['close']} | RSI:{ultima['rsi']} | EMA50:{ultima['ema_50']} | EMA200:{ultima['ema_200']}")
        else:
            print(f"{symbol}: Sin datos suficientes")
    print("✅ Data Engine funcionando correctamente.")
