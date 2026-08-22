"""
Extension a 5.9 anios (2020-09-01 -> 2026-08-21) de la auditoria de
`filtro_eventos.puede_operar_eventos` para SOL LATERAL. Cierra la laguna
documentada en reports/2026-08-21_resumen_sesiones_ariel_claude.md (gate
#6, laguna #3 de la seccion 4): el hallazgo corto (n=104/621 bloqueadas,
16.7%, WR bloqueadas 45.4% vs reales 50.0%, -4.6pp, solo 8.5 meses de 2026)
nunca se extendio -- a diferencia de horario/calidad/estadistico/
multitimeframe en la misma serie, todos ya extendidos.

Metodologia: copia exacta del patron ya usado en
sistema_c/audit_mtf_sol_lateral_extendido.py (que a su vez copia el sandbox
de sistema_c/resim_evaluar_literal_sol_lateral.py), cambiando el punto de
instrumentacion de `detector_multitimeframe.confirmar_tendencia_multitf` a
`filtro_eventos.puede_operar_eventos`. NO reimplementa el gate a mano: se
llama a `francotirador_lateral_sol.evaluar()` LITERAL vela a vela, y para
las senales bloqueadas se simula el cierre con `sol.revisar_cierres()`
LITERAL tambien.

`puede_operar_eventos()` no depende de RSI/precio -- es un gate de reloj
puro (mismo mecanismo que filtro_horario, ver HORAS_RIESGO_MACRO en
filtro_eventos.py). Por eso, igual que en el script de multitimeframe,
"raw_signal" se recalcula de forma independiente (RSI 43-57 + fase LATERAL
via utils.detectar_fase) en cada vela, sin condicionar al orden real de los
6 gates anteriores -- mismo criterio ya usado para el numero "n=621" de la
ventana corta.

Consulta de solo lectura. No modifica NADA en produccion.

Uso:
    python3 sistema_c/audit_eventos_sol_lateral_extendido.py
"""
import sys, os, json, csv, tempfile, types, statistics, random
import urllib.parse, urllib.request
from datetime import datetime, timezone

BOT_DIR = os.path.expanduser("~/bot-padre-v2")
sys.path.insert(0, BOT_DIR)

SYMBOL = "SOLUSDT"
FECHA_INICIO_ANALISIS = "2020-09-01 00:00:00"
FECHA_FIN_ANALISIS    = "2026-08-21 23:59:59"
BACKUP_CSV = os.path.expanduser("~/bot-padre-v2/data/historico_4h/SOLUSDT_4h.csv")
FECHA_DESDE_FALLBACK = datetime(2020, 9, 1, tzinfo=timezone.utc)

RAW_DIR = os.path.expanduser("~/bot-padre-v2/reports/raw")
MAX_VELAS_ISOLADO = 400

# =========================================================
# 1) Datos historicos reales
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

# =========================================================
# 2) SANDBOX -- identico al script de referencia
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

fake_correlacion = types.ModuleType("gestor_correlacion")
fake_correlacion.puede_operar = lambda accion_nueva, symbol_nuevo: True
sys.modules["gestor_correlacion"] = fake_correlacion

# =========================================================
# 3) urlopen falso
# =========================================================
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

# =========================================================
# 4) Importar modulos REALES
# =========================================================
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

TMPDIR = tempfile.mkdtemp(prefix="sol_lateral_eventos_extendido_")
filtro_calidad.LOG_RECHAZOS = os.path.join(TMPDIR, "log_rechazos_fake.csv")
BILLETERA_FAKE = os.path.join(TMPDIR, "billetera_fake.json")
with open(BILLETERA_FAKE, "w") as f:
    json.dump({"USDT": 100000.0, "capital_inicial": 100000.0}, f)
sol.BILLETERA = BILLETERA_FAKE
print(f"[sandbox] archivos temporales en {TMPDIR} (nunca se toca ~/bot-padre-v2)")

