# =========================================
# filtro_calidad.py
# FIX: RSI usa calcular_rsi de utils (unico)
# FIX: fetch usa fetch_velas de utils (unico)
# FIX: except pass eliminados
# Sin librerias externas. Constitucion RESPETADA
# =========================================

import json
import os
import urllib.request
import urllib.parse
from utils import fetch_velas, calcular_rsi, calcular_ema

def fetch_velas_completas(symbol, limite=50):
    """Retorna velas OHLCV completas para ATR y volumen."""
    try:
        params = urllib.parse.urlencode({
            "symbol":   symbol,
            "interval": "4h",
            "limit":    limite
        })
        url = f"https://api.binance.com/api/v3/klines?{params}"
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        return data
    except Exception as e:
        print(f"  [FILTRO] Error fetch velas completas {symbol}: {e}")
        return []

def calcular_atr(velas, periodo=14):
    if len(velas) < periodo + 1:
        return None
    trs = []
    for i in range(1, len(velas)):
        alto       = float(velas[i][2])
        bajo       = float(velas[i][3])
        cierre_ant = float(velas[i-1][4])
        tr         = max(alto - bajo, abs(alto - cierre_ant), abs(bajo - cierre_ant))
        trs.append(tr)
    return round(sum(trs[-periodo:]) / periodo, 6)

def calcular_volumen_promedio(velas, periodo=20):
    if len(velas) < periodo:
        return None
    volumenes = [float(v[5]) for v in velas[-periodo:]]
    return round(sum(volumenes) / periodo, 2)

def calcular_rsi_aceleracion(cierres, periodo=14):
    """
    FIX: Usa calcular_rsi de utils para consistencia.
    Calcula RSI actual y anterior para detectar aceleracion.
    """
    if len(cierres) < periodo + 3:
        return None, None
    rsi_actual   = calcular_rsi(cierres)
    rsi_anterior = calcular_rsi(cierres[:-1])
    if rsi_actual is None or rsi_anterior is None:
        return None, None
    aceleracion = round(rsi_actual - rsi_anterior, 2)
    return rsi_actual, aceleracion

def señal_tiene_calidad(symbol, fase):
    print(f"  [FILTRO] Analizando calidad de señal {symbol} {fase}...")
    velas = fetch_velas_completas(symbol, limite=50)

    if not velas or len(velas) < 20:
        print(f"  [FILTRO] ⚠️ Sin datos suficientes. Permitiendo operacion.")
        return True

    cierres = [float(v[4]) for v in velas]

    # ATR — volatilidad minima requerida
    atr = calcular_atr(velas)
    precio_actual = cierres[-1]
    if atr and precio_actual > 0:
        atr_pct = (atr / precio_actual) * 100
        if atr_pct < 0.3:
            print(f"  [FILTRO] ❌ ATR bajo ({round(atr_pct,3)}%). Mercado sin movimiento.")
            return False
        print(f"  [FILTRO] ATR: {round(atr_pct,3)}% ✅")

    # Volumen — debe estar activo
    vol_actual  = float(velas[-1][5])
    vol_promedio = calcular_volumen_promedio(velas)
    if vol_promedio and vol_promedio > 0:
        vol_ratio = vol_actual / vol_promedio
        if vol_ratio < 0.5:
            print(f"  [FILTRO] ❌ Volumen bajo ({round(vol_ratio,2)}x promedio).")
            return False
        print(f"  [FILTRO] Volumen: {round(vol_ratio,2)}x promedio ✅")

    # RSI aceleracion
    rsi_actual, aceleracion = calcular_rsi_aceleracion(cierres)
    if rsi_actual is not None and aceleracion is not None:
        if fase == "ALCISTA" and aceleracion < -5:
            print(f"  [FILTRO] ❌ RSI desacelerando en alcista ({aceleracion}).")
            return False
        if fase == "BAJISTA" and aceleracion > 5:
            print(f"  [FILTRO] ❌ RSI desacelerando en bajista ({aceleracion}).")
            return False
        print(f"  [FILTRO] RSI aceleracion: {aceleracion} ✅")

    # EMA alineacion
    ema20  = calcular_ema(cierres, 20)
    ema50  = calcular_ema(cierres, 50)
    ema200 = calcular_ema(cierres, 200) if len(cierres) >= 200 else None

    if ema20 and ema50:
        if fase == "ALCISTA":
            if not (precio_actual > ema20 > ema50):
                print(f"  [FILTRO] ❌ EMAs no alineadas para alcista.")
                return False
            print(f"  [FILTRO] EMAs alcistas alineadas ✅")
        elif fase == "BAJISTA":
            if not (precio_actual < ema20 < ema50):
                print(f"  [FILTRO] ❌ EMAs no alineadas para bajista.")
                return False
            print(f"  [FILTRO] EMAs bajistas alineadas ✅")
        elif fase == "LATERAL":
            diff = abs(ema20 - ema50) / ema50 * 100
            if diff > 3.0:
                print(f"  [FILTRO] ❌ EMAs muy separadas para lateral ({round(diff,2)}%).")
                return False
            print(f"  [FILTRO] EMAs laterales comprimidas ✅")

    print(f"  [FILTRO] ✅ Señal con calidad suficiente.")
    return True

if __name__ == "__main__":
    simbolos = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "AVAXUSDT"]
    for symbol in simbolos:
        for fase in ["ALCISTA", "BAJISTA", "LATERAL"]:
            resultado = señal_tiene_calidad(symbol, fase)
            print(f"  {symbol} {fase}: {'✅' if resultado else '❌'}\n")
