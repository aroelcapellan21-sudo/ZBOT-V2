# =========================================
# consultar.py — Consultas de LECTURA sobre data/resultados.db
#
# NO ES CODIGO DE PRODUCCION. Solo lee. Ningun modulo del bot lo importa.
#
# Ejemplos:
#   python3 consultar.py pruebas --moneda SOLUSDT --fase LATERAL
#   python3 consultar.py perdidas --moneda SOLUSDT --fase LATERAL --desde 2025-01-01 --hasta 2026-01-01
#   python3 consultar.py metricas 3
#   python3 consultar.py sql "SELECT veredicto, COUNT(*) FROM pruebas GROUP BY veredicto"
# =========================================

import argparse
import sqlite3
import sys

from resultados_db import DB_PATH


def _conn():
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def _tabla(filas, columnas):
    if not filas:
        print("Sin resultados.")
        return
    anchos = [max(len(c), max(len(str(f[c] if f[c] is not None else "—")) for f in filas))
              for c in columnas]
    print(" | ".join(c.ljust(a) for c, a in zip(columnas, anchos)))
    print("-+-".join("-" * a for a in anchos))
    for f in filas:
        print(" | ".join(str(f[c] if f[c] is not None else "—").ljust(a)
                         for c, a in zip(columnas, anchos)))
    print(f"\n{len(filas)} fila(s).")


def cmd_pruebas(args):
    sql = "SELECT id, fecha, moneda, fase, tema, veredicto, reporte FROM pruebas WHERE 1=1"
    p = []
    for campo, valor in (("moneda", args.moneda), ("fase", args.fase),
                         ("veredicto", args.veredicto)):
        if valor:
            sql += f" AND {campo}=?"
            p.append(valor)
    if args.desde:
        sql += " AND fecha >= ?"; p.append(args.desde)
    if args.hasta:
        sql += " AND fecha < ?"; p.append(args.hasta)
    sql += " ORDER BY fecha, id"
    with _conn() as c:
        _tabla(c.execute(sql, p).fetchall(),
               ["id", "fecha", "moneda", "fase", "tema", "veredicto", "reporte"])


def cmd_metricas(args):
    with _conn() as c:
        cab = c.execute("SELECT fecha, tema, resumen FROM pruebas WHERE id=?",
                        (args.id,)).fetchone()
        if cab is None:
            print(f"No existe la prueba id={args.id}."); return
        print(f"[{cab['fecha']}] {cab['tema']}\n{cab['resumen']}\n")
        _tabla(c.execute("SELECT nombre, valor, unidad FROM metricas WHERE prueba_id=? "
                         "ORDER BY nombre", (args.id,)).fetchall(),
               ["nombre", "valor", "unidad"])


def cmd_perdidas(args):
    """Cuenta y resume operaciones simuladas perdedoras. Filtra por moneda/fase/periodo."""
    sql = ("SELECT COUNT(*) AS trades, "
           "SUM(CASE WHEN t.pnl_usdt < 0 THEN 1 ELSE 0 END) AS perdidas, "
           "SUM(CASE WHEN t.pnl_usdt > 0 THEN 1 ELSE 0 END) AS ganadas, "
           "ROUND(SUM(t.pnl_usdt), 4) AS pnl_usdt "
           "FROM trades_backtest t WHERE 1=1")
    p = []
    if args.moneda:
        sql += " AND t.symbol=?"; p.append(args.moneda)
    if args.fase:
        sql += " AND t.fase=?"; p.append(args.fase)
    if args.desde:
        sql += " AND t.ts_entrada >= ?"; p.append(args.desde)
    if args.hasta:
        sql += " AND t.ts_entrada < ?"; p.append(args.hasta)
    with _conn() as c:
        _tabla(c.execute(sql, p).fetchall(), ["trades", "perdidas", "ganadas", "pnl_usdt"])
    print("⚠️  Son operaciones SIMULADAS de las pruebas cargadas, no operaciones reales "
          "de la cuenta (esas estan en auditoria.csv).")


def cmd_sql(args):
    q = args.query.strip()
    if not q.lower().startswith(("select", "with")):
        print("Solo se permiten consultas SELECT/WITH (la DB se abre en modo lectura).")
        sys.exit(1)
    with _conn() as c:
        filas = c.execute(q).fetchall()
        _tabla(filas, list(filas[0].keys()) if filas else [])


def main():
    ap = argparse.ArgumentParser(description="Consultas sobre la DB de resultados de investigacion")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("pruebas", help="listar pruebas registradas")
    for f in ("--moneda", "--fase", "--veredicto", "--desde", "--hasta"):
        p1.add_argument(f)
    p1.set_defaults(func=cmd_pruebas)

    p2 = sub.add_parser("metricas", help="metricas de una prueba")
    p2.add_argument("id", type=int)
    p2.set_defaults(func=cmd_metricas)

    p3 = sub.add_parser("perdidas", help="conteo de trades simulados y perdidas")
    for f in ("--moneda", "--fase", "--desde", "--hasta"):
        p3.add_argument(f)
    p3.set_defaults(func=cmd_perdidas)

    p4 = sub.add_parser("sql", help="consulta SELECT libre")
    p4.add_argument("query")
    p4.set_defaults(func=cmd_sql)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
