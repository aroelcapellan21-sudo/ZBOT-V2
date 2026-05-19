# =========================================
# director_orquesta.py
# Director de Orquesta General
# FIX: Spam Telegram eliminado (solo avisa si cambia fase)
# FIX: except desnudo eliminado
# FIX: Precio None si falla fetch
# FIX: Fase global controla activacion de directores
# Sin librerias externas. Constitucion RESPETADA
# =========================================

import urllib.request
import urllib.parse
import json
import time
import os
from datetime import datetime
from director_btc import dirigir as dirigir_btc
from director_eth import dirigir as dirigir_eth
from director_sol import dirigir as dirigir_sol
from director_bnb import dirigir as dirigir_bnb
from director_avax import dirigir as dirigir_avax
from engine import enviar_aviso
from memoria.memoria import registrar_evento
from utils import fetch_velas, detectar_fase
import db

MONEDAS   = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "AVAXUSDT"]
MODO_FILE = os.path.expanduser("~/bot-padre-v2/signals/modo.json")

def _leer_modo():
    try:
        with open(MODO_FILE) as f:
            cfg = json.load(f)
        return cfg.get("modo", "REAL"), cfg.get("intervalo_velas", "4h"), int(cfg.get("sleep_segundos", 240))
    except Exception:
        return "REAL", "4h", 240

def detectar_fase_global(intervalo="4h"):
    fases  = {}
    precios = {}

    for symbol in MONEDAS:
        cierres = fetch_velas(symbol, intervalo=intervalo, limite=210)
        if cierres:
            fases[symbol]  = detectar_fase(cierres, symbol=symbol)
            precios[symbol] = cierres[-1]
        else:
            fases[symbol]  = "DESCONOCIDA"
            precios[symbol] = None

    conteo = {"ALCISTA": 0, "BAJISTA": 0, "LATERAL": 0}
    for fase in fases.values():
        if fase in conteo:
            conteo[fase] += 1

    if conteo["BAJISTA"] >= 3:
        fase_global = "BAJISTA"
    elif conteo["ALCISTA"] >= 3:
        fase_global = "ALCISTA"
    else:
        fase_global = "LATERAL"

    return fase_global, fases, precios

def _precio_str(precios, symbol):
    p = precios.get(symbol)
    return f"${p}" if p is not None else "Sin datos"

def ejecutar_ciclo():
    modo, intervalo, _ = _leer_modo()
    previo = db.json_get("fase_orquesta")
    fase_anterior = previo.get("fase") if previo else None
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n{'='*60}")
    print(f"[DIRECTOR DE ORQUESTA] {timestamp}  [{modo} | {intervalo}]")
    print(f"{'='*60}")

    fase_global, fases, precios = detectar_fase_global(intervalo=intervalo)

    print(f"  BTCUSDT : {_precio_str(precios,'BTCUSDT')} | Fase: {fases['BTCUSDT']}")
    print(f"  ETHUSDT : {_precio_str(precios,'ETHUSDT')} | Fase: {fases['ETHUSDT']}")
    print(f"  SOLUSDT : {_precio_str(precios,'SOLUSDT')} | Fase: {fases['SOLUSDT']}")
    print(f"  BNBUSDT : {_precio_str(precios,'BNBUSDT')} | Fase: {fases['BNBUSDT']}")
    print(f"  AVAXUSDT: {_precio_str(precios,'AVAXUSDT')} | Fase: {fases['AVAXUSDT']}")
    print(f"  {'='*40}")
    print(f"  FASE GLOBAL: {fase_global}")
    print(f"{'='*60}")

    registrar_evento(
        f"ORQUESTA: Fase global {fase_global} | "
        f"BTC:{fases['BTCUSDT']} ETH:{fases['ETHUSDT']} "
        f"SOL:{fases['SOLUSDT']} BNB:{fases['BNBUSDT']} AVAX:{fases['AVAXUSDT']}"
    )

    if fase_anterior is not None and fase_global != fase_anterior:
        if fase_global == "BAJISTA":
            mensaje = (
                f"🔻 DIRECTOR DE ORQUESTA\n"
                f"Fase global: BAJISTA\n"
                f"BTC: {_precio_str(precios,'BTCUSDT')} | {fases['BTCUSDT']}\n"
                f"ETH: {_precio_str(precios,'ETHUSDT')} | {fases['ETHUSDT']}\n"
                f"SOL: {_precio_str(precios,'SOLUSDT')} | {fases['SOLUSDT']}\n"
                f"BNB: {_precio_str(precios,'BNBUSDT')} | {fases['BNBUSDT']}\n"
                f"AVAX: {_precio_str(precios,'AVAXUSDT')} | {fases['AVAXUSDT']}\n"
                f"Activando Francotiradores Bajistas"
            )
            enviar_aviso(mensaje)

        elif fase_global == "ALCISTA":
            mensaje = (
                f"🟢 DIRECTOR DE ORQUESTA\n"
                f"Fase global: ALCISTA\n"
                f"BTC: {_precio_str(precios,'BTCUSDT')} | {fases['BTCUSDT']}\n"
                f"ETH: {_precio_str(precios,'ETHUSDT')} | {fases['ETHUSDT']}\n"
                f"SOL: {_precio_str(precios,'SOLUSDT')} | {fases['SOLUSDT']}\n"
                f"BNB: {_precio_str(precios,'BNBUSDT')} | {fases['BNBUSDT']}\n"
                f"AVAX: {_precio_str(precios,'AVAXUSDT')} | {fases['AVAXUSDT']}\n"
                f"Activando Francotiradores Alcistas"
            )
            enviar_aviso(mensaje)

        elif fase_global == "LATERAL":
            enviar_aviso(
                f"⚖️ DIRECTOR DE ORQUESTA\n"
                f"Fase global: LATERAL\n"
                f"Directores en modo proteccion."
            )

    db.json_set("fase_orquesta", {"fase": fase_global, "timestamp": timestamp})

    # Directores solo se activan segun fase global
    if fase_global == "ALCISTA":
        print(f"  🟢 Activando Directores en modo ALCISTA")
        dirigir_btc("ALCISTA")
        dirigir_eth("ALCISTA")
        dirigir_sol("ALCISTA")
        dirigir_bnb("ALCISTA")
        dirigir_avax("ALCISTA")

    elif fase_global == "BAJISTA":
        print(f"  🔻 Activando Directores en modo BAJISTA")
        dirigir_btc("BAJISTA")
        dirigir_eth("BAJISTA")
        dirigir_sol("BAJISTA")
        dirigir_bnb("BAJISTA")
        dirigir_avax("BAJISTA")

    else:
        print(f"  ⚖️ Mercado lateral. Directores en modo proteccion.")
        dirigir_btc("LATERAL")
        dirigir_eth("LATERAL")
        dirigir_sol("LATERAL")
        dirigir_bnb("LATERAL")
        dirigir_avax("LATERAL")

    print(f"{'='*60}\n")

def orquestar():
    while True:
        try:
            ejecutar_ciclo()
        except Exception as e:
            registrar_evento(f"ORQUESTA ERROR: {e}")
            print(f"[DIRECTOR ORQUESTA] Error en ciclo: {e}")
        _, _, sleep_seg = _leer_modo()
        print(f"[DIRECTOR ORQUESTA] Próximo ciclo en {sleep_seg}s.")
        time.sleep(sleep_seg)

if __name__ == "__main__":
    orquestar()
