"""
Fase 2-B Parte 2, items 8 y 9:
8. Compresion EMA20/100 <1% (gate ya investigado en
   reports/2026-08-17_compresion-4-monedas-alcista.md con ventana de 8 meses,
   0-4 trades -- se re-corre con 9 años completos) para BTC y ETH.
9. Sistema C (RSI 55-60 + gate EMA200 diaria anti-lookahead) para BTC,
   comparado cabeza a cabeza contra el perfil de 12 gates de produccion
   completo (a diferencia de la investigacion original que solo comparaba
   contra un baseline simplificado). ETH ya descartado, no se repite.

Mismo sandbox evaluar()/revisar_cierres() literal de toda la sesion.
Mismo punto de enganche que resim_evaluar_literal_alcista_4monedas.py para
compresion: gestor_correlacion.puede_operar (gate de fase-director real +
correlacion real + filtro extra), replicado aqui.

EMA200 diaria anti-lookahead: se construye a partir de la propia serie 4h ya
cargada (BTCUSDT), tomando el cierre de la vela "20:00:00" de cada dia como
cierre diario equivalente (esa vela cierra exactamente a las 00:00 UTC del
dia siguiente, igual que una vela diaria de Binance). Al evaluar en una vela
del dia D, se usa el EMA200 calculado con cierres diarios hasta el dia D-1
inclusive -- nunca el cierre (todavia no ocurrido) del dia D.

Solo lectura. No toca config_cartera.py, francotiradores reales,
auditoria.csv. Sin commits. Sin activar nada.

Uso:
    python3 sistema_c/fase2c_parte2.py BTC
    python3 sistema_c/fase2c_parte2.py ETH
"""
import sys, os, json, csv, tempfile, types
import urllib.parse, urllib.request
from datetime import datetime, timezone, timedelta

BOT_DIR = os.path.expanduser("~/bot-padre-v2")
sys.path.insert(0, BOT_DIR)

if len(sys.argv) != 2 or sys.argv[1] not in ("BTC", "ETH"):
    print("Uso: python3 fase2c_parte2.py [BTC|ETH]")
    sys.exit(1)

MONEDA_ARG = sys.argv[1]
SYMBOL = f"{MONEDA_ARG}USDT"
MODULO_NOMBRE = f"francotirador_alcista_{MONEDA_ARG.lower()}"
FECHA_INICIO_ANALISIS = "2017-09-01 00:00:00"
FECHA_FIN_ANALISIS    = datetime.now(timezone.utc).strftime("%Y-%m-%d 23:59:59")
BACKUP_CSV = os.path.expanduser(f"~/bot-padre-v3-backup/data/historico_4h/{SYMBOL}_4h.csv")
FECHA_DESDE_FALLBACK = datetime(2017, 8, 17, tzinfo=timezone.utc)
RAW_DIR = os.path.expanduser("~/bot-padre-v2/reports/raw")
COMPRESION_MAX_PCT = 1.0


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
if SYMBOL == "BTCUSDT":
    serie_btc = serie
else:
    serie_btc = _cargar_serie("BTCUSDT", os.path.expanduser("~/bot-padre-v3-backup/data/historico_4h/BTCUSDT_4h.csv"))
SERIES = {SYMBOL: serie, "BTCUSDT": serie_btc}
TS_LISTAS = {sym: [v[0] for v in s] for sym, s in SERIES.items()}
closes_btc_f = [float(v[4]) for v in serie_btc]

_inicio_dt = datetime.strptime(FECHA_INICIO_ANALISIS, "%Y-%m-%d %H:%M:%S")
_inicio_ajustado = (_inicio_dt - timedelta(hours=4)).strftime("%Y-%m-%d %H:%M:%S")
idx_ini = next(i for i, v in enumerate(serie) if v[0] >= _inicio_ajustado)
idx_fin = len(serie) - 1
if serie[-1][0] > FECHA_FIN_ANALISIS:
    idx_fin = next(i for i, v in enumerate(serie) if v[0] > FECHA_FIN_ANALISIS) - 1
print(f"[datos] {SYMBOL}: ventana {serie[idx_ini][0]} -> {serie[idx_fin][0]} ({idx_fin-idx_ini+1} velas)")

# ---------- EMA200 diaria anti-lookahead (solo se usa para variante sistema_c, BTC) ----------
_dias_cierre_btc = [(v[0][:10], float(v[4])) for v in serie_btc if v[0][11:] == "20:00:00"]
_dias_cierre_btc.sort(key=lambda x: x[0])
_fechas_btc = [d for d, _ in _dias_cierre_btc]
_closes_diarios_btc = [c for _, c in _dias_cierre_btc]

