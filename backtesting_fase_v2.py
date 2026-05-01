# =========================================
# backtesting_fase_v2.py
# Metodologia final con filtro EMA200
# Umbrales especificos por activo
# Sin librerias externas. Constitucion RESPETADA
# =========================================

import urllib.request
import urllib.parse
import json
from datetime import datetime
from utils import detectar_fase, calcular_ema

ACTIVOS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "AVAXUSDT"]

UMBRALES = {
    "BTCUSDT":  {"7d": 1, "30d": 4},
    "ETHUSDT":  {"7d": 1, "30d": 3},
    "SOLUSDT":  {"7d": 3, "30d": 7},
    "BNBUSDT":  {"7d": 1, "30d": 2},
    "AVAXUSDT": {"7d": 2, "30d": 4}
}

ANOS = {
    2021: (1609459200000, 1640995200000),
    2022: (1640995200000, 1672531200000),
    2023: (1672531200000, 1704067200000),
    2024: (1704067200000, 1735689600000)
}

def fetch_historico_rango(symbol, start_ms, end_ms):
    todos = []
    url_base = "https://api.binance.com/api/v3/klines"
    current = start_ms
    while current < end_ms:
        params = urllib.parse.urlencode({
            "symbol": symbol,
            "interval": "4h",
            "startTime": current,
            "endTime": end_ms,
            "limit": 1000
        })
        url = f"{url_base}?{params}"
        try:
            with urllib.request.urlopen(url, timeout=15) as resp:
                data = json.loads(resp.read().decode())
            if not data:
                break
            todos.extend([float(k[4]) for k in data])
            current = data[-1][0] + 1
            if len(data) < 1000:
                break
        except Exception as e:
            print(f"Error {symbol}: {e}")
            break
    return todos

def etiquetar_tendencia_real(cierres, pos, umbral_7d, umbral_30d, velas_7d=42, velas_30d=180):
    if pos < velas_30d or pos + velas_30d >= len(cierres):
        return None
    precio_actual = cierres[pos]
    ema200 = calcular_ema(cierres[:pos], 200)
    precio_7d = cierres[pos - velas_7d]
    precio_30d = cierres[pos - velas_30d]
    cambio_7d = ((precio_actual - precio_7d) / precio_7d) * 100
    cambio_30d = ((precio_actual - precio_30d) / precio_30d) * 100
    if ema200 is None:
        return None
    if precio_actual > ema200 and cambio_7d > umbral_7d and cambio_30d > umbral_30d:
        return "ALCISTA"
    elif precio_actual < ema200 and cambio_7d < -umbral_7d and cambio_30d < -umbral_30d:
        return "BAJISTA"
    else:
        return "LATERAL"

def backtest_v2(symbol, cierres, umbral_7d, umbral_30d):
    resultados = {
        "ALCISTA": {"correctos": 0, "incorrectos": 0},
        "BAJISTA": {"correctos": 0, "incorrectos": 0},
        "LATERAL": {"correctos": 0, "incorrectos": 0}
    }
    total = 0
    correctos_total = 0
    ventana = 210

    for i in range(ventana, len(cierres) - 180):
        segmento = cierres[i-ventana:i]
        fase_detectada = detectar_fase(segmento)
        if fase_detectada == "DESCONOCIDA":
            continue
        tendencia_real = etiquetar_tendencia_real(cierres, i, umbral_7d, umbral_30d)
        if tendencia_real is None:
            continue
        resultado = "CORRECTO" if fase_detectada == tendencia_real else "INCORRECTO"
        resultados[fase_detectada][resultado.lower() + "s"] += 1
        total += 1
        if resultado == "CORRECTO":
            correctos_total += 1

    if total == 0:
        return None

    precision = round((correctos_total / total) * 100, 2)
    return {
        "total": total,
        "correctos": correctos_total,
        "precision": precision,
        "desglose": resultados
    }

def main():
    print("="*55)
    print("BACKTESTING DETECTOR DE FASE V2 - FILTRO EMA200")
    print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*55)

    resumen_final = {}

    for symbol in ACTIVOS:
        u7 = UMBRALES[symbol]["7d"]
        u30 = UMBRALES[symbol]["30d"]
        print(f"\n{'='*55}")
        print(f"ACTIVO: {symbol} | Umbral 7d: {u7}% | Umbral 30d: {u30}%")
        print(f"{'='*55}")

        cierres_total = []
        resultados_por_ano = []

        for ano, (start, end) in ANOS.items():
            print(f"  Descargando {ano}...", end=" ", flush=True)
            nuevos = fetch_historico_rango(symbol, start, end)
            print(f"{len(nuevos)} velas")
            cierres_total.extend(nuevos)

            if len(cierres_total) >= 400:
                res = backtest_v2(symbol, cierres_total, u7, u30)
                if res:
                    resultados_por_ano.append((ano, res))

        print(f"\n  {'ANO':<6} {'EVAL':>5} {'PREC':>7} {'ALCISTA':>10} {'BAJISTA':>10} {'LATERAL':>10}")
        print(f"  {'-'*50}")
        for ano, r in resultados_por_ano:
            d = r["desglose"]
            def pct(fase):
                tot = d[fase]["correctos"] + d[fase]["incorrectos"]
                return f"{round(d[fase]['correctos']/tot*100)}%" if tot > 0 else "N/A"
            estado = "✅" if r["precision"] >= 70 else "❌"
            print(f"  {ano:<6} {r['total']:>5} {r['precision']:>6}% {estado} {pct('ALCISTA'):>10} {pct('BAJISTA'):>10} {pct('LATERAL'):>10}")

        if resultados_por_ano:
            ultima_precision = resultados_por_ano[-1][1]["precision"]
            resumen_final[symbol] = ultima_precision

    print(f"\n{'='*55}")
    print("RESUMEN FINAL")
    print(f"{'='*55}")
    aprobados = 0
    for symbol, precision in resumen_final.items():
        estado = "✅ APROBADO" if precision >= 70 else "❌ REPROBADO"
        if precision >= 70:
            aprobados += 1
        print(f"{symbol}: {precision}% {estado}")

    if resumen_final:
        promedio = sum(resumen_final.values()) / len(resumen_final)
        print(f"\nPrecision promedio: {round(promedio, 2)}%")
        if aprobados == len(resumen_final):
            print("✅ DETECTOR APROBADO - Se puede soltar el freno")
        else:
            print(f"Aprobados: {aprobados}/5")
            print("❌ DETECTOR NECESITA AJUSTES")

if __name__ == "__main__":
    main()
