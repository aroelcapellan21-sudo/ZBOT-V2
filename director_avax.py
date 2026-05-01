# =========================================
# director_avax.py
# Director de AVAX
# FIX: Usa detectar_fase de utils (no duplicado)
# FIX: Usa fetch_velas de utils (no duplicado)
# FIX: Recibe fase_global desde Orquesta
# FIX: limit=210 para EMA200
# Sin librerias externas. Constitucion RESPETADA
# =========================================

from datetime import datetime
from francotirador_alcista_avax import evaluar as evaluar_alcista
from francotirador_bajista_avax import evaluar as evaluar_bajista
from francotirador_lateral_avax import evaluar as evaluar_lateral
from memoria.memoria import registrar_evento
from utils import fetch_velas, detectar_fase

SYMBOL = "AVAXUSDT"

def dirigir(fase_global=None):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n{'='*50}")
    print(f"[DIRECTOR AVAX] {timestamp}")
    print(f"{'='*50}")

    cierres = fetch_velas(SYMBOL, limite=210)
    if not cierres:
        print("[DIRECTOR AVAX] Sin datos de mercado.")
        return

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

    registrar_evento(f"DIRECTOR AVAX: Fase {fase} | Precio ${precio_actual} | Cambio {cambio_30v}%")

    if fase == "ALCISTA":
        print(f"  ✅ Activando FRANCOTIRADOR ALCISTA AVAX")
        evaluar_alcista()
    elif fase == "BAJISTA":
        print(f"  🔻 Activando FRANCOTIRADOR BAJISTA AVAX")
        evaluar_bajista()
    elif fase == "LATERAL":
        print(f"  ⚖️ Activando FRANCOTIRADOR LATERAL AVAX")
        evaluar_lateral()
    else:
        print(f"  ⏸️ Fase desconocida. Sin operacion.")
        registrar_evento(f"DIRECTOR AVAX: Fase desconocida. Sin operacion.")

    print(f"{'='*50}\n")

if __name__ == "__main__":
    import time
    while True:
        dirigir()
        time.sleep(240)
