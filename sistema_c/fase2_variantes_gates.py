"""
Fase 2 de la investigacion de perfil de gates por moneda (BTC/ETH ALCISTA).
Mide el APORTE INDIVIDUAL de variantes de: (a) RSI/EMA de entrada, (b)
MAX_OP_TOTAL, (c) EMA hardcodeada de detector_multitimeframe -- una variante
a la vez, contra el mismo sandbox evaluar()/revisar_cierres() literal ya
usado en toda esta sesion (adaptado de sistema_c/resim_evaluar_literal_
alcista_9anios.py). El resto de los 12 gates queda en su valor real de
produccion en TODAS las corridas (no se combinan cambios).

Limitacion heredada, sin corregir aca (ya documentada en reportes previos):
el interceptor de urlopen sirve la misma ventana 4h para cualquier "interval"
pedido -- confirmar_tendencia_multitf() recibe datos 4h relabeled como si
fueran 1h/1d. Es la misma aproximacion que ya tiene el dataset baseline de
9 anios usado como Sistema A en toda la sesion -- no se introduce aca, se
hereda igual en baseline y en cada variante.

Consulta de solo lectura. No modifica NADA en ~/bot-padre-v2.

Uso:
    python3 sistema_c/fase2_variantes_gates.py BTC
    python3 sistema_c/fase2_variantes_gates.py ETH
"""
import sys, os, json, csv, tempfile, types
import urllib.parse, urllib.request
from datetime import datetime, timezone, timedelta

BOT_DIR = os.path.expanduser("~/bot-padre-v2")
sys.path.insert(0, BOT_DIR)

if len(sys.argv) != 2 or sys.argv[1] not in ("BTC", "ETH"):
    print("Uso: python3 fase2_variantes_gates.py [BTC|ETH]")
    sys.exit(1)

MONEDA_ARG = sys.argv[1]
SYMBOL = f"{MONEDA_ARG}USDT"
MODULO_NOMBRE = f"francotirador_alcista_{MONEDA_ARG.lower()}"

FECHA_INICIO_ANALISIS = "2017-09-01 00:00:00"
FECHA_FIN_ANALISIS    = datetime.now(timezone.utc).strftime("%Y-%m-%d 23:59:59")
BACKUP_CSV = os.path.expanduser(f"~/bot-padre-v3-backup/data/historico_4h/{SYMBOL}_4h.csv")
FECHA_DESDE_FALLBACK = datetime(2017, 8, 17, tzinfo=timezone.utc)
RAW_DIR = os.path.expanduser("~/bot-padre-v2/reports/raw")

# ---- variantes por moneda (Parte 1 del banco de candidatos, orden a/b/c) ----
PRODUCCION = {
    "BTC": dict(rsi_min=50, rsi_max=70, ema_c=20, ema_l=50, max_op=1, mtf_ema_c=20, mtf_ema_l=50),
    "ETH": dict(rsi_min=60, rsi_max=75, ema_c=20, ema_l=100, max_op=1, mtf_ema_c=20, mtf_ema_l=50),
}

VARIANTES = {
    "BTC": [
        ("rsi_45_65", dict(rsi_min=45, rsi_max=65)),
        ("rsi_55_75", dict(rsi_min=55, rsi_max=75)),
        ("ema_20_100", dict(ema_c=20, ema_l=100)),
        ("ema_10_50", dict(ema_c=10, ema_l=50)),
        ("maxop_2", dict(max_op=2)),
        ("maxop_3", dict(max_op=3)),
        ("mtf_20_100", dict(mtf_ema_c=20, mtf_ema_l=100)),
        ("mtf_50_200", dict(mtf_ema_c=50, mtf_ema_l=200)),
    ],
    "ETH": [
        ("rsi_55_70", dict(rsi_min=55, rsi_max=70)),
        ("rsi_65_80", dict(rsi_min=65, rsi_max=80)),
        ("ema_20_50", dict(ema_c=20, ema_l=50)),
        ("ema_10_100", dict(ema_c=10, ema_l=100)),
        ("maxop_2", dict(max_op=2)),
        ("maxop_3", dict(max_op=3)),
        ("mtf_20_100", dict(mtf_ema_c=20, mtf_ema_l=100)),
        ("mtf_50_200", dict(mtf_ema_c=50, mtf_ema_l=200)),
    ],
}


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


