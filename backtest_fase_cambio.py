# ============================================================
# backtest_fase_cambio.py
# Pregunta: Si las 376 posiciones FASE_CAMBIO hubieran
# continuado hasta TP o SL, ¿cuál sería el resultado real?
# SOLO LECTURA — no toca el bot ni auditoria.csv
# ============================================================

import csv
import json
import urllib.request
import urllib.parse
import time
from datetime import datetime, timezone

AUDITORIA = "/home/ariel/bot-padre-v2/auditoria.csv"

PARAMETROS = {
    "BTCUSDT": {
        "alcista": {"sl": 5.0, "tp": 6.0},
        "bajista": {"sl": 3.5, "tp": 4.0},
        "lateral": {"sl": 3.5, "tp": 4.0},
    },
    "ETHUSDT": {
        "alcista": {"sl": 4.5, "tp": 5.0},
        "bajista": {"sl": 3.0, "tp": 4.0},
        "lateral": {"sl": 4.5, "tp": 6.0},
    },
    "SOLUSDT": {
        "alcista": {"sl": 5.0, "tp": 6.0},
        "bajista": {"sl": 3.5, "tp": 5.0},
        "lateral": {"sl": 3.5, "tp": 4.0},
    },
    "BNBUSDT": {
        "alcista": {"sl": 4.5, "tp": 5.0},
        "bajista": {"sl": 3.5, "tp": 4.0},
        "lateral": {"sl": 4.5, "tp": 5.0},
    },
    "AVAXUSDT": {
        "alcista": {"sl": 4.5, "tp": 5.0},
        "bajista": {"sl": 3.5, "tp": 4.0},
        "lateral": {"sl": 5.0, "tp": 6.0},
    },
}

def fetch_velas_desde(symbol, desde_ts, limite=50):
    """Descarga velas 4H desde un timestamp dado."""
    params = urllib.parse.urlencode({
        "symbol": symbol,
        "interval": "4h",
        "startTime": desde_ts,
        "limit": limite
    })
    url = f"https://api.binance.com/api/v3/klines?{params}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        # Devuelve lista de (high, low, close)
        return [(float(k[2]), float(k[3]), float(k[4])) for k in data]
    except Exception as e:
        return []

def simular_trade(symbol, accion, precio_entrada, desde_ts):
    """
    Simula si el trade habría llegado a TP o SL.
    Devuelve: 'TP', 'SL', o 'TIMEOUT' (no llegó en 50 velas)
    """
    accion_key = accion.lower()
    if symbol not in PARAMETROS or accion_key not in PARAMETROS[symbol]:
        return "DESCONOCIDO", 0.0

    sl_pct = PARAMETROS[symbol][accion_key]["sl"] / 100
    tp_pct = PARAMETROS[symbol][accion_key]["tp"] / 100

    if accion_key == "bajista":
        precio_sl = precio_entrada * (1 + sl_pct)
        precio_tp = precio_entrada * (1 - tp_pct)
    else:
        precio_sl = precio_entrada * (1 - sl_pct)
        precio_tp = precio_entrada * (1 + tp_pct)

    velas = fetch_velas_desde(symbol, desde_ts)
    if not velas:
        return "ERROR", 0.0

    for (high, low, close) in velas:
        if accion_key == "bajista":
            if low <= precio_tp:
                cambio = ((precio_entrada - precio_tp) / precio_entrada) * 100
                return "TP", round(cambio, 2)
            if high >= precio_sl:
                cambio = ((precio_entrada - precio_sl) / precio_entrada) * 100
                return "SL", round(cambio, 2)
        else:
            if high >= precio_tp:
                cambio = ((precio_tp - precio_entrada) / precio_entrada) * 100
                return "TP", round(cambio, 2)
            if low <= precio_sl:
                cambio = ((precio_sl - precio_entrada) / precio_entrada) * 100
                return "SL", round(cambio, 2)

    cambio = ((close - precio_entrada) / precio_entrada) * 100
    return "TIMEOUT", round(cambio, 2)

