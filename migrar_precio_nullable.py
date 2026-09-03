"""migrar_precio_nullable.py — quita el NOT NULL de trades_backtest.precio_entrada.

NO ES CODIGO DE PRODUCCION y es de UN SOLO USO. Escribe solo sobre
data/resultados.db (o RESULTADOS_DB). No toca signals/bot.db, auditoria.csv ni
billetera.json, y ningun modulo del bot lo importa.

Por que un script aparte y no _migrar(): esa funcion tiene documentado que solo
hace ALTER TABLE ADD COLUMN y CREATE INDEX, sin DROP ni reconstruccion. Esa
promesa es lo que la hace segura de reejecutar en cada init_db(). Recrear una
tabla ahi dentro la romperia.

SQLite no permite quitar un NOT NULL con ALTER, asi que se sigue el
procedimiento oficial: tabla nueva -> copiar -> drop -> rename -> indices, todo
en una transaccion. Verificado antes de correr: ninguna otra tabla referencia
trades_backtest.

    python3 migrar_precio_nullable.py --dry-run
    python3 migrar_precio_nullable.py
"""
import argparse
import os
import shutil
import sqlite3
import sys
from datetime import datetime

DB = os.environ.get("RESULTADOS_DB",
                    os.path.expanduser("~/bot-padre-v2/data/resultados.db"))

NUEVA = """
CREATE TABLE trades_backtest_nueva (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    prueba_id       INTEGER NOT NULL REFERENCES pruebas(id) ON DELETE CASCADE,
    symbol          TEXT NOT NULL,
    fase            TEXT NOT NULL,
    ts_entrada      TEXT NOT NULL,
    ts_salida       TEXT,
    precio_entrada  REAL,
    precio_salida   REAL,
    motivo_cierre   TEXT,
    monto_usdt      REAL,
    pnl_pct         REAL,
    pnl_usdt        REAL,
    rsi_entrada     REAL,
    velas           INTEGER,
    trade_id_origen TEXT,
    ts_salida_derivada INTEGER DEFAULT 0
)"""

INDICES = [
    "CREATE INDEX idx_trades_symbol_fase_ts ON trades_backtest(symbol, fase, ts_entrada)",
    "CREATE INDEX idx_trades_prueba ON trades_backtest(prueba_id)",
    "CREATE UNIQUE INDEX ux_trades_clave ON trades_backtest(prueba_id, symbol, ts_entrada)",
    "CREATE INDEX idx_trades_ts ON trades_backtest(ts_entrada)",
]

COLS = ("id", "prueba_id", "symbol", "fase", "ts_entrada", "ts_salida",
        "precio_entrada", "precio_salida", "motivo_cierre", "monto_usdt",
        "pnl_pct", "pnl_usdt", "rsi_entrada", "velas", "trade_id_origen",
        "ts_salida_derivada")


def estado(conn):
    q = lambda s: conn.execute(s).fetchone()[0]
    return {
        "trades": q("SELECT COUNT(*) FROM trades_backtest"),
        "pruebas": q("SELECT COUNT(*) FROM pruebas"),
        "metricas": q("SELECT COUNT(*) FROM metricas"),
        "max_id": q("SELECT COALESCE(MAX(id), 0) FROM trades_backtest"),
        "suma_pnl": q("SELECT COALESCE(ROUND(SUM(pnl_pct), 6), 0) FROM trades_backtest"),
        "indices": sorted(r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND tbl_name='trades_backtest' AND name NOT LIKE 'sqlite_%'")),
        "not_null": sorted(r[1] for r in conn.execute(
            "PRAGMA table_info(trades_backtest)") if r[3]),
    }


def main(dry):
    if not os.path.exists(DB):
        sys.exit(f"no existe: {DB}")
    conn = sqlite3.connect(DB)
    antes = estado(conn)
    print(f"DB: {DB}")
    print(f"  antes -> {antes['pruebas']} pruebas, {antes['trades']:,} trades, "
          f"{antes['metricas']} metricas, max(id)={antes['max_id']:,}")
    print(f"  NOT NULL actuales: {antes['not_null']}")
    print(f"  indices: {antes['indices']}")

    if "precio_entrada" not in antes["not_null"]:
        print("\n  precio_entrada YA es nullable — nada que hacer.")
        return 0
    if dry:
        print("\n  [DRY-RUN] no se escribe nada.")
        return 0

    bak = f"{DB}.pre_nullable_{datetime.now():%Y%m%d_%H%M%S}.bak"
    conn.execute(f"VACUUM INTO '{bak}'")
    print(f"\n  backup: {bak}  ({os.path.getsize(bak):,} bytes)")

    conn.execute("PRAGMA foreign_keys=OFF")
    try:
        conn.execute("BEGIN")
        conn.execute(NUEVA)
        conn.execute(f"INSERT INTO trades_backtest_nueva ({','.join(COLS)}) "
                     f"SELECT {','.join(COLS)} FROM trades_backtest")
        copiadas = conn.execute("SELECT COUNT(*) FROM trades_backtest_nueva").fetchone()[0]
        if copiadas != antes["trades"]:
            raise RuntimeError(f"copiadas {copiadas} != {antes['trades']} originales")
        conn.execute("DROP TABLE trades_backtest")
        conn.execute("ALTER TABLE trades_backtest_nueva RENAME TO trades_backtest")
        for idx in INDICES:
            conn.execute(idx)
        conn.execute("COMMIT")
    except Exception as e:
        conn.execute("ROLLBACK")
        print(f"\n  ROLLBACK — nada se modifico: {e}")
        raise
    finally:
        conn.execute("PRAGMA foreign_keys=ON")

    despues = estado(conn)
    ok_fk = list(conn.execute("PRAGMA foreign_key_check"))
    integridad = conn.execute("PRAGMA integrity_check").fetchone()[0]

    print(f"\n  despues -> {despues['pruebas']} pruebas, {despues['trades']:,} trades, "
          f"{despues['metricas']} metricas, max(id)={despues['max_id']:,}")
    print(f"  NOT NULL ahora: {despues['not_null']}")
    print(f"  indices: {despues['indices']}")
    print(f"  integrity_check: {integridad}   foreign_key_check: "
          f"{'sin filas (OK)' if not ok_fk else ok_fk}")

    fallos = []
    for k in ("trades", "pruebas", "metricas", "max_id", "suma_pnl"):
        if antes[k] != despues[k]:
            fallos.append(f"{k}: {antes[k]} -> {despues[k]}")
    if antes["indices"] != despues["indices"]:
        fallos.append(f"indices: {antes['indices']} -> {despues['indices']}")
    if "precio_entrada" in despues["not_null"]:
        fallos.append("precio_entrada sigue NOT NULL")
    if integridad != "ok" or ok_fk:
        fallos.append("integridad")

    print("\n" + ("  ✅ OK — todo conservado" if not fallos
                  else "  ❌ DISCREPANCIAS:\n    " + "\n    ".join(fallos)))
    conn.close()
    return 1 if fallos else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    sys.exit(main(ap.parse_args().dry_run))
