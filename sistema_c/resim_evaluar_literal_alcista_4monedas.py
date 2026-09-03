"""
Re-simulacion de BTC/ETH/BNB/AVAX ALCISTA corriendo evaluar() LITERAL (la
funcion real completa de cada francotirador, sin reimplementar nada de su
logica interna: ni gates, ni revisar_cierres(), ni SL/TP/breakeven/trailing)
sobre velas historicas reales, vela a vela.

Adaptacion directa de sistema_c/resim_evaluar_literal_sol_lateral.py (ver
reports/2026-08-17_evaluar-literal-sol-lateral.md) a las 4 monedas restantes
en fase ALCISTA. Mismo sandbox, mismo punto de enganche del filtro de
compresion (gestor_correlacion.puede_operar), mismo umbral EMA20/100 <1%.

Ventana: 2026-01-01 -> 2026-08-17. Se corre primero BASELINE (sin filtro) y
se compara contra los numeros ya documentados:
  BTC: 8 trades / WR 42.9% / +1.65%
  ETH: 13 trades / WR 50.0% / +7.80%
  BNB: 8 trades / WR 28.6% / -9.18%
  AVAX: 10 trades / WR 20.0% / -27.80%
Luego se corre CON FILTRO (compresion EMA20/100 <1%, mismo hook que SOL).

Sandbox estricto -- se reemplazan en sys.modules ANTES de cualquier import
real: db, engine, ejecutor, guardian_riesgo, medidor_spread, gestor_billetera,
memoria_propia, memoria (paquete) / memoria.memoria (submodulo),
gestor_correlacion (punto de enganche del filtro de compresion). NUNCA tocan
bot.db, Telegram, billetera.json real, auditoria.csv real,
log_rechazos_calidad.csv real ni data/memoria_propia.json real -- todo va a
archivos temporales.

Se mantienen REALES (import real, ejecutado tal cual vive en el repo):
termometro, filtro_horario, filtro_eventos, limitador_diario,
detector_multitimeframe, filtro_calidad, utils, config_cartera (solo ETH lo
usa en produccion), y cada francotirador_alcista_<moneda> completo
(evaluar()/revisar_cierres() literales).

Gates aproximados (siempre pasan, documentado, no reconstruibles
historicamente): guardian de riesgo (curva de capital), spread (libro de
ordenes en vivo), memoria propia (para no leer/escribir el archivo real).

Limitacion heredada del script de SOL: fake_urlopen sirve la misma ventana
4h para cualquier pedido de klines, sin distinguir "interval" -- si
detector_multitimeframe pide una vela mayor (1d), igual recibe velas
etiquetadas como si fueran de ese intervalo. Misma aproximacion ya aceptada
en la corrida validada de SOL.

Uso:
    python3 sistema_c/resim_evaluar_literal_alcista_4monedas.py BTC
    python3 sistema_c/resim_evaluar_literal_alcista_4monedas.py ETH
    python3 sistema_c/resim_evaluar_literal_alcista_4monedas.py BNB
    python3 sistema_c/resim_evaluar_literal_alcista_4monedas.py AVAX

Cada invocacion es un proceso Python separado -- aislamiento total entre
monedas (nada de estado global compartido entre corridas).

Requiere conexion a internet (rellena velas 4h recientes via API publica de
Binance) y usa el CSV de respaldo en
~/bot-padre-v3-backup/data/historico_4h/<SYMBOL>_4h.csv si existe.

Consulta de solo lectura. No modifica NADA en ~/bot-padre-v2. Verificar con
mtime/tamaño idénticos en archivos sensibles antes/despues de correr.

Sin librerias externas (Python estandar) -- feedback_librerias_externas_investigacion.
"""
import sys, os, json, csv, tempfile, types, statistics
import urllib.parse, urllib.request
from datetime import datetime, timezone

BOT_DIR = os.path.expanduser("~/bot-padre-v2")
sys.path.insert(0, BOT_DIR)

if len(sys.argv) != 2 or sys.argv[1] not in ("BTC", "ETH", "BNB", "AVAX"):
    print("Uso: python3 resim_evaluar_literal_alcista_4monedas.py [BTC|ETH|BNB|AVAX]")
    sys.exit(1)

