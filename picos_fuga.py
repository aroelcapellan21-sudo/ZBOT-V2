# =========================================
# picos_fuga.py - Memoria de Retrocesos
# FIX: Rutas absolutas
# FIX: except pass eliminados
# MEJORA: Estado JSON para integracion
# Sin librerias externas. Constitucion RESPETADA
# =========================================

import json
import time
import urllib.request
import os
from datetime import datetime

MONEDAS           = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'AVAXUSDT']
ARCHIVO_CSV       = os.path.expanduser("~/bot-padre-v2/data/memoria_fugas.csv")
ESTADO_JSON       = os.path.expanduser("~/bot-padre-v2/signals/estado_fugas.json")

RETROCESO_MINIMO  = 0.5
RETROCESO_MAXIMO  = 5.0
INTERVALO         = 30

maximos_sesion       = {m: None for m in MONEDAS}
historial_retrocesos = {m: [] for m in MONEDAS}
_dia_actual          = datetime.now().date()

def obtener_precios():
    url = "https://api.binance.com/api/v3/ticker/price"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            datos = json.loads(resp.read().decode())
        return {
            item['symbol']: float(item['price'])
            for item in datos if item['symbol'] in MONEDAS
        }
    except Exception as e:
        print(f"[FUGAS] Error precios: {e}")
        return None

def cargar_historial():
    if not os.path.exists(ARCHIVO_CSV):
        return
    try:
        with open(ARCHIVO_CSV, 'r') as f:
            lineas = f.readlines()[1:]
        for linea in lineas:
            partes = linea.strip().split(',')
            if len(partes) >= 5:
                symbol = partes[1]
                if symbol in historial_retrocesos:
                    try:
                        retroceso = float(partes[4].replace('%', ''))
                        historial_retrocesos[symbol].append(retroceso)
                    except:
                        pass
    except Exception as e:
        print(f"[FUGAS] Error cargando historial: {e}")

def retroceso_normal(symbol, retroceso):
    historial = historial_retrocesos[symbol]
    if len(historial) < 10:
        return True, 50
    menores   = sum(1 for r in historial if r < retroceso)
    percentil = round((menores / len(historial)) * 100, 1)
    return percentil < 80, percentil

def registrar_retroceso(symbol, maximo, actual, retroceso, es_normal, percentil):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        os.makedirs(os.path.dirname(ARCHIVO_CSV), exist_ok=True)
        escribir_header = not os.path.exists(ARCHIVO_CSV) or os.path.getsize(ARCHIVO_CSV) == 0
        with open(ARCHIVO_CSV, 'a') as f:
            if escribir_header:
                f.write("timestamp,symbol,maximo,actual,retroceso,es_normal,percentil\n")
            f.write(f"{timestamp},{symbol},{maximo:.4f},{actual:.4f},{retroceso:.2f}%,{es_normal},{percentil}%\n")
    except Exception as e:
        print(f"[FUGAS] Error guardando CSV: {e}")

def guardar_estado(alertas):
    try:
        os.makedirs(os.path.dirname(ESTADO_JSON), exist_ok=True)
        with open(ESTADO_JSON, 'w') as f:
            json.dump({
                "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "alertas":   alertas,
                "total":     len(alertas)
            }, f, indent=2)
    except Exception as e:
        print(f"[FUGAS] Error guardando estado: {e}")

def actualizar_maximos(precios):
    alertas = []
    for symbol in MONEDAS:
        precio_act = precios.get(symbol)
        if precio_act is None:
            continue
        if maximos_sesion[symbol] is None:
            maximos_sesion[symbol] = precio_act
            continue
        if precio_act > maximos_sesion[symbol]:
            maximos_sesion[symbol] = precio_act
        else:
            retroceso = ((maximos_sesion[symbol] - precio_act) / maximos_sesion[symbol]) * 100
            if RETROCESO_MINIMO <= retroceso <= RETROCESO_MAXIMO:
                es_normal, percentil = retroceso_normal(symbol, retroceso)
                historial_retrocesos[symbol].append(retroceso)
                if not es_normal:
                    registrar_retroceso(symbol, maximos_sesion[symbol], precio_act, retroceso, es_normal, percentil)
                    alertas.append({
                        "symbol":    symbol,
                        "retroceso": round(retroceso, 2),
                        "percentil": percentil,
                        "maximo":    round(maximos_sesion[symbol], 4),
                        "actual":    round(precio_act, 4)
                    })
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ {symbol}: Retroceso {retroceso:.2f}% ANORMAL (p{percentil})")
                else:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] ✓ {symbol}: Retroceso {retroceso:.2f}% normal (p{percentil})")
    return alertas

def limpiar_maximos_diarios():
    global _dia_actual
    hoy = datetime.now().date()
    if hoy != _dia_actual:
        for symbol in MONEDAS:
            maximos_sesion[symbol] = None
        _dia_actual = hoy
        print("[FUGAS] Maximos diarios reseteados")

if __name__ == "__main__":
    print("=" * 50)
    print("🧠 picos_fuga - Memoria de Retrocesos")
    print(f"   Monedas  : {', '.join(MONEDAS)}")
    print(f"   Intervalo: {INTERVALO}s")
    print("=" * 50)

    cargar_historial()

    while True:
        try:
            precios = obtener_precios()
            if precios:
                alertas = actualizar_maximos(precios)
                guardar_estado(alertas)
                limpiar_maximos_diarios()
            time.sleep(INTERVALO)

        except KeyboardInterrupt:
            print("\n🛑 picos_fuga detenido")
            break
        except Exception as e:
            print(f"[FUGAS] Error en ciclo: {e}")
            time.sleep(10)
