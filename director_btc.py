# =========================================
# director_btc.py
# Director de BTC
# FIX: Usa detectar_fase de utils (no duplicado)
# FIX: Usa fetch_velas de utils (no duplicado)
# FIX: Recibe fase_global desde Orquesta
# FIX: limit=210 para EMA200
# Sin librerias externas. Constitucion RESPETADA
# =========================================

from datetime import datetime
from francotirador_alcista_btc import evaluar as evaluar_alcista
from francotirador_bajista_btc import evaluar as evaluar_bajista
from francotirador_lateral_btc import evaluar as evaluar_lateral
from memoria.memoria import registrar_evento
from utils import fetch_velas, detectar_fase

SYMBOL = "BTCUSDT"

def dirigir(fase_global=None):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n{'='*50}")
    print(f"[DIRECTOR BTC] {timestamp}")
    print(f"{'='*50}")

    cierres = fetch_velas(SYMBOL, limite=210)
    if not cierres:
        print("[DIRECTOR BTC] Sin datos de mercado.")
        return

    # FIX: Usar fase recibida del Orquesta si viene, sino detectar local
    if fase_global:
        fase = fase_global
    else:
        fase = detectar_fase(cierres, symbol=SYMBOL)

    precio_actual = cierres[-1]
    cambio_30v    = round(((cierres[-1] - cierres[-30]) / cierres[-30]) * 100, 2)

    print(f"  Symbol  : {SYMBOL}")
    print(f"  Precio  : ${precio_actual}")
    print(f"  Cambio  : {cambio_30v}% ultimas 30 velas 4H")
    print(f"  Fase    : {fase}")
    print(f"{'='*50}")

    registrar_evento(f"DIRECTOR BTC: Fase {fase} | Precio ${precio_actual} | Cambio {cambio_30v}%")

    if fase == "ALCISTA":
        print(f"  ✅ Activando FRANCOTIRADOR ALCISTA BTC")
        evaluar_alcista()
    elif fase == "BAJISTA":
        print(f"  🔻 Activando FRANCOTIRADOR BAJISTA BTC")
        evaluar_bajista()
    elif fase == "LATERAL":
        print(f"  ⚖️ Activando FRANCOTIRADOR LATERAL BTC")
        evaluar_lateral()
    else:
        print(f"  ⏸️ Fase desconocida. Sin operacion.")
        registrar_evento(f"DIRECTOR BTC: Fase desconocida. Sin operacion.")

    print(f"{'='*50}\n")

if __name__ == "__main__":
    import time
    while True:
        dirigir()
        time.sleep(240)