def _ema200_diaria_hasta(fecha_str_yyyy_mm_dd):
    import bisect as _bisect
    idx = _bisect.bisect_left(_fechas_btc, fecha_str_yyyy_mm_dd)  # primer dia >= fecha_actual
    if idx < 200:
        return None
    ventana = _closes_diarios_btc[:idx]  # estrictamente anterior al dia actual
    k = 2 / (200 + 1)
    ema = sum(ventana[:200]) / 200
    for precio in ventana[200:]:
        ema = precio * k + ema * (1 - k)
    return ema

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

def _calcular_ema_local(cierres, periodo):
    if len(cierres) < periodo:
        return None
    k = 2 / (periodo + 1)
    ema = sum(cierres[:periodo]) / periodo
    for precio in cierres[periodo:]:
        ema = precio * k + ema * (1 - k)
    return ema

ESTADO_VARIANTE = {"kind": None}

def _puede_operar_gate(accion_nueva, symbol_nuevo):
    if _fase_symbol_actual() != "ALCISTA":
        return False
    if not _real_puede_operar(accion_nueva, symbol_nuevo):
        return False
    kind = ESTADO_VARIANTE["kind"]
    if kind == "compresion":
        idx = RELOJ["i"]
        ventana = closes_f[max(0, idx - 209): idx + 1]
        ema_c = _calcular_ema_local(ventana, 20)
        ema_l = _calcular_ema_local(ventana, 100)
        if ema_c is None or ema_l is None:
            return True
        compresion = abs(ema_c - ema_l) / ema_l * 100
        return compresion < COMPRESION_MAX_PCT
    if kind == "sistema_c":
        fecha_actual = serie[RELOJ["i"]][0][:10]
        ema200d = _ema200_diaria_hasta(fecha_actual)
        if ema200d is None:
            return False  # sin suficiente historia diaria -- anti-lookahead estricto, no se permite
        precio_actual = closes_f[RELOJ["i"]]
        return precio_actual > ema200d
    return True

gestor_correlacion.puede_operar = _puede_operar_gate

import importlib
fr = importlib.import_module(MODULO_NOMBRE)
_RSI_MIN_REAL, _RSI_MAX_REAL = fr.RSI_MIN, fr.RSI_MAX

class FakeDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        base = RELOJ["ahora"]
        return base.astimezone(tz) if tz is not None else base.replace(tzinfo=None)

filtro_horario.datetime = FakeDateTime
filtro_eventos.datetime = FakeDateTime
limitador_diario.datetime = FakeDateTime
fr.datetime = FakeDateTime

TMPDIR = tempfile.mkdtemp(prefix=f"{MONEDA_ARG.lower()}_fase2c_")
filtro_calidad.LOG_RECHAZOS = os.path.join(TMPDIR, "log_rechazos_fake.csv")
BILLETERA_FAKE = os.path.join(TMPDIR, "billetera_fake.json")
with open(BILLETERA_FAKE, "w") as f:
    json.dump({"USDT": 100000.0, "capital_inicial": 100000.0}, f)
fr.BILLETERA = BILLETERA_FAKE
print(f"[sandbox] {SYMBOL}: temporales en {TMPDIR}")

if MONEDA_ARG == "BTC":
    VARIANTES = [("compresion_1pct", "compresion", None), ("sistema_c_rsi55_60_ema200d", "sistema_c", (55, 60))]
else:
    VARIANTES = [("compresion_1pct", "compresion", None)]


def aplicar_config(kind, params):
    fr.RSI_MIN, fr.RSI_MAX = _RSI_MIN_REAL, _RSI_MAX_REAL
    ESTADO_VARIANTE["kind"] = kind
    if kind == "sistema_c" and params:
        fr.RSI_MIN, fr.RSI_MAX = params


def correr_variante(nombre, kind, params):
    aplicar_config(kind, params)
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

    print(f"\n=== BASELINE (los 12 gates en su valor real de produccion) ===")
    resultados["baseline"] = correr_variante("baseline", None, None)

    print(f"\n=== VARIANTES ===")
    for nombre, kind, params in VARIANTES:
        resultados[nombre] = correr_variante(nombre, kind, params)

    ruta = os.path.join(RAW_DIR, f"{MONEDA_ARG.lower()}_fase2c_parte2_{fecha}.json")
    with open(ruta, "w") as f:
        json.dump(resultados, f, indent=2, default=str)
    print(f"\n[output] {ruta}")
