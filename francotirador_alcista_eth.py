# =========================================
# francotirador_alcista_eth.py
# INTEGRADO: Breakeven automatico aprobado
# Backtesting: WR 46% → 69% aprobado
# 2 velas (8h) + umbral +0.8%
# Sin librerias externas. Constitucion RESPETADA
# =========================================

import os
import fcntl
import json
from datetime import datetime
from engine import enviar_aviso
from gestor_billetera import registrar_tp, registrar_sl
from guardian_riesgo import esta_bloqueado
from gestor_correlacion import puede_operar
from termometro import puede_operar_termometro
from medidor_spread import spread_aceptable
from filtro_calidad import señal_tiene_calidad
from filtro_horario import puede_operar_horario
from detector_multitimeframe import confirmar_tendencia_multitf
from limitador_diario import puede_operar_hoy
from filtro_eventos import puede_operar_eventos
from memoria.memoria import registrar_evento
from utils import fetch_velas, calcular_rsi, calcular_ema, aplicar_filtro_estadistico, puede_operar_memoria
from ejecutor import ejecutar_operacion, cerrar_posicion
from memoria_propia import actualizar_memoria

SYMBOL             = "ETHUSDT"
MONEDA             = "ETH"
TIPO_TRADE         = "ALCISTA"
CAPITAL_MAX_POR_OP = 0.02

from config_cartera import get_params as _get_params

_p = _get_params(SYMBOL, TIPO_TRADE.lower())

RSI_MIN            = _p["rsi_min"]
RSI_MAX            = _p["rsi_max"]
STOP_LOSS          = _p["sl"]
TAKE_PROFIT        = _p["tp"]
EMA_CORTA          = _p["ec"]
EMA_LARGA          = _p["el"]
MAX_OP_TOTAL       = 1
TRAILING_ACTIVACION = _p["trail_act"]
TRAILING_DISTANCIA  = _p["trail_dist"]

BE_VELAS_ESPERA = 2
BE_UMBRAL       = 0.8
BE_COMISION     = 0.2

BILLETERA = os.path.expanduser("~/bot-padre-v2/signals/billetera.json")
AUDITORIA = os.path.expanduser("~/bot-padre-v2/auditoria.csv")
AUDITORIA_LOCK = AUDITORIA + ".lock"


def cargar_capital():
    try:
        with open(BILLETERA, "r") as f:
            billetera = json.load(f)
        capital = billetera.get("USDT", 0)
        if capital <= 0:
            print("  [CAPITAL] ⚠️ Capital cero o negativo.")
            return 0
        return capital
    except Exception as e:
        print(f"  [CAPITAL] ERROR leyendo billetera: {e}")
        return 0


def contar_operaciones_abiertas():
    try:
        with open(AUDITORIA, "r") as f:
            lineas = f.readlines()

        return sum(
            1 for l in lineas[1:]
            if len(l.strip().split(",")) >= 6 and
            l.strip().split(",")[2] == SYMBOL and
            l.strip().split(",")[5] in ("ABIERTA", "RESERVADA")
        )

    except Exception as e:
        print(f"  [AUDITORIA] Error contando ops: {e}")
        return 0


def reservar_operacion(accion, precio, rsi, monto):
    """
    Escribe la fila ANTES de mandar la orden, en estado RESERVADA y bajo el
    mismo lock que usan los que reescriben el archivo entero.
    """

    fila_id = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    _lk = open(AUDITORIA_LOCK, "w")
    fcntl.flock(_lk, fcntl.LOCK_EX)

    try:
        with open(AUDITORIA, "a") as f:
            f.write(
                f"{fila_id},{accion},{SYMBOL},{precio},{rsi},"
                f"RESERVADA,{monto},\n"
            )

        return fila_id

    except Exception as e:
        print(f"  [AUDITORIA] ERROR reservando operacion: {e}")
        enviar_aviso(
            f"⚠️ {SYMBOL}: no se pudo reservar la fila de auditoria.\n"
            f"NO se opera.\n{e}"
        )
        return None

    finally:
        fcntl.flock(_lk, fcntl.LOCK_UN)
        _lk.close()


