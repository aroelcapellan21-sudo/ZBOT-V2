# =========================================
# liquidez_libro.py - Order Book Imbalance
# FIX: Rutas absolutas
# FIX: AVAXUSDT agregado al quinteto
# FIX: except pass eliminados
# MEJORA: Niveles de muro detectados
# MEJORA: Estado JSON para integracion
# Sin librerias externas. Constitucion RESPETADA
# =========================================

import os
import time
import json
import urllib.request
import urllib.parse
from datetime import datetime

ACTIVOS       = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'AVAXUSDT']
LIMITE_ORDENES = 20
INTERVALO     = 300  # 5 minutos

ARCHIVO_CSV   = os.path.expanduser("~/bot-padre-v2/data/muros_liquidez.csv")
ESTADO_JSON   = os.path.expanduser("~/bot-padre-v2/signals/estado_obi.json")

def obtener_order_book(symbol):
    try:
        params = urllib.parse.urlencode({"symbol": symbol, "limit": LIMITE_ORDENES})
        url    = f"https://api.binance.com/api/v3/depth?{params}"
        with urllib.request.urlopen(url, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"[OBI] Error order book {symbol}: {e}")
        return None

def calcular_obi(order_book):
    if not order_book:
        return None
    vol_compra = sum(float(bid[1]) for bid in order_book.get('bids', []))
    vol_venta  = sum(float(ask[1]) for ask in order_book.get('asks', []))
    if vol_compra + vol_venta == 0:
        return 0
    return round((vol_compra - vol_venta) / (vol_compra + vol_venta), 4)

def detectar_muros(order_book, precio_actual):
    """
    MEJORA: Detecta muros grandes en bids y asks.
    Un muro es una orden >= 3x el promedio del libro.
    """
    if not order_book or precio_actual == 0:
        return [], []

    bids = [(float(p), float(v)) for p, v in order_book.get('bids', [])]
    asks = [(float(p), float(v)) for p, v in order_book.get('asks', [])]

    if not bids or not asks:
        return [], []

    avg_bid_vol = sum(v for _, v in bids) / len(bids)
    avg_ask_vol = sum(v for _, v in asks) / len(asks)

    muros_compra = [
        {"precio": p, "volumen": round(v, 4), "distancia_pct": round(((precio_actual - p) / precio_actual) * 100, 3)}
        for p, v in bids if v >= avg_bid_vol * 3
    ]
    muros_venta = [
        {"precio": p, "volumen": round(v, 4), "distancia_pct": round(((p - precio_actual) / precio_actual) * 100, 3)}
        for p, v in asks if v >= avg_ask_vol * 3
    ]

    return muros_compra, muros_venta

def obtener_precio_actual(symbol):
    try:
        params = urllib.parse.urlencode({"symbol": symbol})
        url    = f"https://api.binance.com/api/v3/ticker/price?{params}"
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        return float(data["price"])
    except Exception as e:
        print(f"[OBI] Error precio {symbol}: {e}")
        return 0.0

def interpretar_obi(obi):
    if obi is None:
        return "SIN_DATOS"
    elif obi > 0.3:
        return "FUERTEMENTE_COMPRA"
    elif obi > 0.1:
        return "COMPRA"
    elif obi < -0.3:
        return "FUERTEMENTE_VENTA"
    elif obi < -0.1:
        return "VENTA"
    else:
        return "NEUTRAL"

def guardar_csv(timestamp, symbol, obi, interpretacion):
    try:
        os.makedirs(os.path.dirname(ARCHIVO_CSV), exist_ok=True)
        escribir_header = not os.path.exists(ARCHIVO_CSV) or os.path.getsize(ARCHIVO_CSV) == 0
        with open(ARCHIVO_CSV, "a") as f:
            if escribir_header:
                f.write("timestamp,symbol,obi,interpretacion\n")
            f.write(f"{timestamp},{symbol},OBI:{obi},{interpretacion}\n")
    except Exception as e:
        print(f"[OBI] Error guardando CSV: {e}")

def guardar_estado(resultados):
    try:
        os.makedirs(os.path.dirname(ESTADO_JSON), exist_ok=True)
        with open(ESTADO_JSON, 'w') as f:
            json.dump({
                "timestamp":  datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "resultados": resultados
            }, f, indent=2)
    except Exception as e:
        print(f"[OBI] Error guardando estado: {e}")

def chequear_muros():
    timestamp  = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    resultados = []

    print(f"\n[{timestamp}] 📊 ORDER BOOK IMBALANCE")
    print(f"  {'─'*44}")

    for symbol in ACTIVOS:
        order_book    = obtener_order_book(symbol)
        precio_actual = obtener_precio_actual(symbol)
        obi           = calcular_obi(order_book)
        interpretacion = interpretar_obi(obi)
        muros_compra, muros_venta = detectar_muros(order_book, precio_actual)

        obi_str = f"{obi:.4f}" if obi is not None else "N/A"

        emoji = "🟢" if interpretacion in ("COMPRA", "FUERTEMENTE_COMPRA") else \
                "🔴" if interpretacion in ("VENTA", "FUERTEMENTE_VENTA") else "⚪"

        print(f"  {emoji} {symbol}: OBI {obi_str} — {interpretacion}")

        if muros_compra:
            for m in muros_compra[:2]:
                print(f"     🛡️ Muro COMPRA: ${m['precio']} | Vol: {m['volumen']} | -{m['distancia_pct']}%")
        if muros_venta:
            for m in muros_venta[:2]:
                print(f"     🧱 Muro VENTA:  ${m['precio']} | Vol: {m['volumen']} | +{m['distancia_pct']}%")

        guardar_csv(timestamp, symbol, obi_str, interpretacion)

        resultados.append({
            "symbol":        symbol,
            "obi":           obi,
            "interpretacion": interpretacion,
            "muros_compra":  muros_compra[:3],
            "muros_venta":   muros_venta[:3]
        })

    print(f"  {'─'*44}")
    guardar_estado(resultados)

if __name__ == "__main__":
    os.makedirs(os.path.expanduser("~/bot-padre-v2/data"), exist_ok=True)
    os.makedirs(os.path.expanduser("~/bot-padre-v2/signals"), exist_ok=True)

    print("=" * 50)
    print("📊 liquidez_libro - Order Book Imbalance")
    print(f"   Activos  : {', '.join(ACTIVOS)}")
    print(f"   Intervalo: {INTERVALO}s")
    print("=" * 50)

    while True:
        try:
            chequear_muros()
            time.sleep(INTERVALO)
        except KeyboardInterrupt:
            print("\n🛑 liquidez_libro detenido")
            break
        except Exception as e:
            print(f"[OBI] Error en ciclo: {e}")
            time.sleep(10)

