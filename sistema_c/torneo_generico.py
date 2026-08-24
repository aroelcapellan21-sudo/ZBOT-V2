"""
Torneo de francotiradores -- sandbox generico parametrizado por MONEDA y
FASE, mismo metodo evaluar()/revisar_cierres() literal de toda la sesion,
para generar los 12 datasets que faltan de los 15 posibles (BTC/ETH ALCISTA
y SOL LATERAL ya existen de corridas previas de esta sesion).

Extension respecto al patron ya usado en fase2b/fase2c/etc.:
- FASE parametrizable (ALCISTA/LATERAL/BAJISTA) -- el gate de director-fase
  del sandbox exige utils.detectar_fase()==FASE, igual que se viene
  haciendo para ALCISTA, extendido aca a LATERAL/BAJISTA.
- BAJISTA: ademas del gate de fase, se parchea bajistas_activos()=True
  (gate real de gestor_bajistas.py, bloqueado hoy por falta de capital en
  Futuros -- se ignora a proposito para esta investigacion, tal como pidio
  Ariel: "evaluar su rendimiento igual, sin el sesgo de que estan apagados
  por algo"). Se parchea sobre el atributo propio del francotirador
  (fr.bajistas_activos) porque usa "from gestor_bajistas import
  bajistas_activos".
- El simulador de fills ahora acepta "VENTA" (apertura de posicion corta,
  usada por los 5 francotiradores bajistas) ademas de "COMPRA". El P&L de
  una vela bajista es la formula espejo de la alcista (gana cuando el
  precio BAJA), aplicada en el script de analisis, no aca -- este script
  solo registra "accion" (ALCISTA/LATERAL/BAJISTA) en cada trade para que
  el analisis sepa que formula aplicar.

CASO ESPECIAL -- ETH LATERAL: el propio evaluar() de
francotirador_lateral_eth.py tiene un `return` incondicional (desactivado
por codigo desde 2026-08-13, ver CLAUDE.md) -- llamarlo literalmente da
0 trades siempre, no aporta nada. Este caso NO se corre con este script; se
usa el numero de referencia ya documentado (backtest forense PF 0.904,
reports/2026-08-16_ranking-frecuencia-expectancy-15-francotiradores.md).

Solo lectura. No toca config_cartera.py, francotiradores reales,
auditoria.csv. Sin commits.

Uso:
    python3 sistema_c/torneo_generico.py BNB ALCISTA
    python3 sistema_c/torneo_generico.py BNB LATERAL
    python3 sistema_c/torneo_generico.py BNB BAJISTA
    ... etc para AVAX, y BTC/ETH LATERAL/BAJISTA, SOL ALCISTA/BAJISTA
"""
import sys, os, json, csv, tempfile, types
import urllib.parse, urllib.request
from datetime import datetime, timezone, timedelta

BOT_DIR = os.path.expanduser("~/bot-padre-v2")
sys.path.insert(0, BOT_DIR)

if len(sys.argv) != 3 or sys.argv[2] not in ("ALCISTA", "LATERAL", "BAJISTA"):
    print("Uso: python3 torneo_generico.py [BTC|ETH|SOL|BNB|AVAX] [ALCISTA|LATERAL|BAJISTA]")
    sys.exit(1)

MONEDA_ARG = sys.argv[1]
FASE_ARG = sys.argv[2]
SYMBOL = f"{MONEDA_ARG}USDT"
MODULO_NOMBRE = f"francotirador_{FASE_ARG.lower()}_{MONEDA_ARG.lower()}"
ES_BAJISTA = FASE_ARG == "BAJISTA"

FECHA_DESDE_POR_MONEDA = {
    "BTC": datetime(2017, 8, 17, tzinfo=timezone.utc),
    "ETH": datetime(2017, 8, 17, tzinfo=timezone.utc),
    "BNB": datetime(2017, 11, 5, tzinfo=timezone.utc),
    "AVAX": datetime(2020, 9, 22, tzinfo=timezone.utc),
    "SOL": datetime(2020, 8, 25, tzinfo=timezone.utc),
}
FECHA_DESDE_FALLBACK = FECHA_DESDE_POR_MONEDA[MONEDA_ARG]
FECHA_INICIO_ANALISIS = (FECHA_DESDE_FALLBACK + timedelta(days=14)).strftime("%Y-%m-%d 00:00:00")
FECHA_FIN_ANALISIS = datetime.now(timezone.utc).strftime("%Y-%m-%d 23:59:59")
BACKUP_CSV = os.path.expanduser(f"~/bot-padre-v3-backup/data/historico_4h/{SYMBOL}_4h.csv")
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


