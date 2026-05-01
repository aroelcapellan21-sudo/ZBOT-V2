# =========================================
# medidor_spread.py
# FIX: Si falla fetch bloquea en vez de permitir
# FIX: except pass eliminados
# Sin librerias externas. Constitucion RESPETADA
# =========================================

import json
import os
import urllib.request
import urllib.parse

TP_PCT        = 6.0
SPREAD_MAXIMO = TP_PCT * 0.08

def obtener_spread(symbol):
    try:
        params = urllib.parse.urlencode({"symbol": symbol})
        url    = f"https://api.binance.com/api/v3/ticker/bookTicker?{params}"
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        bid    = float(data["bidPrice"])
        ask    = float(data["askPrice"])
        spread = ((ask - bid) / bid) * 100
        return round(spread, 6), bid, ask
    except Exception as e:
        print(f"  [SPREAD] Error obteniendo spread {symbol}: {e}")
        return None, None, None

def spread_aceptable(symbol):
    spread, bid, ask = obtener_spread(symbol)

    if spread is None:
        # FIX: Si no se puede medir el spread, bloquear por seguridad
        print(f"  [SPREAD] ❌ No se pudo medir spread de {symbol}. Bloqueando operacion.")
        return False

    print(f"  [SPREAD] {symbol} | Bid: {bid} | Ask: {ask} | Spread: {spread}%")

    if spread > SPREAD_MAXIMO:
        print(f"  [SPREAD] ❌ Spread {spread}% supera limite {SPREAD_MAXIMO}%. No operar.")
        return False

    print(f"  [SPREAD] ✅ Spread aceptable ({spread}%). Puede operar.")
    return True

if __name__ == "__main__":
    simbolos = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "AVAXUSDT"]
    print("📊 Midiendo spreads del mercado...\n")
    for symbol in simbolos:
        spread_aceptable(symbol)
        print()
