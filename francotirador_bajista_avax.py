# =========================================
# francotirador_bajista_avax.py
# INTEGRADO: Breakeven automatico aprobado
# Backtesting: WR 50% → 66% aprobado
# 2 velas (8h) + umbral +0.8%
# FIX: VENTA en lugar de COMPRA
# Sin librerias externas. Constitucion RESPETADA
# =========================================

import os
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

SYMBOL             = "AVAXUSDT"
MONEDA             = "AVAX"
TIPO_TRADE         = "BAJISTA"
CAPITAL_MAX_POR_OP = 0.02
RSI_MIN            = 30
RSI_MAX            = 50
STOP_LOSS          = 4.0
TAKE_PROFIT        = 7
EMA_CORTA          = 20
EMA_LARGA          = 50
MAX_OP_TOTAL       = 1
TRAILING_ACTIVACION = 0.5
TRAILING_DISTANCIA  = 1.0

BE_VELAS_ESPERA = 2
BE_UMBRAL       = 0.8
BE_COMISION     = 0.2

BILLETERA = os.path.expanduser("~/bot-padre-v2/signals/billetera.json")
AUDITORIA = os.path.expanduser("~/bot-padre-v2/auditoria.csv")

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
            l.strip().split(",")[5] == "ABIERTA"
        )
    except Exception as e:
        print(f"  [AUDITORIA] Error contando ops: {e}")
        return 0

def registrar_operacion(accion, precio, rsi, monto):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(AUDITORIA, "a") as f:
            f.write(f"{timestamp},{accion},{SYMBOL},{precio},{rsi},ABIERTA,{monto}\n")
    except Exception as e:
        print(f"  [AUDITORIA] ERROR registrando operacion: {e}")

