"""
Fase 2-B -- aporte individual de los gates de Parte 1 que faltaban probar:
filtro_horario, filtro_calidad (ATR/volumen), utils.aplicar_filtro_estadistico
(umbral de racha), gestor_correlacion fase-macro (UMBRALES_FASE de BTC).
Mismo sandbox evaluar()/revisar_cierres() literal de toda la sesion, 9 anios,
BTC/ETH ALCISTA por separado.

Gates NO incluidos en este batch, con motivo:
- filtro_eventos (ancho de ventana): NO se corrio -- se resuelve por
  argumento analitico, ver el reporte final. En este sandbox evaluar() solo
  corre en los limites exactos de cada vela de 4h (00/04/08/12/16/20h UTC).
  De los 5 eventos configurados, 4 caen a >=90 min del limite de vela mas
  cercano (fuera de cualquier ventana +-10/15/30min probada) y 1 (20:00 UTC)
  cae EXACTO en un limite de vela (diff=0min) -- se bloquea sin importar el
  ancho de ventana. Variar el ancho de +-10 a +-30 min no puede cambiar el
  resultado con esta granularidad: daria el mismo output en los 3 casos.

Nota sobre las funciones-variante: filtro_calidad.señal_tiene_calidad(),
utils.aplicar_filtro_estadistico() y gestor_correlacion.obtener_fase_btc()
tienen los umbrales como literales dentro del cuerpo de la funcion (no
constantes de modulo) -- no se pueden monkeypatchear directamente. Para cada
uno se escribio un wrapper que llama a las funciones auxiliares REALES sin
modificar (calcular_atr, calcular_volumen_promedio, calcular_rsi_aceleracion,
calcular_ema, fetch_velas, _cargar_probabilidades, detectar_racha_actual) y
solo reimplementa la comparacion final contra el umbral, parametrizada.
filtro_horario si tiene constantes de modulo (HORA_INICIO/HORA_FIN) --
se parchean directamente, sin wrapper.

Nota sobre memoria_propia: en este sandbox el modulo real esta permanentemente
reemplazado por un fake desde el inicio de la sesion (utils.py hace
"from memoria_propia import puede_operar_memoria" -- al registrar
memoria_propia como fake ANTES de importar utils, utils queda con la version
fake). El modulo real depende de auditoria.csv (historial propio del bot en
produccion, multi-simbolo) -- no existe un equivalente historico reconstruible
para un backtest de un solo simbolo. Para poder medir este gate igual, se
construyo una "memoria rodante" a partir de los cierres que el propio
backtest va generando (CIERRES_LOG, ya en orden cronologico, sin look-ahead
porque en cada evaluacion solo contiene cierres PASADOS): WR del simbolo
(bloquea si <40%, replicando el umbral real) y perdidas en los ultimos 5
cierres de los ultimos 14 dias (igual que el original). Aproximacion
documentada: "gano" se aproxima por cambio_pct>0 (el original usa el campo
"estado" de auditoria.csv, no reconstruible 1:1 aqui) y no se reproducen los
componentes de RSI-range/hora-range ni el factor de tamaño de posicion
(0.6x-1.3x) -- solo el mecanismo de BLOQUEO binario, que es lo que importa
para esta pregunta (¿frena entradas o no?).

Consulta de solo lectura. No modifica NADA en ~/bot-padre-v2.

Uso:
    python3 sistema_c/fase2b_gates_restantes.py BTC
    python3 sistema_c/fase2b_gates_restantes.py ETH
"""
import sys, os, json, csv, tempfile, types
import urllib.parse, urllib.request
from datetime import datetime, timezone, timedelta

BOT_DIR = os.path.expanduser("~/bot-padre-v2")
sys.path.insert(0, BOT_DIR)

if len(sys.argv) != 2 or sys.argv[1] not in ("BTC", "ETH"):
    print("Uso: python3 fase2b_gates_restantes.py [BTC|ETH]")
    sys.exit(1)

MONEDA_ARG = sys.argv[1]
SYMBOL = f"{MONEDA_ARG}USDT"
MODULO_NOMBRE = f"francotirador_alcista_{MONEDA_ARG.lower()}"
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
filtro_eventos.puede_operar_eventos = lambda: True  # aprox. establecida en toda la sesion (ver docstring)
import termometro, limitador_diario, detector_multitimeframe, filtro_calidad, utils, config_cartera, gestor_correlacion

_real_puede_operar = gestor_correlacion.puede_operar
_real_obtener_fase_btc = gestor_correlacion.obtener_fase_btc
_HORA_INICIO_REAL, _HORA_FIN_REAL = filtro_horario.HORA_INICIO, filtro_horario.HORA_FIN

