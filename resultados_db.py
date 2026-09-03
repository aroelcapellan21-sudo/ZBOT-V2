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
import math
import sqlite3
import hashlib
from collections import namedtuple
from datetime import datetime

# Override por entorno para poder testear sin tocar la DB real
DB_PATH = os.environ.get(
    "RESULTADOS_DB",
    os.path.expanduser("~/bot-padre-v2/data/resultados.db")
)

VEREDICTOS = ("APLICADO", "PROMETEDOR", "DESCARTADO", "NO_CONCLUYENTE")
# DESCONOCIDA = la fase no consta en los datos. NO significa "las tres":
# el 73,4% de los trades historicos de reports/raw/ no registran fase.
FASES = ("ALCISTA", "BAJISTA", "LATERAL", "TODAS", "DESCONOCIDA")

ResultadoRegistro = namedtuple(
    "ResultadoRegistro",
    "prueba_id creada trades_insertados trades_ignorados")

# Columnas agregadas el 2026-09-02. Solo ALTER TABLE ADD COLUMN: no se borra
# ni se reescribe ninguna fila existente.
_COLUMNAS_NUEVAS = {
    "pruebas": [
        ("origen_archivo", "TEXT"),    # reports/raw/<archivo> que la origino
        ("hash_datos",     "TEXT"),    # sha1 del contenido -> idempotencia
        ("escenario",      "TEXT"),    # ACTUAL | DOBLE_2x | rama del JSON anidado
        ("tp_pct",         "REAL"),
        ("sl_pct",         "REAL"),
        ("monto_usdt",     "REAL"),
        ("capital_usdt",   "REAL"),
    ],
    "metricas": [("fuente", "TEXT DEFAULT 'reportada'")],
    "trades_backtest": [
        ("rsi_entrada",        "REAL"),
        ("velas",              "INTEGER"),
        ("trade_id_origen",    "TEXT"),
        ("ts_salida_derivada", "INTEGER DEFAULT 0"),  # 1 = calculada, no leida
    ],
}


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
        _migrar(conn)
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


def _migrar(conn):
    """Aditiva e idempotente. Solo ALTER TABLE ADD COLUMN y CREATE INDEX.
    No hay DROP, DELETE, UPDATE masivo ni reconstruccion de tablas."""
    for tabla, cols in _COLUMNAS_NUEVAS.items():
        existentes = {r[1] for r in conn.execute(f"PRAGMA table_info({tabla})")}
        for nombre, tipo in cols:
            if nombre not in existentes:
                conn.execute(f"ALTER TABLE {tabla} ADD COLUMN {nombre} {tipo}")
    # Verificado 2026-09-02: los 3.492 trades existentes dan 3.492 claves
    # distintas, asi que el UNIQUE se crea sin conflicto.
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_trades_clave "
                 "ON trades_backtest(prueba_id, symbol, ts_entrada)")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_pruebas_hash "
                 "ON pruebas(hash_datos) WHERE hash_datos IS NOT NULL")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_ts "
                 "ON trades_backtest(ts_entrada)")


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


def agregar_metricas(prueba_id, metricas, unidades=None, fuente="reportada"):
    """metricas: dict {nombre: valor}. Un valor None NO se inserta (dato ausente != 0)."""
    unidades = unidades or {}
    filas = [(prueba_id, k, float(v), unidades.get(k), fuente)
             for k, v in metricas.items() if v is not None]
    with _conn() as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO metricas (prueba_id, nombre, valor, unidad, fuente) "
            "VALUES (?,?,?,?,?)",
            filas)
    return len(filas)


def agregar_trades(prueba_id, trades):
    """trades: lista de dicts con las claves de la tabla trades_backtest.

    UNICO camino de insercion de trades del sistema. INSERT OR IGNORE contra el
    indice ux_trades_clave: reejecutar no duplica. Devuelve cuantos entraron.
    """
    campos = ("symbol", "fase", "ts_entrada", "ts_salida", "precio_entrada",
              "precio_salida", "motivo_cierre", "monto_usdt", "pnl_pct", "pnl_usdt",
              "rsi_entrada", "velas", "trade_id_origen", "ts_salida_derivada")
    filas = [tuple([prueba_id] + [t.get(c) for c in campos]) for t in trades]
    with _conn() as conn:
        cur = conn.executemany(
            f"INSERT OR IGNORE INTO trades_backtest (prueba_id, {','.join(campos)}) "
            f"VALUES ({','.join('?' * (len(campos) + 1))})", filas)
        return cur.rowcount


