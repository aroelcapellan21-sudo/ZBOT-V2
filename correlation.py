# =========================================
# correlation.py - Radar de Correlacion
# FIX: Rutas absolutas
# FIX: except pass eliminados
# MEJORA: Estado JSON para integracion
# MEJORA: Señal de fuga guardada en signals/
# Sin librerias externas. Constitucion RESPETADA
# =========================================

import json
import time
import urllib.request
import os
import math
from datetime import datetime

LEADER    = 'BTCUSDT'
ARSENAL   = ['ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'AVAXUSDT']
ALL       = [LEADER] + ARSENAL

ESTADO_JSON = os.path.expanduser("~/bot-padre-v2/signals/estado_correlacion.json")

VENTANA   = 30
INTERVALO = 10

historial = {s: [] for s in ALL}

def obtener_precios():
    url = "https://api.binance.com/api/v3/ticker/price"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            datos = json.loads(resp.read().decode())
        return {
            item['symbol']: float(item['price'])
            for item in datos if item['symbol'] in ALL
        }
    except Exception as e:
        print(f"[CORRELACION] Error precios: {e}")
        return None

def retornos(serie):
    if len(serie) < 2:
        return []
    return [((serie[i] - serie[i-1]) / serie[i-1]) * 100 for i in range(1, len(serie))]

def calcular_correlacion(serie_a, serie_b):
    if len(serie_a) < 5 or len(serie_b) < 5:
        return None
    n      = min(len(serie_a), len(serie_b))
    a      = serie_a[-n:]
    b      = serie_b[-n:]
    med_a  = sum(a) / n
    med_b  = sum(b) / n
    num    = sum((a[i] - med_a) * (b[i] - med_b) for i in range(n))
    den_a  = math.sqrt(sum((x - med_a) ** 2 for x in a))
    den_b  = math.sqrt(sum((x - med_b) ** 2 for x in b))
    if den_a == 0 or den_b == 0:
        return None
    return round(num / (den_a * den_b), 4)

def interpretar(corr):
    if corr is None:
        return "CALIBRANDO", ""
    if corr >= 0.85:
        return "MUY_PEGADO",    "Sigue a BTC casi exacto"
    if corr >= 0.60:
        return "PEGADO",        "Correlacion moderada con BTC"
    if corr >= 0.30:
        return "SOLTANDOSE",    "Posible movimiento propio"
    return "SUELTO",            "Alta probabilidad de fuga independiente"

def emoji_corr(corr):
    if corr is None:  return "⏳"
    if corr >= 0.85:  return "🔗"
    if corr >= 0.60:  return "📎"
    if corr >= 0.30:  return "🌀"
    return "💥"

def guardar_estado(correlaciones, muestras):
    try:
        os.makedirs(os.path.dirname(ESTADO_JSON), exist_ok=True)
        fugas      = [s for s, v in correlaciones.items() if v['correlacion'] is not None and v['correlacion'] < 0.30]
        soltandose = [s for s, v in correlaciones.items() if v['correlacion'] is not None and 0.30 <= v['correlacion'] < 0.60]
        with open(ESTADO_JSON, 'w') as f:
            json.dump({
                "timestamp":    datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "lider":        LEADER,
                "muestras":     muestras,
                "correlaciones": correlaciones,
                "fugas":        fugas,
                "soltandose":   soltandose,
                "mercado_correlacionado": len(fugas) == 0 and len(soltandose) == 0
            }, f, indent=2)
    except Exception as e:
        print(f"[CORRELACION] Error guardando estado: {e}")

if __name__ == "__main__":
    print("=" * 50)
    print("🎯 correlation - Radar de Correlacion con BTC")
    print(f"   Lider   : {LEADER}")
    print(f"   Arsenal : {', '.join(ARSENAL)}")
    print(f"   Ventana : {VENTANA} lecturas")
    print("=" * 50)

    ciclo = 0

    while True:
        try:
            precios = obtener_precios()
            if precios:
                for s in ALL:
                    if s in precios:
                        historial[s].append(precios[s])
                        if len(historial[s]) > VENTANA + 1:
                            historial[s].pop(0)

                ret_btc       = retornos(historial[LEADER])
                correlaciones = {}
                ciclo        += 1

                for symbol in ARSENAL:
                    ret_alt = retornos(historial[symbol])
                    corr    = calcular_correlacion(ret_btc, ret_alt)
                    estado, detalle = interpretar(corr)
                    correlaciones[symbol] = {
                        "correlacion": corr,
                        "estado":      estado,
                        "detalle":     detalle
                    }

                muestras = len(historial[LEADER])

                if ciclo % 6 == 0:
                    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 🎯 CORRELACION ({muestras}/{VENTANA})")
                    print(f"  {'─'*42}")
                    for symbol in ARSENAL:
                        v        = correlaciones[symbol]
                        corr_str = f"{v['correlacion']:.4f}" if v['correlacion'] is not None else "N/A"
                        print(f"  {emoji_corr(v['correlacion'])} {symbol}: {corr_str} — {v['estado']}")

                    fugas      = [s for s, v in correlaciones.items() if v['correlacion'] is not None and v['correlacion'] < 0.30]
                    soltandose = [s for s, v in correlaciones.items() if v['correlacion'] is not None and 0.30 <= v['correlacion'] < 0.60]
                    print(f"  {'─'*42}")
                    if fugas:
                        print(f"  💥 FUGA: {', '.join(fugas)}")
                    elif soltandose:
                        print(f"  🌀 Soltandose: {', '.join(soltandose)}")
                    else:
                        print(f"  🔗 Mercado correlacionado")

                guardar_estado(correlaciones, muestras)

            time.sleep(INTERVALO)

        except KeyboardInterrupt:
            print("\n🛑 correlation detenido")
            break
        except Exception as e:
            print(f"[CORRELACION] Error: {e}")
            time.sleep(10)
