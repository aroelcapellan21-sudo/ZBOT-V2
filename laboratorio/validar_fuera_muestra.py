#!/usr/bin/env python3
"""L3 — validacion fuera de muestra. Chequeo permanente, no de una vez.

Pregunta que responde: cuando se comparan varias configuraciones y se elige la
mejor, ¿esa eleccion GENERALIZA, o se esta eligiendo ruido?

Tres niveles, de menos a mas exigente:

  1. ESTABILIDAD POR ANIO — ¿el orden de las configuraciones se repite entre
     anios? Se mide con Spearman entre los ordenes de cada par de anios.
     rho=+1 el orden se repite · rho=0 es azar · rho<0 se invierte.

  2. DENTRO DE GRUPO — la misma prueba comparando solo configuraciones del
     mismo grupo (p. ej. fases de la misma moneda), para descartar que el
     desorden venga de "que moneda se movio ese anio" y no de la eleccion.

  3. WALK-FORWARD ENCADENADO — el mas exigente. Elegir la mejor con los datos
     hasta el mes N, medir que rindio en el mes N+1, correr la ventana y
     repetir. Se compara contra elegir AL AZAR y contra el TECHO (elegir
     sabiendo el futuro). Si no le gana al azar, el metodo no aporta nada.

Lee los trades ya guardados en data/resultados.db: no corre simulaciones.

Exit code 0 si la seleccion demuestra valor; 1 si no. Pensado para CI.
"""
import argparse, sqlite3, sys
from collections import defaultdict
import numpy as np

try:
    from scipy.stats import spearmanr
except ImportError:
    sys.exit("[FATAL] hace falta scipy (pip install scipy)")

ap = argparse.ArgumentParser()
ap.add_argument("--db", default="/home/ariel/bot-padre-v2/data/resultados.db")
ap.add_argument("--patron", default="torneo_%",
                help="patron SQL de los temas a comparar entre si (por defecto el torneo)")
ap.add_argument("--min-hist", type=int, default=24, help="meses de historia antes de la 1a eleccion")
ap.add_argument("--min-trades", type=int, default=8, help="trades minimos por anio para contar")
ap.add_argument("--incluir-sin-trades", action="store_true",
                help="cuenta los meses en que la elegida NO opero como resultado 0. OJO: sesga a "
                     "favor de la elegida, porque en meses malos 'no operar' parece una virtud")
A = ap.parse_args()

c = sqlite3.connect(A.db)
q = """select p.tema, t.ts_salida, t.pnl_pct from trades_backtest t join pruebas p on p.id = t.prueba_id
       where p.tema like ? and t.ts_salida is not null and t.pnl_pct is not null"""
tr = defaultdict(list)
for tema, ts, pct in c.execute(q, (A.patron,)):
    tr[tema.replace(" · trades", "")].append((ts, float(pct)))
if len(tr) < 2:
    sys.exit(f"[FATAL] hacen falta >=2 configuraciones con el patron {A.patron!r}; hay {len(tr)}")

combos = sorted(tr)
meses = sorted({ts[:7] for k in tr for ts, _ in tr[k]})
anios = sorted({ts[:4] for k in tr for ts, _ in tr[k]})
pnl_m = defaultdict(lambda: defaultdict(float)); n_m = defaultdict(lambda: defaultdict(int))
pnl_a = defaultdict(lambda: defaultdict(float)); n_a = defaultdict(lambda: defaultdict(int))
for k in combos:
    for ts, p in tr[k]:
        pnl_m[k][ts[:7]] += p; n_m[k][ts[:7]] += 1
        pnl_a[k][ts[:4]] += p; n_a[k][ts[:4]] += 1

print("=" * 72)
print(f"L3 — VALIDACION FUERA DE MUESTRA · {len(combos)} configuraciones · "
      f"{sum(len(v) for v in tr.values()):,} trades · {anios[0]}-{anios[-1]}")
print("=" * 72)
res = {}

# ── 1 · estabilidad por anio ────────────────────────────────────────────────
print("\n1 · ESTABILIDAD DEL ORDEN ENTRE ANIOS")
buenos = [a for a in anios if sum(1 for k in combos if n_a[k].get(a, 0) >= A.min_trades) >= len(combos) * 0.8]
if len(buenos) < 3:
    print(f"  ⚠️ solo {len(buenos)} anios utilizables — no alcanza"); res["estabilidad"] = None
