# =========================================
# historial_precios.py
# Registra precio de cada simbolo 1 vez por hora en SQLite.
# Retiene 7 dias (168 horas). Se auto-limpia.
# Sin librerias externas. Constitucion RESPETADA
# =========================================

import sqlite3
import json
import os
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta
from db import DB_PATH

SIMBOLOS      = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "AVAXUSDT"]
RETENER_HORAS = 168  # 7 dias


def _conn():
    conn = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _init_tabla():
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS historial_precios (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol  TEXT NOT NULL,
                precio  REAL NOT NULL,
                ts      TEXT NOT NULL
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_hp_symbol_ts ON historial_precios(symbol, ts)"
        )


def _fetch_precio(symbol):
    try:
        params = urllib.parse.urlencode({"symbol": symbol, "interval": "1m", "limit": 1})
        url = f"https://api.binance.com/api/v3/klines?{params}"
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode())
        return float(data[-1][4])
    except Exception as e:
        print(f"  [HISTORIAL_PRECIOS] Error fetching {symbol}: {e}")
        return None


def registrar_snapshot():
    """
    Guarda precio actual de cada simbolo si no se guardo en la ultima hora.
    Seguro llamarlo cada minuto — el gate interno evita duplicados.
    """
    _init_tabla()
    ahora      = datetime.now(timezone.utc)
    ts         = ahora.strftime("%Y-%m-%d %H:%M:%S")
    hora_corte = (ahora - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    guardados  = 0

    with _conn() as conn:
        for symbol in SIMBOLOS:
            ultimo = conn.execute(
                "SELECT ts FROM historial_precios WHERE symbol=? AND ts > ? LIMIT 1",
                (symbol, hora_corte)
            ).fetchone()
            if ultimo:
                continue  # Ya registrado en la ultima hora

            precio = _fetch_precio(symbol)
            if precio is None:
                continue

            conn.execute(
                "INSERT INTO historial_precios (symbol, precio, ts) VALUES (?,?,?)",
                (symbol, precio, ts)
            )
            guardados += 1

        # Limpiar registros mas viejos que RETENER_HORAS
        corte_viejo = (ahora - timedelta(hours=RETENER_HORAS)).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("DELETE FROM historial_precios WHERE ts < ?", (corte_viejo,))

    if guardados:
        print(f"  [HISTORIAL_PRECIOS] ✅ {guardados} precios guardados a las {ts[:16]} UTC")

    return guardados


def obtener_historial(symbol, horas=24):
    """Retorna lista de (ts, precio) del simbolo en las ultimas N horas."""
    _init_tabla()
    corte = (datetime.now(timezone.utc) - timedelta(hours=horas)).strftime("%Y-%m-%d %H:%M:%S")
    with _conn() as conn:
        rows = conn.execute(
            "SELECT ts, precio FROM historial_precios WHERE symbol=? AND ts > ? ORDER BY ts ASC",
            (symbol, corte)
        ).fetchall()
    return rows


def leer_historial_formateado(horas=24):
    """Texto listo para el asistente con evolucion de precios."""
    _init_tabla()
    texto = f"\nHISTORIAL DE PRECIOS (ultimas {horas}h UTC):\n"

    for symbol in SIMBOLOS:
        rows = obtener_historial(symbol, horas)
        if not rows:
            texto += f"  {symbol}: sin datos aun\n"
            continue

        primero_ts, primero_p = rows[0]
        ultimo_ts,  ultimo_p  = rows[-1]
        cambio_pct = round((ultimo_p - primero_p) / primero_p * 100, 2)
        signo      = "+" if cambio_pct >= 0 else ""
        precio_min = min(p for _, p in rows)
        precio_max = max(p for _, p in rows)

        texto += (
            f"  {symbol}: ${ultimo_p:,.2f}  ({signo}{cambio_pct}% en {horas}h)"
            f"  [{len(rows)} puntos]\n"
            f"    Rango: ${precio_min:,.2f} — ${precio_max:,.2f}"
            f"  |  Desde {primero_ts[:16]} hasta {ultimo_ts[:16]} UTC\n"
        )

    return texto


if __name__ == "__main__":
    print("📈 Historial de Precios\n")
    n = registrar_snapshot()
    print(f"\nRegistros nuevos: {n}")
    print(leer_historial_formateado(horas=24))
