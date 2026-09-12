#!/usr/bin/env python3
"""L12 · Deriva entre los sandboxes y produccion (item 0b).

Compara, sin ejecutar nada, cada modulo falso que un sandbox instala en
`sys.modules` contra el modulo real del repo: firma por firma y constante por
constante. Todo el analisis es estatico (`ast`): ningun backtest corre, ninguna
vela se baja y produccion no se importa ni una vez.

Por que existe: el 31-ago el commit f61c066 agrego `sl_pct` a
`ejecutor.ejecutar_operacion()` y los 9 sandboxes de sistema_c/ siguieron
mockeando la firma vieja. Se descubrio el 10-sep, al ir a rehacer 36 estudios y
encontrar que NINGUNO corria. El TypeError al menos fue ruidoso; si el argumento
nuevo hubiera tenido un default compatible, los 36 habrian corrido en silencio
midiendo otra cosa. Por eso aca se reportan los dos casos, no solo el que rompe.

Categorias:
  ROMPE       el mock no acepta una llamada valida de produccion (TypeError), o
              al reves; o el orden de los parametros compartidos no coincide; o
              el mock define algo que en produccion ya no existe.
  SILENCIOSO  el mock acepta la llamada pero ignora un parametro que produccion
              si tiene (absorbido por *args/**kwargs). No falla: mide otra cosa.
  VALOR       constante mockeada con un valor distinto al de produccion.
  PAUSADO     (chequeo aparte) francotirador con `return` incondicional en
              `evaluar()`: cualquier estudio que lo mida da 0 trades.

Uso:
    python3 laboratorio/verificar_mocks.py              # chequeo completo
    python3 laboratorio/verificar_mocks.py --todo       # lista tambien las conocidas
    python3 laboratorio/verificar_mocks.py --actualizar # reescribe el baseline

Exit code 1 si aparece una divergencia que no este en el baseline.
"""

import argparse
import ast
import json
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASELINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mocks_baseline.json")

# No se escanean: no tienen codigo del proyecto o son copias.
EXCLUIDOS = {".git", "__pycache__", "node_modules", "reports", "venv", ".venv",
             "data", "data_1m", "memoria", "signals", "backups"}

_SIN_LITERAL = object()


# ── lectura del lado real ────────────────────────────────────────────────────

def _archivo_real(modulo):
    """Ruta del .py de produccion para un nombre de modulo importable."""
    partes = modulo.split(".")
    for candidato in (os.path.join(RAIZ, *partes) + ".py",
                      os.path.join(RAIZ, *partes, "__init__.py")):
        if os.path.exists(candidato):
            return candidato
    return None


def _firma(nodo):
    """(params, tiene_star, tiene_kwargs) de un def o un lambda."""
    a = nodo.args
    posicionales = a.posonlyargs + a.args
    corte = len(posicionales) - len(a.defaults)
    params = [(p.arg, i >= corte) for i, p in enumerate(posicionales)]
    params += [(p.arg, d is not None) for p, d in zip(a.kwonlyargs, a.kw_defaults)]
    return params, a.vararg is not None, a.kwarg is not None


def _fmt(firma):
    params, star, kwargs = firma
    trozos = [p + ("=..." if d else "") for p, d in params]
    if star:
        trozos.append("*args")
    if kwargs:
        trozos.append("**kwargs")
    return "(" + ", ".join(trozos) + ")"


def _leer_modulo_real(ruta):
    """{nombre: ('func'|'clase'|'const', dato)} del nivel de modulo."""
    with open(ruta, encoding="utf-8") as fh:
        arbol = ast.parse(fh.read(), ruta)
    simbolos = {}
    for nodo in arbol.body:
        if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
            simbolos[nodo.name] = ("func", _firma(nodo))
        elif isinstance(nodo, ast.ClassDef):
            simbolos[nodo.name] = ("clase", None)
        elif isinstance(nodo, ast.Assign):
            for destino in nodo.targets:
                if isinstance(destino, ast.Name):
                    try:
                        simbolos[destino.id] = ("const", ast.literal_eval(nodo.value))
                    except (ValueError, TypeError, SyntaxError):
                        simbolos[destino.id] = ("const", _SIN_LITERAL)
    return simbolos


# ── lectura del lado sandbox ─────────────────────────────────────────────────