def revisar_cierres(precio_actual):
    try:
        with open(AUDITORIA, "r") as f:
            lineas = f.readlines()
    except Exception as e:
        print(f"  [AUDITORIA] Error leyendo: {e}")
        return

    header        = lineas[0] if lineas else "timestamp,accion,symbol,precio,rsi,estado,monto\n"
    nuevas_lineas = [header]

    for linea in lineas[1:]:
        partes = linea.strip().split(",")
        if len(partes) < 6:
            nuevas_lineas.append(linea)
            continue

        if partes[2] == SYMBOL and partes[1] == TIPO_TRADE and partes[5] == "ABIERTA":
            try:
                precio_entrada  = float(partes[3])
                timestamp_entry = partes[0]
                cambio          = ((precio_entrada - precio_actual) / precio_entrada) * 100

                try:
                    dt_entrada   = datetime.strptime(timestamp_entry, "%Y-%m-%d %H:%M:%S")
                    horas_abiert = (datetime.now() - dt_entrada).total_seconds() / 3600
                    velas_abiert = horas_abiert / 4
                except:
                    velas_abiert = 0

                sl_efectivo = round(precio_entrada * (1 + STOP_LOSS / 100), 4)

                be_price  = round(precio_entrada * (1 - BE_COMISION / 100), 4)
                be_activo = False
                if velas_abiert >= BE_VELAS_ESPERA and cambio >= BE_UMBRAL:
                    if sl_efectivo > be_price:
                        sl_efectivo = be_price
                        be_activo   = True

                if cambio > 0:
                    sl_trail    = round(precio_actual * (1 + TRAILING_DISTANCIA / 100), 4)
                    sl_efectivo = min(sl_efectivo, sl_trail)
                    trailing_on = cambio >= TRAILING_ACTIVACION
                else:
                    trailing_on = False

                monto_op = float(partes[6]) if len(partes) > 6 else 10.0
                if cambio >= TAKE_PROFIT:
                    res_cierre = cerrar_posicion(MONEDA, TIPO_TRADE, precio_entrada, monto_op)
                    if "❌" in res_cierre:
                        print(f"  ⚠️ Cierre fallido (TP): {res_cierre}")
                        enviar_aviso(f"⚠️ ERROR CIERRE {SYMBOL}\nNo se pudo cerrar posición en Binance (TP).\nPosición queda ABIERTA — reintentando próximo ciclo.\nError: {res_cierre}")
                        nuevas_lineas.append(linea)
                        continue
                    partes[5] = "TP"
                    registrar_tp(precio_entrada, precio_actual, monto_op, MONEDA, TIPO_TRADE)
                    enviar_aviso(f"✅ TP BAJISTA {SYMBOL}\nEntrada: ${precio_entrada}\nSalida: ${precio_actual}\nGanancia: +{round(cambio,2)}%")
                    registrar_evento(f"BAJISTA AVAX: TP {SYMBOL} +{round(cambio,2)}%")
                    actualizar_memoria(SYMBOL, cambio)
                    print(f"  ✅ TP: ${precio_entrada} → ${precio_actual}")

                elif precio_actual >= sl_efectivo:
                    res_cierre = cerrar_posicion(MONEDA, TIPO_TRADE, precio_entrada, monto_op)
                    if "❌" in res_cierre:
                        print(f"  ⚠️ Cierre fallido (SL): {res_cierre}")
                        enviar_aviso(f"⚠️ ERROR CIERRE {SYMBOL}\nNo se pudo cerrar posición en Binance (SL).\nPosición queda ABIERTA — reintentando próximo ciclo.\nError: {res_cierre}")
                        nuevas_lineas.append(linea)
                        continue
                    if be_activo and sl_efectivo <= be_price:
                        partes[5] = "BE"
                        registrar_sl(precio_entrada, sl_efectivo, monto_op, MONEDA, TIPO_TRADE)
                        enviar_aviso(
                            f"🛡️ BREAKEVEN BAJISTA {SYMBOL}\n"
                            f"Entrada: ${precio_entrada}\n"
                            f"Salida: ${sl_efectivo}\n"
                            f"Resultado: +{BE_COMISION}% protegido\n"
                            f"Trade de {round(velas_abiert,1)} velas protegido"
                        )
                        registrar_evento(f"BAJISTA AVAX: BE {SYMBOL} protegido tras {round(velas_abiert,1)} velas")
                        print(f"  🛡️ BE: ${precio_entrada} → ${sl_efectivo} protegido")
                    elif trailing_on:
                        partes[5] = "TRAILING_SL"
                        registrar_sl(precio_entrada, sl_efectivo, monto_op, MONEDA, TIPO_TRADE)
                        enviar_aviso(f"🎯 TRAILING SL BAJISTA {SYMBOL}\nEntrada: ${precio_entrada}\nSalida: ${sl_efectivo}")
                        registrar_evento(f"BAJISTA AVAX: TRAILING_SL {SYMBOL} ${sl_efectivo}")
                        print(f"  🎯 TRAILING_SL: ${precio_entrada} → ${sl_efectivo}")
                    else:
                        partes[5] = "SL"
                        registrar_sl(precio_entrada, sl_efectivo, monto_op, MONEDA, TIPO_TRADE)
                        enviar_aviso(f"🛑 SL BAJISTA {SYMBOL}\nEntrada: ${precio_entrada}\nSalida: ${sl_efectivo}\nPerdida: -{STOP_LOSS}%")
                        registrar_evento(f"BAJISTA AVAX: SL {SYMBOL} -{STOP_LOSS}%")
                        print(f"  🛑 SL: ${precio_entrada} → ${sl_efectivo}")
                    actualizar_memoria(SYMBOL, cambio)

                nuevas_lineas.append(",".join(partes) + "\n")
            except Exception as e:
                print(f"  [AUDITORIA] Error procesando linea: {e}")
                nuevas_lineas.append(linea)
        else:
            nuevas_lineas.append(linea)

    try:
        with open(AUDITORIA, "w") as f:
            f.writelines(nuevas_lineas)
    except Exception as e:
        print(f"  [AUDITORIA] ERROR CRITICO guardando: {e}")