def main():
    trades = []
    with open(AUDITORIA, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("estado", "").strip() == "FASE_CAMBIO":
                try:
                    ts_str  = row["timestamp"].strip()
                    ts_dt   = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                    ts_ms   = int(ts_dt.replace(tzinfo=timezone.utc).timestamp() * 1000)
                    trades.append({
                        "ts":     ts_str,
                        "ts_ms":  ts_ms,
                        "symbol": row["symbol"].strip(),
                        "accion": row["accion"].strip(),
                        "precio": float(row["precio"].strip()),
                    })
                except Exception as e:
                    continue

    print(f"\nTotal FASE_CAMBIO a simular: {len(trades)}")
    print("Descargando velas históricas de Binance (puede tardar unos minutos)...\n")

    resultados = {"TP": 0, "SL": 0, "TIMEOUT": 0, "ERROR": 0, "DESCONOCIDO": 0}
    ganancia_simulada = 0.0
    ganancia_real     = 0.0  # $0.12 promedio por FASE_CAMBIO
    monto_op          = 20.0
    detalles          = []

    for i, t in enumerate(trades):
        resultado, cambio_pct = simular_trade(
            t["symbol"], t["accion"], t["precio"], t["ts_ms"]
        )
        resultados[resultado] = resultados.get(resultado, 0) + 1

        if resultado == "TP":
            pnl = monto_op * (cambio_pct / 100)
        elif resultado == "SL":
            pnl = -monto_op * (abs(cambio_pct) / 100)
        else:
            pnl = monto_op * (cambio_pct / 100)

        ganancia_simulada += pnl
        ganancia_real     += 0.12  # lo que realmente ganó en promedio

        detalles.append({
            "ts":       t["ts"],
            "symbol":   t["symbol"],
            "accion":   t["accion"],
            "resultado": resultado,
            "cambio_pct": cambio_pct,
            "pnl":      round(pnl, 4)
        })

        if (i + 1) % 20 == 0:
            print(f"  Procesados {i+1}/{len(trades)}...")
        time.sleep(0.05)  # respetar rate limit Binance

    # ── Reporte ──────────────────────────────────────────────
    total_validos = resultados["TP"] + resultados["SL"]
    wr_simulado   = round(resultados["TP"] / total_validos * 100, 1) if total_validos else 0

    print("\n" + "="*55)
    print("RESULTADO DEL BACKTEST — SIN FASE_CAMBIO")
    print("="*55)
    print(f"Total trades simulados : {len(trades)}")
    print(f"  → TP (ganaron)       : {resultados['TP']}")
    print(f"  → SL (perdieron)     : {resultados['SL']}")
    print(f"  → TIMEOUT (50 velas) : {resultados['TIMEOUT']}")
    print(f"  → ERROR/DESCONOCIDO  : {resultados.get('ERROR',0) + resultados.get('DESCONOCIDO',0)}")
    print(f"\nWin Rate simulado      : {wr_simulado}%")
    print(f"PnL simulado total     : ${round(ganancia_simulada, 2)}")
    print(f"PnL real (FASE_CAMBIO) : ${round(ganancia_real, 2)}")
    print(f"Diferencia             : ${round(ganancia_simulada - ganancia_real, 2)}")
    print("="*55)

    # Guardar detalle
    reporte = "/home/ariel/bot-padre-v2/reports/backtest_fase_cambio.json"
    import os
    os.makedirs(os.path.dirname(reporte), exist_ok=True)
    with open(reporte, "w") as f:
        json.dump({"resumen": resultados, "wr": wr_simulado,
                   "pnl_simulado": round(ganancia_simulada,2),
                   "pnl_real": round(ganancia_real,2),
                   "detalles": detalles}, f, indent=2)
    print(f"\nDetalle guardado en: {reporte}")

if __name__ == "__main__":
    main()