# ── Hash determinista del contenido completo (v2) ─────────────────────────────
_CAMPOS_TRADE = ("symbol", "fase", "ts_entrada", "ts_salida", "precio_entrada",
                 "precio_salida", "motivo_cierre", "pnl_pct", "pnl_usdt",
                 "rsi_entrada", "velas", "trade_id_origen", "ts_salida_derivada")
_CAMPOS_META = ("tema", "moneda", "fase", "escenario", "tp_pct", "sl_pct",
                "monto_usdt", "capital_usdt")


def _norm(v):
    """Normaliza un valor para que el hash no dependa del formato de origen."""
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (int, float)):
        return round(float(v), 10)
    s = str(v).strip()
    if not s:
        return None
    try:  # timestamp -> ISO canonico (con espacio o con T, con o sin zona)
        return datetime.fromisoformat(s.replace(" ", "T")).replace(
            tzinfo=None).isoformat()
    except ValueError:
        pass
    try:
        return round(float(s), 10)
    except ValueError:
        return s


def _hash_prueba(meta, trades):
    """SHA-1 del contenido normalizado completo: mismos datos -> mismo hash,
    cualquier diferencia real -> hash distinto. Independiente del orden de las
    claves, del orden de los trades y del formato del JSON/CSV de origen."""
    filas = [[_norm(t.get(c)) for c in _CAMPOS_TRADE] for t in trades]
    filas.sort(key=lambda f: json.dumps(f, default=str))
    payload = {"v": 2,
               "meta": {c: _norm(meta.get(c)) for c in _CAMPOS_META},
               "trades": filas}
    crudo = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False, default=str)
    return hashlib.sha1(crudo.encode("utf-8")).hexdigest()


# ── Metricas canonicas — SIN capital ficticio ─────────────────────────────────
_UNIDADES = {"wr": "%", "pf": "ratio", "n": "conteo", "sharpe": "ratio",
             "dd_max_pct": "%", "dd_max_pp": "pp", "dd_max_usdt": "USDT",
             "pnl_usdt": "USDT", "suma_pct_trades": "pp", "expectancy_usdt": "USDT",
             "expectancy_pct": "%", "peor5_usdt": "USDT", "peor5_pct": "%",
             "racha_perdidas": "conteo", "racha_ganancias": "conteo",
             "tp_alcanzados": "conteo"}


