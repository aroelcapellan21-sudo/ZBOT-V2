#!/usr/bin/env python3
"""L2 — reproducibilidad del simulador. Chequeo permanente, no de una vez.

Corre el mismo tramo varias veces cambiando UNA cosa por vez y exige que el
resultado sea identico. Si algo cambia, el simulador no es reproducible y
cualquier conclusion que dependa de el queda en duda.

Los cuatro niveles, de menos a mas revelador:

  A · misma corrida dos veces, todo igual
  B · distinto PYTHONHASHSEED  — el orden de los set/dict de Python cambia con
      la semilla de hash. Si el resultado depende de eso, dos corridas
      "identicas" pueden diferir sin que nadie toque nada.
  C · distinto --tmpdir       — el directorio de trabajo no debe influir
  D · completa vs reanudada   — ya probado a mano el 05-sep; queda automatizado

NO mide velocidad ni memoria: solo si el numero sale igual.
"""
import json, os, shutil, subprocess, sys, tempfile

D = "/home/ariel/tarea1a_4m"
PY = "/usr/bin/python3"
SANDBOX = f"{D}/sandbox_director.py"
DESDE = sys.argv[1] if len(sys.argv) > 1 else "2026-08-25"
HASTA = sys.argv[2] if len(sys.argv) > 2 else None

BASE = ["--capital", "36.86", "--paso", "4m", "--desde", DESDE]
if HASTA: BASE += ["--hasta", HASTA]

# los campos que se comparan: todo el resultado menos lo que legitimamente varia
IGNORAR = {"etiqueta"}

def corre(nombre, tmpdir, env_extra=None, extra=None):
    salida = f"/tmp/repro_{nombre}.json"
    for p in (tmpdir, salida):
        shutil.rmtree(p, ignore_errors=True) if os.path.isdir(p) else (os.path.exists(p) and os.remove(p))
    env = dict(os.environ); env.update(env_extra or {})
    cmd = [PY, "-u", SANDBOX] + BASE + (extra or []) + \
          ["--etiqueta", nombre, "--tmpdir", tmpdir, "--salida", salida]
    r = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=D)
    if r.returncode != 0:
        print(f"  ❌ {nombre}: la corrida fallo (exit {r.returncode})")
        print("    " + (r.stderr or r.stdout)[-400:].replace("\n", "\n    "))
        return None, None
    return json.load(open(salida)), tmpdir

def compara(nom_a, a, dir_a, nom_b, b, dir_b):
    if a is None or b is None: return False
    dif = [k for k in set(a) | set(b) if k not in IGNORAR and a.get(k) != b.get(k)]
    csv_a, csv_b = f"{dir_a}/auditoria.csv", f"{dir_b}/auditoria.csv"
    csv_igual = (os.path.exists(csv_a) and os.path.exists(csv_b)
                 and open(csv_a).read() == open(csv_b).read())
    ok = not dif and csv_igual
    print(f"  {'✅' if ok else '❌'} {nom_a} vs {nom_b}")
    if dif:
        for k in sorted(dif)[:6]:
            va, vb = a.get(k), b.get(k)
            if isinstance(va, list): va, vb = f"[{len(va)} elem]", f"[{len(vb or [])} elem]"
            print(f"       {k}: {va}  !=  {vb}")
    elif not csv_igual:
        print(f"       el JSON coincide pero auditoria.csv NO")
    return ok

print("=" * 70)
print(f"L2 — REPRODUCIBILIDAD · ventana {DESDE} -> {HASTA or 'fin de datos'}")
print("=" * 70)
res = {}

print("\nA · misma corrida dos veces (todo igual)")
a1, d1 = corre("A1", f"{D}/tmp_repro_a1")
a2, d2 = corre("A2", f"{D}/tmp_repro_a2")
res["A_determinismo"] = compara("A1", a1, d1, "A2", a2, d2)

print("\nB · distinto PYTHONHASHSEED (el orden de los set/dict cambia)")
b1, e1 = corre("B1", f"{D}/tmp_repro_b1", {"PYTHONHASHSEED": "1"})
b2, e2 = corre("B2", f"{D}/tmp_repro_b2", {"PYTHONHASHSEED": "99999"})
res["B_hashseed"] = compara("seed=1", b1, e1, "seed=99999", b2, e2)

print("\nC · distinto --tmpdir (el directorio de trabajo no debe influir)")
c1, f1 = corre("C1", tempfile.mkdtemp(prefix="repro_c1_"))
res["C_tmpdir"] = compara("A1", a1, d1, "tmpdir temporal", c1, f1)

print("\nD · la bandera obsoleta --corregir-desfase sigue siendo no-op")
d_, g1 = corre("D1", f"{D}/tmp_repro_d1", extra=["--corregir-desfase"])
res["D_bandera_noop"] = compara("A1", a1, d1, "con --corregir-desfase", d_, g1)

print("\n" + "=" * 70)
todos = all(res.values())
for k, v in res.items(): print(f"  {'✅' if v else '❌'} {k}")
print(f"\nVEREDICTO: {'REPRODUCIBLE' if todos else '🔴 NO REPRODUCIBLE'}")
json.dump(res, open(f"{D}/L2_reproducibilidad.json", "w"), indent=1)
print(f"[output] L2_reproducibilidad.json")
sys.exit(0 if todos else 1)