def evaluar():
    print(f"[FRANCOTIRADOR BAJISTA AVAX] Evaluando {SYMBOL}...")
    cierres = fetch_velas(SYMBOL, limite=210)
    if not cierres:
        print("[ERROR] Sin datos.")
        return

    precio_actual = cierres[-1]

    if esta_bloqueado():
        print("  🚨 Guardian activo.")
        return
    if not puede_operar_termometro():
        print("  🌡️ Termometro activo.")
        return
    if not spread_aceptable(SYMBOL):
        print("  📊 Spread alto.")
        return
    if not puede_operar_horario():
        print("  🕐 Fuera de horario.")
        return
    if not puede_operar_hoy():
        print("  📅 Limite diario.")
        return
    if not puede_operar_eventos():
        print("  📰 Evento macro.")
        return

    revisar_cierres(precio_actual)

    rsi   = calcular_rsi(cierres)
    ema_c = calcular_ema(cierres, EMA_CORTA)
    ema_l = calcular_ema(cierres, EMA_LARGA)
    print(f"  Precio: ${precio_actual} | RSI: {rsi} | EMA{EMA_CORTA}: {ema_c} | EMA{EMA_LARGA}: {ema_l}")

    if rsi is None or ema_c is None or ema_l is None:
        print("  Sin datos suficientes.")
        return

    capital = cargar_capital()
    if capital <= 0:
        print("  Sin capital disponible.")
        return

    ops_abiertas = contar_operaciones_abiertas()
    print(f"  Ops abiertas: {ops_abiertas}")

    if ops_abiertas >= MAX_OP_TOTAL:
        print(f"  Limite {MAX_OP_TOTAL} ops. Descansando.")
        return

    if not confirmar_tendencia_multitf(SYMBOL, "BAJISTA"):
        print("  🔭 Tendencia no confirmada.")
        return

    if not señal_tiene_calidad(SYMBOL, "BAJISTA"):
        print("  🔬 Sin calidad.")
        return

    ok_stats, motivo_stats = aplicar_filtro_estadistico(cierres)
    if not ok_stats:
        print(f"  📊 Filtro estadistico: {motivo_stats}.")
        return

    ok_mem, motivo_mem, factor_mem = puede_operar_memoria(SYMBOL, rsi)
    if not ok_mem:
        print(f"  🧠 Memoria bloquea: {motivo_mem}")
        return

    if RSI_MIN <= rsi <= RSI_MAX and ema_c < ema_l:
        if not puede_operar("BAJISTA", SYMBOL):
            print("  [CORRELACION] ❌ Bloqueado.")
            return

        monto_base = capital * CAPITAL_MAX_POR_OP
        monto_op   = round(monto_base * factor_mem, 2)

        resultado = ejecutar_operacion(MONEDA, "VENTA", precio_actual, monto_op)
        print(f"  {resultado}")

        if "✅" in resultado:
            registrar_operacion("BAJISTA", precio_actual, rsi, monto_op)
            registrar_evento(f"FRANCOTIRADOR BAJISTA AVAX: ENTRADA {precio_actual} RSI:{rsi} | {resultado}")
            enviar_aviso(
                f"📉 FRANCOTIRADOR BAJISTA AVAX\n"
                f"Symbol: {SYMBOL}\n"
                f"Precio: ${precio_actual}\n"
                f"RSI: {rsi} | EMA{EMA_CORTA}: {ema_c} | EMA{EMA_LARGA}: {ema_l}\n"
                f"Operacion: {ops_abiertas+1}/{MAX_OP_TOTAL}\n"
                f"Monto: ${monto_op} | Factor memoria: {factor_mem}\n"
                f"SL: {STOP_LOSS}% | TP: {TAKE_PROFIT}%\n"
                f"Breakeven: 8h + {BE_UMBRAL}%\n"
                f"{resultado}"
            )
    else:
        print(f"  Sin señal bajista. RSI:{rsi} EMA_C:{ema_c} EMA_L:{ema_l}")
        registrar_evento(f"FRANCOTIRADOR BAJISTA AVAX: Sin señal. RSI:{rsi}")

if __name__ == "__main__":
    evaluar()
