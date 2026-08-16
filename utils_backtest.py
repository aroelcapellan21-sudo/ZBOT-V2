"""
utils_backtest.py — utilidades compartidas para backtests históricos.

export_trades_csv() guarda la lista de trades que cada backtest ya arma en
memoria (dentro de simular()) a reports/raw/<nombre>_<fecha>.csv, para que
el detalle por trade sobreviva a la corrida y no solo el agregado.

NO usar para forward/live tracking — eso es sistema_c/store.py.
"""
import csv
import os
from datetime import datetime, timezone

RAW_DIR = os.path.expanduser("~/bot-padre-v2/reports/raw")

CSV_FIELDS = [
    "trade_id",
    "symbol",
    "entry_timestamp",
    "exit_timestamp",
    "entry_price",
    "exit_price",
    "cantidad",
    "fee_entrada",
    "fee_salida",
    "pnl_bruto",
    "pnl_neto",
    "resultado",
    "fase",
]


def export_trades_csv(trades, nombre_backtest, fecha=None):
    """
    Escribe `trades` (lista de dicts) a reports/raw/<nombre_backtest>_<fecha>.csv.

    Cada dict de `trades` puede traer cualquier subconjunto de CSV_FIELDS;
    las claves ausentes quedan vacías y las claves de más se ignoran. Si un
    trade no trae "trade_id", se genera uno como "<nombre_backtest>-000001".

    fecha: string "YYYY-MM-DD"; por defecto la fecha de hoy en UTC.

    Devuelve la ruta del archivo escrito.
    """
    if fecha is None:
        fecha = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    os.makedirs(RAW_DIR, exist_ok=True)
    ruta = os.path.join(RAW_DIR, f"{nombre_backtest}_{fecha}.csv")

    with open(ruta, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for i, trade in enumerate(trades, start=1):
            fila = {campo: trade.get(campo, "") for campo in CSV_FIELDS}
            if not fila["trade_id"]:
                fila["trade_id"] = f"{nombre_backtest}-{i:06d}"
            writer.writerow(fila)

    return ruta
