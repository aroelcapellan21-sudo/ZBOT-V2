# =========================================
# director_sol.py
# Director de SOL
# FIX: Usa detectar_fase de utils (no duplicado)
# FIX: Usa fetch_velas de utils (no duplicado)
# FIX: Recibe fase_global desde Orquesta
# FIX: limit=210 para EMA200
# Sin librerias externas. Constitucion RESPETADA
# =========================================

from datetime import datetime
from francotirador_alcista_sol import (evaluar as evaluar_alcista,
                                       revisar_cierres as cierres_alcista)
from francotirador_bajista_sol import (evaluar as evaluar_bajista,
                                       revisar_cierres as cierres_bajista)
from francotirador_lateral_sol import (evaluar as evaluar_lateral,
                                       revisar_cierres as cierres_lateral)
from memoria.memoria import registrar_evento
from utils import fetch_velas, detectar_fase

SYMBOL = "SOLUSDT"

def _proteger_otras_fases(fase_activa, precio_actual):
    """
    revisar_cierres() de cada francotirador filtra por su propio TIPO_TRADE
    (partes[1] == TIPO_TRADE), asi que una posicion abierta en una fase deja de
    tener TP/SL en cuanto la fase LOCAL de la moneda cambia a otra: el director
    enruta al francotirador de la fase nueva, que no ve la fila de la vieja.

    cerrar_huerfanas() en director_orquesta.py no cubre esto: solo se dispara
    cuando cambia la fase GLOBAL (415 veces en el historico de eventos.log,
    contra 2152 cambios de fase local -- 5.2x mas frecuentes). Caso real: la
    posicion BTC ALCISTA del 30-ago-2026 quedo sin stop al pasar la fase local
    a LATERAL, y termino cerrada a mano con -2.41%.

    Se corren solo las fases que NO se evaluan este ciclo. La activa ya llama a
    revisar_cierres dentro de su propio evaluar(), y duplicarla cambiaria el
    comportamiento: evaluar() hace return temprano cuando revisar_cierres
    devuelve True, asi que cerrar aca la posicion de la fase activa le
    permitiria abrir una nueva en el mismo ciclo.

    evaluar_tp=True porque este es un gate de FASE, no de entrada -- mismo
    criterio que gestor_bajistas y que la pausa de SOL/AVAX lateral (commit
    5713c0a). Ver CLAUDE.md, "Patron obligatorio de salidas vs. gates de
    entrada".
    """
    for nombre, revisar in (("ALCISTA", cierres_alcista),
                            ("BAJISTA", cierres_bajista),
                            ("LATERAL", cierres_lateral)):
        if nombre == fase_activa:
            continue
        try:
            revisar(precio_actual, evaluar_tp=True)
        except Exception as e:
            print(f"  [PROTECCION {nombre}] Error revisando cierres: {e}")
            registrar_evento(
                f"DIRECTOR SOL: fallo proteccion cross-fase {nombre}: {e}")

def dirigir(fase_global=None):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n{'='*50}")
    print(f"[DIRECTOR SOL] {timestamp}")
    print(f"{'='*50}")

    cierres = fetch_velas(SYMBOL, limite=210)
    if not cierres:
        print("[DIRECTOR SOL] Sin datos de mercado.")
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

    registrar_evento(f"DIRECTOR SOL: Fase {fase} | Precio ${precio_actual} | Cambio {cambio_30v}%")

    _proteger_otras_fases(fase, precio_actual)

    if fase == "ALCISTA":
        print(f"  ✅ Activando FRANCOTIRADOR ALCISTA SOL")
        evaluar_alcista()
    elif fase == "BAJISTA":
        print(f"  🔻 Activando FRANCOTIRADOR BAJISTA SOL")
        evaluar_bajista()
    elif fase == "LATERAL":
        print(f"  ⚖️ Activando FRANCOTIRADOR LATERAL SOL")
        evaluar_lateral()
    else:
        print(f"  ⏸️ Fase desconocida. Sin operacion.")
        registrar_evento(f"DIRECTOR SOL: Fase desconocida. Sin operacion.")

    print(f"{'='*50}\n")

if __name__ == "__main__":
    import time
    while True:
        dirigir()
        time.sleep(240)