def _fase_symbol_actual():
    idx = RELOJ["i"]
    ventana = closes_f[max(0, idx - 209): idx + 1]
    return utils.detectar_fase(ventana, symbol=SYMBOL)

def _puede_operar_gate(accion_nueva, symbol_nuevo):
    if _fase_symbol_actual() != "ALCISTA":
        return False
    return gestor_correlacion.puede_operar_real_actual(accion_nueva, symbol_nuevo)

gestor_correlacion.puede_operar_real_actual = _real_puede_operar
gestor_correlacion.puede_operar = _puede_operar_gate

import importlib
fr = importlib.import_module(MODULO_NOMBRE)
_FAKE_puede_operar_memoria = fr.puede_operar_memoria  # el fake (True,"aproximado",1.0) del sandbox

class FakeDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        base = RELOJ["ahora"]
        return base.astimezone(tz) if tz is not None else base.replace(tzinfo=None)

filtro_horario.datetime = FakeDateTime
filtro_eventos.datetime = FakeDateTime
limitador_diario.datetime = FakeDateTime
fr.datetime = FakeDateTime

TMPDIR = tempfile.mkdtemp(prefix=f"{MONEDA_ARG.lower()}_fase2b_")
filtro_calidad.LOG_RECHAZOS = os.path.join(TMPDIR, "log_rechazos_fake.csv")
BILLETERA_FAKE = os.path.join(TMPDIR, "billetera_fake.json")
with open(BILLETERA_FAKE, "w") as f:
    json.dump({"USDT": 100000.0, "capital_inicial": 100000.0}, f)
fr.BILLETERA = BILLETERA_FAKE
print(f"[sandbox] {SYMBOL}: temporales en {TMPDIR}")


# ---------- wrappers de variantes (llaman funciones auxiliares reales, solo parametrizan el umbral final) ----------

def _wrapper_calidad(atr_min, vol_min):
    def wrapper(symbol, fase):
        velas = filtro_calidad.fetch_velas_completas(symbol, limite=50)
        if not velas or len(velas) < 20:
            return True
        cierres = [float(v[4]) for v in velas]
        atr = filtro_calidad.calcular_atr(velas)
        precio_actual = cierres[-1]
        if atr and precio_actual > 0:
            atr_pct = (atr / precio_actual) * 100
            if atr_pct < atr_min:
                return False
        vol_actual = float(velas[-2][5])
        vol_promedio = filtro_calidad.calcular_volumen_promedio(velas[:-1])
        if vol_promedio and vol_promedio > 0:
            vol_ratio = vol_actual / vol_promedio
            if vol_ratio < vol_min:
                return False
        rsi_actual, aceleracion = filtro_calidad.calcular_rsi_aceleracion(cierres)
        if rsi_actual is not None and aceleracion is not None:
            if fase == "ALCISTA" and aceleracion < -5:
                return False
            if fase == "BAJISTA" and aceleracion > 5:
                return False
        ema20 = filtro_calidad.calcular_ema(cierres, 20)
        ema50 = filtro_calidad.calcular_ema(cierres, 50)
        if ema20 and ema50:
            if fase == "ALCISTA" and not (precio_actual > ema20 > ema50):
                return False
            elif fase == "BAJISTA" and not (precio_actual < ema20 < ema50):
                return False
        return True
    return wrapper


def _wrapper_estadistico(racha_bloqueo_min):
    def wrapper(cierres, symbol=""):
        probs = utils._cargar_probabilidades()
        if not probs:
            return True, "sin_datos_estadisticos"
        racha, color = utils.detectar_racha_actual(cierres)
        if racha >= racha_bloqueo_min:
            return False, f"racha_{racha}_{color}s_zona_muerta_variante"
        clave = f"racha_{min(racha, 6)}_{color}s" if racha >= 2 else None
        if clave and clave in probs.get("rachas", {}):
            p = probs["rachas"][clave]
            prob_rev = p["reversion"]
            muestras = p["muestras"]
            if muestras >= 30 and prob_rev < 0.54:
                return False, f"{clave}_prob_baja_{prob_rev}"
            return True, f"{clave}_prob_{prob_rev}_muestras_{muestras}"
        return True, "sin_patron_relevante"
    return wrapper