else:
    glob = max(combos, key=lambda k: sum(pnl_a[k][a] for a in buenos))
    gana = sum(1 for a in buenos if max(combos, key=lambda k: pnl_a[k][a]) == glob)
    ordenes = {a: [sorted(combos, key=lambda k: -pnl_a[k][a]).index(k) for k in combos] for a in buenos}
    rs = [spearmanr(ordenes[a], ordenes[b])[0] for i, a in enumerate(buenos) for b in buenos[i+1:]]
    print(f"  anios: {', '.join(buenos)}")
    print(f"  mejor global: {glob} — gana {gana}/{len(buenos)} anios")
    print(f"  rho medio del orden: {np.mean(rs):+.3f} ({len(rs)} pares · {min(rs):+.3f} a {max(rs):+.3f})")
    res["estabilidad"] = np.mean(rs)

# ── 2 · dentro de grupo ─────────────────────────────────────────────────────
print("\n2 · DENTRO DE GRUPO (descarta que sea 'que activo se movio')")
grupos = defaultdict(list)
for k in combos:
    partes = k.split("_")
    grupos["_".join(partes[:2]) if len(partes) > 2 else k].append(k)
todos = []
for g, ks in sorted(grupos.items()):
    if len(ks) < 2: continue
    bb = [a for a in anios if all(n_a[k].get(a, 0) >= A.min_trades for k in ks)]
    if len(bb) < 3: continue
    ordenes = {a: [sorted(ks, key=lambda k: -pnl_a[k][a]).index(k) for k in ks] for a in bb}
    rs = [spearmanr(ordenes[a], ordenes[b])[0] for i, a in enumerate(bb) for b in bb[i+1:]]
    todos += rs
    print(f"  {g:22s} {len(ks)} config · {len(bb)} anios · rho medio {np.mean(rs):+.3f}")
res["dentro_grupo"] = np.mean(todos) if todos else None
if todos: print(f"  → rho medio dentro de grupo: {np.mean(todos):+.3f} ({len(todos)} pares)")

# ── 3 · walk-forward encadenado ─────────────────────────────────────────────
print(f"\n3 · WALK-FORWARD ENCADENADO (historia minima {A.min_hist} meses"
      f"{', meses sin operar incluidos' if A.incluir_sin_trades else ', meses sin operar EXCLUIDOS'})")
rng = np.random.default_rng(7)
el, az, techo = [], [], []
for i in range(A.min_hist, len(meses) - 1):
    hist, sig = meses[:i+1], meses[i+1]
    mejor = max(combos, key=lambda k: sum(pnl_m[k][m] for m in hist))
    if not A.incluir_sin_trades and n_m[mejor].get(sig, 0) == 0: continue
    el.append(pnl_m[mejor][sig])
    az.append(float(np.mean([pnl_m[k][sig] for k in combos])))
    techo.append(max(pnl_m[k][sig] for k in combos))
if len(el) < 10:
    print("  ⚠️ menos de 10 decisiones — no alcanza"); res["walkforward"] = None
else:
    d = np.array(el) - np.array(az)
    b = np.array([rng.choice(d, len(d), replace=True).sum() for _ in range(10000)])
    lo, hi = np.percentile(b, [2.5, 97.5])
    p = 100 * (b > 0).mean()
    print(f"  decisiones fuera de muestra: {len(el)}")
    print(f"  elegir el mejor : {sum(el):+9.2f}%   ·  al azar: {sum(az):+9.2f}%  ·  techo: {sum(techo):+9.2f}%")
    print(f"  captura del techo: {100*sum(el)/sum(techo):.1f}%" if sum(techo) else "")
    print(f"  ventaja sobre el azar: {d.sum():+.2f}% · IC95% [{lo:+.2f}, {hi:+.2f}] · P(>0) = {p:.1f}%")
    res["walkforward"] = p

print("\n" + "=" * 72)
# la vara del proyecto: se rechazo un cambio con P=83%
VARA = 83.0
ok_wf = res.get("walkforward") is not None and res["walkforward"] >= VARA
ok_est = res.get("estabilidad") is not None and res["estabilidad"] >= 0.3
print(f"  estabilidad entre anios : rho {res.get('estabilidad')} "
      f"({'OK' if ok_est else 'el orden no se sostiene'})")
print(f"  walk-forward            : P(>0) {res.get('walkforward')} "
      f"({'OK' if ok_wf else f'por debajo de la vara del proyecto ({VARA}%)'})")
veredicto = ok_wf and ok_est
print(f"\nVEREDICTO: {'la seleccion demuestra valor' if veredicto else '🔴 ELEGIR LA MEJOR NO ESTA RESPALDADO'}")
sys.exit(0 if veredicto else 1)
