"""
importar_raw.py — carga reports/raw/ a data/resultados.db.

NO ES CODIGO DE PRODUCCION. Lectura sobre reports/raw/ (nunca escribe ahi),
escritura solo sobre data/resultados.db. No toca signals/bot.db, auditoria.csv
ni billetera.json, y ningun modulo del bot lo importa.

Reejecutable: cada prueba se identifica por hash del contenido normalizado, asi
que correrlo dos veces no duplica nada.

    python3 importar_raw.py --dry-run     # que haria, sin escribir
    python3 importar_raw.py               # importa
    python3 importar_raw.py --solo csv    # solo los 10 CSV (los unicos con USD)

Reglas que respeta, verificadas en dry-run el 2026-09-02:
  - No inventa capital_usdt ni pnl_usdt: los JSON no traen monto, queda NULL.
  - No inventa fase: si no consta, va DESCONOCIDA (nunca TODAS).
  - Cada rama de un JSON anidado es una prueba propia, con su ruta en escenario.
  - La insercion de trades ocurre en un unico lugar: registrar_backtest().
"""
import argparse
import collections
import csv
import glob
import json
import os
import re
from datetime import datetime, timedelta

import resultados_db as R

RAW = os.path.expanduser("~/bot-padre-v2/reports/raw")
CLAVES_TRADE = {"entrada", "salida", "ts_entrada", "symbol", "cambio_pct"}
PAT_MONEDA = re.compile(r"(btc|eth|sol|bnb|avax|link|xrp)", re.I)
PAT_FASE = re.compile(r"(alcista|bajista|lateral)", re.I)
# La fecha del nombre del archivo NO es contenido de la prueba: dos corridas del
# mismo estudio en dias distintos son la misma prueba. origen_archivo conserva
# el nombre completo, asi que la trazabilidad no se pierde.
PAT_FECHA = re.compile(r"_?\d{4}-\d{2}-\d{2}$")


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def moneda_de(trade, archivo):
    s = trade.get("symbol")
    if s:
        return s.upper().replace("USDT", "") + "USDT"
    m = PAT_MONEDA.search(os.path.basename(archivo))
    return (m.group(1).upper() + "USDT") if m else None


def fase_de(trade, archivo):
    """Fase REAL o DESCONOCIDA. Nunca 'TODAS' por defecto: eso afirmaria que la
    prueba cubrio las tres fases. Cobertura medida: 26,6%."""
    a = (trade.get("accion") or trade.get("fase") or "").upper()
    if a in ("ALCISTA", "BAJISTA", "LATERAL"):
        return a
    m = PAT_FASE.search(os.path.basename(archivo))
    return m.group(1).upper() if m else "DESCONOCIDA"


def canonico(t, archivo):
    """Normaliza los 5 esquemas JSON. ts_salida ausente se deriva de `velas`."""
    ts_e, ts_s, derivada = t.get("ts_entrada"), t.get("ts_salida"), 0
    if not ts_s and t.get("velas") is not None:
        try:
            ts_s = (datetime.fromisoformat(str(ts_e).replace(" ", "T"))
                    + timedelta(hours=4 * int(t["velas"]))).isoformat()
            derivada = 1
        except Exception:
            ts_s = None
    return {
        "symbol": moneda_de(t, archivo),
        "fase": fase_de(t, archivo),
        "ts_entrada": ts_e,
        "ts_salida": ts_s,
        "ts_salida_derivada": derivada,
        "precio_entrada": t.get("entrada"),
        "precio_salida": t.get("salida"),
        "motivo_cierre": t.get("estado") or t.get("accion"),
        "pnl_pct": t.get("cambio_pct"),
        "pnl_usdt": None,    # los JSON no traen monto: no se inventa PnL en USD
        "monto_usdt": None,  # idem capital: ausente, no supuesto
        "rsi_entrada": _num(t.get("rsi")),
        "velas": t.get("velas"),
        "trade_id_origen": None,
    }