def _actualizar_fila(fila_id, nuevo_estado, precio=None, qty=None):
    """
    Cierra el ciclo de una reserva:
    ABIERTA con el fill real si la orden salió,
    ANULADA si falló.
    """

    _lk = open(AUDITORIA_LOCK, "w")
    fcntl.flock(_lk, fcntl.LOCK_EX)

    try:
        with open(AUDITORIA, "r") as f:
            lineas = f.readlines()

        for i, l in enumerate(lineas):
            p = l.rstrip("\n").split(",")

            if (
                len(p) >= 6
                and p[0] == fila_id
                and p[2] == SYMBOL
                and p[5] == "RESERVADA"
            ):
                p[5] = nuevo_estado

                if precio is not None:
                    p[3] = str(precio)

                while len(p) < 8:
                    p.append("")

                if qty is not None:
                    p[7] = str(qty)

                lineas[i] = ",".join(p) + "\n"
                break

        else:
            print(
                f"[AUDITORIA] ⚠️ No se encontro la reserva "
                f"{fila_id} de {SYMBOL}"
            )
            return False

        _tmp = AUDITORIA + ".tmp"

        with open(_tmp, "w") as f:
            f.writelines(lineas)

        os.replace(_tmp, AUDITORIA)
        return True

    except Exception as e:
        print(
            f"  [AUDITORIA] ERROR actualizando reserva "
            f"{fila_id}: {e}"
        )

        enviar_aviso(
            f"⚠️ DESCUADRE {SYMBOL}\n"
            f"Orden {nuevo_estado} pero la fila quedo en RESERVADA:\n"
            f"{e}"
        )

        return False

    finally:
        fcntl.flock(_lk, fcntl.LOCK_UN)
        _lk.close()


def _contabilizar(fn, *args, **kwargs):
    """
    Corre la contabilidad de un cierre que YA se ejecutó en Binance.
    """

    try:
        return fn(*args, **kwargs)

    except Exception as e:
        print(
            f"  [CONTABILIDAD] ⚠️ FALLO tras un cierre YA ejecutado: {e}"
        )

        enviar_aviso(
            f"⚠️ DESCUADRE {SYMBOL}\n"
            f"El cierre SI se ejecuto en Binance pero la "
            f"contabilidad fallo:\n{e}\n"
            f"Revisar billetera.json a mano."
        )

        return 0