def calcular_metricas(trades, capital_usdt=None):
    """Metricas desde los trades. Reglas:
      - dato ausente = metrica ausente. Nunca un 0 ni un capital supuesto.
      - si todos los trades traen pnl_usdt -> base USDT; si no, base %.
      - dd_max_pct (drawdown sobre capital) SOLO si hay capital_usdt real.
        Sin capital se emite dd_max_pp, que es otra cosa y se llama distinto.
      - suma_pct_trades es la SUMA ARITMETICA de los cambios porcentuales por
        trade. NO es retorno sobre capital ni retorno compuesto. Con MONTO_FIJO
        (el sizing real del bot) se convierte a USD multiplicando por el monto
        por trade; componerla no representa nada, porque el bot no reinvierte.
        Se llama distinto de pnl_pct_total, su nombre anterior, justamente
        porque ese nombre se leia como retorno y en series largas infla el
        resultado (993 trades: 1.126 pp frente a 46,4% de retorno real).
    Formulas heredadas de los scripts *_bootstrap_sistema_c_* (PF, WR,
    expectancy, racha, peor5) y Sharpe de optimizador_completo.py:76
    (media/std * sqrt(252)). No se introduce ninguna formula nueva.
    """
    n = len(trades)
    if n == 0:
        return {}
    usa_usd = all(t.get("pnl_usdt") is not None for t in trades)
    clave = "pnl_usdt" if usa_usd else "pnl_pct"
    if not all(t.get(clave) is not None for t in trades):
        return {"n": n}  # sin serie completa no se calcula nada mas

    v = [t[clave] for t in sorted(
        trades, key=lambda t: (str(t.get("ts_salida") or t["ts_entrada"]),
                               str(t["ts_entrada"])))]
    g = [x for x in v if x > 0]
    p = [x for x in v if x <= 0]
    total_g, total_p = sum(g), abs(sum(p))

    curva = pico = caida = 0.0
    for x in v:
        curva += x
        pico = max(pico, curva)
        caida = max(caida, pico - curva)

    def racha(cond):
        mx = act = 0
        for x in v:
            act = act + 1 if cond(x) else 0
            mx = max(mx, act)
        return mx

    media = sum(v) / n
    std = math.sqrt(sum((x - media) ** 2 for x in v) / n)
    suf = "usdt" if usa_usd else "pct"

    m = {
        "n": n,
        "wr": 100 * len(g) / n,
        "pf": (total_g / total_p) if total_p else None,  # sin perdidas -> ausente
        f"expectancy_{suf}": media,
        f"peor5_{suf}": min((sum(v[i:i + 5]) for i in range(max(1, n - 4))),
                            default=None),
        "racha_perdidas": racha(lambda x: x <= 0),
        "racha_ganancias": racha(lambda x: x > 0),
        "sharpe": (media / std) * math.sqrt(252) if std else None,
        "tp_alcanzados": sum(1 for t in trades if t.get("motivo_cierre") == "TP"),
    }
    if usa_usd:
        m["pnl_usdt"] = sum(v)
        m["dd_max_usdt"] = caida
        if capital_usdt:  # solo con capital REAL
            m["dd_max_pct"] = 100 * caida / capital_usdt
    else:
        m["suma_pct_trades"] = sum(v)   # pp sumados, NO retorno — ver docstring
        m["dd_max_pp"] = caida  # puntos porcentuales, NO % de cuenta
    return m


def registrar_backtest(*, tema, moneda, fase, trades, veredicto="NO_CONCLUYENTE",
                       resumen="", fecha=None, tipo="backtest", escenario=None,
                       tp_pct=None, sl_pct=None, monto_usdt=None, capital_usdt=None,
                       ventana_desde=None, ventana_hasta=None, parametros=None,
                       reporte=None, origen_archivo=None, commit_git=None,
                       metricas_extra=None):
    """UNICO punto que registra una prueba completa (prueba + metricas + trades).
    Idempotente por hash de contenido. Devuelve ResultadoRegistro."""
    init_db()
    meta = dict(tema=tema, moneda=moneda, fase=fase, escenario=escenario,
                tp_pct=tp_pct, sl_pct=sl_pct, monto_usdt=monto_usdt,
                capital_usdt=capital_usdt)
    h = _hash_prueba(meta, trades)
    with _conn() as conn:
        ya = conn.execute("SELECT id FROM pruebas WHERE hash_datos=?", (h,)).fetchone()
    if ya:
        return ResultadoRegistro(ya[0], False, 0, len(trades))

    if trades:
        ventana_desde = ventana_desde or str(min(t["ts_entrada"] for t in trades))[:10]
        ventana_hasta = ventana_hasta or str(max(
            (t.get("ts_salida") or t["ts_entrada"]) for t in trades))[:10]

    pid = registrar_prueba(
        fecha=fecha or datetime.now().strftime("%Y-%m-%d"), tema=tema, tipo=tipo,
        veredicto=veredicto, resumen=resumen, moneda=moneda, fase=fase,
        ventana_desde=ventana_desde, ventana_hasta=ventana_hasta,
        parametros=parametros, reporte=reporte, commit_git=commit_git)
    with _conn() as conn:
        conn.execute("UPDATE pruebas SET origen_archivo=?, hash_datos=?, escenario=?,"
                     " tp_pct=?, sl_pct=?, monto_usdt=?, capital_usdt=? WHERE id=?",
                     (origen_archivo, h, escenario, tp_pct, sl_pct,
                      monto_usdt, capital_usdt, pid))
    agregar_metricas(pid, calcular_metricas(trades, capital_usdt),
                     unidades=_UNIDADES, fuente="recalculada")
    if metricas_extra:
        agregar_metricas(pid, metricas_extra, fuente="reportada")
    insertados = agregar_trades(pid, trades)  # unico insert de trades
    return ResultadoRegistro(pid, True, insertados, len(trades) - insertados)


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
