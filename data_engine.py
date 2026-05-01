import json
import urllib.request
import os

def fetch_candles(symbol, interval="4h", limit=100):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"[ERROR] Fetch {symbol}: {e}")
        return []

def calcular_rsi(precios, periodo=14):
    if len(precios) <= periodo: return 50
    ganancias = [max(precios[i] - precios[i-1], 0) for i in range(1, len(precios))]
    perdidas = [max(precios[i-1] - precios[i], 0) for i in range(1, len(precios))]
    avg_gain = sum(ganancias[-periodo:]) / periodo
    avg_loss = sum(perdidas[-periodo:]) / periodo
    if avg_loss == 0: return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calcular_ema(precios, periodo):
    if not precios: return 0
    if len(precios) < periodo: return precios[-1]
    k = 2 / (periodo + 1)
    ema = precios[0]
    for precio in precios[1:]:
        ema = (precio * k) + (ema * (1 - k))
    return round(ema, 2)

def preparar_datos_mercado(symbol, velas_raw):
    # Si ya es un diccionario (datos procesados), lo devolvemos tal cual
    if isinstance(velas_raw, dict):
        return velas_raw
        
    if not velas_raw or not isinstance(velas_raw, list):
        print(f"[ERROR] Datos invalidos para {symbol}: {type(velas_raw)}")
        return {"symbol": symbol, "last_close": 0, "rsi": 50, "ema_50": 0, "ema_200": 0}

    try:
        # Si las velas vienen como lista de listas (Binance)
        if isinstance(velas_raw[0], list):
            cierres = [float(k[4]) for k in velas_raw]
        else:
            # Si ya son solo una lista de precios
            cierres = [float(c) for c in velas_raw]
            
        return {
            "symbol": symbol,
            "last_close": cierres[-1],
            "rsi": calcular_rsi(cierres),
            "ema_50": calcular_ema(cierres, 50),
            "ema_200": calcular_ema(cierres, 200)
        }
    except Exception as e:
        print(f"[ERROR] Fallo critico en {symbol}: {e}")
        return {"symbol": symbol, "last_close": 0, "rsi": 50, "ema_50": 0, "ema_200": 0}