def revisar_cierres(precio_actual, evaluar_tp=True):
    _lk = open(AUDITORIA_LOCK, "w")
    fcntl.flock(_lk, fcntl.LOCK_EX)

    try:
        with open(AUDITORIA, "r") as f:
            lineas = f.readlines()

    except Exception as e:
        print(f"  [AUDITORIA] Error leyendo: {e}")
        fcntl.flock(_lk, fcntl.LOCK_UN)
        _lk.close()
        return False

    header = (
        lineas[0]
        if lineas
        else "timestamp,accion,symbol,precio,rsi,estado,monto,qty\n"
    )

    nuevas_lineas = [header]
    cerro_algo = False

    for linea in lineas[1:]:
        partes = linea.strip().split(",")

        if len(partes) < 6:
            nuevas_lineas.append(linea)
            continue

        if (
            partes[2] == SYMBOL
            and partes[1] == TIPO_TRADE
            and partes[5] == "ABIERTA"
        ):
            try:
                precio_entrada = float(partes[3])
                timestamp_entry = partes[0]

                cambio = (
                    (precio_actual - precio_entrada)
                    / precio_entrada
                ) * 100

                try:
                    dt_entrada = datetime.strptime(
                        timestamp_entry,
                        "%Y-%m-%d %H:%M:%S"
                    )

                    horas_abiert = (
                        datetime.now() - dt_entrada
                    ).total_seconds() / 3600

                    velas_abiert = horas_abiert / 4

                except Exception:
                    velas_abiert = 0

                sl_efectivo = round(
                    precio_entrada * (1 - STOP_LOSS / 100),
                    4
                )

                be_price = round(
                    precio_entrada * (1 + BE_COMISION / 100),
                    4
                )

                be_activo = False

                if (
                    velas_abiert >= BE_VELAS_ESPERA
                    and cambio >= BE_UMBRAL
                ):
                    if sl_efectivo < be_price:
                        sl_efectivo = be_price
                        be_activo = True

                if cambio > 0:
                    sl_trail = round(
                        precio_actual * (1 - TRAILING_DISTANCIA / 100),
                        4
                    )

                    sl_efectivo = max(
                        sl_efectivo,
                        sl_trail
                    )

                    trailing_on = (
                        cambio >= TRAILING_ACTIVACION
                    )

                else:
                    trailing_on = False

                monto_op = (
                    float(partes[6])
                    if len(partes) > 6
                    else 10.0
                )

                qty_op = (
                    float(partes[7])
                    if len(partes) > 7 and partes[7]
                    else None
                )

                if evaluar_tp and cambio >= TAKE_PROFIT:

                    res_cierre, fill_cierre = cerrar_posicion(
                        MONEDA,
                        TIPO_TRADE,
                        precio_entrada,
                        monto_op,
                        qty_op
                    )

                    if "❌" in res_cierre:
                        print(
                            f"  ⚠️ Cierre fallido (TP): {res_cierre}"
                        )

                        enviar_aviso(
                            f"⚠️ ERROR CIERRE {SYMBOL}\n"
                            f"No se pudo cerrar posición en Binance (TP).\n"
                            f"Posición queda ABIERTA — reintentando próximo ciclo.\n"
                            f"Error: {res_cierre}"
                        )

                        nuevas_lineas.append(linea)
                        continue

                    partes[5] = "TP"
                    cerro_algo = True

                    _contabilizar(
                        registrar_tp,
                        precio_entrada,
                        precio_actual,
                        monto_op,
                        MONEDA,
                        TIPO_TRADE,
                        qty=(fill_cierre or {}).get("qty"),
                        usdt=(fill_cierre or {}).get("usdt")
                    )

                    enviar_aviso(
                        f"✅ TP ALCANZADO {SYMBOL}\n"
                        f"Entrada: ${precio_entrada}\n"
                        f"Salida: ${precio_actual}\n"
                        f"Ganancia: +{round(cambio,2)}%"
                    )

                    registrar_evento(
                        f"ALCISTA ETH: TP {SYMBOL} +{round(cambio,2)}%"
                    )

                    actualizar_memoria(
                        SYMBOL,
                        cambio
                    )

                    print(
                        f"  ✅ TP: ${precio_entrada} → ${precio_actual}"
                    )

                elif precio_actual <= sl_efectivo:

                    res_cierre, fill_cierre = cerrar_posicion(
                        MONEDA,
                        TIPO_TRADE,
                        precio_entrada,
                        monto_op,
                        qty_op
                    )

                    if "❌" in res_cierre:
                        print(
                            f"  ⚠️ Cierre fallido (SL): {res_cierre}"
                        )

                        enviar_aviso(
                            f"⚠️ ERROR CIERRE {SYMBOL}\n"
                            f"No se pudo cerrar posición en Binance (SL).\n"
                            f"Posición queda ABIERTA — reintentando próximo ciclo.\n"
                            f"Error: {res_cierre}"
                        )

                        nuevas_lineas.append(linea)
                        continue

                    if be_activo and sl_efectivo >= be_price:

                        partes[5] = "BE"
                        cerro_algo = True

                        _contabilizar(
                            registrar_sl,
                            precio_entrada,
                            precio_actual,
                            monto_op,
                            MONEDA,
                            TIPO_TRADE,
                            qty=(fill_cierre or {}).get("qty"),
                            usdt=(fill_cierre or {}).get("usdt")
                        )

                        enviar_aviso(
                            f"🛡️ BREAKEVEN {SYMBOL}\n"
                            f"Entrada: ${precio_entrada}\n"
                            f"Salida: ${precio_actual}\n"
                            f"Resultado: +{BE_COMISION}% protegido\n"
                            f"Trade de {round(velas_abiert,1)} velas protegido"
                        )

                        registrar_evento(
                            f"ALCISTA ETH: BE {SYMBOL} "
                            f"protegido tras {round(velas_abiert,1)} velas"
                        )

                        print(
                            f"  🛡️ BE: ${precio_entrada} → "
                            f"${sl_efectivo} protegido"
                        )

                    elif trailing_on:

                        partes[5] = "TRAILING_SL"
                        cerro_algo = True

                        _contabilizar(
                            registrar_sl,
                            precio_entrada,
                            precio_actual,
                            monto_op,
                            MONEDA,
                            TIPO_TRADE,
                            qty=(fill_cierre or {}).get("qty"),
                            usdt=(fill_cierre or {}).get("usdt")
                        )

                        enviar_aviso(
                            f"🎯 TRAILING SL {SYMBOL}\n"
                            f"Entrada: ${precio_entrada}\n"
                            f"Salida: ${precio_actual}"
                        )

                        registrar_evento(
                            f"ALCISTA ETH: TRAILING_SL "
                            f"{SYMBOL} ${sl_efectivo}"
                        )

                        print(
                            f"  🎯 TRAILING_SL: "
                            f"${precio_entrada} → ${sl_efectivo}"
                        )

                    else:

                        partes[5] = "SL"
                        cerro_algo = True

                        _contabilizar(
                            registrar_sl,
                            precio_entrada,
                            precio_actual,
                            monto_op,
                            MONEDA,
                            TIPO_TRADE,
                            qty=(fill_cierre or {}).get("qty"),
                            usdt=(fill_cierre or {}).get("usdt")
                        )

                        enviar_aviso(
                            f"🛑 SL {SYMBOL}\n"
                            f"Entrada: ${precio_entrada}\n"
                            f"Salida: ${precio_actual}\n"
                            f"Perdida: -{STOP_LOSS}%"
                        )

                        registrar_evento(
                            f"ALCISTA ETH: SL {SYMBOL} -{STOP_LOSS}%"
                        )

                        print(
                            f"  🛑 SL: "
                            f"${precio_entrada} → ${sl_efectivo}"
                        )

                    actualizar_memoria(
                        SYMBOL,
                        cambio
                    )

                nuevas_lineas.append(
                    ",".join(partes) + "\n"
                )

            except Exception as e:
                print(
                    f"  [AUDITORIA] Error procesando linea: {e}"
                )

                if partes[5] != "ABIERTA":
                    nuevas_lineas.append(
                        ",".join(partes) + "\n"
                    )
                else:
                    nuevas_lineas.append(linea)

        else:
            nuevas_lineas.append(linea)

    try:
        _tmp = AUDITORIA + ".tmp"

        with open(_tmp, "w") as f:
            f.writelines(nuevas_lineas)

        os.replace(_tmp, AUDITORIA)

    except Exception as e:
        print(
            f"  [AUDITORIA] ERROR CRITICO guardando: {e}"
        )

    fcntl.flock(_lk, fcntl.LOCK_UN)
    _lk.close()
    return cerro_algo


