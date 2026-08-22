"""
Variante de sistema_c/resim_evaluar_literal_sol_lateral.py con la ventana de
analisis extendida a la historia completa disponible (2020-09-01 -> hoy),
en vez de solo 2026. Misma logica exacta, mismo sandbox, sin ningun cambio
de metodologia -- ver ese archivo para la documentacion completa del
sandbox (que modulos se reemplazan, cuales quedan reales, limitaciones).

Motivo: reports/2026-08-21_resumen_sesiones_ariel_claude.md, seccion 5,
punto 2 -- "correr evaluar() literal de SOL LATERAL (12 gates reales, sin
reimplementar nada) sobre 2020-2026 completo, no solo 2026" -- paso marcado
como prioritario tras confirmar que 2 de los 12 gates (filtro_calidad,
detector_multitimeframe) revierten su hallazgo de ventana corta al
extenderse a 5.9 anios.

No se sobreescribe el script original (principio de conservacion del
proyecto: ninguna prueba experimental destruye informacion anterior).

Consulta de solo lectura. No modifica NADA en ~/bot-padre-v2.

Uso:
    python3 sistema_c/resim_evaluar_literal_sol_lateral_2020_2026.py
"""
import sys, os, json, csv, tempfile, types, statistics
import urllib.parse, urllib.request
from datetime import datetime, timezone

BOT_DIR = os.path.expanduser("~/bot-padre-v2")
sys.path.insert(0, BOT_DIR)

SYMBOL = "SOLUSDT"
FECHA_INICIO_ANALISIS = "2020-09-01 00:00:00"   # unico cambio real vs el script original
FECHA_FIN_ANALISIS    = "2026-08-21 23:59:59"
COMPRESION_MAX_PCT    = 1.0
BACKUP_CSV = os.path.expanduser("~/bot-padre-v3-backup/data/historico_4h/SOLUSDT_4h.csv")
FECHA_DESDE_FALLBACK = datetime(2020, 9, 1, tzinfo=timezone.utc)

RAW_DIR = os.path.expanduser("~/bot-padre-v2/reports/raw")


def _fetch_klines_real(symbol, start_ms, end_ms, interval="4h"):
    out, cur = [], start_ms
    while cur < end_ms:
        params = urllib.parse.urlencode({"symbol": symbol, "interval": interval,
                                          "startTime": cur, "endTime": end_ms, "limit": 1000})
        url = f"https://api.binance.com/api/v3/klines?{params}"
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        if not data:
            break
        out.extend(data)
        cur = data[-1][0] + 1
        if len(data) < 1000:
            break
    return out


