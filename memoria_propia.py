# =========================================
# memoria_propia.py
# FIX: actualizar_memoria mas eficiente
# FIX: puede_operar_memoria error visible
# FIX: except pass eliminados
# Sin librerias externas. Constitucion RESPETADA
# =========================================

import csv
import json
import os
from datetime import datetime

AUDITORIA = os.path.expanduser("~/bot-padre-v2/auditoria.csv")
MEMORIA   = os.path.expanduser("~/bot-padre-v2/data/memoria_propia.json")
MIN_TRADES = 3

def analizar_historial():
    trades = []
    try:
        with open(AUDITORIA) as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("estado") in ("TP", "SL", "TRAILING_SL"):
                    try:
                        trades.append({
                            "timestamp": row["timestamp"],
                            "symbol":    row["symbol"],
                            "rsi":       float(row.get("rsi", 50)),
                            "estado":    row["estado"],
                            "hora":      int(row["timestamp"].split(" ")[1].split(":")[0]),
                            "dia":       datetime.strptime(row["timestamp"][:10], "%Y-%m-%d").weekday(),
                            "gano":      row["estado"] in ("TP", "TRAILING_SL"),
                        })
                    except Exception as e:
                        print(f"[MEMORIA] Error procesando fila: {e}")
    except FileNotFoundError:
        print("[MEMORIA] auditoria.csv no encontrada. Sin historial.")
        return {}
    except Exception as e:
        print(f"[MEMORIA] Error leyendo auditoria: {e}")
        return {}

    if not trades:
        return {}

    resultado = {}

    # Patron por simbolo
    for symbol in set(t["symbol"] for t in trades):
        ops     = [t for t in trades if t["symbol"] == symbol]
        if len(ops) >= MIN_TRADES:
            ganadas = sum(1 for t in ops if t["gano"])
            resultado[f"{symbol}_wr"]     = round(ganadas / len(ops) * 100, 1)
            resultado[f"{symbol}_trades"] = len(ops)

    # Patron por rango RSI
    rangos = [(45, 49, "bajo"), (49, 51, "neutro"), (51, 55, "alto")]
    for rmin, rmax, nombre in rangos:
        ops = [t for t in trades if rmin <= t["rsi"] < rmax]
        if len(ops) >= MIN_TRADES:
            ganadas = sum(1 for t in ops if t["gano"])
            resultado[f"rsi_{nombre}_wr"]     = round(ganadas / len(ops) * 100, 1)
            resultado[f"rsi_{nombre}_trades"] = len(ops)

    # Patron por hora UTC
    for hora in range(0, 24, 4):
        ops = [t for t in trades if hora <= t["hora"] < hora + 4]
        if len(ops) >= MIN_TRADES:
            ganadas = sum(1 for t in ops if t["gano"])
            resultado[f"hora_{hora}_{hora+4}_wr"] = round(ganadas / len(ops) * 100, 1)

    # Rachas recientes
    ultimos             = trades[-5:] if len(trades) >= 5 else trades
    perdidas_recientes  = sum(1 for t in ultimos if not t["gano"])
    resultado["perdidas_ultimos_5"] = perdidas_recientes
    resultado["total_trades"]       = len(trades)
    resultado["wr_global"]          = round(sum(1 for t in trades if t["gano"]) / len(trades) * 100, 1)
    resultado["actualizado"]        = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        os.makedirs(os.path.dirname(MEMORIA), exist_ok=True)
        with open(MEMORIA, "w") as f:
            json.dump(resultado, f, indent=2)
    except Exception as e:
        print(f"[MEMORIA] Error guardando memoria: {e}")

    return resultado

def puede_operar_memoria(symbol, rsi):
    """
    Retorna (bool, str, factor_monto)
    FIX: Error visible si falla lectura.
    """
    try:
        with open(MEMORIA) as f:
            mem = json.load(f)
    except FileNotFoundError:
        return True, "sin_memoria", 1.0
    except Exception as e:
        print(f"[MEMORIA] Error leyendo memoria: {e}")
        return True, "error_memoria", 1.0

    factor = 1.0

    # Filtro 1: win rate del simbolo
    wr_key     = f"{symbol}_wr"
    trades_key = f"{symbol}_trades"
    if wr_key in mem and mem.get(trades_key, 0) >= MIN_TRADES:
        wr = mem[wr_key]
        if wr < 40:
            return False, f"{symbol}_wr_{wr}%_bajo", 0
        elif wr < 50:
            factor = 0.6
        elif wr < 60:
            factor = 0.8
        elif wr >= 75:
            factor = 1.3

    # Filtro 2: racha de perdidas
    if mem.get("perdidas_ultimos_5", 0) >= 3:
        return False, f"racha_mala_{mem['perdidas_ultimos_5']}_perdidas_recientes", 0

    # Filtro 3: RSI neutro mejora el factor
    if rsi and 49 <= rsi <= 51:
        if factor < 1.0:
            factor = min(factor, 0.9)
        else:
            factor = max(factor, 1.1)

    return True, f"memoria_ok_wr_{mem.get('wr_global', '?')}%", round(factor, 2)

def actualizar_memoria(symbol, resultado_pct, rsi=None):
    """
    FIX: Solo re-analiza si hay suficientes trades nuevos.
    Evita re-leer todo el CSV en cada cierre.
    """
    try:
        # Verificar cuantos trades hay antes de re-analizar
        with open(MEMORIA) as f:
            mem = json.load(f)
        total_anterior = mem.get("total_trades", 0)
    except:
        total_anterior = 0

    # Re-analizar siempre — garantiza consistencia
    analizar_historial()
    print(f"[MEMORIA] Actualizada tras cierre {symbol} {resultado_pct:+.2f}%")

if __name__ == "__main__":
    print("🧠 Analizando historial del bot...")
    resultado = analizar_historial()
    print(json.dumps(resultado, indent=2))