def _cargar_serie(symbol, backup_csv):
    velas = {}
    if os.path.exists(backup_csv):
        with open(backup_csv) as f:
            for row in csv.DictReader(f):
                velas[row["timestamp"]] = (row["open"], row["high"], row["low"], row["close"], row["volume"])
        ultimo_ts = max(velas.keys())
        start_relleno = datetime.strptime(ultimo_ts, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        print(f"[datos] {symbol}: backup local hasta {ultimo_ts} -- completando desde ahi via Binance API")
    else:
        start_relleno = FECHA_DESDE_FALLBACK
        print(f"[datos] {symbol}: sin backup local -- descargando todo desde {start_relleno} via Binance API")
    end_relleno = datetime.strptime(FECHA_FIN_ANALISIS, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    kl = _fetch_klines_real(symbol, int(start_relleno.timestamp() * 1000), int(end_relleno.timestamp() * 1000))
    for k in kl:
        ts = datetime.fromtimestamp(k[0] / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        velas[ts] = (str(k[1]), str(k[2]), str(k[3]), str(k[4]), str(k[5]))
    print(f"[datos] {symbol}: {len(kl)} velas frescas de Binance API")
    ts_sorted = sorted(velas.keys())
    return [(ts, *velas[ts]) for ts in ts_sorted]


serie = _cargar_serie(SYMBOL, BACKUP_CSV)
closes_f = [float(v[4]) for v in serie]
if SYMBOL == "BTCUSDT":
    serie_btc = serie
else:
    serie_btc = _cargar_serie("BTCUSDT", os.path.expanduser("~/bot-padre-v3-backup/data/historico_4h/BTCUSDT_4h.csv"))
SERIES = {SYMBOL: serie, "BTCUSDT": serie_btc}
TS_LISTAS = {sym: [v[0] for v in s] for sym, s in SERIES.items()}

_inicio_dt = datetime.strptime(FECHA_INICIO_ANALISIS, "%Y-%m-%d %H:%M:%S")
_inicio_ajustado = (_inicio_dt - timedelta(hours=4)).strftime("%Y-%m-%d %H:%M:%S")
idx_ini = next(i for i, v in enumerate(serie) if v[0] >= _inicio_ajustado)
idx_fin = len(serie) - 1
if serie[-1][0] > FECHA_FIN_ANALISIS:
    idx_fin = next(i for i, v in enumerate(serie) if v[0] > FECHA_FIN_ANALISIS) - 1
print(f"[datos] {SYMBOL}: ventana {serie[idx_ini][0]} -> {serie[idx_fin][0]} ({idx_fin-idx_ini+1} velas)")

RELOJ = {"i": idx_ini, "ahora": None}

def _calcular_ema(cierres, periodo):
    if len(cierres) < periodo:
        return None
    k = 2 / (periodo + 1)
    ema = sum(cierres[:periodo]) / periodo
    for precio in cierres[periodo:]:
        ema = precio * k + ema * (1 - k)
    return ema

_fake_db_store = {"estado_termometro": {"timestamp": "2026-03-04 22:51:28", "estado": "TENDENCIA_DEBIL",
                   "parametros": {"tp_mult": 1.0, "sl_mult": 1.0, "operar": True, "descripcion": "x"}}}
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
CIERRES_LOG, APERTURAS_LOG = [], []

def _fake_ejecutar_operacion(moneda, tipo, precio, monto=None):
    if not monto or monto <= 0 or monto < 5.0:
        return f"❌ RECHAZADO", None
    precio_fill = closes_f[RELOJ["i"]]
    if tipo == "COMPRA":
        qty_neta = (monto / precio_fill) * (1 - COMISION_SPOT)
        fill = {"qty": qty_neta, "usdt": monto, "precio": precio_fill}
        APERTURAS_LOG.append({"idx": RELOJ["i"], "ts": serie[RELOJ["i"]][0], "precio": precio_fill})
        return f"✅ [SIM] EJECUTADO", fill
    return f"❌ Tipo desconocido", None

def _fake_cerrar_posicion(moneda, tipo_trade, precio_entrada, monto_op, qty=None):
    precio_fill = closes_f[RELOJ["i"]]
    if qty is None:
        qty = monto_op / precio_entrada
    usdt_neto = qty * precio_fill * (1 - COMISION_SPOT)
    fill = {"qty": qty, "usdt": usdt_neto, "precio": precio_fill}
    CIERRES_LOG.append({"idx": RELOJ["i"], "ts": serie[RELOJ["i"]][0],
                         "precio_entrada": precio_entrada, "precio_salida": precio_fill,
                         "cambio_pct": round((precio_fill - precio_entrada) / precio_entrada * 100, 3)})
    return f"✅ [SIM] CIERRE", fill

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

import bisect

class FakeResponse:
    def __init__(self, body): self._body = body
    def read(self): return self._body
    def __enter__(self): return self
    def __exit__(self, *a): return False

def fake_urlopen(url, timeout=10, data=None, **kw):
    if "api/v3/klines" not in url:
        raise RuntimeError(f"URL no esperada: {url}")
    qs = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    limit = int(qs.get("limit", ["210"])[0])
    sym = qs.get("symbol", [SYMBOL])[0]
    if sym not in SERIES:
        raise RuntimeError(f"Symbol no soportado: {sym}")
    serie_sym = SERIES[sym]; ts_lista = TS_LISTAS[sym]
    ahora_str = RELOJ["ahora"].strftime("%Y-%m-%d %H:%M:%S")
    idx = bisect.bisect_right(ts_lista, ahora_str) - 1
    if idx < 0: idx = 0
    start = max(0, idx - limit + 1)
    window = serie_sym[start: idx + 1]
    if len(window) < limit:
        window = ([window[0]] * (limit - len(window)) + window) if window else [serie_sym[0]] * limit
    klines = [[0, o, h, l, c, v, 0, "0", 0, "0", "0", "0"] for (_, o, h, l, c, v) in window]
    return FakeResponse(json.dumps(klines).encode())

urllib.request.urlopen = fake_urlopen

import filtro_horario, filtro_eventos
filtro_eventos.puede_operar_eventos = lambda: True
import termometro, limitador_diario, detector_multitimeframe, filtro_calidad, utils, config_cartera, gestor_correlacion

_real_puede_operar = gestor_correlacion.puede_operar

def _fase_symbol_actual(ema_c, ema_l):
    idx = RELOJ["i"]
    ventana = closes_f[max(0, idx - 209): idx + 1]
    return utils.detectar_fase(ventana, symbol=SYMBOL)

def _puede_operar_gate(accion_nueva, symbol_nuevo):
    if _fase_symbol_actual(None, None) != "ALCISTA":
        return False
    return _real_puede_operar(accion_nueva, symbol_nuevo)

gestor_correlacion.puede_operar = _puede_operar_gate

import importlib
fr = importlib.import_module(MODULO_NOMBRE)

class FakeDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        base = RELOJ["ahora"]
        return base.astimezone(tz) if tz is not None else base.replace(tzinfo=None)

filtro_horario.datetime = FakeDateTime
filtro_eventos.datetime = FakeDateTime
limitador_diario.datetime = FakeDateTime
fr.datetime = FakeDateTime

TMPDIR = tempfile.mkdtemp(prefix=f"{MONEDA_ARG.lower()}_fase2_")
filtro_calidad.LOG_RECHAZOS = os.path.join(TMPDIR, "log_rechazos_fake.csv")
BILLETERA_FAKE = os.path.join(TMPDIR, "billetera_fake.json")
with open(BILLETERA_FAKE, "w") as f:
    json.dump({"USDT": 100000.0, "capital_inicial": 100000.0}, f)
fr.BILLETERA = BILLETERA_FAKE

# ---- parche de EMA de multitimeframe (intercepta solo las llamadas de ESE modulo) ----
_orig_mtf_ema = detector_multitimeframe.calcular_ema
_MTF_PATCH = {"c": 20, "l": 50}
def _mtf_ema_patched(cierres, periodo):
    if periodo == 20:
        periodo = _MTF_PATCH["c"]
    elif periodo == 50:
        periodo = _MTF_PATCH["l"]
    return _orig_mtf_ema(cierres, periodo)
detector_multitimeframe.calcular_ema = _mtf_ema_patched

print(f"[sandbox] {SYMBOL}: temporales en {TMPDIR}")


def correr_variante(nombre, params):
    p = dict(PRODUCCION[MONEDA_ARG])
    p.update(params)
    fr.RSI_MIN = p["rsi_min"]; fr.RSI_MAX = p["rsi_max"]
    fr.EMA_CORTA = p["ema_c"]; fr.EMA_LARGA = p["ema_l"]
    fr.MAX_OP_TOTAL = p["max_op"]
    _MTF_PATCH["c"] = p["mtf_ema_c"]; _MTF_PATCH["l"] = p["mtf_ema_l"]

    aud = os.path.join(TMPDIR, f"auditoria_{nombre}.csv")
    with open(aud, "w") as f:
        f.write("timestamp,accion,symbol,precio,rsi,estado,monto,qty\n")
    fr.AUDITORIA = aud; fr.AUDITORIA_LOCK = aud + ".lock"
    limitador_diario.AUDITORIA = aud; gestor_correlacion.AUDITORIA = aud
    _fake_db_store["estado_diario"] = None
    CIERRES_LOG.clear(); APERTURAS_LOG.clear()

    i = idx_ini
    while i <= idx_fin:
        RELOJ["i"] = i
        RELOJ["ahora"] = datetime.strptime(serie[i][0], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        fr.evaluar()
        i += 1

    with open(aud) as f:
        lineas = f.readlines()[1:]
    filas = [l.strip().split(",") for l in lineas if len(l.strip().split(",")) >= 6]
    filas_resueltas = [p2 for p2 in filas if p2[5] in ("TP", "SL", "TRAILING_SL", "BE")]
    trades = []
    for p2, c in zip(filas_resueltas, CIERRES_LOG):
        ts_entrada = p2[0]
        idx_entrada = next(k for k, v in enumerate(serie) if v[0] == ts_entrada)
        trades.append({"ts_entrada": ts_entrada, "ts_salida": serie[c["idx"]][0], "rsi": p2[4],
                        "estado": p2[5], "entrada": c["precio_entrada"], "salida": c["precio_salida"],
                        "cambio_pct": c["cambio_pct"], "velas": c["idx"] - idx_entrada})
    tp = [t for t in trades if t["estado"] == "TP"]
    wr = round(len(tp) / len(trades) * 100, 1) if trades else None
    print(f"  [{nombre}] n={len(trades)} TP={len(tp)} WR={wr}% params={ {k:v for k,v in p.items()} }")
    return trades


if __name__ == "__main__":
    os.makedirs(RAW_DIR, exist_ok=True)
    fecha = datetime.now().strftime("%Y-%m-%d")
    resultados = {}

    print(f"\n=== BASELINE (produccion real) ===")
    trades_base = correr_variante("baseline", {})
    resultados["baseline"] = trades_base

    print(f"\n=== VARIANTES ===")
    for nombre, params in VARIANTES[MONEDA_ARG]:
        resultados[nombre] = correr_variante(nombre, params)

    ruta = os.path.join(RAW_DIR, f"{MONEDA_ARG.lower()}_fase2_variantes_{fecha}.json")
    with open(ruta, "w") as f:
        json.dump(resultados, f, indent=2, default=str)
    print(f"\n[output] {ruta}")
