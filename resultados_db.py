# =========================================
# resultados_db.py — Registro consultable de resultados de investigacion
#
# NO ES CODIGO DE PRODUCCION. Ningun modulo del bot importa este archivo.
# No abre ni cierra posiciones, no lee billetera, no toca signals/bot.db.
#
# Guarda en data/resultados.db lo que se PROBO (backtests, auditorias),
# no lo que se EJECUTO — el historial real sigue siendo auditoria.csv.
# =========================================

import os
import json
import sqlite3
from datetime import datetime

# Override por entorno para poder testear sin tocar la DB real
DB_PATH = os.environ.get(
    "RESULTADOS_DB",
    os.path.expanduser("~/bot-padre-v2/data/resultados.db")
)

VEREDICTOS = ("APLICADO", "PROMETEDOR", "DESCARTADO", "NO_CONCLUYENTE")
FASES = ("ALCISTA", "BAJISTA", "LATERAL", "TODAS")


def _conn():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Crea tablas, indices y la vista. Idempotente."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pruebas (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha          TEXT NOT NULL,
                tema           TEXT NOT NULL,
                tipo           TEXT NOT NULL,
                moneda         TEXT,
                fase           TEXT,
                ventana_desde  TEXT,
                ventana_hasta  TEXT,
                parametros     TEXT,
                veredicto      TEXT NOT NULL,
                resumen        TEXT NOT NULL,
                reporte        TEXT,
                commit_git     TEXT,
                creado_ts      TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS metricas (
                prueba_id  INTEGER NOT NULL REFERENCES pruebas(id) ON DELETE CASCADE,
                nombre     TEXT NOT NULL,
                valor      REAL NOT NULL,
                unidad     TEXT,
                PRIMARY KEY (prueba_id, nombre)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS trades_backtest (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                prueba_id       INTEGER NOT NULL REFERENCES pruebas(id) ON DELETE CASCADE,
                symbol          TEXT NOT NULL,
                fase            TEXT NOT NULL,
                ts_entrada      TEXT NOT NULL,
                ts_salida       TEXT,
                precio_entrada  REAL NOT NULL,
                precio_salida   REAL,
                motivo_cierre   TEXT,
                monto_usdt      REAL,
                pnl_pct         REAL,
                pnl_usdt        REAL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_pruebas_moneda_fase ON pruebas(moneda, fase)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_pruebas_fecha       ON pruebas(fecha)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_symbol_fase_ts ON trades_backtest(symbol, fase, ts_entrada)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_prueba         ON trades_backtest(prueba_id)")
        conn.execute("""
            CREATE VIEW IF NOT EXISTS v_indice AS
            SELECT p.id, p.fecha, p.moneda, p.fase, p.tema,
                   MAX(CASE WHEN m.nombre='n'      THEN m.valor END) AS n,
                   MAX(CASE WHEN m.nombre='wr'     THEN m.valor END) AS wr,
                   MAX(CASE WHEN m.nombre='pf'     THEN m.valor END) AS pf,
                   MAX(CASE WHEN m.nombre='sharpe' THEN m.valor END) AS sharpe,
                   p.veredicto, p.resumen, p.reporte
            FROM pruebas p LEFT JOIN metricas m ON m.prueba_id = p.id
            GROUP BY p.id
        """)
    return DB_PATH


def registrar_prueba(fecha, tema, tipo, veredicto, resumen,
                     moneda=None, fase=None, ventana_desde=None, ventana_hasta=None,
                     parametros=None, reporte=None, commit_git=None):
    """Inserta una prueba cerrada y devuelve su id."""
    if veredicto not in VEREDICTOS:
        raise ValueError(f"veredicto invalido: {veredicto!r}. Validos: {VEREDICTOS}")
    if fase is not None and fase not in FASES:
        raise ValueError(f"fase invalida: {fase!r}. Validas: {FASES}")
    if parametros is not None and not isinstance(parametros, str):
        parametros = json.dumps(parametros, ensure_ascii=False, sort_keys=True)
    with _conn() as conn:
        cur = conn.execute("""
            INSERT INTO pruebas (fecha, tema, tipo, moneda, fase, ventana_desde, ventana_hasta,
                                 parametros, veredicto, resumen, reporte, commit_git, creado_ts)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (fecha, tema, tipo, moneda, fase, ventana_desde, ventana_hasta,
              parametros, veredicto, resumen, reporte, commit_git,
              datetime.now().isoformat(timespec="seconds")))
        return cur.lastrowid


def agregar_metricas(prueba_id, metricas, unidades=None):
    """metricas: dict {nombre: valor}. Un valor None NO se inserta (dato ausente != 0)."""
    unidades = unidades or {}
    filas = [(prueba_id, k, float(v), unidades.get(k))
             for k, v in metricas.items() if v is not None]
    with _conn() as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO metricas (prueba_id, nombre, valor, unidad) VALUES (?,?,?,?)",
            filas)
    return len(filas)


def agregar_trades(prueba_id, trades):
    """trades: lista de dicts con las claves de la tabla trades_backtest."""
    campos = ("symbol", "fase", "ts_entrada", "ts_salida", "precio_entrada",
              "precio_salida", "motivo_cierre", "monto_usdt", "pnl_pct", "pnl_usdt")
    filas = [tuple([prueba_id] + [t.get(c) for c in campos]) for t in trades]
    with _conn() as conn:
        conn.executemany(
            f"INSERT INTO trades_backtest (prueba_id, {','.join(campos)}) "
            f"VALUES ({','.join('?' * (len(campos) + 1))})", filas)
    return len(filas)


def _fmt(valor, decimales=2, sufijo=""):
    return "—" if valor is None else f"{valor:,.{decimales}f}{sufijo}"


def exportar_indice(destino=None):
    """Genera la tabla Markdown de las pruebas cargadas EN LA DB.

    ⚠️ NUNCA sobrescribe INDICE_RESULTADOS.md. Mientras el backfill de los reportes
    anteriores al 2026-09-02 no este hecho, la DB tiene menos filas que el indice a mano:
    regenerarlo borraria historial. Escribe a un archivo aparte y la fila se pega a mano.
    """
    indice_real = os.path.expanduser("~/bot-padre-v2/INDICE_RESULTADOS.md")
    if destino and os.path.abspath(destino) == os.path.abspath(indice_real):
        raise RuntimeError(
            "Negado: exportar_indice() no sobrescribe INDICE_RESULTADOS.md. "
            "La DB aun no contiene las filas historicas (backfill pendiente).")
    lineas = ["| Fecha | Moneda | Fase | Qué se probó | n | WR | PF | Sharpe | Veredicto | Resultado | Reporte |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
    with _conn() as conn:
        conn.row_factory = sqlite3.Row
        for r in conn.execute("SELECT * FROM v_indice ORDER BY fecha, id"):
            lineas.append(
                f"| {r['fecha']} | {r['moneda'] or '—'} | {r['fase'] or '—'} | {r['tema']} | "
                f"{_fmt(r['n'], 0)} | {_fmt(r['wr'], 1, '%')} | {_fmt(r['pf'], 3)} | "
                f"{_fmt(r['sharpe'], 3)} | {r['veredicto']} | {r['resumen']} | "
                f"`{r['reporte'] or '—'}` |")
    salida = "\n".join(lineas)
    if destino:
        with open(destino, "w", encoding="utf-8") as f:
            f.write(salida + "\n")
    return salida


if __name__ == "__main__":
    ruta = init_db()
    with _conn() as conn:
        tablas = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table','view') ORDER BY name")]
        n = conn.execute("SELECT COUNT(*) FROM pruebas").fetchone()[0]
    print(f"DB lista: {ruta}")
    print(f"Objetos: {', '.join(tablas)}")
    print(f"Pruebas cargadas: {n}")