def _wrapper_fase_btc(u7, u30):
    def wrapper():
        cierres = utils.fetch_velas("BTCUSDT", limite=210)
        if not cierres or len(cierres) < 55:
            return "DESCONOCIDA"
        precio = cierres[-1]
        ema50 = utils.calcular_ema(cierres, 50)
        ema200 = utils.calcular_ema(cierres, 200) if len(cierres) >= 200 else None
        if ema50 is None or ema200 is None:
            return "DESCONOCIDA"
        velas_7d, velas_30d = 42, 180
        if len(cierres) < velas_30d:
            return "DESCONOCIDA"
        cambio_7d = ((precio - cierres[-velas_7d]) / cierres[-velas_7d]) * 100
        cambio_30d = ((precio - cierres[-velas_30d]) / cierres[-velas_30d]) * 100
        if precio > ema200 and cambio_7d > u7 and cambio_30d > u30:
            return "ALCISTA"
        elif precio < ema200 and cambio_7d < -u7 and cambio_30d < -u30:
            return "BAJISTA"
        return "LATERAL"
    return wrapper


def _wrapper_memoria(perdidas_umbral, min_trades):
    def wrapper(symbol, rsi):
        ahora = RELOJ["ahora"]
        cierres_symbol = CIERRES_LOG  # sandbox de 1 simbolo: todos los cierres son de esta moneda
        if len(cierres_symbol) >= min_trades:
            ganadas = sum(1 for c in cierres_symbol if c["cambio_pct"] > 0)
            wr = ganadas / len(cierres_symbol) * 100
            if wr < 40:
                return False, f"wr_bajo_variante_{round(wr,1)}pct", 0
        hace_14 = ahora - timedelta(days=14)
        recientes = [c for c in cierres_symbol
                     if datetime.strptime(c["ts"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc) >= hace_14]
        ultimos = recientes[-5:] if len(recientes) >= 5 else recientes
        perdidas = sum(1 for c in ultimos if c["cambio_pct"] <= 0)
        if perdidas >= perdidas_umbral:
            return False, f"racha_mala_variante_{perdidas}_perdidas", 0
        return True, "memoria_variante_ok", 1.0
    return wrapper


VARIANTES = [
    ("horario_2_23", "horario", (2, 23)),
    ("horario_6_19", "horario", (6, 19)),
    ("calidad_atr_0.2", "calidad", (0.2, 0.5)),
    ("calidad_atr_0.5", "calidad", (0.5, 0.5)),
    ("calidad_vol_0.4", "calidad", (0.3, 0.4)),
    ("calidad_vol_0.7", "calidad", (0.3, 0.7)),
    ("estadistico_racha4", "estadistico", 4),
    ("estadistico_racha_ampliada", "estadistico", 5),  # bloquea 5 Y 6 (>=5), en vez de solo ==5
    ("correlacion_fase_1.0_1.5", "correlacion", (1.0, 1.5)),
    ("correlacion_fase_2.0_3.0", "correlacion", (2.0, 3.0)),
    ("memoria_perdidas_2", "memoria", (2, 15)),
    ("memoria_perdidas_4", "memoria", (4, 15)),
    ("memoria_mintrades_10", "memoria", (3, 10)),
    ("memoria_mintrades_20", "memoria", (3, 20)),
]


def aplicar_config(kind, params):
    # reset a valores reales primero
    filtro_horario.HORA_INICIO, filtro_horario.HORA_FIN = _HORA_INICIO_REAL, _HORA_FIN_REAL
    fr.señal_tiene_calidad = filtro_calidad.señal_tiene_calidad
    fr.aplicar_filtro_estadistico = utils.aplicar_filtro_estadistico
    gestor_correlacion.obtener_fase_btc = _real_obtener_fase_btc
    fr.puede_operar_memoria = _FAKE_puede_operar_memoria

    if kind is None:
        return
    if kind == "horario":
        filtro_horario.HORA_INICIO, filtro_horario.HORA_FIN = params
    elif kind == "calidad":
        atr_min, vol_min = params
        fr.señal_tiene_calidad = _wrapper_calidad(atr_min, vol_min)
    elif kind == "estadistico":
        fr.aplicar_filtro_estadistico = _wrapper_estadistico(params)
    elif kind == "correlacion":
        u7, u30 = params
        gestor_correlacion.obtener_fase_btc = _wrapper_fase_btc(u7, u30)
    elif kind == "memoria":
        perdidas_umbral, min_trades = params
        fr.puede_operar_memoria = _wrapper_memoria(perdidas_umbral, min_trades)


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

    print(f"\n=== VARIANTES (un gate a la vez, umbral distinto) ===")
    for nombre, kind, params in VARIANTES:
        resultados[nombre] = correr_variante(nombre, kind, params)

    ruta = os.path.join(RAW_DIR, f"{MONEDA_ARG.lower()}_fase2b_gates_{fecha}.json")
    with open(ruta, "w") as f:
        json.dump(resultados, f, indent=2, default=str)
    print(f"\n[output] {ruta}")