MONEDA_ARG = sys.argv[1]
SYMBOL = f"{MONEDA_ARG}USDT"
MODULO_NOMBRE = f"francotirador_alcista_{MONEDA_ARG.lower()}"

FECHA_INICIO_ANALISIS = "2026-01-01 00:00:00"
FECHA_FIN_ANALISIS    = "2026-08-17 23:59:59"
COMPRESION_MAX_PCT    = 1.0  # mismo umbral usado en la corrida de SOL
BACKUP_CSV = os.path.expanduser(f"~/bot-padre-v3-backup/data/historico_4h/{SYMBOL}_4h.csv")
FECHA_DESDE_FALLBACK = datetime(2020, 9, 1, tzinfo=timezone.utc)

RAW_DIR = os.path.expanduser("~/bot-padre-v2/reports/raw")

# =========================================================
# 1) Datos historicos reales: CSV de respaldo + relleno via Binance API real
# =========================================================
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
    serie_local = [(ts, *velas[ts]) for ts in ts_sorted]

    huecos = 0
    for i in range(1, len(serie_local)):
        t0 = datetime.strptime(serie_local[i - 1][0], "%Y-%m-%d %H:%M:%S")
        t1 = datetime.strptime(serie_local[i][0], "%Y-%m-%d %H:%M:%S")
        if (t1 - t0).total_seconds() != 4 * 3600:
            huecos += 1
    print(f"[datos] {symbol}: velas totales: {len(serie_local)} | huecos de continuidad (!=4h): {huecos}")
    return serie_local

# Serie de la moneda activa (para evaluar/fills/compresion) y serie de BTC
# (SIEMPRE cargada aparte -- gestor_correlacion.obtener_fase_btc() consulta la
# fase macro de BTC real para CUALQUIER francotirador ALCISTA, incluido BTC
# mismo, asi que el gate no se puede simular sin datos reales de BTC).
serie = _cargar_serie(SYMBOL, BACKUP_CSV)
closes_f = [float(v[4]) for v in serie]

if SYMBOL == "BTCUSDT":
    serie_btc = serie
else:
    BACKUP_CSV_BTC = os.path.expanduser("~/bot-padre-v3-backup/data/historico_4h/BTCUSDT_4h.csv")
    serie_btc = _cargar_serie("BTCUSDT", BACKUP_CSV_BTC)

SERIES = {SYMBOL: serie, "BTCUSDT": serie_btc}
TS_LISTAS = {sym: [v[0] for v in s] for sym, s in SERIES.items()}

# Los timestamps de la serie son OPEN-TIME de Binance (k[0]). Arrancar con
# "v[0] >= FECHA_INICIO_ANALISIS" excluye la vela que ABRIO 4h antes de la
# fecha de inicio pero CIERRA justo en ese instante -- esa vela es la que
# cuenta como "la primera señal del año" en los reportes de referencia
# (labeling por cierre, no por apertura). Confirmado en BNB: la vela
# 2025-12-31 20:00 (close $869.16, RSI 62.8) es exactamente el primer trade
# documentado como "2026-01-01 00:00" en reports/2026-08-16_trades-reales-
# simulados-bnb-2026.md -- sin este ajuste, esa vela (y su señal) se pierde.
from datetime import timedelta as _timedelta
_inicio_dt = datetime.strptime(FECHA_INICIO_ANALISIS, "%Y-%m-%d %H:%M:%S")
_inicio_ajustado = (_inicio_dt - _timedelta(hours=4)).strftime("%Y-%m-%d %H:%M:%S")
idx_ini = next(i for i, v in enumerate(serie) if v[0] >= _inicio_ajustado)
idx_fin = len(serie) - 1
if serie[-1][0] > FECHA_FIN_ANALISIS:
    idx_fin = next(i for i, v in enumerate(serie) if v[0] > FECHA_FIN_ANALISIS) - 1
print(f"[datos] {SYMBOL}: ventana de analisis: {serie[idx_ini][0]} -> {serie[idx_fin][0]}")

RELOJ = {"i": idx_ini, "ahora": None}

