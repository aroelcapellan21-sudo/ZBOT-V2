# =========================================
# db.py — Capa de persistencia SQLite
# Reemplaza json.load/dump para archivos de estado.
# Escrituras atomicas. WAL mode para concurrencia.
# Sin librerias externas. Constitucion RESPETADA
# =========================================

import sqlite3
import json
import os
from datetime import datetime

DB_PATH = os.path.expanduser("~/bot-padre-v2/signals/bot.db")

# Archivos JSON a migrar automaticamente en el primer arranque
_MIGRAR = {
    "estado_diario":    "~/bot-padre-v2/signals/estado_diario.json",
    "estado_riesgo":    "~/bot-padre-v2/signals/estado_riesgo.json",
    "estado_consejero": "~/bot-padre-v2/signals/estado_consejero.json",
    "estado_termometro":"~/bot-padre-v2/signals/estado_termometro.json",
    "eventos_macro":    "~/bot-padre-v2/signals/eventos_macro.json",
    "trailing_data":    "~/bot-padre-v2/signals/trailing_data.json",
}

_ready = False


def _conn():
    conn = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _ensure_ready():
    if not _ready:
        init_db()


def init_db():
    """Crea la tabla y migra JSON existentes si la fila aun no existe."""
    global _ready
    _ready = True  # Marcar antes de cualquier query para cortar recursion
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS estado_json (
                tabla TEXT PRIMARY KEY,
                data  TEXT NOT NULL,
                ts    TEXT NOT NULL
            )
        """)
        for tabla, ruta in _MIGRAR.items():
            ruta = os.path.expanduser(ruta)
            if not os.path.exists(ruta):
                continue
            existing = conn.execute(
                "SELECT 1 FROM estado_json WHERE tabla=?", (tabla,)
            ).fetchone()
            if existing is not None:
                continue
            try:
                with open(ruta) as f:
                    data = json.load(f)
                conn.execute(
                    "INSERT OR REPLACE INTO estado_json (tabla, data, ts) VALUES (?,?,?)",
                    (tabla, json.dumps(data, ensure_ascii=False), datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                )
                print(f"[DB] Migrado {os.path.basename(ruta)} → '{tabla}'")
            except Exception as e:
                print(f"[DB] Error migrando {ruta}: {e}")


def json_get(tabla, default=None):
    """Lee el JSON almacenado para esta tabla. Retorna default si no existe."""
    _ensure_ready()
    try:
        with _conn() as conn:
            row = conn.execute(
                "SELECT data FROM estado_json WHERE tabla=?", (tabla,)
            ).fetchone()
            if row:
                return json.loads(row[0])
    except Exception as e:
        print(f"[DB] Error leyendo '{tabla}': {e}")
    return default


def json_set(tabla, data):
    """Guarda el JSON para esta tabla de forma atomica."""
    _ensure_ready()
    _json_set_raw(tabla, data)


def _json_set_raw(tabla, data):
    """Escritura directa (sin _ensure_ready para evitar recursion en init)."""
    try:
        with _conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO estado_json (tabla, data, ts) VALUES (?,?,?)",
                (tabla, json.dumps(data, ensure_ascii=False), datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            )
    except Exception as e:
        print(f"[DB] ERROR CRITICO guardando '{tabla}': {e}")
        raise RuntimeError(f"[DB] No se pudo guardar '{tabla}': {e}")


if __name__ == "__main__":
    print("Inicializando base de datos...")
    init_db()
    print(f"  DB: {DB_PATH}")
    with _conn() as conn:
        tablas = conn.execute("SELECT tabla, ts FROM estado_json ORDER BY tabla").fetchall()
    if tablas:
        print(f"  Tablas en DB ({len(tablas)}):")
        for t, ts in tablas:
            print(f"    {t:<25} (actualizado: {ts})")
    else:
        print("  DB vacia — se llenara en el primer ciclo del bot.")