velas = {}
if os.path.exists(BACKUP_CSV):
    with open(BACKUP_CSV) as f:
        for row in csv.DictReader(f):
            velas[row["timestamp"]] = (row["open"], row["high"], row["low"], row["close"], row["volume"])
    ultimo_ts = max(velas.keys())
    start_relleno = datetime.strptime(ultimo_ts, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    print(f"[datos] backup local hasta {ultimo_ts} -- completando desde ahi via Binance API")
else:
    start_relleno = FECHA_DESDE_FALLBACK
    print(f"[datos] sin backup local -- descargando todo desde {start_relleno} via Binance API")

end_relleno = datetime.strptime(FECHA_FIN_ANALISIS, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
kl = _fetch_klines_real(SYMBOL, int(start_relleno.timestamp() * 1000), int(end_relleno.timestamp() * 1000))
for k in kl:
    ts = datetime.fromtimestamp(k[0] / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    velas[ts] = (str(k[1]), str(k[2]), str(k[3]), str(k[4]), str(k[5]))
print(f"[datos] {len(kl)} velas frescas de Binance API")

ts_sorted = sorted(velas.keys())
serie = [(ts, *velas[ts]) for ts in ts_sorted]
closes_f = [float(v[4]) for v in serie]

huecos = 0
for i in range(1, len(serie)):
    t0 = datetime.strptime(serie[i - 1][0], "%Y-%m-%d %H:%M:%S")
    t1 = datetime.strptime(serie[i][0], "%Y-%m-%d %H:%M:%S")
    if (t1 - t0).total_seconds() != 4 * 3600:
        huecos += 1
print(f"[datos] velas totales: {len(serie)} | huecos de continuidad (!=4h): {huecos}")

idx_ini = next(i for i, v in enumerate(serie) if v[0] >= FECHA_INICIO_ANALISIS)
idx_fin = len(serie) - 1
if serie[-1][0] > FECHA_FIN_ANALISIS:
    idx_fin = next(i for i, v in enumerate(serie) if v[0] > FECHA_FIN_ANALISIS) - 1
print(f"[datos] ventana de analisis: {serie[idx_ini][0]} -> {serie[idx_fin][0]} ({idx_fin - idx_ini + 1} velas)")

RELOJ = {"i": idx_ini, "ahora": None}


def _calcular_ema(cierres, periodo):
    if len(cierres) < periodo:
        return None
    k = 2 / (periodo + 1)
    ema = sum(cierres[:periodo]) / periodo
    for precio in cierres[periodo:]:
        ema = precio * k + ema * (1 - k)
    return ema


_fake_db_store = {
    "estado_termometro": {
        "timestamp": "2026-03-04 22:51:28",
        "estado": "TENDENCIA_DEBIL",
        "parametros": {"tp_mult": 1.0, "sl_mult": 1.0, "operar": True, "descripcion": "Mercado con tendencia debil"},
    }
}
fake_db = types.ModuleType("db")
fake_db.json_get = lambda tabla, default=None: _fake_db_store.get(tabla, default)
fake_db.json_set = lambda tabla, data: _fake_db_store.__setitem__(tabla, data)
sys.modules["db"] = fake_db

fake_engine = types.ModuleType("engine")
fake_engine.enviar_aviso = lambda *a, **k: None
sys.modules["engine"] = fake_engine

COMISION_SPOT = 0.001
fake_ejecutor = types.ModuleType("ejecutor")
fake_ejecutor.MONTO_MINIMO_BINANCE = 5.0
CIERRES_LOG = []
APERTURAS_LOG = []


def _fake_ejecutar_operacion(moneda, tipo, precio, monto=None):
    if not monto or monto <= 0:
        return f"❌ RECHAZADO: Monto invalido (${monto})", None
    if monto < 5.0:
        return f"❌ RECHAZADO: Monto ${monto:.2f} bajo minimo Binance ($5.0)", None
    precio_fill = closes_f[RELOJ["i"]]
    if tipo == "COMPRA":
        qty_neta = (monto / precio_fill) * (1 - COMISION_SPOT)
        fill = {"qty": qty_neta, "usdt": monto, "precio": precio_fill}
        APERTURAS_LOG.append({"idx": RELOJ["i"], "ts": serie[RELOJ["i"]][0], "precio": precio_fill})
        return f"✅ [SIM] EJECUTADO: Compra {moneda} a ${precio_fill}", fill
    return f"❌ Tipo desconocido: {tipo}", None


def _fake_cerrar_posicion(moneda, tipo_trade, precio_entrada, monto_op, qty=None):
    precio_fill = closes_f[RELOJ["i"]]
    if qty is None:
        qty = monto_op / precio_entrada
    usdt_neto = qty * precio_fill * (1 - COMISION_SPOT)
    fill = {"qty": qty, "usdt": usdt_neto, "precio": precio_fill}
    CIERRES_LOG.append({"idx": RELOJ["i"], "ts": serie[RELOJ["i"]][0],
                         "precio_entrada": precio_entrada, "precio_salida": precio_fill,
                         "cambio_pct": round((precio_fill - precio_entrada) / precio_entrada * 100, 3)})
    return f"✅ [SIM] CIERRE {moneda}: vendido {qty} a ${precio_fill}", fill


fake_ejecutor.ejecutar_operacion = _fake_ejecutar_operacion
fake_ejecutor.cerrar_posicion = _fake_cerrar_posicion
sys.modules["ejecutor"] = fake_ejecutor

fake_guardian = types.ModuleType("guardian_riesgo")
fake_guardian.esta_bloqueado = lambda: False
sys.modules["guardian_riesgo"] = fake_guardian

fake_spread = types.ModuleType("medidor_spread")
fake_spread.spread_aceptable = lambda symbol: True
sys.modules["medidor_spread"] = fake_spread

fake_gb = types.ModuleType("gestor_billetera")
fake_gb.registrar_tp = lambda *a, **k: None
fake_gb.registrar_sl = lambda *a, **k: None
sys.modules["gestor_billetera"] = fake_gb

fake_memoria_propia = types.ModuleType("memoria_propia")
fake_memoria_propia.puede_operar_memoria = lambda symbol, rsi: (True, "aproximado", 1.0)
fake_memoria_propia.actualizar_memoria = lambda *a, **k: None
fake_memoria_propia.analizar_historial = lambda *a, **k: {}
sys.modules["memoria_propia"] = fake_memoria_propia

fake_memoria_pkg = types.ModuleType("memoria")
fake_memoria_pkg.__path__ = []
fake_memoria_submod = types.ModuleType("memoria.memoria")
fake_memoria_submod.registrar_evento = lambda *a, **k: None
fake_memoria_pkg.memoria = fake_memoria_submod
sys.modules["memoria"] = fake_memoria_pkg
sys.modules["memoria.memoria"] = fake_memoria_submod

FILTRO_COMPRESION_ACTIVO = {"on": False}
fake_correlacion = types.ModuleType("gestor_correlacion")


def _fake_puede_operar(accion_nueva, symbol_nuevo):
    if not FILTRO_COMPRESION_ACTIVO["on"]:
        return True
    idx = RELOJ["i"]
    ventana = closes_f[max(0, idx - 209): idx + 1]
    ema_c = _calcular_ema(ventana, 20)
    ema_l = _calcular_ema(ventana, 100)
    if ema_c is None or ema_l is None:
        return True
    compresion = abs(ema_c - ema_l) / ema_l * 100
    return compresion < COMPRESION_MAX_PCT


fake_correlacion.puede_operar = _fake_puede_operar
sys.modules["gestor_correlacion"] = fake_correlacion


class FakeResponse:
    def __init__(self, body):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def fake_urlopen(url, timeout=10, data=None, **kw):
    if "api/v3/klines" not in url:
        raise RuntimeError(f"URL no esperada en el sandbox: {url}")
    qs = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    limit = int(qs.get("limit", ["210"])[0])
    idx = RELOJ["i"]
    start = max(0, idx - limit + 1)
    window = serie[start: idx + 1]
    if len(window) < limit:
        window = ([window[0]] * (limit - len(window)) + window) if window else [serie[0]] * limit
    klines = [[0, o, h, l, c, v, 0, "0", 0, "0", "0", "0"] for (_, o, h, l, c, v) in window]
    return FakeResponse(json.dumps(klines).encode())


urllib.request.urlopen = fake_urlopen

import filtro_horario
import filtro_eventos
import termometro
import limitador_diario
import detector_multitimeframe
import filtro_calidad
import utils
import francotirador_lateral_sol as sol


class FakeDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        base = RELOJ["ahora"]
        return base.astimezone(tz) if tz is not None else base.replace(tzinfo=None)


filtro_horario.datetime = FakeDateTime
filtro_eventos.datetime = FakeDateTime
limitador_diario.datetime = FakeDateTime
sol.datetime = FakeDateTime

TMPDIR = tempfile.mkdtemp(prefix="sol_lateral_evaluar_literal_2020_2026_")
filtro_calidad.LOG_RECHAZOS = os.path.join(TMPDIR, "log_rechazos_fake.csv")
BILLETERA_FAKE = os.path.join(TMPDIR, "billetera_fake.json")
with open(BILLETERA_FAKE, "w") as f:
    json.dump({"USDT": 100000.0, "capital_inicial": 100000.0}, f)
sol.BILLETERA = BILLETERA_FAKE

print(f"[sandbox] archivos temporales en {TMPDIR} (nunca se toca ~/bot-padre-v2)")


def correr(con_filtro, label):
    FILTRO_COMPRESION_ACTIVO["on"] = con_filtro
    aud = os.path.join(TMPDIR, f"auditoria_{'con_filtro' if con_filtro else 'baseline'}.csv")
    with open(aud, "w") as f:
        f.write("timestamp,accion,symbol,precio,rsi,estado,monto,qty\n")
    sol.AUDITORIA = aud
    sol.AUDITORIA_LOCK = aud + ".lock"
    limitador_diario.AUDITORIA = aud
    _fake_db_store["estado_diario"] = None
    CIERRES_LOG.clear()
    APERTURAS_LOG.clear()

    i = idx_ini
    total = idx_fin - idx_ini + 1
    while i <= idx_fin:
        RELOJ["i"] = i
        RELOJ["ahora"] = datetime.strptime(serie[i][0], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        sol.evaluar()
        if (i - idx_ini) % 2000 == 0:
            print(f"  [{label}] {i - idx_ini}/{total}")
        i += 1

    print(f"\n=== {label} completado. Auditoria en: {aud} ===")
    return aud, list(APERTURAS_LOG), list(CIERRES_LOG)


def resumen_de_auditoria(path, nombre, cierres_log):
    with open(path) as f:
        lineas = f.readlines()[1:]
    filas = [l.strip().split(",") for l in lineas if len(l.strip().split(",")) >= 6]
    estados = {}
    for p in filas:
        estados[p[5]] = estados.get(p[5], 0) + 1
    print(f"\n{nombre}: {estados}")

    filas_resueltas = [p for p in filas if p[5] in ("TP", "SL", "TRAILING_SL", "BE")]
    trades = []
    for p, c in zip(filas_resueltas, cierres_log):
        ts_entrada = p[0]
        idx_entrada = next(i for i, v in enumerate(serie) if v[0] == ts_entrada)
        trades.append({"ts_entrada": ts_entrada, "rsi": p[4], "estado": p[5],
                        "entrada": c["precio_entrada"], "salida": c["precio_salida"],
                        "cambio_pct": c["cambio_pct"], "velas": c["idx"] - idx_entrada})

    if trades:
        tp = [t for t in trades if t["estado"] == "TP"]
        wr = round(len(tp) / len(trades) * 100, 1)
        pnl = round(sum(t["cambio_pct"] for t in trades), 2)
        print(f"  n={len(trades)} TP={len(tp)} WR={wr}% PnL simple={pnl}%")

        # desglose anual, mismo estandar que el resto de la serie extendida
        por_anio = {}
        for t in trades:
            anio = t["ts_entrada"][:4]
            por_anio.setdefault(anio, []).append(t)
        print("  por anio:")
        for anio in sorted(por_anio):
            ts_ = por_anio[anio]
            tp_ = [t for t in ts_ if t["estado"] == "TP"]
            wr_ = round(len(tp_) / len(ts_) * 100, 1) if ts_ else 0
            pnl_ = round(sum(t["cambio_pct"] for t in ts_), 2)
            print(f"    {anio}: n={len(ts_)} TP={len(tp_)} WR={wr_}% PnL={pnl_}%")
    return estados, trades


if __name__ == "__main__":
    aud_base, ap_base, ci_base = correr(False, "BASELINE 2020-2026 (evaluar() literal, sin filtro)")
    aud_filtro, ap_filtro, ci_filtro = correr(True, f"CON FILTRO 2020-2026 (compresion EMA20/100 <{COMPRESION_MAX_PCT}%)")

    print("\n\n########## RESUMEN (desde auditoria fake, escrita por el codigo REAL) ##########")
    _, trades_base = resumen_de_auditoria(aud_base, "BASELINE", ci_base)
    _, trades_filtro = resumen_de_auditoria(aud_filtro, "CON FILTRO", ci_filtro)

    os.makedirs(RAW_DIR, exist_ok=True)
    fecha = datetime.now().strftime("%Y-%m-%d")
    for nombre, trades in [("baseline", trades_base), ("con_filtro", trades_filtro)]:
        ruta = os.path.join(RAW_DIR, f"sol_lateral_evaluar_literal_2020_2026_{nombre}_{fecha}.json")
        with open(ruta, "w") as f:
            json.dump(trades, f, indent=2)
        print(f"[output] {ruta}")

    print("\n[DONE]")
