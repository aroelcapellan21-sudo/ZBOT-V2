# =========================================
# lector_radares.py - Capa de Integracion REAL
# Lee JSONs reales de ~/bot-padre-v2/estado/
# Usado por francotiradores antes de operar
# FIX: Rutas corregidas a estado/ real
# Sin librerias externas. Constitucion RESPETADA
# =========================================

import json
import os
from datetime import datetime

ESTADO_DIR = os.path.expanduser("~/bot-padre-v2/estado")

ESTADO_CORR      = os.path.join(ESTADO_DIR, "z_correlation.json")
ESTADO_VOLUMEN   = os.path.join(ESTADO_DIR, "z_volumen.json")
ESTADO_HEATMAP   = os.path.join(ESTADO_DIR, "z_heatmap.json")
ESTADO_VELAS     = os.path.join(ESTADO_DIR, "z_velas.json")
ESTADO_PRECISION = os.path.join(ESTADO_DIR, "z_precision.json")
ESTADO_RADAR     = os.path.join(ESTADO_DIR, "z_radar.json")

MAX_EDAD_MINUTOS = 30  # radares se actualizan cada ~10-60s

def _leer_json(ruta):
    try:
        with open(ruta, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except Exception as e:
        print(f"[RADARES] Error leyendo {ruta}: {e}")
        return None

def _es_reciente(data, max_minutos=MAX_EDAD_MINUTOS):
    if not data or "timestamp" not in data:
        return False
    try:
        ts    = datetime.strptime(data["timestamp"], '%Y-%m-%d %H:%M:%S')
        ahora = datetime.now()
        diff  = (ahora - ts).total_seconds() / 60
        return diff <= max_minutos
    except:
        return False

def leer_correlacion(symbol):
    """
    Retorna (puede_operar, motivo)
    Bloquea si symbol esta SUELTO de BTC en mercado correlacionado.
    """
    data = _leer_json(ESTADO_CORR)
    if not data or not _es_reciente(data):
        return True, "correlacion_sin_datos"

    corrs = data.get("correlaciones", {})
    if symbol == "BTCUSDT" or symbol not in corrs:
        return True, "btc_lider_ok"

    corr   = corrs[symbol].get("correlacion")
    estado = corrs[symbol].get("estado", "")

    if corr is None:
        return True, "calibrando"

    # SUELTO = correlacion < 0.30 — movimiento impredecible
    if corr < 0.30:
        return False, f"correlacion_suelta_{corr}"

    return True, f"correlacion_{round(corr,2)}_{estado}"

def leer_volumen(symbol):
    """
    Retorna (puede_operar, motivo)
    Bloquea si hay inyeccion de gas — movimiento artificial.
    """
    data = _leer_json(ESTADO_VOLUMEN)
    if not data or not _es_reciente(data):
        return True, "volumen_sin_datos"

    for r in data.get("resultados", []):
        if r.get("symbol") == symbol:
            estado = r.get("estado", "FLUJO_NORMAL")
            ratio  = r.get("ratio", 1.0)

            # Inyeccion de gas = volumen >2x promedio = manipulacion posible
            if estado == "INYECCION_GAS" and ratio >= 3.0:
                return False, f"inyeccion_gas_ratio_{ratio}"

            return True, f"volumen_{estado}_ratio_{ratio}"

    return True, "volumen_symbol_no_encontrado"

def leer_heatmap(fase):
    """
    Retorna (puede_operar, motivo)
    Bloquea lateral si mercado esta en tendencia fuerte.
    """
    data = _leer_json(ESTADO_HEATMAP)
    if not data or not _es_reciente(data):
        return True, "heatmap_sin_datos"

    lideres  = data.get("lideres", [])
    muertos  = data.get("muertos", [])
    diag     = data.get("diagnostico", "")

    n_lideres = len(lideres)
    n_muertos = len(muertos)

    # Si hay fiesta general y queremos lateral — no es buen momento
    if fase == "LATERAL" and n_lideres >= 3:
        return False, f"heatmap_fiesta_general_{n_lideres}_lideres"

    # Si mercado muy frio y queremos alcista — no es buen momento
    if fase == "ALCISTA" and n_muertos >= 4:
        return False, f"heatmap_mercado_frio_{n_muertos}_muertos"

    return True, f"heatmap_lideres_{n_lideres}_muertos_{n_muertos}"

def leer_velas(symbol, fase):
    """
    Retorna (puede_operar, motivo)
    Usa patron de velas para confirmar direccion.
    """
    data = _leer_json(ESTADO_VELAS)
    if not data or not _es_reciente(data):
        return True, "velas_sin_datos"

    for r in data.get("resultados", []):
        if r.get("symbol") == symbol:
            patron = r.get("patron", "ESTABLE")

            # Inyeccion de gas en velas = volatilidad extrema — esperar
            if patron == "INYECCION_GAS" and fase == "LATERAL":
                return False, f"velas_inyeccion_gas_en_lateral"

            return True, f"velas_{patron}"

    return True, "velas_symbol_no_encontrado"

def leer_precision(symbol):
    """
    Retorna (puede_operar, motivo)
    Usa volatilidad medida por z_precision.
    """
    data = _leer_json(ESTADO_PRECISION)
    if not data or not _es_reciente(data):
        return True, "precision_sin_datos"

    volatilidad = data.get("volatilidad", {})
    vol         = volatilidad.get(symbol, None)

    if vol is not None and vol >= 1.5:
        return False, f"volatilidad_extrema_{vol}pct"

    return True, f"volatilidad_ok_{vol}pct"

def leer_noticias():
    """
    Retorna (puede_operar, motivo)
    Bloquea si hay noticias bajistas dominando.
    """
    data = _leer_json(ESTADO_RADAR)
    if not data or not _es_reciente(data, max_minutos=60):
        return True, "noticias_sin_datos"

    resumen  = data.get("resumen", {})
    bajistas = resumen.get("bajistas", 0)
    alcistas = resumen.get("alcistas", 0)
    sentimiento = resumen.get("sentimiento", "NEUTRAL")

    if bajistas >= 3 and bajistas > alcistas * 2:
        return False, f"noticias_bajistas_dominan_{bajistas}"

    return True, f"noticias_{sentimiento}"

def consultar_radares(symbol, fase):
    """
    Punto de entrada principal para francotiradores.
    Retorna (puede_operar, motivo, score)
    score: 0-100
    """
    checks = []

    # 1. Correlacion (peso 25%)
    ok, mot = leer_correlacion(symbol)
    checks.append(("correlacion", ok, 25, mot))

    # 2. Volumen (peso 20%)
    ok, mot = leer_volumen(symbol)
    checks.append(("volumen", ok, 20, mot))

    # 3. Heatmap (peso 20%)
    ok, mot = leer_heatmap(fase)
    checks.append(("heatmap", ok, 20, mot))

    # 4. Velas (peso 20%)
    ok, mot = leer_velas(symbol, fase)
    checks.append(("velas", ok, 20, mot))

    # 5. Precision/volatilidad (peso 10%)
    ok, mot = leer_precision(symbol)
    checks.append(("precision", ok, 10, mot))

    # 6. Noticias (peso 5%) — informativo
    ok, mot = leer_noticias()
    checks.append(("noticias", ok, 5, mot))

    # Score total
    score       = sum(peso for _, ok, peso, _ in checks if ok)
    bloqueantes = [(nom, mot) for nom, ok, _, mot in checks if not ok]
    puede       = len(bloqueantes) == 0
    resumen     = " | ".join(f"{n}:{m}" for n, _, _, m in checks)

    if bloqueantes:
        print(f"  [RADARES] ❌ {symbol} {fase} bloqueado: {[b[0] for b in bloqueantes]}")
    else:
        print(f"  [RADARES] ✅ {symbol} {fase} | Score: {score}/100")

    return puede, resumen, score

if __name__ == "__main__":
    print("=== PRUEBA LECTOR DE RADARES (DATOS REALES) ===\n")
    for symbol in ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "AVAXUSDT"]:
        for fase in ["ALCISTA", "BAJISTA", "LATERAL"]:
            puede, motivo, score = consultar_radares(symbol, fase)
            emoji = "✅" if puede else "❌"
            print(f"{emoji} {symbol} {fase}: Score {score}/100")
            print(f"   {motivo}\n")