# =========================================================
# 5) Instrumentar puede_operar_eventos -- recalcula raw_signal
#    (RSI 43-57 + fase LATERAL) de forma independiente, sin tocar
#    la logica real del gate
# =========================================================
RSI_MIN, RSI_MAX = sol.RSI_MIN, sol.RSI_MAX  # 43, 57
_real_puede_operar_eventos = filtro_eventos.puede_operar_eventos
EVENTOS_LOG = []

def _puede_operar_eventos_instrumentado():
    idx = RELOJ["i"]
    ventana210 = closes_f[max(0, idx - 209): idx + 1]
    if len(ventana210) < 210:
        ventana210 = ([ventana210[0]] * (210 - len(ventana210)) + ventana210) if ventana210 else [closes_f[0]] * 210
    rsi = utils.calcular_rsi(ventana210)
    fase_director = utils.detectar_fase(ventana210, symbol="SOLUSDT")
    raw_signal = (rsi is not None) and (RSI_MIN <= rsi <= RSI_MAX) and (fase_director == "LATERAL")
    resultado = _real_puede_operar_eventos()
    EVENTOS_LOG.append({"idx": idx, "ts": serie[idx][0], "resultado": resultado,
                         "raw_signal": raw_signal, "rsi": rsi})
    return resultado

filtro_eventos.puede_operar_eventos = _puede_operar_eventos_instrumentado
sol.puede_operar_eventos = _puede_operar_eventos_instrumentado  # 'from X import Y' ya bindeo el nombre

