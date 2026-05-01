# =========================================
# backtesting_anual.py
# Backtesting detector de fase por ano
# 2018 - 2024 desglose completo
# Sin librerias externas. Constitucion RESPETADA
# =========================================

import urllib.request
import urllib.parse
import json
from datetime import datetime
from utils import detectar_fase

ACTIVOS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "AVAXUSDT"]
UMBRAL = 3.0

ANOS = {
    2018: (1514764800000, 1546300800000),
    2019: (1546300800000, 1577836800000),
    2020: (1577836800000, 1609459200000),
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

def validar_fase(fase_detectada, cierres_futuros):
    if len(cierres_futuros) < 20:
        return None
    precio_entrada = cierres_futuros[0]
    maximo = max(cierres_futuros[:20])
    minimo = min(cierres_futuros[:20])
    subida_max = ((maximo - precio_entrada) / precio_entrada) * 100
    bajada_max = ((precio_entrada - minimo) / precio_entrada) * 100
    if fase_detectada == "ALCISTA":
        return "CORRECTO" if subida_max >= UMBRAL else "INCORRECTO"
    elif fase_detectada == "BAJISTA":
        return "CORRECTO" if bajada_max >= UMBRAL else "INCORRECTO"
    else:
        return "CORRECTO" if subida_max < UMBRAL and bajada_max < UMBRAL else "INCORRECTO"

def backtest_anual(symbol, ano, cierres):
    resultados = {
        "ALCISTA": {"correctos": 0, "incorrectos": 0},
        "BAJISTA": {"correctos": 0, "incorrectos": 0},
        "LATERAL": {"correctos": 0, "incorrectos": 0}
    }
    total = 0
    correctos_total = 0
    ventana = 210
    for i in range(ventana, len(cierres) - 20):
        segmento = cierres[i-ventana:i]
        futuros = cierres[i:i+20]
        fase = detectar_fase(segmento)
        if fase == "DESCONOCIDA":
            continue
        resultado = validar_fase(fase, futuros)
        if resultado is None:
            continue
        resultados[fase][resultado.lower() + "s"] += 1
        total += 1
        if resultado == "CORRECTO":
            correctos_total += 1
    if total == 0:
        return None
    precision = round((correctos_total/total)*100, 2)
    return {"ano": ano, "total": total, "correctos": correctos_total, "precision": precision, "desglose": resultados}

def main():
    print("="*55)
    print("BACKTESTING DETECTOR DE FASE POR ANO 2018-2024")
    print(f"Fecha  : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Umbral : {UMBRAL}%")
    print("="*55)

    for symbol in ACTIVOS:
        print(f"\n{'='*55}")
        print(f"ACTIVO: {symbol}")
        print(f"{'='*55}")
        cierres_total = []
        resultados_por_ano = []
        for ano, (start, end) in ANOS.items():
            print(f"  Descargando {ano}...", end=" ", flush=True)
            nuevos = fetch_historico_rango(symbol, start, end)
            print(f"{len(nuevos)} velas")
            cierres_total.extend(nuevos)
            if len(cierres_total) >= 230:
                res = backtest_anual(symbol, ano, cierres_total[-800:])
                if res:
                    resultados_por_ano.append(res)

        print(f"\n  {'ANO':<6} {'EVAL':>5} {'PREC':>7} {'ALCISTA':>10} {'BAJISTA':>10} {'LATERAL':>10}")
        print(f"  {'-'*50}")
        for r in resultados_por_ano:
            d = r["desglose"]
            def pct(fase):
                tot = d[fase]["correctos"] + d[fase]["incorrectos"]
                return f"{round(d[fase]['correctos']/tot*100)}%" if tot > 0 else "N/A"
            estado = "✅" if r["precision"] >= 60 else "❌"
            print(f"  {r['ano']:<6} {r['total']:>5} {r['precision']:>6}% {estado} {pct('ALCISTA'):>10} {pct('BAJISTA'):>10} {pct('LATERAL'):>10}")

    print(f"\n{'='*55}")
    print("COMPLETADO")
    print(f"{'='*55}")

if __name__ == "__main__":
    main()