def _calcular_ema(cierres, periodo):
    if len(cierres) < periodo:
        return None
    k = 2 / (periodo + 1)
    ema = sum(cierres[:periodo]) / periodo
    for precio in cierres[periodo:]:
        ema = precio * k + ema * (1 - k)
    return ema

# =========================================================
# 2) SANDBOX -- modulos falsos en sys.modules ANTES de cualquier import real
# =========================================================
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

# =========================================================
# 3) urlopen falso (unico punto de red durante la simulacion) -- sirve
#    velas historicas reales ya cargadas, ruteando por SYMBOL de la query
#    (necesario porque gestor_correlacion pide velas de BTCUSDT aparte de
#    las de la moneda activa, para el gate de fase macro)
# =========================================================
import bisect

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
    sym = qs.get("symbol", [SYMBOL])[0]
    if sym not in SERIES:
        raise RuntimeError(f"Symbol no soportado en el sandbox: {sym}")
    serie_sym = SERIES[sym]
    ts_lista  = TS_LISTAS[sym]
    ahora_str = RELOJ["ahora"].strftime("%Y-%m-%d %H:%M:%S")
    idx = bisect.bisect_right(ts_lista, ahora_str) - 1
    if idx < 0:
        idx = 0
    start = max(0, idx - limit + 1)
    window = serie_sym[start: idx + 1]
    if len(window) < limit:
        window = ([window[0]] * (limit - len(window)) + window) if window else [serie_sym[0]] * limit
    klines = [[0, o, h, l, c, v, 0, "0", 0, "0", "0", "0"] for (_, o, h, l, c, v) in window]
    return FakeResponse(json.dumps(klines).encode())

urllib.request.urlopen = fake_urlopen  # a partir de aca, sandboxeado

# =========================================================
# 4) Importar modulos REALES (ya con todo sandboxeado)
# =========================================================
import filtro_horario
import filtro_eventos

# APROXIMACION -- igual que los reportes de referencia (2026-08-16), NO se deja
# el gate de eventos macro como bloqueante real. Motivo (confirmado empiricamente
# en BNB): esta simulacion evalua UNA VEZ por vela, en el open-time exacto. Los
# 5 eventos fijos (13:30/14:00/14:30/18:00/20:00 UTC) caen justo sobre el
# open-time de una de las 6 velas 4h del dia (la de 20:00), asi que esa vela
# queda bloqueada el 100% de las veces en esta simulacion -- en produccion el
# bot reintenta cada 4 min durante los 240 min de esa vela, asi que el bloqueo
# real dura ~30 min de 240, casi nunca determina el resultado. Los reportes de
# referencia ya declaran esto ("Se aproximo como 'nunca bloquea toda la
# vela'"); sin este fix, esta simulacion pierde sistematicamente el primer
# trade documentado de BNB (vela 2025-12-31 20:00, RSI 62.8, hubiera sido TP
# +8.32%) por chocar exactamente con la ventana de las 20:00 UTC.
filtro_eventos.puede_operar_eventos = lambda: True

import termometro
import limitador_diario
import detector_multitimeframe
import filtro_calidad
import utils
import config_cartera  # solo ETH lo usa realmente en produccion; harmless para el resto
import gestor_correlacion  # REAL -- a diferencia de SOL LATERAL, para ALCISTA
                            # el gate de fase macro BTC (dentro de puede_operar)
                            # SI bloquea entradas reales; no se puede fakear a True.

FILTRO_COMPRESION_ACTIVO = {"on": False}
_real_puede_operar = gestor_correlacion.puede_operar

# GATE DE FASE POR DIRECTOR -- director_<moneda>.py SOLO llama a evaluar() del
# francotirador ALCISTA cuando detectar_fase(symbol) ya es ALCISTA (ver
# director_btc.py / director_sol.py: "if fase == 'ALCISTA': evaluar_alcista()").
# Esto es orquestacion FUERA del francotirador, no un gate interno de evaluar()
# -- omitirlo (llamar evaluar() en cada vela sin condicion, como hacia el
# script de SOL) deja pasar señales que en produccion nunca se habrian evaluado.
# Para SOL LATERAL esto no importaba (RSI 43-57 ya correlaciona con LATERAL),
# pero para BTC ALCISTA duplico el conteo de trades (16 vs 8 documentados) hasta
# agregar este gate. Se engancha aca (justo antes de correlacion) porque es el
# unico punto disponible sin reimplementar evaluar() ni tocar el francotirador.
def _fase_symbol_actual():
    idx = RELOJ["i"]
    ventana = closes_f[max(0, idx - 209): idx + 1]
    return utils.detectar_fase(ventana, symbol=SYMBOL)