def _cargar_serie(symbol, backup_csv, fecha_desde):
    velas = {}
    if os.path.exists(backup_csv):
        with open(backup_csv) as f:
            for row in csv.DictReader(f):
                velas[row["timestamp"]] = (row["open"], row["high"], row["low"], row["close"], row["volume"])
        ultimo_ts = max(velas.keys())
        start_relleno = datetime.strptime(ultimo_ts, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    else:
        start_relleno = fecha_desde
    end_relleno = datetime.strptime(FECHA_FIN_ANALISIS, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    kl = _fetch_klines_real(symbol, int(start_relleno.timestamp() * 1000), int(end_relleno.timestamp() * 1000))
    for k in kl:
        ts = datetime.fromtimestamp(k[0] / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        velas[ts] = (str(k[1]), str(k[2]), str(k[3]), str(k[4]), str(k[5]))
    ts_sorted = sorted(velas.keys())
    return [(ts, *velas[ts]) for ts in ts_sorted]


serie = _cargar_serie(SYMBOL, BACKUP_CSV, FECHA_DESDE_FALLBACK)
closes_f = [float(v[4]) for v in serie]
if SYMBOL == "BTCUSDT":
    serie_btc = serie
else:
    serie_btc = _cargar_serie("BTCUSDT", os.path.expanduser("~/bot-padre-v3-backup/data/historico_4h/BTCUSDT_4h.csv"),
                               FECHA_DESDE_POR_MONEDA["BTC"])
SERIES = {SYMBOL: serie, "BTCUSDT": serie_btc}
TS_LISTAS = {sym: [v[0] for v in s] for sym, s in SERIES.items()}

_inicio_dt = datetime.strptime(FECHA_INICIO_ANALISIS, "%Y-%m-%d %H:%M:%S")
_inicio_ajustado = (_inicio_dt - timedelta(hours=4)).strftime("%Y-%m-%d %H:%M:%S")
idx_ini = next(i for i, v in enumerate(serie) if v[0] >= _inicio_ajustado)
idx_fin = len(serie) - 1
if serie[-1][0] > FECHA_FIN_ANALISIS:
    idx_fin = next(i for i, v in enumerate(serie) if v[0] > FECHA_FIN_ANALISIS) - 1
print(f"[datos] {SYMBOL} {FASE_ARG}: ventana {serie[idx_ini][0]} -> {serie[idx_fin][0]} ({idx_fin-idx_ini+1} velas)")

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
    if tipo in ("COMPRA", "VENTA"):
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
    if _fase_symbol_actual() != FASE_ARG:
        return False
    return _real_puede_operar(accion_nueva, symbol_nuevo)

gestor_correlacion.puede_operar = _puede_operar_gate

import importlib
fr = importlib.import_module(MODULO_NOMBRE)
if ES_BAJISTA:
    fr.bajistas_activos = lambda: True  # gate real de gestor_bajistas.py, ignorado a proposito

class FakeDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        base = RELOJ["ahora"]
        return base.astimezone(tz) if tz is not None else base.replace(tzinfo=None)

filtro_horario.datetime = FakeDateTime
filtro_eventos.datetime = FakeDateTime
limitador_diario.datetime = FakeDateTime
fr.datetime = FakeDateTime

TMPDIR = tempfile.mkdtemp(prefix=f"{MONEDA_ARG.lower()}_{FASE_ARG.lower()}_torneo_")
filtro_calidad.LOG_RECHAZOS = os.path.join(TMPDIR, "log_rechazos_fake.csv")
BILLETERA_FAKE = os.path.join(TMPDIR, "billetera_fake.json")
with open(BILLETERA_FAKE, "w") as f:
    json.dump({"USDT": 100000.0, "capital_inicial": 100000.0}, f)
fr.BILLETERA = BILLETERA_FAKE
print(f"[sandbox] {SYMBOL} {FASE_ARG}: temporales en {TMPDIR}")

aud = os.path.join(TMPDIR, "auditoria.csv")
with open(aud, "w") as f:
    f.write("timestamp,accion,symbol,precio,rsi,estado,monto,qty\n")
fr.AUDITORIA = aud; fr.AUDITORIA_LOCK = aud + ".lock"
limitador_diario.AUDITORIA = aud; gestor_correlacion.AUDITORIA = aud

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
                    "estado": p[5], "accion": p[1], "entrada": c["precio_entrada"], "salida": c["precio_salida"],
                    "cambio_pct": c["cambio_pct"], "velas": c["idx"] - idx_entrada})
tp = [t for t in trades if t["estado"] == "TP"]
wr = round(len(tp) / len(trades) * 100, 1) if trades else None
print(f"  [{MONEDA_ARG} {FASE_ARG}] n={len(trades)} TP={len(tp)} WR={wr}%")

os.makedirs(RAW_DIR, exist_ok=True)
fecha = datetime.now().strftime("%Y-%m-%d")
ruta = os.path.join(RAW_DIR, f"torneo_{MONEDA_ARG.lower()}_{FASE_ARG.lower()}_{fecha}.json")
with open(ruta, "w") as f:
    json.dump({"trades": trades}, f, indent=2, default=str)
print(f"[output] {ruta}")
