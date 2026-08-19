# =========================================
# corecro/corecro.py - Nucleo de Observacion
# FIX: RSI usa calcular_rsi de utils (unico)
# FIX: Limpieza automatica de reportes antiguos
# FIX: os.makedirs dentro de funcion no en import
# FIX: Rutas absolutas
# NO ejecuta. NO decide. NO toca dinero.
# Constitucion RESPETADA
# =========================================

import os
import urllib.request
import urllib.parse
import json
from datetime import datetime
from utils import fetch_velas, calcular_rsi
from engine import enviar_aviso
import db

BASE_DIR    = os.path.expanduser("~/bot-padre-v2/corecro")
LOGS_DIR    = os.path.join(BASE_DIR, "logs")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
HISTORICO   = os.path.join(REPORTS_DIR, "corecro_signals_historico.txt")

QUINTETO    = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "AVAXUSDT"]
MAX_REPORTES = 10  # FIX: Maximo de archivos a conservar

# Aviso automatico solo en cruce a zona extrema (mas estricto que evaluar_senal)
UMBRAL_EXTREMO_BAJO = 20   # RSI <= esto -> sobreventa extrema
UMBRAL_EXTREMO_ALTO = 80   # RSI >= esto -> sobrecompra extrema
ESTADO_ALERTAS_KEY  = "estado_corecro_alertas"

def evaluar_senal(rsi):
    if rsi is None:
        return "SIN DATOS"
    if rsi < 30:
        return "SOBREVENTA - POSIBLE COMPRA"
    elif rsi > 70:
        return "SOBRECOMPRA - POSIBLE VENTA"
    else:
        return "NEUTRAL - ESPERAR"

def _zona_extrema(rsi):
    """Zona de alerta (mas estricta que evaluar_senal). None = zona normal."""
    if rsi is None:
        return None
    if rsi <= UMBRAL_EXTREMO_BAJO:
        return "SOBREVENTA_EXTREMA"
    if rsi >= UMBRAL_EXTREMO_ALTO:
        return "SOBRECOMPRA_EXTREMA"
    return None

def evaluar_alertas_extremas(resultados):
    """
    Avisa por Telegram solo cuando un simbolo CRUZA a zona extrema (RSI<=20 o >=80),
    no en cada ciclo mientras se mantenga ahi. Estado por simbolo persistido en db.py
    para no repetir el aviso hasta que vuelva a zona normal y cruce de nuevo.
    resultados: lista de (symbol, precio, rsi).
    NO ejecuta, NO decide -- solo informa. Constitucion RESPETADA.
    """
    estado = db.json_get(ESTADO_ALERTAS_KEY) or {}
    avisos = []

    for symbol, precio, rsi in resultados:
        zona_actual = _zona_extrema(rsi)
        zona_previa = estado.get(symbol)

        if zona_actual is None:
            if zona_previa is not None:
                estado[symbol] = None
            continue

        if zona_actual != zona_previa:
            avisos.append(f"{symbol}: ${precio} | RSI {rsi} | {zona_actual}")
            estado[symbol] = zona_actual

    if avisos:
        enviar_aviso(
            "🔎 CORECRO — Extremo detectado\n" + "\n".join(avisos) +
            "\n\nCoreCro no ejecuta ni decide. Solo observacion."
        )

    db.json_set(ESTADO_ALERTAS_KEY, estado)

def limpiar_reportes_antiguos():
    """FIX: Elimina reportes viejos para no acumular miles de archivos."""
    try:
        archivos = sorted([
            a for a in os.listdir(REPORTS_DIR)
            if a.startswith("corecro_report_")
        ])
        if len(archivos) > MAX_REPORTES:
            for viejo in archivos[:-MAX_REPORTES]:
                os.remove(os.path.join(REPORTS_DIR, viejo))
                print(f"  [CORECRO] Reporte antiguo eliminado: {viejo}")
    except Exception as e:
        print(f"  [CORECRO] Error limpiando reportes: {e}")

def generar_reporte():
    # FIX: makedirs dentro de funcion, no en nivel modulo
    os.makedirs(LOGS_DIR, exist_ok=True)
    os.makedirs(REPORTS_DIR, exist_ok=True)

    timestamp      = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    nombre_archivo = f"corecro_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    ruta_archivo   = os.path.join(REPORTS_DIR, nombre_archivo)

    lineas_historico = [f"\n=== {timestamp} ==="]
    reporte = (
        f"===== CORECRO | REPORTE DE OBSERVACION =====\n"
        f"Fecha: {timestamp}\n\n"
    )
    resultados = []

    for symbol in QUINTETO:
        # FIX: Usa fetch_velas y calcular_rsi de utils
        cierres = fetch_velas(symbol, intervalo="15m", limite=50)
        if not cierres:
            linea = f"{symbol}: Sin datos"
        else:
            precio = cierres[-1]
            rsi    = calcular_rsi(cierres)
            senal  = evaluar_senal(rsi)
            linea  = f"{symbol}: ${precio} | RSI: {rsi} | {senal}"
            resultados.append((symbol, precio, rsi))

        reporte += linea + "\n"
        lineas_historico.append(linea)

    reporte += (
        "\nNota constitucional:\n"
        "CoreCro no ejecuta, no decide y no gobierna.\n"
        "=========================================\n"
    )

    try:
        with open(ruta_archivo, "w", encoding="utf-8") as f:
            f.write(reporte)
    except Exception as e:
        print(f"  [CORECRO] Error guardando reporte: {e}")

    try:
        with open(HISTORICO, "a", encoding="utf-8") as f:
            f.write("\n".join(lineas_historico) + "\n")
    except Exception as e:
        print(f"  [CORECRO] Error guardando historico: {e}")

    # FIX: Limpiar reportes antiguos
    limpiar_reportes_antiguos()

    print(f"✔ CoreCro: reporte generado correctamente.")
    print(f"✔ Ruta: {ruta_archivo}")

    return resultados

if __name__ == "__main__":
    generar_reporte()