def _puede_operar_con_compresion(accion_nueva, symbol_nuevo):
    if _fase_symbol_actual() != "ALCISTA":
        return False
    if not _real_puede_operar(accion_nueva, symbol_nuevo):
        return False
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

gestor_correlacion.puede_operar = _puede_operar_con_compresion

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

TMPDIR = tempfile.mkdtemp(prefix=f"{MONEDA_ARG.lower()}_alcista_evaluar_literal_")
filtro_calidad.LOG_RECHAZOS = os.path.join(TMPDIR, "log_rechazos_fake.csv")
BILLETERA_FAKE = os.path.join(TMPDIR, "billetera_fake.json")
with open(BILLETERA_FAKE, "w") as f:
    json.dump({"USDT": 100000.0, "capital_inicial": 100000.0}, f)
fr.BILLETERA = BILLETERA_FAKE

print(f"[sandbox] {SYMBOL}: archivos temporales en {TMPDIR} (nunca se toca ~/bot-padre-v2)")

# =========================================================
# 5) Correr evaluar() literal, vela a vela
# =========================================================
def correr(con_filtro, label):
    FILTRO_COMPRESION_ACTIVO["on"] = con_filtro
    aud = os.path.join(TMPDIR, f"auditoria_{'con_filtro' if con_filtro else 'baseline'}.csv")
    with open(aud, "w") as f:
        f.write("timestamp,accion,symbol,precio,rsi,estado,monto,qty\n")
    fr.AUDITORIA = aud
    fr.AUDITORIA_LOCK = aud + ".lock"
    limitador_diario.AUDITORIA = aud
    gestor_correlacion.AUDITORIA = aud
    _fake_db_store["estado_diario"] = None
    CIERRES_LOG.clear()
    APERTURAS_LOG.clear()

    i = idx_ini
    while i <= idx_fin:
        RELOJ["i"] = i
        RELOJ["ahora"] = datetime.strptime(serie[i][0], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        fr.evaluar()
        i += 1

    print(f"\n=== {SYMBOL} {label} completado. Auditoria en: {aud} ===")
    return aud, list(APERTURAS_LOG), list(CIERRES_LOG)

def resumen_de_auditoria(path, nombre, cierres_log):
    with open(path) as f:
        lineas = f.readlines()[1:]
    filas = [l.strip().split(",") for l in lineas if len(l.strip().split(",")) >= 6]
    estados = {}
    for p in filas:
        estados[p[5]] = estados.get(p[5], 0) + 1
    print(f"\n{SYMBOL} {nombre}: {estados}")

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
    return estados, trades

if __name__ == "__main__":
    aud_base, ap_base, ci_base = correr(False, "BASELINE (evaluar() literal, sin filtro)")
    aud_filtro, ap_filtro, ci_filtro = correr(True, f"CON FILTRO (compresion EMA20/100 <{COMPRESION_MAX_PCT}%)")

    print(f"\n\n########## RESUMEN {SYMBOL} (desde auditoria fake, escrita por el codigo REAL) ##########")
    _, trades_base = resumen_de_auditoria(aud_base, "BASELINE", ci_base)
    _, trades_filtro = resumen_de_auditoria(aud_filtro, "CON FILTRO", ci_filtro)

    os.makedirs(RAW_DIR, exist_ok=True)
    fecha = datetime.now().strftime("%Y-%m-%d")
    for nombre, trades in [("baseline", trades_base), ("con_filtro", trades_filtro)]:
        ruta = os.path.join(RAW_DIR, f"{MONEDA_ARG.lower()}_alcista_evaluar_literal_{nombre}_{fecha}.json")
        with open(ruta, "w") as f:
            json.dump(trades, f, indent=2)
        print(f"[output] {ruta}")
