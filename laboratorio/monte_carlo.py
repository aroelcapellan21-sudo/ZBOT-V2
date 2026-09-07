#!/usr/bin/env python3
"""L4 — Monte Carlo sobre los resultados ya medidos. Chequeo permanente.

Un backtest devuelve UN orden posible de los trades. Barajando ese orden, el
total sumado no cambia (con tamano fijo por trade, sumar % es proporcional a
sumar dolares), pero SI cambian dos cosas que deciden si el bot sobrevive:

  · el DRAWDOWN MAXIMO — el guardian corta en 10%
  · la RACHA PERDEDORA mas larga — el limitador diario corta en 4 seguidas

La pregunta que responde: el drawdown que se observo, ¿fue tipico o fue suerte?

Dos remuestreos, que responden cosas distintas:

  SHUFFLE (baraja el orden, mismos trades)
      "¿cuanto de lo que vi depende del orden en que salieron?"
      El total no cambia; cambian drawdown y rachas.

  BOOTSTRAP (remuestrea con reemplazo, cambia la composicion)
      "¿cuanto depende de QUE trades salieron?"
      Cambia todo, incluido el total. Da el IC del resultado.

SUPUESTO EXPLICITO: el bot opera con MONTO_FIJO por trade, no reinvierte. Por
eso la curva de capital es la suma acumulada de pnl_pct, no el compuesto.
Si algun dia el sizing pasa a ser proporcional, esto hay que rehacerlo.

Exit code 1 si algun estudio tiene el drawdown observado en un percentil
extremo (<5 o >95): significa que su resultado depende del orden, no del metodo.
"""
import argparse, sqlite3, sys
from collections import defaultdict
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("--db", default="/home/ariel/bot-padre-v2/data/resultados.db")
ap.add_argument("--min-trades", type=int, default=100)
ap.add_argument("--sims", type=int, default=10000)
ap.add_argument("--bloque", type=int, default=20,
                help="tamano del bloque al barajar. 1 = trade a trade, que EXAGERA el drawdown "
                     "porque destruye toda la estructura temporal: con bloque 1 salen 41 estudios "
                     "'extremos' de 108, con bloque 20 solo 14. Por eso el default es 20, no 1")
ap.add_argument("--patron", default="%", help="patron SQL de temas a analizar")
ap.add_argument("--top", type=int, default=10, help="cuantos estudios mostrar")
A = ap.parse_args()

def curva(p):
    """Capital acumulado en puntos porcentuales (tamano fijo por trade)."""
    return np.concatenate(([0.0], np.cumsum(p)))

def max_dd(p):
    e = curva(p)
    return float(np.max(np.maximum.accumulate(e) - e))

def racha_perdedora(p):
    peor = act = 0
    for x in p:
        act = act + 1 if x <= 0 else 0
        peor = max(peor, act)
    return peor

c = sqlite3.connect(A.db)
q = """select p.tema, t.pnl_pct from trades_backtest t join pruebas p on p.id = t.prueba_id
       where t.pnl_pct is not null and p.tema like ? order by t.ts_salida"""
d = defaultdict(list)
for tema, pct in c.execute(q, (A.patron,)):
    d[tema.replace(" · trades", "")].append(float(pct))
estudios = {k: np.array(v) for k, v in d.items() if len(v) >= A.min_trades}
if not estudios:
    sys.exit(f"[FATAL] ningun estudio con >= {A.min_trades} trades")

print("=" * 78)
print(f"L4 — MONTE CARLO · {len(estudios)} estudios con >= {A.min_trades} trades · "
      f"{A.sims:,} simulaciones cada uno")
print("=" * 78)
print(f"\nSHUFFLE — baraja el ORDEN en bloques de {A.bloque} (mismos trades, mismo total)")
print(f"  {'estudio':44s} {'n':>5s} {'DD obs':>8s} {'DD medio':>9s} {'pct':>5s} {'racha':>6s}")

rng = np.random.default_rng(7)
sospechosos = []
filas = []
for tema, p in sorted(estudios.items(), key=lambda x: -len(x[1])):
    dd_obs, ra_obs = max_dd(p), racha_perdedora(p)
    dds = np.empty(A.sims); ras = np.empty(A.sims, dtype=int)
    for i in range(A.sims):
        if A.bloque <= 1:
            q_ = rng.permutation(p)
        else:
            b = [p[j:j+A.bloque] for j in range(0, len(p), A.bloque)]
            q_ = np.concatenate([b[j] for j in rng.permutation(len(b))])
        dds[i] = max_dd(q_); ras[i] = racha_perdedora(q_)
    pct = float((dds < dd_obs).mean() * 100)
    filas.append((tema, len(p), dd_obs, dds.mean(), pct, ra_obs, ras.mean(), p))
    if pct < 5 or pct > 95: sospechosos.append((tema, pct, dd_obs, dds.mean()))

for tema, n, dd, ddm, pct, ra, ram, _ in filas[:A.top]:
    marca = " ⚠️" if pct < 5 or pct > 95 else ""
    print(f"  {tema[:44]:44s} {n:>5} {dd:>8.2f} {ddm:>9.2f} {pct:>4.0f}% {ra:>3}/{ram:>2.0f}{marca}")

print("\n  DD obs = drawdown observado (puntos %) · DD medio = promedio barajando")
print("  pct = percentil del observado (50 = tipico · <5 o >95 = el orden importo)")
print("  racha = perdedoras seguidas, observada / promedio barajado")

print("\n\nBOOTSTRAP — remuestrea QUE trades salieron (cambia el total)")
print(f"  {'estudio':44s} {'total obs':>10s} {'IC95% del total':>24s} {'P(>0)':>7s}")
sin_signo = []
for tema, n, dd, ddm, pct, ra, ram, p in filas[:A.top]:
    tot = float(p.sum())
    b = np.array([rng.choice(p, len(p), replace=True).sum() for _ in range(A.sims)])
    lo, hi = np.percentile(b, [2.5, 97.5])
    pp = 100 * (b > 0).mean()
    cruza = lo <= 0 <= hi
    if cruza: sin_signo.append(tema)
    print(f"  {tema[:44]:44s} {tot:>+10.2f} [{lo:>+9.2f}, {hi:>+9.2f}] {pp:>6.1f}%{' ⚠️' if cruza else ''}")

print("\n" + "=" * 78)
print(f"  estudios cuyo DRAWDOWN depende del orden (percentil extremo): {len(sospechosos)}")
for t, pct, dd, ddm in sospechosos[:6]:
    print(f"    ⚠️ {t[:50]:50s} pct {pct:>4.0f}%  obs {dd:.2f} vs medio {ddm:.2f}")
print(f"  estudios cuyo TOTAL no tiene signo definido (IC95% cruza cero): "
      f"{len(sin_signo)} de {min(A.top, len(filas))} mostrados")
ok = not sospechosos
print(f"\nVEREDICTO: {'ningun resultado depende del orden' if ok else '🔴 HAY RESULTADOS QUE DEPENDEN DEL ORDEN'}")
sys.exit(0 if ok else 1)