# =========================================================
# 6) Correr evaluar() literal, vela a vela (baseline)
# =========================================================
def correr_baseline():
    aud = os.path.join(TMPDIR, "auditoria_baseline.csv")
    with open(aud, "w") as f:
        f.write("timestamp,accion,symbol,precio,rsi,estado,monto,qty\n")
    sol.AUDITORIA = aud
    sol.AUDITORIA_LOCK = aud + ".lock"
    limitador_diario.AUDITORIA = aud
    _fake_db_store["estado_diario"] = None
    CIERRES_LOG.clear()
    APERTURAS_LOG.clear()
    EVENTOS_LOG.clear()

    i = idx_ini
    total = idx_fin - idx_ini + 1
    while i <= idx_fin:
        RELOJ["i"] = i
        RELOJ["ahora"] = datetime.strptime(serie[i][0], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        sol.evaluar()
        if (i - idx_ini) % 3000 == 0:
            print(f"  [baseline] {i - idx_ini}/{total}")
        i += 1
    print(f"\n=== BASELINE completado. Auditoria en: {aud} ===")
    return aud

def resumen_de_auditoria(path):
    with open(path) as f:
        lineas = f.readlines()[1:]
    filas = [l.strip().split(",") for l in lineas if len(l.strip().split(",")) >= 6]
    filas_resueltas = [p for p in filas if p[5] in ("TP", "SL", "TRAILING_SL", "BE")]
    trades = []
    for p, c in zip(filas_resueltas, CIERRES_LOG):
        ts_entrada = p[0]
        idx_entrada = next(i for i, v in enumerate(serie) if v[0] == ts_entrada)
        trades.append({"ts_entrada": ts_entrada, "estado": p[5], "cambio_pct": c["cambio_pct"],
                        "velas": c["idx"] - idx_entrada})
    return trades

# =========================================================
# 7) Simular trade aislado (revisar_cierres() LITERAL)
# =========================================================
def simular_trade_aislado(idx_entrada, rsi_entrada):
    ts_entrada = serie[idx_entrada][0]
    precio_entrada = closes_f[idx_entrada]
    aud = os.path.join(TMPDIR, f"aislado_{idx_entrada}.csv")
    with open(aud, "w") as f:
        f.write("timestamp,accion,symbol,precio,rsi,estado,monto,qty\n")
        f.write(f"{ts_entrada},LATERAL,{SYMBOL},{precio_entrada},{rsi_entrada},ABIERTA,5.0,\n")
    sol.AUDITORIA = aud
    sol.AUDITORIA_LOCK = aud + ".lock"

    i = idx_entrada + 1
    tope = min(idx_fin, idx_entrada + MAX_VELAS_ISOLADO)
    while i <= tope:
        RELOJ["i"] = i
        RELOJ["ahora"] = datetime.strptime(serie[i][0], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        precio_actual = closes_f[i]
        sol.revisar_cierres(precio_actual, evaluar_tp=True)
        with open(aud) as f:
            fila = f.readlines()[1].strip().split(",")
        if fila[5] != "ABIERTA":
            cambio = round((closes_f[i] - precio_entrada) / precio_entrada * 100, 3)
            return {"idx_entrada": idx_entrada, "ts_entrada": ts_entrada, "estado": fila[5],
                    "cambio_pct": cambio, "velas": i - idx_entrada}
        i += 1
    cambio = round((closes_f[tope] - precio_entrada) / precio_entrada * 100, 3)
    return {"idx_entrada": idx_entrada, "ts_entrada": ts_entrada, "estado": "VIGENTE",
            "cambio_pct": cambio, "velas": tope - idx_entrada}

# =========================================================
# 8) Bootstrap simple del delta WR (bloqueadas - reales)
# =========================================================
def bootstrap_delta_wr(muestra_bloqueadas_bin, muestra_reales_bin, n_iter=10000, seed=42):
    rng = random.Random(seed)
    deltas = []
    nb, nr = len(muestra_bloqueadas_bin), len(muestra_reales_bin)
    if nb < 5 or nr < 5:
        return None
    for _ in range(n_iter):
        rb = [muestra_bloqueadas_bin[rng.randrange(nb)] for _ in range(nb)]
        rr = [muestra_reales_bin[rng.randrange(nr)] for _ in range(nr)]
        deltas.append(sum(rb) / nb - sum(rr) / nr)
    deltas.sort()
    lo = deltas[int(0.025 * n_iter)]
    hi = deltas[int(0.975 * n_iter) - 1]
    p_mayor_cero = sum(1 for d in deltas if d > 0) / n_iter
    return {"ic95_lo": round(lo * 100, 2), "ic95_hi": round(hi * 100, 2), "p_mayor_cero": round(p_mayor_cero * 100, 1)}

# =========================================================
# MAIN
# =========================================================
if __name__ == "__main__":
    aud_base = correr_baseline()
    trades_reales = resumen_de_auditoria(aud_base)
    tp_reales = [t for t in trades_reales if t["estado"] == "TP"]
    wr_reales = round(len(tp_reales) / len(trades_reales) * 100, 1) if trades_reales else None
    print(f"\n[BASELINE] trades reales resueltos: n={len(trades_reales)} TP={len(tp_reales)} WR={wr_reales}%")

    # Verificacion de metodo: subconjunto 2026-01-01..2026-08-17 debe acercarse
    # al funnel original (n=38, WR~50-51%) -- referencia laxa, no exacta, porque
    # esta corrida es continua (arrastra estado desde 2020) y el funnel original
    # arrancaba en limpio el 1-ene (ver hallazgo ya documentado en el reporte).
    trades_2026 = [t for t in trades_reales if "2026-01-01" <= t["ts_entrada"] <= "2026-08-17 23:59:59"]
    tp_2026 = [t for t in trades_2026 if t["estado"] == "TP"]
    wr_2026 = round(len(tp_2026) / len(trades_2026) * 100, 1) if trades_2026 else None
    print(f"[VERIFICACION] subconjunto 2026-01-01..08-17: n={len(trades_2026)} TP={len(tp_2026)} WR={wr_2026}% "
          f"(referencia laxa, corrida continua vs funnel original aislado)")

    bloqueadas_raw = [m for m in EVENTOS_LOG if m["raw_signal"] and not m["resultado"]]
    print(f"\n[EVENTOS] llamadas totales: {len(EVENTOS_LOG)} | raw_signal=True: {sum(1 for m in EVENTOS_LOG if m['raw_signal'])} "
          f"| bloqueadas (raw_signal=True, resultado=False): {len(bloqueadas_raw)}")

    print("\n[EVENTOS] simulando trades aislados para cada senal bloqueada (revisar_cierres() literal)...")
    resultados_aislados = []
    for j, m in enumerate(bloqueadas_raw):
        r = simular_trade_aislado(m["idx"], m["rsi"])
        resultados_aislados.append(r)
        if (j + 1) % 20 == 0:
            print(f"  ... {j+1}/{len(bloqueadas_raw)}")

    resueltas = [r for r in resultados_aislados if r["estado"] != "VIGENTE"]
    tp_bloq = [r for r in resueltas if r["estado"] == "TP"]
    wr_bloq = round(len(tp_bloq) / len(resueltas) * 100, 1) if resueltas else None
    pnl_bloq = round(sum(r["cambio_pct"] for r in resueltas), 2) if resueltas else None
    print(f"\n[RESULTADO EXTENDIDO 5.9 anios] bloqueadas: n={len(resultados_aislados)} resueltas={len(resueltas)} "
          f"TP={len(tp_bloq)} WR={wr_bloq}% PnL_simple={pnl_bloq}%")

    # Desglose por hora UTC de la vela bloqueada (para confirmar/descartar el
    # patron "solo vela 20:00-00:00 UTC" ya documentado en la ventana corta)
    print("\n[DESGLOSE POR HORA UTC DE LA VELA BLOQUEADA]")
    por_hora = {}
    for r in resultados_aislados:
        hora = r["ts_entrada"][11:13]
        por_hora.setdefault(hora, []).append(r)
    for hora in sorted(por_hora):
        print(f"  {hora}:00 UTC -> n={len(por_hora[hora])}")

    # Desglose por sub-periodo
    tramos = [("2020-09-01", "2022-08-31"), ("2022-09-01", "2024-08-31"), ("2024-09-01", "2026-08-21")]
    print("\n[DESGLOSE POR SUB-PERIODO]")
    for ini, fin in tramos:
        sub_bloq = [r for r in resultados_aislados if ini <= r["ts_entrada"] <= fin and r["estado"] != "VIGENTE"]
        sub_real = [t for t in trades_reales if ini <= t["ts_entrada"] <= fin]
        tp_b = [r for r in sub_bloq if r["estado"] == "TP"]
        tp_r = [t for t in sub_real if t["estado"] == "TP"]
        wr_b = round(len(tp_b) / len(sub_bloq) * 100, 1) if sub_bloq else None
        wr_r = round(len(tp_r) / len(sub_real) * 100, 1) if sub_real else None
        print(f"  {ini}..{fin}: bloqueadas n={len(sub_bloq)} WR={wr_b}% | reales n={len(sub_real)} WR={wr_r}%")

    # Desglose por ano
    print("\n[DESGLOSE POR ANO]")
    for anio in range(2020, 2027):
        sub_bloq = [r for r in resultados_aislados if r["ts_entrada"].startswith(str(anio)) and r["estado"] != "VIGENTE"]
        tp_b = [r for r in sub_bloq if r["estado"] == "TP"]
        wr_b = round(len(tp_b) / len(sub_bloq) * 100, 1) if sub_bloq else None
        if sub_bloq:
            print(f"  {anio}: n={len(sub_bloq)} TP={len(tp_b)} WR={wr_b}%")

    # Bootstrap
    tp_reales_bin = [1 if t["estado"] == "TP" else 0 for t in trades_reales]
    tp_bloq_bin = [1 if r["estado"] == "TP" else 0 for r in resueltas]
    boot = bootstrap_delta_wr(tp_bloq_bin, tp_reales_bin)
    print(f"\n[BOOTSTRAP] delta WR (bloqueadas - reales), IC95%: {boot}")

    os.makedirs(RAW_DIR, exist_ok=True)
    fecha = datetime.now().strftime("%Y-%m-%d")
    with open(os.path.join(RAW_DIR, f"sol_lateral_eventos_extendido_{fecha}.json"), "w") as f:
        json.dump({
            "trades_reales": trades_reales,
            "bloqueadas_aisladas": resultados_aislados,
            "verificacion_2026": {"n": len(trades_2026), "tp": len(tp_2026), "wr": wr_2026},
            "bootstrap": boot,
        }, f, indent=2)
    print(f"\n[OK] raw guardado en reports/raw/sol_lateral_eventos_extendido_{fecha}.json")
    print("[DONE]")
