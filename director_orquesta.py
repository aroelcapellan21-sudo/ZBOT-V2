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
import fcntl
from datetime import datetime
from director_btc import dirigir as dirigir_btc
from director_eth import dirigir as dirigir_eth
from director_sol import dirigir as dirigir_sol
from director_avax import dirigir as dirigir_avax
from engine import enviar_aviso
from memoria.memoria import registrar_evento
from utils import fetch_velas, detectar_fase
from ejecutor import cerrar_posicion
from gestor_billetera import registrar_tp, registrar_sl
from memoria_propia import actualizar_memoria
import db

MONEDAS        = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "AVAXUSDT"]
MODO_FILE      = os.path.expanduser("~/bot-padre-v2/signals/modo.json")
AUDITORIA      = os.path.expanduser("~/bot-padre-v2/auditoria.csv")
AUDITORIA_LOCK = AUDITORIA + ".lock"

def cerrar_huerfanas(fase_nueva):
    """
    Al cambiar de fase, cierra en Binance toda posicion ABIERTA cuyo tipo
    no coincide con la nueva fase. Evita que queden sin guardian de TP/SL.
    """
    _lk = open(AUDITORIA_LOCK, "w")
    fcntl.flock(_lk, fcntl.LOCK_EX)
    try:
        with open(AUDITORIA, "r") as f:
            lineas = f.readlines()
    except Exception as e:
        print(f"  [HUERFANAS] Error leyendo auditoria: {e}")
        _lk.close()
        return

    header   = lineas[0] if lineas else "timestamp,accion,symbol,precio,rsi,estado,monto,qty\n"
    nuevas   = [header]
    cerradas = 0

    for linea in lineas[1:]:
        partes = linea.strip().split(",")
        if len(partes) < 7 or partes[5] != "ABIERTA" or partes[1] == fase_nueva:
            nuevas.append(linea)
            continue

        accion = partes[1]
        symbol = partes[2]
        try:
            precio_entrada = float(partes[3])
            monto_op       = float(partes[6])
            # qty real del fill de entrada; None en filas previas al fix #4
            qty_op         = float(partes[7]) if len(partes) > 7 and partes[7] else None
            moneda         = symbol.replace("USDT", "")

            cierres       = fetch_velas(symbol, limite=5)
            precio_actual = cierres[-1] if cierres else precio_entrada

            res, fill_cierre = cerrar_posicion(moneda, accion, precio_entrada, monto_op, qty_op)
            if "❌" in res:
                print(f"  [HUERFANAS] Cierre fallido {symbol} {accion}: {res}")
                enviar_aviso(
                    f"⚠️ ZOMBIE NO CERRADA — {symbol} ({accion})\n"
                    f"Error al cerrar en Binance: {res}\n"
                    f"Cerrar manualmente con /cerrar {symbol}."
                )
                nuevas.append(linea)
                continue

            # La orden YA se ejecuto en Binance: marcar la fila cerrada ANTES de
            # contabilizar. Si la contabilidad falla y la fila volviera a
            # ABIERTA, el proximo ciclo re-venderia una posicion inexistente.
            partes[5] = "FASE_CAMBIO"
            cerradas += 1

            ganando = (precio_actual < precio_entrada) if accion == "BAJISTA" \
                      else (precio_actual > precio_entrada)
            qty_real  = (fill_cierre or {}).get("qty")
            usdt_real = (fill_cierre or {}).get("usdt")
            try:
                registrador = registrar_tp if ganando else registrar_sl
                registrador(precio_entrada, precio_actual, monto_op, moneda, accion,
                            qty=qty_real, usdt=usdt_real)
            except Exception as e:
                print(f"  [HUERFANAS] ⚠️ Contabilidad fallida tras cierre ejecutado: {e}")
                enviar_aviso(
                    f"⚠️ DESCUADRE {symbol}\n"
                    f"El cierre por cambio de fase SI se ejecuto en Binance, pero la "
                    f"contabilidad fallo:\n{e}\nRevisar billetera.json a mano."
                )

            cambio = ((precio_entrada - precio_actual) / precio_entrada * 100) if accion == "BAJISTA" \
                     else ((precio_actual - precio_entrada) / precio_entrada * 100)
            actualizar_memoria(symbol, cambio)
            enviar_aviso(
                f"🔄 CIERRE POR CAMBIO DE FASE\n"
                f"{symbol} ({accion})\n"
                f"Entrada: ${precio_entrada} → Salida: ${precio_actual}\n"
                f"Resultado: {'+' if cambio >= 0 else ''}{round(cambio, 2)}%\n"
                f"Nueva fase: {fase_nueva}"
            )
            print(f"  [HUERFANAS] Cerrada {symbol} {accion} → {round(cambio, 2)}%")
        except Exception as e:
            print(f"  [HUERFANAS] Error cerrando {symbol} {accion}: {e}")
            # Igual que arriba: si ya se cerro en Binance, la fila no vuelve a ABIERTA.
            nuevas.append((",".join(partes) + "\n") if partes[5] != "ABIERTA" else linea)
            continue

        nuevas.append(",".join(partes) + "\n")

    try:
        _tmp = AUDITORIA + ".tmp"
        with open(_tmp, "w") as f:
            f.writelines(nuevas)
        os.replace(_tmp, AUDITORIA)
    except Exception as e:
        print(f"  [HUERFANAS] ERROR CRITICO guardando auditoria: {e}")
    _lk.close()

    if cerradas > 0:
        registrar_evento(
            f"ORQUESTA: {cerradas} posicion(es) zombie cerradas al pasar a fase {fase_nueva}"
        )


def _leer_modo():
    # Fallback SIMULADOR: coherente con ejecutor._leer_modo(). Ante cualquier
    # fallo de lectura, nunca asumir REAL.
    try:
        with open(MODO_FILE) as f:
            cfg = json.load(f)
        return cfg.get("modo", "SIMULADOR"), cfg.get("intervalo_velas", "4h"), int(cfg.get("sleep_segundos", 240))
    except Exception as e:
        print(f"  [ORQUESTA] ⚠️ Error leyendo {MODO_FILE}: {e} — asumiendo SIMULADOR.")
        return "SIMULADOR", "4h", 240

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
        cerrar_huerfanas(fase_global)
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

    # Directores se activan segun la fase LOCAL de cada moneda (no el voto de fase_global).
    # BNB sigue huerfano (director_bnb.py existe pero no se llama aca) — no forma parte
    # de este cambio. AVAX se suma como 4to activo (combo O del torneo), 2026-08-25.
    print(f"  🟢 Activando Director BTC (fase local: {fases['BTCUSDT']})")
    dirigir_btc(fases['BTCUSDT'])

    print(f"  🟢 Activando Director ETH (fase local: {fases['ETHUSDT']})")
    dirigir_eth(fases['ETHUSDT'])

    print(f"  🟢 Activando Director SOL (fase local: {fases['SOLUSDT']})")
    dirigir_sol(fases['SOLUSDT'])

    print(f"  🟢 Activando Director AVAX (fase local: {fases['AVAXUSDT']})")
    dirigir_avax(fases['AVAXUSDT'])

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
