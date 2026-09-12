#!/usr/bin/env python3
"""Metricas de un raw del torneo, con el signo del short bien puesto.

POR QUE EXISTE (12-sep-2026). Las tablas del torneo del 24-ago se armaron con
un script que no quedo guardado en ningun lado (item 0c), y ese script calculo
el retorno del short como (entrada - salida)/SALIDA en vez de /ENTRADA. Eso
infla los ganadores —donde la salida es menor— y achica los perdedores, con lo
que los 5 francotiradores BAJISTA quedaron publicados mejor de lo que son:
AVAX 1,262 cuando es 1,068, y el grupo 1,074 cuando es 0,921, que ademas pierde
plata. Los LATERAL y ALCISTA no estaban afectados (son long).

La correccion vive aca, en la herramienta, y no en la cabeza del que la usa:
la fase se deduce del propio trade (campo "accion") y el signo se aplica solo.

Formulas identicas a resultados_db.calcular_metricas() para que los numeros
sean comparables con la DB: PF sobre la suma de ganancias/perdidas, Sharpe
media/std * sqrt(252) con std poblacional, drawdown sobre la curva acumulada
de puntos porcentuales.

Uso:
    python3 sistema_c/metricas_torneo.py reports/raw/torneo_avax_bajista_2026-08-23.json
    python3 sistema_c/metricas_torneo.py --combo a.json b.json c.json
    python3 sistema_c/metricas_torneo.py --todos          # los 15 + los 3 grupos
    python3 sistema_c/metricas_torneo.py --todos --bruto  # sin descontar comision
"""

import argparse
import glob
import json
import math
import os
import re

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMISION_PP = 0.2      # 0,1 % por lado, ida y vuelta
MONEDAS = ["btc", "eth", "sol", "bnb", "avax"]
FASES = ["alcista", "lateral", "bajista"]


def _fase_del_trade(t, archivo):
    """La fase sale del propio trade; el nombre del archivo es el respaldo."""
    accion = (t.get("accion") or "").upper()
    if accion in ("ALCISTA", "LATERAL", "BAJISTA"):
        return accion
    m = re.search(r"(alcista|lateral|bajista)", os.path.basename(archivo))
    return m.group(1).upper() if m else "ALCISTA"


def cargar(archivo, comision=COMISION_PP):
    """[(ts_salida, retorno_pct_neto)] con el signo correcto por fase."""
    with open(archivo, encoding="utf-8") as fh:
        d = json.load(fh)
    trades = d.get("trades") if isinstance(d, dict) else d
    # hay raws con otra forma (barridos por escenario, resumenes): no son series
    # de trades y se devuelven vacios en vez de reventar.
    if not isinstance(trades, list) or (trades and "cambio_pct" not in trades[0]):
        return []
    filas = []
    for t in trades:
        cambio = t["cambio_pct"]
        # SHORT: se gana cuando el precio BAJA, y el retorno es sobre el capital
        # comprometido, o sea sobre el precio de ENTRADA -> es -cambio_pct.
        # Dividir por la salida es el error que motivo este script.
        r = -cambio if _fase_del_trade(t, archivo) == "BAJISTA" else cambio
        filas.append((t.get("ts_salida") or t["ts_entrada"], r - comision))
    return filas


def metricas(filas):
    if not filas:
        return {"n": 0}
    v = [x for _, x in sorted(filas)]
    n = len(v)
    g = [x for x in v if x > 0]
    p = [x for x in v if x <= 0]
    total_p = abs(sum(p))
    media = sum(v) / n
    std = math.sqrt(sum((x - media) ** 2 for x in v) / n)

    curva = pico = caida = 0.0
    for x in v:
        curva += x
        pico = max(pico, curva)
        caida = max(caida, pico - curva)

    racha = act = 0
    for x in v:
        act = act + 1 if x <= 0 else 0
        racha = max(racha, act)

    return {"n": n, "wr": 100 * len(g) / n,
            "pf": (sum(g) / total_p) if total_p else None,
            "sharpe": (media / std * math.sqrt(252)) if std else None,
            "suma_pp": sum(v), "dd_max_pp": caida, "racha_perdidas": racha,
            "expectancy_pp": media}