def _leer_sandbox(arbol):
    """[(modulo_real, atributo, tipo, dato, linea)] de los mocks de un archivo."""
    defs = {n.name: n for n in ast.walk(arbol)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    local_a_modulo = {}   # nombre local del ModuleType -> modulo que suplanta
    atributos = {}        # (nombre local, atributo) -> (tipo, dato, linea)

    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.Assign):
            continue
        valor = nodo.value
        for destino in nodo.targets:
            # sys.modules["ejecutor"] = fake_ejecutor
            if (isinstance(destino, ast.Subscript)
                    and isinstance(destino.value, ast.Attribute)
                    and destino.value.attr == "modules"
                    and isinstance(valor, ast.Name)):
                try:
                    local_a_modulo[valor.id] = ast.literal_eval(destino.slice)
                except (ValueError, TypeError, SyntaxError):
                    pass
            # fake_ejecutor.ejecutar_operacion = _fake_ejecutar_operacion
            elif isinstance(destino, ast.Attribute) and isinstance(destino.value, ast.Name):
                clave = (destino.value.id, destino.attr)
                if isinstance(valor, ast.Lambda):
                    atributos[clave] = ("func", _firma(valor), nodo.lineno)
                elif isinstance(valor, ast.Name) and valor.id in defs:
                    atributos[clave] = ("func", _firma(defs[valor.id]), nodo.lineno)
                else:
                    try:
                        atributos[clave] = ("const", ast.literal_eval(valor), nodo.lineno)
                    except (ValueError, TypeError, SyntaxError):
                        atributos[clave] = ("const", _SIN_LITERAL, nodo.lineno)

    mocks = []
    for (local, attr), (tipo, dato, linea) in sorted(atributos.items(), key=lambda x: x[1][2]):
        modulo = local_a_modulo.get(local)
        if modulo and not attr.startswith("__"):
            mocks.append((modulo, attr, tipo, dato, linea))
    return mocks


# ── comparacion ──────────────────────────────────────────────────────────────

def _comparar_firmas(real, mock):
    """[(categoria, detalle)] entre la firma real y la del mock."""
    r_params, _r_star, _r_kw = real
    m_params, m_star, m_kw = mock
    r_nombres = [p for p, _ in r_params]
    m_nombres = [p for p, _ in m_params]
    m_default = dict(m_params)
    hallazgos = []

    faltan = [p for p in r_nombres if p not in m_nombres]
    if faltan:
        silencioso = m_kw or m_star
        hallazgos.append(("SILENCIOSO" if silencioso else "ROMPE",
                          ("el mock absorbe sin modelar " if silencioso
                           else "el mock no acepta ") + ", ".join(faltan)))

    sobran = [p for p, d in m_params if p not in r_nombres and not d]
    if sobran:
        hallazgos.append(("ROMPE", f"el mock exige {', '.join(sobran)}, "
                                   "que produccion no manda"))

    obligatorios = [p for p, d in r_params if d and p in m_nombres and not m_default[p]]
    if obligatorios:
        hallazgos.append(("ROMPE", f"{', '.join(obligatorios)} tiene default en produccion "
                                   "y es obligatorio en el mock"))

    comunes_r = [p for p in r_nombres if p in m_nombres]
    comunes_m = [p for p in m_nombres if p in r_nombres]
    if comunes_r != comunes_m:
        hallazgos.append(("ROMPE", f"orden distinto: produccion {comunes_r} vs mock {comunes_m}"))

    return hallazgos


def _archivos_py():
    for base, dirs, archivos in os.walk(RAIZ):
        dirs[:] = [d for d in sorted(dirs) if d not in EXCLUIDOS and not d.startswith(".")]
        for nombre in sorted(archivos):
            if nombre.endswith(".py"):
                yield os.path.join(base, nombre)


def revisar_mocks():
    """[(archivo, modulo, atributo, linea, categoria, detalle, firmas)]"""
    reales = {}
    salida = []
    propio = os.path.abspath(__file__)

    for ruta in _archivos_py():
        if os.path.abspath(ruta) == propio:
            continue
        with open(ruta, encoding="utf-8") as fh:
            fuente = fh.read()
        if "sys.modules[" not in fuente:
            continue
        rel = os.path.relpath(ruta, RAIZ)
        try:
            arbol = ast.parse(fuente, ruta)
        except SyntaxError as e:
            salida.append((rel, "-", "-", e.lineno or 0, "ROMPE",
                           f"no se pudo parsear el sandbox: {e.msg}", ""))
            continue

        for modulo, attr, tipo, dato, linea in _leer_sandbox(arbol):
            if modulo not in reales:
                archivo = _archivo_real(modulo)
                reales[modulo] = _leer_modulo_real(archivo) if archivo else None
            simbolos = reales[modulo]
            if simbolos is None:
                salida.append((rel, modulo, attr, linea, "ROMPE",
                               f"no existe {modulo}.py en el repo", ""))
                continue
            if attr not in simbolos:
                # puede ser un submodulo real de un paquete: memoria.memoria
                if _archivo_real(f"{modulo}.{attr}"):
                    continue
                salida.append((rel, modulo, attr, linea, "ROMPE",
                               f"{modulo}.{attr} no existe en produccion", ""))
                continue

            tipo_real, dato_real = simbolos[attr]
            if tipo == "func" and tipo_real == "func":
                for cat, det in _comparar_firmas(dato_real, dato):
                    salida.append((rel, modulo, attr, linea, cat, det,
                                   f"real{_fmt(dato_real)} vs mock{_fmt(dato)}"))
            elif tipo == "const" and tipo_real == "const":
                if _SIN_LITERAL not in (dato, dato_real) and dato != dato_real:
                    salida.append((rel, modulo, attr, linea, "VALOR",
                                   f"mock {dato!r} vs produccion {dato_real!r}", ""))
            elif tipo != tipo_real:
                salida.append((rel, modulo, attr, linea, "ROMPE",
                               f"el mock lo define como {tipo} y produccion como {tipo_real}", ""))
    return salida


