import json, os
from datetime import datetime, timezone, timedelta
from utils import fetch_velas, calcular_rsi, calcular_ema, detectar_fase
from guardian_riesgo import esta_bloqueado
from termometro import puede_operar_termometro
from medidor_spread import spread_aceptable
from filtro_horario import puede_operar_horario
from limitador_diario import puede_operar_hoy
from filtro_eventos import puede_operar_eventos
from filtro_calidad import señal_tiene_calidad
from detector_multitimeframe import confirmar_tendencia_multitf

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "AVAXUSDT"]
BILLETERA = os.path.expanduser("~/bot-padre-v2/signals/billetera.json")
REPORTE = os.path.expanduser("~/bot-padre-v2/estado_diagnostico.json")

RSI_MIN = 50
RSI_MAX = 70

def cargar_capital():
    try:
        with open(BILLETERA) as f:
            b = json.load(f)
        return float(b.get("USDT", 0))
    except:
        return 0.0

def generar_diagnostico():
    reporte = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "capital_usdt": cargar_capital(),
        "filtros_globales": {},
        "monedas": {}
    }

    reporte["filtros_globales"]["guardian_riesgo"] = not esta_bloqueado()
    reporte["filtros_globales"]["termometro"] = puede_operar_termometro()
    reporte["filtros_globales"]["horario"] = puede_operar_horario()
    reporte["filtros_globales"]["limite_diario"] = puede_operar_hoy()
    reporte["filtros_globales"]["eventos_macro"] = puede_operar_eventos()

    fases = []
    for symbol in SYMBOLS:
        cierres = fetch_velas(symbol, limite=210)
        if not cierres:
            continue

        fase = detectar_fase(cierres, symbol=symbol)
        rsi = calcular_rsi(cierres)
        ema20 = calcular_ema(cierres, 20)
        ema50 = calcular_ema(cierres, 50)
        spread_ok = spread_aceptable(symbol)
        calidad_ok = señal_tiene_calidad(symbol, fase)
        multitf_ok = confirmar_tendencia_multitf(symbol, fase)
        fases.append(fase)

        señal_rsi = RSI_MIN <= (rsi or 0) <= RSI_MAX
        ema_ok = (ema20 or 0) > (ema50 or 0)

        # Calcular cercanía al disparo
        if rsi is not None:
            if rsi < RSI_MIN:
                rsi_distancia = round(RSI_MIN - rsi, 2)
                rsi_estado = f"faltan {rsi_distancia} puntos para llegar a RSI {RSI_MIN}"
            elif rsi > RSI_MAX:
                rsi_distancia = round(rsi - RSI_MAX, 2)
                rsi_estado = f"RSI {rsi} está {rsi_distancia} puntos por encima del máximo {RSI_MAX}"
            else:
                rsi_distancia = 0
                rsi_estado = f"RSI {rsi} dentro del rango ✅"
        else:
            rsi_distancia = None
            rsi_estado = "sin datos de RSI"

        if ema20 and ema50:
            ema_diferencia = round(ema20 - ema50, 4)
            if ema_diferencia > 0:
                ema_estado = f"EMA20 está {ema_diferencia} por encima de EMA50 ✅"
            else:
                ema_estado = f"EMA20 está {abs(ema_diferencia)} por debajo de EMA50 — necesita subir"
        else:
            ema_estado = "sin datos de EMA"

        razones = []
        if not señal_rsi:
            razones.append(f"RSI fuera de rango ({rsi}) — {rsi_estado}")
        if not ema_ok:
            razones.append(f"EMA no alineada — {ema_estado}")
        if not spread_ok:
            razones.append("spread alto")
        if not calidad_ok:
            razones.append("señal sin calidad suficiente")
        if not multitf_ok:
            razones.append("tendencia no confirmada en múltiples timeframes")

        listo = señal_rsi and ema_ok and spread_ok and calidad_ok and multitf_ok

        reporte["monedas"][symbol] = {
            "precio": cierres[-1],
            "fase": fase,
            "rsi": rsi,
            "rsi_estado": rsi_estado,
            "rsi_distancia": rsi_distancia,
            "ema20": ema20,
            "ema50": ema50,
            "ema_estado": ema_estado,
            "spread_ok": spread_ok,
            "calidad_ok": calidad_ok,
            "multitf_ok": multitf_ok,
            "señal_rsi": señal_rsi,
            "ema_ok": ema_ok,
            "listo": listo,
            "razones_bloqueado": razones
        }

    conteo = {"ALCISTA": fases.count("ALCISTA"), "BAJISTA": fases.count("BAJISTA"), "LATERAL": fases.count("LATERAL")}
    if conteo["ALCISTA"] >= 3:
        fase_global = "ALCISTA"
    elif conteo["BAJISTA"] >= 3:
        fase_global = "BAJISTA"
    else:
        fase_global = "LATERAL"

    reporte["fase_global"] = fase_global
    reporte["conteo_fases"] = conteo

    with open(REPORTE, "w") as f:
        json.dump(reporte, f, indent=2, ensure_ascii=False)

    print(f"✅ Diagnóstico generado: {REPORTE}")
    return reporte

if __name__ == "__main__":
    generar_diagnostico()