def evaluar():
    print(
        f"[FRANCOTIRADOR ALCISTA ETH] Evaluando {SYMBOL}..."
    )

    cierres = fetch_velas(
        SYMBOL,
        limite=210
    )

    if not cierres:
        print("[ERROR] Sin datos.")
        return

    precio_actual = cierres[-1]

    if esta_bloqueado():
        print("  🚨 Guardian activo.")
        revisar_cierres(
            precio_actual,
            evaluar_tp=False
        )
        return

    if not puede_operar_termometro():
        print("  🌡️ Termometro activo.")
        revisar_cierres(
            precio_actual,
            evaluar_tp=False
        )
        return

    if not spread_aceptable(SYMBOL):
        print("  📊 Spread alto.")
        revisar_cierres(
            precio_actual,
            evaluar_tp=False
        )
        return

    if not puede_operar_horario():
        print("  🕐 Fuera de horario.")
        revisar_cierres(
            precio_actual,
            evaluar_tp=False
        )
        return

    if not puede_operar_hoy():
        print("  📅 Limite diario.")
        revisar_cierres(
            precio_actual,
            evaluar_tp=False
        )
        return

    if not puede_operar_eventos():
        print("  📰 Evento macro.")
        revisar_cierres(
            precio_actual,
            evaluar_tp=False
        )
        return

    if revisar_cierres(
        precio_actual,
        evaluar_tp=True
    ):
        print(f"  ⏸️ {SYMBOL}: posición cerrada este ciclo — sin evaluar entrada nueva hasta el próximo.")
        return

    rsi = calcular_rsi(cierres)
    ema_c = calcular_ema(
        cierres,
        EMA_CORTA
    )
    ema_l = calcular_ema(
        cierres,
        EMA_LARGA
    )

    print(
        f"  Precio: ${precio_actual} | "
        f"RSI: {rsi} | "
        f"EMA{EMA_CORTA}: {ema_c} | "
        f"EMA{EMA_LARGA}: {ema_l}"
    )

    if (
        rsi is None
        or ema_c is None
        or ema_l is None
    ):
        print("  Sin datos suficientes.")
        return

    capital = cargar_capital()

    if capital <= 0:
        print("  Sin capital disponible.")
        return

    ops_abiertas = contar_operaciones_abiertas()

    print(
        f"  Ops abiertas: {ops_abiertas}"
    )

    if ops_abiertas >= MAX_OP_TOTAL:
        print(
            f"  Limite {MAX_OP_TOTAL} ops. Descansando."
        )
        return

    if not confirmar_tendencia_multitf(
        SYMBOL,
        "ALCISTA"
    ):
        print("  🔭 Tendencia no confirmada.")
        return

    if not señal_tiene_calidad(
        SYMBOL,
        "ALCISTA"
    ):
        print("  🔬 Sin calidad.")
        return

    ok_stats, motivo_stats = aplicar_filtro_estadistico(
        cierres
    )

    if not ok_stats:
        print(
            f"  📊 Filtro estadistico: "
            f"{motivo_stats}."
        )
        return

    ok_mem, motivo_mem, factor_mem = puede_operar_memoria(
        SYMBOL,
        rsi
    )

    if not ok_mem:
        print(
            f"  🧠 Memoria bloquea: "
            f"{motivo_mem}"
        )
        return

    if (
        RSI_MIN <= rsi <= RSI_MAX
        and ema_c > ema_l
    ):

        if not puede_operar(
            "ALCISTA",
            SYMBOL
        ):
            print(
                "  [CORRELACION] ❌ Bloqueado."
            )
            return

        monto_op = 5.0

        fila_id = reservar_operacion(
            "ALCISTA",
            precio_actual,
            rsi,
            monto_op
        )

        if fila_id is None:
            print(
                "  [AUDITORIA] Reserva fallida. "
                "NO se opera."
            )
            return

        resultado, fill = ejecutar_operacion(
            MONEDA,
            "COMPRA",
            precio_actual,
            monto_op
        )

        print(
            f"  {resultado}"
        )

        if "✅" in resultado:

            _actualizar_fila(
                fila_id,
                "ABIERTA",
                precio=fill["precio"],
                qty=fill["qty"]
            )

            registrar_evento(
                f"FRANCOTIRADOR ALCISTA ETH: "
                f"ENTRADA {fill['precio']} "
                f"RSI:{rsi} | {resultado}"
            )

            enviar_aviso(
                f"🚀 FRANCOTIRADOR ALCISTA ETH\n"
                f"Symbol: {SYMBOL}\n"
                f"Precio: ${fill['precio']} (fill real)\n"
                f"RSI: {rsi} | "
                f"EMA{EMA_CORTA}: {ema_c} | "
                f"EMA{EMA_LARGA}: {ema_l}\n"
                f"Operacion: {ops_abiertas+1}/{MAX_OP_TOTAL}\n"
                f"Monto: ${monto_op} | "
                f"Factor memoria: {factor_mem}\n"
                f"SL: {STOP_LOSS}% | "
                f"TP: {TAKE_PROFIT}%\n"
                f"Breakeven: 8h + {BE_UMBRAL}%\n"
                f"{resultado}"
            )

        else:
            _actualizar_fila(
                fila_id,
                "ANULADA"
            )

    else:
        print(
            f"  Sin señal. "
            f"RSI:{rsi} "
            f"EMA_C:{ema_c} "
            f"EMA_L:{ema_l}"
        )

        registrar_evento(
            f"FRANCOTIRADOR ALCISTA ETH: "
            f"Sin señal. RSI:{rsi}"
        )


if __name__ == "__main__":
    evaluar()