# ── segundo mecanismo: francotirador pausado por codigo ──────────────────────

def revisar_pausados():
    """[(archivo, linea, detalle)] de francotiradores con `evaluar()` cortado.

    El otro canal de deriva del item 0b: la prueba 276 corrio contra
    `lateral_sol` un dia despues de que lo pausaran (commit 5713c0a), dio
    0 trades, y se registro igual en el indice como NO_CONCLUYENTE.
    """
    salida = []
    for ruta in sorted(_archivos_py()):
        nombre = os.path.basename(ruta)
        if not nombre.startswith("francotirador_"):
            continue
        with open(ruta, encoding="utf-8") as fh:
            arbol = ast.parse(fh.read(), ruta)
        for nodo in arbol.body:
            if not (isinstance(nodo, ast.FunctionDef) and nodo.name == "evaluar"):
                continue
            for i, sent in enumerate(nodo.body[:-1]):
                if isinstance(sent, ast.Return):
                    muertas = nodo.body[-1].end_lineno - nodo.body[i + 1].lineno + 1
                    salida.append((os.path.relpath(ruta, RAIZ), sent.lineno,
                                   f"`return` incondicional en evaluar() — "
                                   f"{muertas} lineas nunca se ejecutan"))
                    break
    return salida


# ── baseline y reporte ───────────────────────────────────────────────────────

def _clave(h):
    archivo, modulo, attr, _linea, cat, det, _firmas = h
    return "|".join([archivo, modulo, attr, cat, det])


def _imprimir(hallazgos, conocidos, mostrar_todo):
    archivo_actual = None
    for h in sorted(hallazgos, key=lambda x: (x[0], x[3])):
        archivo, modulo, attr, linea, cat, det, firmas = h
        nueva = _clave(h) not in conocidos
        if not nueva and not mostrar_todo:
            continue
        if archivo != archivo_actual:
            print(f"\n{archivo}")
            archivo_actual = archivo
        print(f"  {'NUEVA ' if nueva else '      '}{cat:<10} L{linea:<5} "
              f"{modulo}.{attr} — {det}")
        if firmas:
            print(f"{'':>25}{firmas}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--todo", action="store_true",
                    help="lista tambien las divergencias ya registradas en el baseline")
    ap.add_argument("--actualizar", action="store_true",
                    help="reescribe el baseline con lo que hay hoy (requiere revision humana)")
    ap.add_argument("--categorias", default="",
                    help="con --actualizar: registra solo estas categorias, separadas por coma "
                         "(el resto queda en rojo a proposito)")
    args = ap.parse_args()

    hallazgos = revisar_mocks()
    pausados = revisar_pausados()

    conocidos = set()
    if os.path.exists(BASELINE):
        with open(BASELINE, encoding="utf-8") as fh:
            conocidos = set(json.load(fh)["conocidas"])

    if args.actualizar:
        filtro = {c.strip().upper() for c in args.categorias.split(",") if c.strip()}
        registrar = [h for h in hallazgos if not filtro or h[4] in filtro]
        with open(BASELINE, "w", encoding="utf-8") as fh:
            json.dump({
                "_comentario": "Divergencias sandbox<->produccion ya conocidas. El chequeo "
                               "falla solo con las que NO estan aca. Vaciarlo es la meta, "
                               "no dejarlo crecer.",
                "conocidas": sorted(_clave(h) for h in registrar),
            }, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        print(f"[baseline] {len(registrar)} de {len(hallazgos)} divergencias registradas en "
              f"{os.path.relpath(BASELINE, RAIZ)}")
        return 0

    nuevas = [h for h in hallazgos if _clave(h) not in conocidos]
    por_cat = {}
    for h in hallazgos:
        por_cat[h[4]] = por_cat.get(h[4], 0) + 1

    print("=" * 78)
    print("L12 · Deriva entre los sandboxes y produccion")
    print("=" * 78)

    if hallazgos:
        print(f"\n{len(hallazgos)} divergencias · " +
              " · ".join(f"{c} {n}" for c, n in sorted(por_cat.items())) +
              f" · {len(nuevas)} nuevas")
        _imprimir(hallazgos, conocidos, args.todo)
        if not args.todo and not nuevas:
            print("\n(todas estan en el baseline; --todo las lista una por una)")
    else:
        print("\nSin divergencias: todos los mocks coinciden con produccion.")

    if pausados:
        print(f"\n{'-' * 78}\nPAUSADOS · {len(pausados)} francotiradores no operan aunque "
              "se los mida:")
        for archivo, linea, det in pausados:
            print(f"  {archivo}:{linea} — {det}")
        print("  Un estudio sobre estos da 0 trades sin avisar (caso prueba 276).")

    if nuevas:
        print(f"\n[FALLA] {len(nuevas)} divergencias nuevas. Un mock que no coincide con "
              "produccion\nno mide produccion. Corregir el mock, o registrar la excepcion con "
              "--actualizar\ndejando dicho en la cola por que se acepta.")
        return 1

    print(f"\n[OK] sin deriva nueva contra el baseline ({len(hallazgos)} conocidas).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