def _fmt(m, nombre, ancho=22):
    if not m.get("n"):
        return f"{nombre:<{ancho}} sin trades"
    pf = f"{m['pf']:.3f}" if m["pf"] is not None else "—"
    sh = f"{m['sharpe']:+.3f}" if m["sharpe"] is not None else "—"
    return (f"{nombre:<{ancho}} {m['n']:>5} {m['wr']:>6.1f} {pf:>8} {sh:>8} "
            f"{m['suma_pp']:>+9.1f} {m['dd_max_pp']:>8.1f} {m['racha_perdidas']:>6}")


CAB = (f"{'francotirador':<22} {'n':>5} {'WR%':>6} {'PF':>8} {'Sharpe':>8} "
       f"{'suma pp':>9} {'DD pp':>8} {'racha':>6}")


def _buscar(moneda, fase, fecha=""):
    """(archivo, es_sustituto) para esa moneda y fase.

    Primero la corrida del propio torneo, la mas reciente que no este vacia —
    una vacia significa francotirador pausado por codigo, no ausencia de senal.
    Si no hay ninguna, cae a otro raw de la misma moneda y fase y lo devuelve
    MARCADO: mezclar corridas distintas sin decirlo es la clase de error que
    este script existe para no repetir.
    """
    propias = sorted(glob.glob(f"{RAIZ}/reports/raw/torneo_{moneda}_{fase}_*{fecha}*.json"),
                     reverse=True)
    for a in propias:
        if cargar(a):
            return a, False
    # BTC y ETH ALCISTA del torneo se guardaron con OTRO nombre
    # (<moneda>_alcista_evaluar_literal_9anios_baseline_2026-08-22.json).
    # Verificado el 12-sep: reproducen exacto el PF publicado (1,369 y 1,438).
    gemelas = sorted(glob.glob(f"{RAIZ}/reports/raw/{moneda}_{fase}_*9anios*{fecha or '2026-08-2'}*.json"),
                     reverse=True)
    for a in gemelas:
        if cargar(a):
            return a, False
    otras = [a for a in glob.glob(f"{RAIZ}/reports/raw/{moneda}_{fase}_*.json") if cargar(a)]
    if otras:
        return max(otras, key=lambda a: len(cargar(a))), True
    return None, False


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("archivos", nargs="*", help="raws a medir, uno por linea de salida")
    ap.add_argument("--combo", action="store_true", help="combinar los archivos en una sola cartera")
    ap.add_argument("--todos", action="store_true", help="los 15 del torneo mas los 3 grupos de fase")
    ap.add_argument("--bruto", action="store_true", help="no descontar comision (para comparar con la DB)")
    ap.add_argument("--fecha", default="", help="fijar la corrida por fecha, p.ej. 2026-08-23 (por defecto, la mas reciente)")
    args = ap.parse_args()
    com = 0.0 if args.bruto else COMISION_PP

    print(f"comision aplicada: {com} pp por trade\n{CAB}")

    if args.todos:
        grupos = {f: [] for f in FASES}
        for fase in FASES:
            for moneda in MONEDAS:
                arch, sustituto = _buscar(moneda, fase, args.fecha)
                nombre = f"{moneda.upper()} {fase[:3].upper()}" + (" *" if sustituto else "")
                if not arch:
                    print(f"{nombre:<22} sin raw del torneo (item 0c)")
                    continue
                filas = cargar(arch, com)
                grupos[fase] += filas
                print(_fmt(metricas(filas), nombre))
            print()
        print(CAB.replace("francotirador", "grupo        "))
        for fase in FASES:
            print(_fmt(metricas(grupos[fase]), f"GRUPO {fase.upper()}"))
        print("\n* no hay corrida del torneo para esa celda: se uso otro raw de la misma")
        print("  moneda y fase, que NO es comparable trade a trade con el resto.")
        return 0

    if not args.archivos:
        ap.error("pasa al menos un raw, o --todos")

    if args.combo:
        filas = [f for a in args.archivos for f in cargar(a, com)]
        print(_fmt(metricas(filas), f"COMBO ({len(args.archivos)})"))
    else:
        for a in args.archivos:
            print(_fmt(metricas(cargar(a, com)), os.path.basename(a)[:22]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
