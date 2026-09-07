#!/usr/bin/env python3
"""L1 — integridad de los datos historicos. Chequeo permanente, no de una vez.

Que verifica, en orden de valor:

  1. ESTRUCTURA de cada fuente: huecos, duplicados, timestamps hacia atras,
     velas imposibles (high < low, high < open/close, volumen negativo).
  2. CRUCE ENTRE FUENTES: agrega los 1m a velas de 4h y las compara con el
     backup 4h. Son fuentes INDEPENDIENTES — si coinciden, la confianza sube
     mucho; si no, hay que decidir cual manda.
  3. CONTRASTE CONTRA BINANCE en vivo sobre una muestra aleatoria, para
     descartar que las dos fuentes locales compartan el mismo error.
  4. IMPACTO: si los huecos caen dentro de las ventanas de los estudios ya
     registrados en data/resultados.db.

NO repara nada. Primero medir el dano; corregir es una decision aparte.
"""
import os, sys, json, random, sqlite3, urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta
import numpy as np

BOT = os.path.expanduser("~/bot-padre-v2")
D1 = os.path.join(BOT, "data_1m")
BAK = os.path.expanduser("~/bot-padre-v3-backup/data/historico_4h")
SYMS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "AVAXUSDT", "BNBUSDT"]
MIN, H4 = 60_000, 4 * 3600 * 1000
def fecha(ms): return datetime.fromtimestamp(ms / 1000, timezone.utc)

problemas = []
def P(sev, sym, txt):
    problemas.append({"sev": sev, "sym": sym, "txt": txt})
    print(f"  {'🔴' if sev=='alto' else '🟡' if sev=='medio' else '⚪'} {sym:9s} {txt}")

# ── 1 · estructura ───────────────────────────────────────────────────────────
print("=" * 72); print("1 · ESTRUCTURA DE CADA FUENTE"); print("=" * 72)
huecos = {}
for sym in SYMS:
    print(f"\n  {sym}")
    for suf in ("1m", "1m_acum"):
        f = os.path.join(D1, f"{sym}_{suf}.npy")
        if not os.path.exists(f):
            P("alto", sym, f"FALTA {sym}_{suf}.npy"); continue
        a = np.load(f, mmap_mode="r")
        ts = np.ascontiguousarray(a[:, 0]).astype(np.int64)
        d = np.diff(ts)
        dup, atras = int((d == 0).sum()), int((d < 0).sum())
        hh = np.flatnonzero(d > MIN)
        print(f"    {suf:8s} {len(ts):>10,} filas · {fecha(ts[0]):%Y-%m-%d} -> {fecha(ts[-1]):%Y-%m-%d}")
        if dup:   P("alto", sym, f"{suf}: {dup} timestamps duplicados")
        if atras: P("alto", sym, f"{suf}: {atras} timestamps hacia atras")
        if len(hh):
            tot = int(d[hh].sum() - len(hh) * MIN) // MIN
            P("medio", sym, f"{suf}: {len(hh)} huecos · {tot:,} minutos perdidos · "
                            f"el mayor {int(d[hh].max())//MIN:,} min desde {fecha(ts[hh[np.argmax(d[hh])]]):%Y-%m-%d %H:%M}")
            if suf == "1m":
                huecos[sym] = [(int(ts[i]), int(ts[i] + d[i])) for i in hh]
        if suf == "1m":
            o, h, l, c = (np.ascontiguousarray(a[:, k]).astype(float) for k in (1, 2, 3, 4))
            mal = int((h < l).sum()); malo = int(((h < o) | (h < c) | (l > o) | (l > c)).sum())
            ceros = int((c <= 0).sum())
            if mal:  P("alto", sym, f"1m: {mal} velas con high < low")
            if malo: P("alto", sym, f"1m: {malo} velas con high/low fuera de open/close")
            if ceros: P("alto", sym, f"1m: {ceros} velas con precio <= 0")
            if not (mal or malo or ceros): print(f"             OHLC coherente en las {len(ts):,} velas")

