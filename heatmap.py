# =========================================
# heatmap.py - Mapa de Calor del Mercado
# FIX: Rutas absolutas
# FIX: except pass eliminados
# MEJORA: Estado JSON para integracion
# MEJORA: Señal global guardada en signals/
# Sin librerias externas. Constitucion RESPETADA
# =========================================

import json
import time
import urllib.request
import os
from datetime import datetime

MONEDAS     = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'AVAXUSDT']
ESTADO_JSON = os.path.expanduser("~/bot-padre-v2/signals/estado_heatmap.json")
INTERVALO   = 60

def obtener_cambios_24h():
    url = "https://api.binance.com/api/v3/ticker/24hr"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            datos = json.loads(resp.read().decode())
        return {
            item['symbol']: round(float(item['priceChangePercent']), 2)
            for item in datos if item['symbol'] in MONEDAS
        }
    except Exception as e:
        print(f"[HEATMAP] Error obteniendo datos: {e}")
        return None

def clasificar(cambios):
    lideres    = []
    seguidores = []
    muertos    = []
    for symbol, cambio in cambios.items():
        if cambio >= 2.0:
            lideres.append((symbol, cambio))
        elif cambio >= -1.0:
            seguidores.append((symbol, cambio))
        else:
            muertos.append((symbol, cambio))
    return lideres, seguidores, muertos

def emoji_cambio(cambio):
    if cambio >= 3.0:  return "🟢🟢"
    if cambio >= 1.0:  return "🟢"
    if cambio >= -1.0: return "🟡"
    if cambio >= -3.0: return "🔴"
    return "🔴🔴"

def diagnostico(lideres, seguidores, muertos):
    n_lid = len(lideres)
    n_seg = len(seguidores)
    n_mue = len(muertos)
    if n_lid >= 3:
        return "FIESTA_GENERAL",    "Dinero distribuido en el mercado"
    elif n_lid <= 1 and n_mue >= 2:
        return "CONCENTRADO",       "Dinero concentrado en pocos activos"
    elif n_mue >= 3:
        return "MERCADO_FRIO",      "Mayoria en rojo"
    elif n_seg >= 3:
        return "LATERAL",           "Sin direccion clara"
    else:
        return "MIXTO",             "Mercado mixto — observar"

def guardar_estado(cambios, lideres, seguidores, muertos, diag_codigo, diag_texto):
    try:
        os.makedirs(os.path.dirname(ESTADO_JSON), exist_ok=True)
        with open(ESTADO_JSON, 'w') as f:
            json.dump({
                "timestamp":    datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "cambios_24h":  cambios,
                "lideres":      [s for s, _ in lideres],
                "seguidores":   [s for s, _ in seguidores],
                "muertos":      [s for s, _ in muertos],
                "diagnostico":  diag_codigo,
                "descripcion":  diag_texto,
                "mercado_sano": diag_codigo in ("FIESTA_GENERAL", "MIXTO")
            }, f, indent=2)
    except Exception as e:
        print(f"[HEATMAP] Error guardando estado: {e}")

if __name__ == "__main__":
    print("=" * 50)
    print("🗺️  heatmap - Mapa de Calor del Mercado")
    print(f"   Activos  : {', '.join(MONEDAS)}")
    print(f"   Intervalo: {INTERVALO}s")
    print("=" * 50)

    while True:
        try:
            cambios = obtener_cambios_24h()
            if cambios:
                lideres, seguidores, muertos    = clasificar(cambios)
                diag_codigo, diag_texto         = diagnostico(lideres, seguidores, muertos)

                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 🗺️  MAPA DE CALOR")
                print(f"  {'─'*38}")

                print(f"  🏆 LIDERES ({len(lideres)}):")
                for s, c in sorted(lideres, key=lambda x: -x[1]):
                    print(f"     {emoji_cambio(c)} {s}: {c:+.2f}%")

                print(f"  😐 SEGUIDORES ({len(seguidores)}):")
                for s, c in sorted(seguidores, key=lambda x: -x[1]):
                    print(f"     {emoji_cambio(c)} {s}: {c:+.2f}%")

                print(f"  💀 MUERTOS ({len(muertos)}):")
                for s, c in sorted(muertos, key=lambda x: -x[1]):
                    print(f"     {emoji_cambio(c)} {s}: {c:+.2f}%")

                print(f"  {'─'*38}")
                print(f"  📊 {diag_codigo}: {diag_texto}")

                guardar_estado(cambios, lideres, seguidores, muertos, diag_codigo, diag_texto)

            time.sleep(INTERVALO)

        except KeyboardInterrupt:
            print("\n🛑 heatmap detenido")
            break
        except Exception as e:
            print(f"[HEATMAP] Error en ciclo: {e}")
            time.sleep(10)
