"""
Combinacion de los 2 candidatos mas prometedores de Fase 2 para BTC ALCISTA:
RSI 55-75 (en vez de 50-70) + MAX_OP_TOTAL=2 (en vez de 1), aplicados A LA
VEZ. Los demas 10 gates quedan en su valor real de produccion, sin tocar.

Ninguno de los dos cruzo significancia por separado en Fase 2
(reports/2026-08-23_fase2-aporte-individual-gates.md) -- rsi_55_75 fue el
candidato descriptivo mas estable entre ventanas walk-forward sin ser
significativo; MAX_OP_TOTAL=2 subia el Sharpe pero con trade-off de
drawdown/racha y debilidad en la ventana walk-forward mas reciente. Esta
corrida los combina para ver si juntos cruzan la barra que ninguno cruzo
solo.

Mismo sandbox evaluar()/revisar_cierres() literal de toda la sesion, 9 anios
(2017-2026). Solo lectura. No toca config_cartera.py, francotiradores
reales, auditoria.csv. Sin commits. Sin activar nada.
"""
import sys, os, json, csv, tempfile, types
import urllib.parse, urllib.request
from datetime import datetime, timezone, timedelta

BOT_DIR = os.path.expanduser("~/bot-padre-v2")
sys.path.insert(0, BOT_DIR)

SYMBOL = "BTCUSDT"
MODULO_NOMBRE = "francotirador_alcista_btc"
FECHA_INICIO_ANALISIS = "2017-09-01 00:00:00"
FECHA_FIN_ANALISIS    = datetime.now(timezone.utc).strftime("%Y-%m-%d 23:59:59")
BACKUP_CSV = os.path.expanduser(f"~/bot-padre-v3-backup/data/historico_4h/{SYMBOL}_4h.csv")
FECHA_DESDE_FALLBACK = datetime(2017, 8, 17, tzinfo=timezone.utc)
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
        print(f"[datos] {symbol}: sin backup local -- descargando todo via Binance API")
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
serie_btc = serie
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

def _fase_symbol_actual():
    idx = RELOJ["i"]
    ventana = closes_f[max(0, idx - 209): idx + 1]
    return utils.detectar_fase(ventana, symbol=SYMBOL)

def _puede_operar_gate(accion_nueva, symbol_nuevo):
    if _fase_symbol_actual() != "ALCISTA":
        return False
    return _real_puede_operar(accion_nueva, symbol_nuevo)

gestor_correlacion.puede_operar = _puede_operar_gate

import importlib
fr = importlib.import_module(MODULO_NOMBRE)
_RSI_MIN_REAL, _RSI_MAX_REAL = fr.RSI_MIN, fr.RSI_MAX
_MAX_OP_TOTAL_REAL = fr.MAX_OP_TOTAL

class FakeDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        base = RELOJ["ahora"]
        return base.astimezone(tz) if tz is not None else base.replace(tzinfo=None)

filtro_horario.datetime = FakeDateTime
filtro_eventos.datetime = FakeDateTime
limitador_diario.datetime = FakeDateTime
fr.datetime = FakeDateTime

TMPDIR = tempfile.mkdtemp(prefix="btc_combinacion_")
filtro_calidad.LOG_RECHAZOS = os.path.join(TMPDIR, "log_rechazos_fake.csv")
BILLETERA_FAKE = os.path.join(TMPDIR, "billetera_fake.json")
with open(BILLETERA_FAKE, "w") as f:
    json.dump({"USDT": 100000.0, "capital_inicial": 100000.0}, f)
fr.BILLETERA = BILLETERA_FAKE
print(f"[sandbox] {SYMBOL}: temporales en {TMPDIR}")


def aplicar_config(kind):
    fr.RSI_MIN, fr.RSI_MAX = _RSI_MIN_REAL, _RSI_MAX_REAL
    fr.MAX_OP_TOTAL = _MAX_OP_TOTAL_REAL
    if kind == "combinacion":
        fr.RSI_MIN, fr.RSI_MAX = 55, 75
        fr.MAX_OP_TOTAL = 2


def correr_variante(nombre, kind):
    aplicar_config(kind)
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
    filas_resueltas = [p for p in filas if p[5] in ("TP", "SL", "TRAILING_SL", "BE")]
    trades = []
    for p, c in zip(filas_resueltas, CIERRES_LOG):
        ts_entrada = p[0]
        idx_entrada = next(k for k, v in enumerate(serie) if v[0] == ts_entrada)
        trades.append({"ts_entrada": ts_entrada, "ts_salida": serie[c["idx"]][0], "rsi": p[4],
                        "estado": p[5], "entrada": c["precio_entrada"], "salida": c["precio_salida"],
                        "cambio_pct": c["cambio_pct"], "velas": c["idx"] - idx_entrada})
    tp = [t for t in trades if t["estado"] == "TP"]
    wr = round(len(tp) / len(trades) * 100, 1) if trades else None
    print(f"  [{nombre}] n={len(trades)} TP={len(tp)} WR={wr}%")
    return trades


if __name__ == "__main__":
    os.makedirs(RAW_DIR, exist_ok=True)
    fecha = datetime.now().strftime("%Y-%m-%d")
    resultados = {}

    print(f"\n=== BASELINE (RSI 50-70, MAX_OP_TOTAL=1, produccion real) ===")
    resultados["baseline"] = correr_variante("baseline", None)

    print(f"\n=== COMBINACION (RSI 55-75 + MAX_OP_TOTAL=2) ===")
    resultados["combinacion"] = correr_variante("combinacion", "combinacion")

    ruta = os.path.join(RAW_DIR, f"btc_combinacion_rsi_maxop_{fecha}.json")
    with open(ruta, "w") as f:
        json.dump(resultados, f, indent=2, default=str)
    print(f"\n[output] {ruta}")