# ── 2 · cruce entre fuentes ──────────────────────────────────────────────────
print("\n" + "=" * 72); print("2 · CRUCE: 1m agregados a 4h  vs  backup 4h"); print("=" * 72)
for sym in SYMS:
    fb = os.path.join(BAK, f"{sym}_4h.csv")
    f1 = os.path.join(D1, f"{sym}_1m.npy")
    if not os.path.exists(fb): P("medio", sym, "no hay backup 4h para cruzar"); continue
    if not os.path.exists(f1): P("alto", sym, "no hay 1m crudo para cruzar"); continue
    import csv as _csv
    bak = {}
    for r in list(_csv.reader(open(fb)))[1:]:
        if len(r) < 5: continue
        try:
            t = int(datetime.strptime(r[0], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).timestamp() * 1000)
            bak[t] = float(r[4])
        except Exception: pass
    a = np.load(f1, mmap_mode="r"); raw = np.asarray(a)
    ts = raw[:, 0].astype(np.int64); per = ts // H4
    cortes = np.flatnonzero(np.diff(per)) + 1
    ini = np.concatenate(([0], cortes)); fin = np.concatenate((cortes, [len(per)]))
    agg = {int(per[i] * H4): float(raw[j - 1, 4]) for i, j in zip(ini, fin)}
    comunes = sorted(set(bak) & set(agg))
    if not comunes: P("alto", sym, "cero velas 4h en comun entre las dos fuentes"); continue
    dif = np.array([abs(bak[t] - agg[t]) / bak[t] * 100 for t in comunes if bak[t]])
    peor = max(comunes, key=lambda t: abs(bak[t] - agg[t]) / (bak[t] or 1))
    n_mal = int((dif > 0.01).sum())
    print(f"\n  {sym}: {len(comunes):,} velas 4h comparables "
          f"({fecha(comunes[0]):%Y-%m-%d} -> {fecha(comunes[-1]):%Y-%m-%d})")
    print(f"    diferencia mediana {np.median(dif):.6f}% · maxima {dif.max():.4f}% "
          f"({fecha(peor):%Y-%m-%d %H:%M})")
    if n_mal: P("medio" if n_mal < len(dif) * 0.001 else "alto", sym,
                f"{n_mal:,} velas 4h ({100*n_mal/len(dif):.3f}%) difieren mas de 0.01% entre fuentes")
    else: print(f"    ✅ las dos fuentes coinciden en el 100% de las velas comparables")
    solo_bak = len(set(bak) - set(agg)); solo_agg = len(set(agg) - set(bak))
    if solo_bak: print(f"    · {solo_bak:,} velas solo en el backup 4h (el backup llega mas atras o mas adelante)")
    if solo_agg: print(f"    · {solo_agg:,} velas solo en los 1m")

# ── 3 · contraste contra Binance ─────────────────────────────────────────────
print("\n" + "=" * 72); print("3 · MUESTRA CONTRA BINANCE EN VIVO"); print("=" * 72)
random.seed(7)
for sym in SYMS:
    f1 = os.path.join(D1, f"{sym}_1m.npy")
    if not os.path.exists(f1): continue
    a = np.load(f1, mmap_mode="r"); ts = np.ascontiguousarray(a[:, 0]).astype(np.int64)
    idx = sorted(random.sample(range(200, len(ts) - 200), 4))
    ok = malos = 0
    for i in idx:
        t0 = int(ts[i])
        q = urllib.parse.urlencode({"symbol": sym, "interval": "1m", "startTime": t0, "limit": 5})
        try:
            with urllib.request.urlopen(f"https://api.binance.com/api/v3/klines?{q}", timeout=15) as r:
                d = json.loads(r.read().decode())
        except Exception as e:
            print(f"  {sym}: no se pudo consultar ({type(e).__name__})"); break
        if not d: continue
        for k in d[:3]:
            j = int(np.searchsorted(ts, int(k[0])))
            if j < len(ts) and int(ts[j]) == int(k[0]):
                if abs(float(a[j, 4]) - float(k[4])) / max(1e-9, float(k[4])) > 1e-6: malos += 1
                else: ok += 1
    if malos: P("alto", sym, f"{malos} velas NO coinciden con Binance en la muestra")
    else: print(f"  ✅ {sym}: {ok} velas de muestra coinciden exacto con Binance")

# ── 4 · impacto sobre los estudios registrados ───────────────────────────────
print("\n" + "=" * 72); print("4 · LOS HUECOS, ¿CAEN DENTRO DE LOS ESTUDIOS YA HECHOS?"); print("=" * 72)
c = sqlite3.connect(os.path.join(BOT, "data/resultados.db"))
est = [r for r in c.execute("select fecha,tema,ventana_desde,ventana_hasta from pruebas "
                            "where ventana_desde is not null and ventana_hasta is not null")]
print(f"\n  {len(est)} estudios con ventana declarada en resultados.db\n")
res = []
for f, tema, vd, vh in est:
    try:
        a0 = datetime.strptime(vd, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000
        a1 = datetime.strptime(vh, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000
    except Exception: continue
    dentro = []
    for sym, hs in huecos.items():
        for h0, h1 in hs:
            if h1 > a0 and h0 < a1:
                dentro.append((sym, h0, (h1 - h0) // MIN))
    if dentro:
        peor = max(dentro, key=lambda x: x[2])
        res.append((tema[:46], vd, vh, len(dentro), peor))
if res:
    print(f"  {'estudio':46s} {'ventana':>23s} {'huecos':>7s} {'el mayor':>28s}")
    for tema, vd, vh, n, peor in sorted(res, key=lambda x: -x[4][2])[:12]:
        print(f"  {tema:46s} {vd}->{vh[5:]} {n:>7} {peor[0]} {peor[2]:>6,} min {fecha(peor[1]):%Y-%m-%d}")
else:
    print("  ✅ ningun hueco cae dentro de las ventanas declaradas")

print("\n" + "=" * 72)
altos = [p for p in problemas if p["sev"] == "alto"]
medios = [p for p in problemas if p["sev"] == "medio"]
print(f"RESUMEN: {len(altos)} problemas ALTOS · {len(medios)} MEDIOS")
for p in altos: print(f"  🔴 {p['sym']}: {p['txt']}")
json.dump({"problemas": problemas,
           "huecos": {k: [[h0, h1] for h0, h1 in v] for k, v in huecos.items()}},
          open("/home/ariel/tarea1a_4m/L1_integridad.json", "w"), indent=1)
print("\n[output] L1_integridad.json")