def canonico_csv(f):
    """Esquema de utils_backtest.export_trades_csv — el unico con PnL en USD."""
    return {
        "symbol": f.get("symbol"),
        "fase": f.get("fase") or "DESCONOCIDA",
        "ts_entrada": f.get("entry_timestamp"),
        "ts_salida": f.get("exit_timestamp"),
        "ts_salida_derivada": 0,
        "precio_entrada": _num(f.get("entry_price")),
        "precio_salida": _num(f.get("exit_price")),
        "motivo_cierre": f.get("resultado"),
        "pnl_pct": None,
        "pnl_usdt": _num(f.get("pnl_neto")),
        "monto_usdt": None,
        "rsi_entrada": None,
        "velas": None,
        "trade_id_origen": f.get("trade_id"),
    }


def bloques_de_trades(obj, ruta=()):
    """Devuelve (ruta_dentro_del_json, lista). Cada rama = un escenario propio."""
    if (isinstance(obj, list) and obj and isinstance(obj[0], dict)
            and len(set(obj[0]) & CLAVES_TRADE) >= 3):
        yield ruta, obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from bloques_de_trades(v, ruta + (str(k),))
    elif isinstance(obj, list):
        for i, v in enumerate(obj[:80]):
            yield from bloques_de_trades(v, ruta + (str(i),))


def fecha_de(nombre):
    m = re.search(r"(\d{4}-\d{2}-\d{2})", nombre)
    return m.group(1) if m else datetime.now().strftime("%Y-%m-%d")


def importar(dry=False, solo=None):
    if not dry:
        R.init_db()
    c = collections.Counter()
    archivos = sorted(glob.glob(f"{RAW}/*.json") + glob.glob(f"{RAW}/*.csv"))
    for ruta in archivos:
        base = os.path.basename(ruta)
        es_csv = ruta.endswith(".csv")
        if solo and not ruta.endswith(solo):
            continue
        try:
            if es_csv:
                bloques = [((), [canonico_csv(f) for f in csv.DictReader(open(ruta))])]
            else:
                bloques = [(r, [canonico(t, ruta) for t in tr])
                           for r, tr in bloques_de_trades(json.load(open(ruta)))]
            c["archivos_ok"] += 1
        except Exception as e:
            c["errores"] += 1
            print(f"  [ERROR] {base}: {e}")
            continue

        for rama, trades in bloques:
            trades = [t for t in trades if t["symbol"] and t["ts_entrada"]]
            if not trades:
                c["bloques_sin_trades"] += 1
                continue
            escenario = "/".join(rama) if rama else "baseline"
            stem = PAT_FECHA.sub("", base.rsplit(".", 1)[0])
            monedas = {t["symbol"] for t in trades}
            meta = dict(
                tema=stem + (f" · {escenario}" if rama else ""),
                moneda=monedas.pop() if len(monedas) == 1 else "MULTI",
                fase=trades[0]["fase"],
                escenario=escenario,
                fecha=fecha_de(base),
                veredicto="NO_CONCLUYENTE",
                resumen=(f"Importado de reports/raw/{base}. Metricas recalculadas "
                         f"desde {len(trades)} trades; el reporte .md asociado "
                         f"queda por enlazar a mano."),
                origen_archivo=f"reports/raw/{base}",
            )
            if dry:
                c["pruebas_nuevas"] += 1
                c["trades_insertados"] += len(trades)
                print(f"  [DRY] {base:<52} {escenario:<26} {len(trades):>6} trades")
                continue

            r = R.registrar_backtest(trades=trades, **meta)  # unico insert
            if r.creada:
                c["pruebas_nuevas"] += 1
                c["trades_insertados"] += r.trades_insertados
                c["trades_ya_existentes"] += r.trades_ignorados
            else:
                c["pruebas_existentes"] += 1
                c["trades_excluidos_por_duplicado"] += r.trades_ignorados
                print(f"  [DUP] {base} :: {escenario} -> ya existe como prueba "
                      f"{r.prueba_id} ({r.trades_ignorados} trades no se reimportan)")

    print("\n" + "=" * 62)
    for k in ("archivos_ok", "errores", "pruebas_nuevas", "pruebas_existentes",
              "trades_insertados", "trades_ya_existentes",
              "trades_excluidos_por_duplicado", "bloques_sin_trades"):
        print(f"  {k:<32} {c[k]:>8,}")
    return c


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Importa reports/raw/ a data/resultados.db")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--solo", choices=["csv", "json"])
    a = ap.parse_args()
    importar(dry=a.dry_run,
             solo=(".csv" if a.solo == "csv" else ".json" if a.solo == "json" else None))
