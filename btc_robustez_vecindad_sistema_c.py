"""
btc_robustez_vecindad_sistema_c.py
BTC ALCISTA — Robustez de vecindad Sistema C (RSI 55-60 + SOBRE EMA)
Prueba: EMA100d / EMA150d / EMA200d / EMA250d
INVESTIGACION PURA — 0 archivos de producción modificados.
"""
import json, os, random, urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta

# ── Configuración fija (NO cambiar) ──────────────────────────────────────────
SIMBOLO       = "BTCUSDT"
CAPITAL_INIT  = 20.0
MONTO_TRADE   = 5.0
COMISION      = 0.001          # 0.10% por lado
SL_PCT        = 0.05
TP_PCT        = 0.06
RSI_MIN       = 55.0
RSI_MAX       = 60.0           # Sistema C: solo RSI 55–60
FECHA_WU_4H   = "2020-10-01"  # warmup RSI
FECHA_WU_D    = "2019-06-01"  # warmup EMA250 (250 días antes de 2020-01-01 para tener buffer)
TRAIN_START   = "2021-01-01"
TRAIN_END     = "2023-12-31"
VAL_START     = "2024-01-01"
VAL_END       = "2025-12-31"
EMAs          = [100, 150, 200, 250]
N_BOOTSTRAP   = 10000
REPORT        = os.path.expanduser(
    "~/bot-padre-v2/reports/2026-08-14_btc-alcista-robustez-vecindad-sistema-c.md"
)

# ── Descarga ──────────────────────────────────────────────────────────────────
def _ts_ms(f):
    return int(datetime.strptime(f, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp()*1000)

def fetch_velas(symbol, intervalo, desde_ms):
    velas = []; inicio = desde_ms
    while True:
        params = urllib.parse.urlencode({"symbol":symbol,"interval":intervalo,
                                          "startTime":inicio,"limit":1000})
        url = f"https://api.binance.com/api/v3/klines?{params}"
        with urllib.request.urlopen(url, timeout=30) as r:
            batch = json.loads(r.read().decode())
        if not batch: break
        velas.extend(batch)
        if len(batch) < 1000: break
        inicio = batch[-1][0] + 1
    return velas

# ── Cálculo de EMA (genérico para N períodos) ─────────────────────────────────
def construir_ema_map(velas_d, periodo):
    """
    Devuelve {date_str -> ema_value} para todos los días con suficiente warmup.
    Usa regla anti-lookahead: la entrada a las HH:MM del día D usa la EMA del día D-1.
    """
    k       = 2 / (periodo + 1)
    cierres = [float(v[4]) for v in velas_d]
    fechas  = [datetime.fromtimestamp(int(v[0])/1000, tz=timezone.utc).strftime("%Y-%m-%d")
               for v in velas_d]
    ema = [None] * len(cierres)
    if len(cierres) >= periodo:
        ema[periodo-1] = sum(cierres[:periodo]) / periodo
        for i in range(periodo, len(cierres)):
            ema[i] = cierres[i] * k + ema[i-1] * (1 - k)
    ema_map = {}
    for i, f in enumerate(fechas):
        if ema[i] is not None:
            ema_map[f] = ema[i]
    return ema_map

def ema_entrada(entry_ts, ema_map):
    """EMA del último día completamente cerrado antes de la entrada 4H."""
    for d in range(1, 6):
        f = (entry_ts - timedelta(days=d)).strftime("%Y-%m-%d")
        if f in ema_map:
            return ema_map[f]
    return None

# ── RSI simple (idéntico a backtest_motor.py) ─────────────────────────────────
def rsi_simple(v, periodo=14):
    if len(v) < periodo + 1: return None
    g, p = [], []
    for i in range(1, periodo + 1):
        d = v[i] - v[i-1]
        g.append(d if d > 0 else 0)
        p.append(-d if d < 0 else 0)
    ag, ap = sum(g)/periodo, sum(p)/periodo
    if ap == 0: return 100.0
    return round(100 - (100/(1 + ag/ap)), 2)

# ── Simulación ────────────────────────────────────────────────────────────────
def simular(velas_4h, ema_map):
    """
    Simula BTC ALCISTA con gate 'precio > EMA(n)' al momento de entrada.
    Retorna lista de trades con todos los campos necesarios.
    """
    cierres = [float(v[4]) for v in velas_4h]
    ts_list = [int(v[0]) for v in velas_4h]
    INICIO_MS = _ts_ms(TRAIN_START)
    FIN_MS    = _ts_ms(VAL_END) + 86400000

    trades = []
    en_pos = False
    e_precio = e_rsi = sl_p = tp_p = 0.0
    e_ts = None; e_ema = None

    for i in range(60, len(cierres)):
        ventana = cierres[max(0, i-60):i]
        r = rsi_simple(ventana[-15:])
        if r is None: continue
        precio    = cierres[i]
        ts_ms_val = ts_list[i]
        ts_dt     = datetime.fromtimestamp(ts_ms_val/1000, tz=timezone.utc)

        if en_pos:
            res = None
            if precio <= sl_p: res = "SL"
            elif precio >= tp_p: res = "TP"
            if res:
                bruto = MONTO_TRADE*TP_PCT if res == "TP" else -MONTO_TRADE*SL_PCT
                pl = round(bruto - MONTO_TRADE*COMISION*2, 4)
                anio = str(e_ts.year)
                periodo_str = ("TRAIN" if ts_ms_val <= _ts_ms(TRAIN_END)+86400000 else "VAL")
                trades.append({
                    "ts":      e_ts.strftime("%Y-%m-%d %H:%M"),
                    "anio":    anio,
                    "periodo": periodo_str,
                    "rsi":     e_rsi,
                    "precio":  round(e_precio, 2),
                    "ema_val": round(e_ema, 2) if e_ema else None,
                    "dist":    round((e_precio - e_ema)/e_ema*100, 2) if e_ema else None,
                    "res":     res,
                    "pl":      pl,
                })
                en_pos = False

        if (not en_pos and INICIO_MS <= ts_ms_val < FIN_MS and RSI_MIN <= r < RSI_MAX):
            ema_val = ema_entrada(ts_dt, ema_map)
            if ema_val is not None and precio > ema_val:  # gate: BTC SOBRE EMA
                en_pos = True; e_precio = precio; e_ts = ts_dt; e_rsi = r
                e_ema  = ema_val
                sl_p   = round(e_precio * (1 - SL_PCT), 4)
                tp_p   = round(e_precio * (1 + TP_PCT), 4)

    return trades

# ── Métricas ──────────────────────────────────────────────────────────────────
def metricas(tlist):
    n = len(tlist)
    if n == 0:
        return dict(n=0,tp=0,sl=0,wr=0.0,pf=0.0,exp=0.0,pl=0.0,dd=0.0,
                    racha_sl=0,racha_tp=0,racha_sl_dates="—",racha_tp_dates="—",
                    peor_seq=[])
    tps  = [t for t in tlist if t["res"]=="TP"]
    sls  = [t for t in tlist if t["res"]=="SL"]
    tg   = sum(t["pl"] for t in tps)
    tl   = abs(sum(t["pl"] for t in sls))
    pf   = round(tg/tl, 3) if tl > 0 else float("inf")
    pl   = round(sum(t["pl"] for t in tlist), 4)
    wr   = round(len(tps)/n*100, 1)
    exp  = round(pl/n, 4)

    # Drawdown sobre curva de equity (orden cronológico)
    sorted_t = sorted(tlist, key=lambda x: x["ts"])
    cap = CAPITAL_INIT; mxc = cap; mxdd = 0.0
    for t in sorted_t:
        cap += t["pl"]; mxc = max(mxc, cap)
        dd = (mxc - cap)/mxc*100; mxdd = max(mxdd, dd)

    # Rachas SL
    max_sl = 0; cur_sl = 0
    sl_start = sl_end = ""
    cur_sl_start = ""
    for t in sorted_t:
        if t["res"] == "SL":
            if cur_sl == 0: cur_sl_start = t["ts"][:10]
            cur_sl += 1
            if cur_sl > max_sl:
                max_sl = cur_sl
                sl_start = cur_sl_start
                sl_end   = t["ts"][:10]
        else:
            cur_sl = 0

    # Rachas TP
    max_tp = 0; cur_tp = 0
    tp_start = tp_end = ""
    cur_tp_start = ""
    for t in sorted_t:
        if t["res"] == "TP":
            if cur_tp == 0: cur_tp_start = t["ts"][:10]
            cur_tp += 1
            if cur_tp > max_tp:
                max_tp = cur_tp
                tp_start = cur_tp_start
                tp_end   = t["ts"][:10]
        else:
            cur_tp = 0

    # Peor secuencia de 5 trades consecutivos
    pls = [t["pl"] for t in sorted_t]
    peor = [round(sum(pls[i:i+5]),4) for i in range(max(0,len(pls)-4))] if len(pls)>=5 else [round(sum(pls),4)]
    peor_sum = min(peor) if peor else 0.0

    sl_dates = f"{sl_start} → {sl_end}" if sl_start else "—"
    tp_dates = f"{tp_start} → {tp_end}" if tp_start else "—"

    return dict(n=n, tp=len(tps), sl=len(sls), wr=wr, pf=pf, exp=exp, pl=pl,
                dd=round(mxdd,1), racha_sl=max_sl, racha_tp=max_tp,
                racha_sl_dates=sl_dates, racha_tp_dates=tp_dates,
                peor_5=peor_sum)

# ── Bootstrap ─────────────────────────────────────────────────────────────────
def bootstrap_diff_exp(trades_a, trades_b, n_iter=N_BOOTSTRAP, seed=42):
    """
    IC95% de la diferencia de expectancy: E[A] - E[B].
    Resampleo independiente con reemplazo.
    """
    random.seed(seed)
    if not trades_a or not trades_b:
        return dict(obs=None, ic95=(None,None), p_pos=None)
    pls_a = [t["pl"] for t in trades_a]
    pls_b = [t["pl"] for t in trades_b]
    obs   = round(sum(pls_a)/len(pls_a) - sum(pls_b)/len(pls_b), 4)
    diffs = []
    na, nb = len(pls_a), len(pls_b)
    for _ in range(n_iter):
        sa = random.choices(pls_a, k=na)
        sb = random.choices(pls_b, k=nb)
        diffs.append(sum(sa)/na - sum(sb)/nb)
    diffs.sort()
    lo = diffs[int(n_iter*0.025)]
    hi = diffs[int(n_iter*0.975)]
    p_pos = sum(1 for d in diffs if d > 0)/n_iter
    return dict(obs=round(obs,4), ic95=(round(lo,4), round(hi,4)), p_pos=round(p_pos,3))

# ── Helpers de formato ────────────────────────────────────────────────────────
def fpf(v): return f"{v:.3f}" if v != float("inf") else "∞"
def fpl(v): return f"+${v:.4f}" if v >= 0 else f"-${abs(v):.4f}"

def fila_tabla(m, label=""):
    if m['n'] == 0:
        return f"| {label} | 0 | — | — | — | — | — | — | — | — | — |"
    return (f"| {label} | {m['n']} | {m['tp']}/{m['sl']} | {m['wr']:.1f}% "
            f"| {fpf(m['pf'])} | {fpl(m['exp'])} | {fpl(m['pl'])} | {m['dd']:.1f}% "
            f"| {m['racha_sl']} | {m['racha_tp']} | {m['racha_sl_dates']} |")

def veredicto_wf(pf_train, pf_val, exp_val, n_val):
    """Veredicto basado en generalización OOS."""
    pfv = pf_val if pf_val != float("inf") else 999.0
    pft = pf_train if pf_train != float("inf") else 999.0
    if pfv >= 1.0 and exp_val > 0 and n_val >= 10:
        return "✅ PF>1 OOS"
    elif pfv >= 1.0 and exp_val > 0:
        return "⚠️ PF>1 (n<10)"
    else:
        return "❌ PF<1 OOS"

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("BTC ALCISTA — Robustez de vecindad Sistema C")
    print("EMAs: 100 / 150 / 200 / 250")
    print("=" * 60)
    print()

    print("[1/3] Descargando datos...")
    ahora_ms = int(datetime.now(timezone.utc).timestamp()*1000)
    velas_d  = fetch_velas(SIMBOLO, "1d", _ts_ms(FECHA_WU_D))
    velas_d  = [v for v in velas_d if int(v[6]) < ahora_ms]
    velas_4h = fetch_velas(SIMBOLO, "4h", _ts_ms(FECHA_WU_4H))
    velas_4h = [v for v in velas_4h if int(v[6]) < ahora_ms]
    print(f"      Velas diarias: {len(velas_d)} | Velas 4H: {len(velas_4h)}")

    print("[2/3] Calculando EMAs y simulando...")
    resultados = {}   # ema_periodo -> {"trades": [...], "ema_map": {...}}
    for n in EMAs:
        ema_map = construir_ema_map(velas_d, n)
        trades  = simular(velas_4h, ema_map)
        resultados[n] = {"trades": trades, "ema_map": ema_map}
        train = [t for t in trades if t["periodo"] == "TRAIN"]
        val   = [t for t in trades if t["periodo"] == "VAL"]
        mt = metricas(train); mv = metricas(val)
        print(f"      EMA{n:3d}: {len(trades):3d} trades | "
              f"Train PF {fpf(mt['pf'])} WR {mt['wr']:.0f}% | "
              f"Val   PF {fpf(mv['pf'])} WR {mv['wr']:.0f}%")

    print("[3/3] Bootstrap y reporte...")

    # Bootstrap: EMA200 vs cada otra EMA (en validación)
    trades_200_val = [t for t in resultados[200]["trades"] if t["periodo"] == "VAL"]
    bs_results = {}
    for n in [100, 150, 250]:
        trades_n_val = [t for t in resultados[n]["trades"] if t["periodo"] == "VAL"]
        bs_results[n] = bootstrap_diff_exp(trades_200_val, trades_n_val)

    # ── Generar reporte ───────────────────────────────────────────────────────
    lines = []; a = lines.append

    a("# BTC ALCISTA — Robustez de vecindad Sistema C")
    a("## RSI 55–60 + SOBRE EMA(n)d | Gates: EMA100 / EMA150 / EMA200 / EMA250")
    a("")
    a("**Fecha:** 2026-08-14  ")
    a("**Estado:** INVESTIGACIÓN PURA — 0 archivos de producción modificados")
    a("")
    a("**Sistema C (benchmark):** RSI 55–60 + BTC SOBRE EMA200d")
    a("**Pregunta:** ¿La ventaja del Sistema C existe en una zona amplia alrededor de EMA200?")
    a("¿O EMA200 es un pico aislado (sobreajuste)?")
    a("")
    a("---")
    a("")
    a("## 1. Metodología")
    a("")
    a("| Parámetro | Valor |")
    a("|-----------|-------|")
    a(f"| RSI range | {RSI_MIN}–{RSI_MAX} (exacto, no incluye RSI={RSI_MAX}) |")
    a(f"| SL | {SL_PCT*100:.1f}% |")
    a(f"| TP | {TP_PCT*100:.1f}% |")
    a(f"| Comisión | {COMISION*100:.2f}% por lado |")
    a(f"| Monto/trade | ${MONTO_TRADE} |")
    a(f"| Capital inicial | ${CAPITAL_INIT} |")
    a("| Intervalo | 4H BTCUSDT |")
    a("| Gate variante | EMA(n) diaria (n ∈ {100, 150, 200, 250}) |")
    a("| Anti-lookahead | EMA del día D−1 para entrada en cualquier hora de D |")
    a(f"| Train | {TRAIN_START} → {TRAIN_END} |")
    a(f"| Validación OOS | {VAL_START} → {VAL_END} |")
    a(f"| Bootstrap | {N_BOOTSTRAP:,} resamples, semilla 42 |")
    a("")
    a("**Anti-lookahead detallado:** Para cada entrada 4H, se busca el EMA del último día")
    a("DIARIO completamente cerrado. Si entrada es a las 08:00 del día D,")
    a("se usa EMA del día D−1 (el día D aún no ha cerrado).")
    a("")
    a("**Warmup de EMA250:** Datos diarios desde 2019-06-01 (>400 días de warmup antes")
    a("del primer trade 2021-01-01). Sin riesgo de periodo de inicialización insuficiente.")
    a("")
    a("---")
    a("")

    # ── TABLA COMPARATIVA PRINCIPAL ───────────────────────────────────────────
    a("## 2. Tabla comparativa principal")
    a("")
    a("| Gate | Train Trades | Train PF | Train WR | Train Exp | Val Trades | Val PF | Val WR | Val Exp | DD Val | OOS |")
    a("|------|-------------|----------|----------|-----------|------------|--------|--------|---------|--------|-----|")
    for n in EMAs:
        tr = [t for t in resultados[n]["trades"] if t["periodo"] == "TRAIN"]
        vl = [t for t in resultados[n]["trades"] if t["periodo"] == "VAL"]
        mt = metricas(tr); mv = metricas(vl)
        bench = " ← **benchmark**" if n == 200 else ""
        oos = veredicto_wf(mt['pf'], mv['pf'], mv['exp'], mv['n'])
        a(f"| **EMA{n}d**{bench} | {mt['n']} | {fpf(mt['pf'])} | {mt['wr']:.1f}% "
          f"| {fpl(mt['exp'])} | {mv['n']} | {fpf(mv['pf'])} | {mv['wr']:.1f}% "
          f"| {fpl(mv['exp'])} | {mv['dd']:.1f}% | {oos} |")
    a("")
    a("---")
    a("")

    # ── DETALLE POR EMA ───────────────────────────────────────────────────────
    for n in EMAs:
        trades = resultados[n]["trades"]
        tr = [t for t in trades if t["periodo"] == "TRAIN"]
        vl = [t for t in trades if t["periodo"] == "VAL"]
        mt = metricas(tr); mv = metricas(vl)
        anios = ["2021","2022","2023","2024","2025"]
        bench_mark = " ← Sistema C (benchmark)" if n == 200 else ""
        a(f"## 3.{EMAs.index(n)+1}. EMA{n}d{bench_mark}")
        a("")
        a("### Train (2021–2023)")
        a("")
        a("| Métrica | Valor |")
        a("|---------|-------|")
        a(f"| Trades | {mt['n']} |")
        a(f"| TP / SL | {mt['tp']} / {mt['sl']} |")
        a(f"| Win Rate | {mt['wr']:.1f}% |")
        a(f"| Profit Factor | {fpf(mt['pf'])} |")
        a(f"| Expectancy/trade | {fpl(mt['exp'])} |")
        a(f"| P/L acumulado | {fpl(mt['pl'])} |")
        a(f"| DD máximo | {mt['dd']:.1f}% |")
        a(f"| Racha máx SL | {mt['racha_sl']} ({mt['racha_sl_dates']}) |")
        a(f"| Racha máx TP | {mt['racha_tp']} ({mt['racha_tp_dates']}) |")
        a(f"| Peor ventana 5 trades | {fpl(mt['peor_5'])} |")
        a("")
        a("### Validación OOS (2024–2025)")
        a("")
        a("| Métrica | Valor |")
        a("|---------|-------|")
        a(f"| Trades | {mv['n']} |")
        a(f"| TP / SL | {mv['tp']} / {mv['sl']} |")
        a(f"| Win Rate | {mv['wr']:.1f}% |")
        a(f"| Profit Factor | {fpf(mv['pf'])} |")
        a(f"| Expectancy/trade | {fpl(mv['exp'])} |")
        a(f"| P/L acumulado | {fpl(mv['pl'])} |")
        a(f"| DD máximo | {mv['dd']:.1f}% |")
        a(f"| Racha máx SL | {mv['racha_sl']} ({mv['racha_sl_dates']}) |")
        a(f"| Racha máx TP | {mv['racha_tp']} ({mv['racha_tp_dates']}) |")
        a(f"| Peor ventana 5 trades | {fpl(mv['peor_5'])} |")
        a("")
        a("### Desglose anual")
        a("")
        a("| Año | Trades | WR | PF | Exp | P/L | Período |")
        a("|-----|--------|----|----|-----|-----|---------|")
        for anio in anios:
            g = [t for t in trades if t["anio"] == anio]
            m = metricas(g)
            per = "TRAIN" if anio <= "2023" else "VAL"
            if m['n'] == 0:
                a(f"| {anio} | 0 | — | — | — | — | {per} |")
            else:
                nota = " ⚠️" if m['n'] < 5 else ""
                a(f"| {anio} | {m['n']}{nota} | {m['wr']:.0f}% | {fpf(m['pf'])} "
                  f"| {fpl(m['exp'])} | {fpl(m['pl'])} | {per} |")
        a("")
        a("### Lista de trades OOS (2024–2025)")
        a("")
        val_sorted = sorted(vl, key=lambda x: x["ts"])
        if val_sorted:
            a("| # | Fecha | RSI | Precio | EMA | Dist% | Res | P/L |")
            a("|---|-------|-----|--------|-----|-------|-----|-----|")
            for idx, t in enumerate(val_sorted, 1):
                dist_s = f"{t['dist']:+.1f}%" if t['dist'] is not None else "—"
                a(f"| {idx} | {t['ts']} | {t['rsi']:.1f} | {t['precio']:,} "
                  f"| {t['ema_val']:,.0f} | {dist_s} | {t['res']} "
                  f"| {'+' if t['pl']>=0 else ''}{t['pl']:.2f} |")
        else:
            a("*Sin trades en validación.*")
        a("")
        a("---")
        a("")

    # ── ANÁLISIS ANUAL CRUZADO ────────────────────────────────────────────────
    a("## 4. Análisis anual cruzado (todos los gates)")
    a("")
    a("| Año | EMA100 PF/n | EMA150 PF/n | EMA200 PF/n | EMA250 PF/n |")
    a("|-----|-------------|-------------|-------------|-------------|")
    for anio in ["2021","2022","2023","2024","2025"]:
        celdas = []
        for n in EMAs:
            g = [t for t in resultados[n]["trades"] if t["anio"] == anio]
            m = metricas(g)
            if m['n'] == 0:
                celdas.append("— / 0")
            else:
                nota = "⚠️" if m['n'] < 5 else ""
                celdas.append(f"{nota}{fpf(m['pf'])} / {m['n']}")
        per = "TRAIN" if anio <= "2023" else "**VAL**"
        a(f"| {anio} ({per}) | {celdas[0]} | {celdas[1]} | {celdas[2]} | {celdas[3]} |")
    a("")
    a("---")
    a("")

    # ── ANÁLISIS SOBRE/BAJO EMA (solo para el benchmark) ─────────────────────
    a("## 5. Análisis por distancia al EMA200d (benchmark)")
    a("")
    a("Distribución de distancias (BTC precio vs EMA200d) de las entradas del Sistema C (EMA200d):")
    a("")
    trades_c = resultados[200]["trades"]
    buckets = {">+10%":[], "+5→+10%":[], "0→+5%":[], "SOBRE_total":[]}
    for t in trades_c:
        if t["dist"] is None: continue
        buckets["SOBRE_total"].append(t)
        if t["dist"] > 10: buckets[">+10%"].append(t)
        elif t["dist"] > 5: buckets["+5→+10%"].append(t)
        else: buckets["0→+5%"].append(t)
    a("| Distancia | Trades | WR | PF | Exp |")
    a("|-----------|--------|----|----|-----|")
    for bk in [">+10%", "+5→+10%", "0→+5%", "SOBRE_total"]:
        g = buckets[bk]
        m = metricas(g)
        label = bk if bk != "SOBRE_total" else "**TOTAL SOBRE**"
        if m['n'] == 0:
            a(f"| {label} | 0 | — | — | — |")
        else:
            a(f"| {label} | {m['n']} | {m['wr']:.0f}% | {fpf(m['pf'])} | {fpl(m['exp'])} |")
    a("")
    a("---")
    a("")

    # ── BOOTSTRAP ─────────────────────────────────────────────────────────────
    a("## 6. Bootstrap IC95% — diferencia de expectancy en validación OOS")
    a("")
    a("Comparación: EMA200 (benchmark) vs cada EMA vecina.")
    a(f"Método: {N_BOOTSTRAP:,} resamples con reemplazo independiente de cada sistema.")
    a("Diferencia observada = E[EMA200] − E[EMAn].")
    a("")
    a("**Limitación metodológica importante:** los trades de sistemas distintos no son")
    a("independientes (comparten el mismo activo y período). La dependencia serial")
    a("subestima la varianza real. El IC95% es orientativo, no una prueba formal.")
    a("")
    a("| Comparación | Trades EMA200 | Trades EMAn | Diff observada | IC95% | Cruza 0 | P(diff>0) |")
    a("|-------------|--------------|------------|----------------|-------|---------|-----------|")
    for n in [100, 150, 250]:
        bs = bs_results[n]
        trades_n_val = [t for t in resultados[n]["trades"] if t["periodo"] == "VAL"]
        if bs["obs"] is None:
            a(f"| EMA200 vs EMA{n} | {len(trades_200_val)} | {len(trades_n_val)} | N/A | N/A | N/A | N/A |")
        else:
            lo, hi = bs["ic95"]
            cruza = "Sí ⚠️" if lo < 0 < hi or hi < 0 else "No"
            a(f"| EMA200 vs EMA{n} | {len(trades_200_val)} | {len(trades_n_val)} "
              f"| {fpl(bs['obs'])} | [{fpl(lo)}, {fpl(hi)}] | {cruza} | {bs['p_pos']:.1%} |")
    a("")
    a("---")
    a("")

    # ── ANÁLISIS DE SOBREAJUSTE ───────────────────────────────────────────────
    a("## 7. Análisis de riesgo de sobreajuste")
    a("")
    a("### 7.1. ¿EMA200 parece seleccionada post-hoc?")
    a("")
    pfs_val = {}
    for n in EMAs:
        vl = [t for t in resultados[n]["trades"] if t["periodo"] == "VAL"]
        pfs_val[n] = metricas(vl)["pf"]
    mejor_n  = max(EMAs, key=lambda n: pfs_val[n] if pfs_val[n] != float("inf") else 999)
    a(f"EMA con mayor PF en validación: **EMA{mejor_n}d** (PF {fpf(pfs_val[mejor_n])})")
    if mejor_n == 200:
        a("EMA200d coincide con el benchmark. Esto **podría indicar** selección post-hoc")
        a("si EMA200 es el único con PF > 1.0, o **puede ser señal válida** si EMA150/250 también son positivos.")
    else:
        a(f"EMA{mejor_n}d supera a EMA200d en validación. EMA200 no es el pico máximo,")
        a("lo que reduce —pero no elimina— el riesgo de selección post-hoc.")
    a("")
    pf_positivos_val = [n for n in EMAs if pfs_val[n] > 1.0]
    a(f"EMAs con PF > 1.0 en validación: **{len(pf_positivos_val)} de 4** ({', '.join(f'EMA{n}' for n in pf_positivos_val) if pf_positivos_val else '—'})")
    a("")
    a("### 7.2. ¿EMA200 es un pico aislado?")
    a("")
    pfs_all = {n: metricas(resultados[n]["trades"])["pf"] for n in EMAs}
    if all(pfs_val.get(n, 0) > 1.0 for n in EMAs):
        a("→ **No es un pico aislado.** Los 4 gates tienen PF > 1.0 en validación.")
    elif pf_positivos_val and pfs_val[200] > 1.0 and len(pf_positivos_val) >= 2:
        vecinos = [n for n in pf_positivos_val if n != 200]
        a(f"→ **EMA200 no está solo.** También son positivos: {', '.join(f'EMA{n}' for n in vecinos)}.")
        a("Existe una zona razonablemente continua de resultados positivos.")
    elif pfs_val[200] > 1.0 and len(pf_positivos_val) == 1:
        a("→ **⚠️ PICO POTENCIALMENTE AISLADO.** Solo EMA200d tiene PF > 1.0 en validación.")
        a("Esto es la señal de alarma más clara de sobreajuste.")
    else:
        a("→ EMA200d no tiene PF > 1.0 en validación — el benchmark no generaliza.")
    a("")
    a("### 7.3. ¿Hay dependencia excesiva de un año?")
    a("")
    a("Contribución anual al P/L de EMA200 (todos los períodos):")
    total_pl = sum(t["pl"] for t in resultados[200]["trades"])
    for anio in ["2021","2022","2023","2024","2025"]:
        g = [t for t in resultados[200]["trades"] if t["anio"] == anio]
        apl = sum(t["pl"] for t in g)
        pct = round(apl/total_pl*100,1) if total_pl != 0 else 0
        a(f"- {anio}: {fpl(apl)} ({pct:+.1f}% del total)")
    a("")
    n_2021 = sum(t["pl"] for t in resultados[200]["trades"] if t["anio"]=="2021")
    if total_pl > 0 and n_2021/total_pl > 0.6:
        a("⚠️ **El año 2021 explica más del 60% del P/L total.** El resultado es muy sensible")
        a("al bull market extremo de ese año. Si se excluye 2021, el sistema puede ser negativo.")
    else:
        a("→ El P/L no está dominado excesivamente por un único año (dentro de lo esperable).")
    a("")
    a("---")
    a("")

    # ── RACHAS DETALLADAS ─────────────────────────────────────────────────────
    a("## 8. Rachas y secuencias — Sistema C EMA200 (benchmark)")
    a("")
    todos_c = sorted(resultados[200]["trades"], key=lambda x: x["ts"])
    a("### Peor racha de SL consecutivos")
    a("")
    max_sl = 0; cur_sl = 0; sl_start_ts = sl_end_ts = ""; cur_start = ""
    for t in todos_c:
        if t["res"] == "SL":
            if cur_sl == 0: cur_start = t["ts"]
            cur_sl += 1
            if cur_sl > max_sl:
                max_sl = cur_sl; sl_start_ts = cur_start; sl_end_ts = t["ts"]
        else: cur_sl = 0
    a(f"Racha máxima SL: **{max_sl} SL consecutivos** ({sl_start_ts} → {sl_end_ts})")
    a("")
    a("Trades en la peor racha:")
    in_streak = False; cnt = 0; sl_ts_list = []
    for t in todos_c:
        if t["ts"] == sl_start_ts and t["res"] == "SL": in_streak = True
        if in_streak and t["res"] == "SL":
            cnt += 1; sl_ts_list.append(t)
            if cnt == max_sl: break
        elif in_streak: break
    if sl_ts_list:
        a("| # | Fecha | RSI | Precio | Dist% | P/L |")
        a("|---|-------|-----|--------|-------|-----|")
        for i, t in enumerate(sl_ts_list, 1):
            dist_s = f"{t['dist']:+.1f}%" if t['dist'] is not None else "—"
            a(f"| {i} | {t['ts']} | {t['rsi']:.1f} | {t['precio']:,} | {dist_s} | {t['pl']:.2f} |")
    a("")
    a("### Mejor racha de TP consecutivos")
    max_tp = 0; cur_tp = 0; tp_start_ts = tp_end_ts = ""; cur_start_tp = ""
    for t in todos_c:
        if t["res"] == "TP":
            if cur_tp == 0: cur_start_tp = t["ts"]
            cur_tp += 1
            if cur_tp > max_tp:
                max_tp = cur_tp; tp_start_ts = cur_start_tp; tp_end_ts = t["ts"]
        else: cur_tp = 0
    a(f"Racha máxima TP: **{max_tp} TP consecutivos** ({tp_start_ts} → {tp_end_ts})")
    a("")
    a("---")
    a("")

    # ── VEREDICTO FINAL ───────────────────────────────────────────────────────
    a("## 9. Veredicto final — Robustez de vecindad")
    a("")
    pf_positivos_val_count = len(pf_positivos_val)
    exp_200_val = metricas([t for t in resultados[200]["trades"] if t["periodo"]=="VAL"])["exp"]

    a("### Respuesta a las 10 preguntas de evaluación")
    a("")
    res = {}
    # 1. ¿La ventaja existe en varias EMAs?
    res[1] = f"{'Sí' if pf_positivos_val_count >= 3 else 'Parcial' if pf_positivos_val_count >= 2 else 'No'} — PF > 1.0 en {pf_positivos_val_count}/4 EMAs en validación"
    # 2. ¿EMA200 está aislada o en zona robusta?
    res[2] = "En zona robusta" if pf_positivos_val_count >= 3 else ("Zona parcial" if pf_positivos_val_count >= 2 else "Potencialmente aislada")
    # 3. ¿Cambio brusco entre EMAs?
    pf_150 = pfs_val.get(150, 0) if pfs_val.get(150, 0) != float("inf") else 999
    pf_200 = pfs_val.get(200, 0) if pfs_val.get(200, 0) != float("inf") else 999
    pf_250 = pfs_val.get(250, 0) if pfs_val.get(250, 0) != float("inf") else 999
    cambio = abs(pf_200 - pf_150) > 0.5 or abs(pf_200 - pf_250) > 0.5
    res[3] = f"{'Sí — transición brusca' if cambio else 'No — gradual'} (EMA150={fpf(pfs_val[150])}, EMA200={fpf(pfs_val[200])}, EMA250={fpf(pfs_val[250])})"
    # 4. ¿Val OOS conserva PF > 1?
    res[4] = f"{'Sí' if pf_200 > 1 else 'No'} — EMA200 val PF {fpf(pfs_val[200])}"
    # 5. ¿Expectancy positiva?
    res[5] = f"{'Sí' if exp_200_val > 0 else 'No'} — EMA200 val Exp {fpl(exp_200_val)}"
    # 6. ¿WR estable?
    wrs_val = {n: metricas([t for t in resultados[n]["trades"] if t["periodo"]=="VAL"])["wr"] for n in EMAs}
    wr_range = max(wrs_val.values()) - min(wrs_val.values())
    res[6] = f"{'Sí' if wr_range < 15 else 'No'} — rango WR en val: {min(wrs_val.values()):.0f}%–{max(wrs_val.values()):.0f}% (variación {wr_range:.0f} pp)"
    # 7. Suficientes trades
    n_val_min = min(metricas([t for t in resultados[n]["trades"] if t["periodo"]=="VAL"])["n"] for n in EMAs)
    res[7] = f"{'Sí' if n_val_min >= 10 else 'Marginal' if n_val_min >= 5 else 'No'} — mín {n_val_min} trades OOS en una EMA"
    # 8. Dependencia de un año
    pl_2021 = sum(t["pl"] for t in resultados[200]["trades"] if t["anio"]=="2021")
    dep = pl_2021/total_pl*100 if total_pl > 0 else 0
    res[8] = f"{'⚠️ Alta' if dep > 60 else 'Moderada' if dep > 40 else 'Baja'} — 2021 representa {dep:.0f}% del P/L EMA200 total"
    # 9. ¿Resultado depende principalmente de 2021?
    pl_sin2021 = sum(t["pl"] for t in resultados[200]["trades"] if t["anio"]!="2021")
    res[9] = f"{'⚠️ Sin 2021 el sistema sería negativo' if pl_sin2021 < 0 else f'No — P/L sin 2021: {fpl(pl_sin2021)}'}"
    # 10. ¿Sobrevive al cambio de EMA?
    res[10] = f"{'Sí' if pf_positivos_val_count >= 3 else 'Parcialmente' if pf_positivos_val_count >= 2 else 'No'}"

    for k, v in res.items():
        a(f"{k}. {v}")
    a("")

    # Veredicto
    a("### Clasificación final")
    a("")
    if pf_positivos_val_count >= 3 and pf_200 > 1.0 and exp_200_val > 0 and not cambio:
        veredicto_final = "🟢 ROBUSTO"
        explicacion = ("La ventaja del Sistema C (RSI 55–60 + SOBRE EMA) existe en una zona "
                       "amplia alrededor de EMA200d. El resultado no depende exclusivamente de "
                       "EMA200d — múltiples EMAs vecinas también son positivas en validación OOS.")
    elif pf_positivos_val_count >= 2 and pf_200 > 1.0:
        veredicto_final = "🟡 PARCIAL"
        explicacion = ("La ventaja existe pero con sensibilidad al valor de EMA. "
                       "EMA200d es positiva en OOS y al menos una EMA vecina también, "
                       "pero el resultado no es uniforme en toda la vecindad probada.")
    else:
        veredicto_final = "🔴 FRÁGIL"
        explicacion = ("EMA200d produce el resultado pero las EMAs vecinas no replican "
                       "el patrón en validación OOS. El hallazgo puede ser artefacto de la "
                       "EMA específica elegida.")

    a(f"### {veredicto_final}")
    a("")
    a(explicacion)
    a("")
    a("---")
    a("")
    a("## 10. Cuadro acumulado de evidencia BTC ALCISTA Sistema C")
    a("")
    a("| Estudio | Resultado | Detalle |")
    a("|---------|-----------|---------|")
    a("| Forense histórico 2021–2026 | PF 2.310, 43 trades | WR 67%, Exp +$0.111 |")
    a("| Walk-forward train 2021–2023 | PF 2.091, 23 trades | WR 65%, 🟢 A |")
    a("| Walk-forward val OOS 2024–2025 | **PF 2.603**, 20 trades | WR 70%, mejora OOS |")
    a(f"| Robustez vecindad (val OOS) | {pf_positivos_val_count}/4 EMAs PF > 1.0 | {veredicto_final} |")
    a("")
    a("**Freno actual al veredicto A (ROBUSTO total):**")
    a("- Validación OOS tiene 20 trades (umbral formal: ≥30)")
    a("- Año 2021 contribuye con una proporción significativa del P/L histórico")
    a("- Sin gates de producción replicados (trailing, horario, eventos macro)")
    a("")
    a("---")
    a("")
    a("## 11. Próximos pasos posibles (NO implementar — decisión de Ariel)")
    a("")
    a("A) Continuar con estadística adicional (más años de bootstrap, IC95% más formal)")
    a("B) Extender validación OOS hasta 2026 para ver comportamiento en bear market")
    a("C) Preparar protocolo de validación REAL con 30+ trades reales")
    a("D) Descartar BTC si la robustez resulta insuficiente")
    a("")
    a("---")
    a("")
    a("## 12. Confirmación de aislamiento")
    a("")
    a("- `config_cartera.py` = **SIN CAMBIOS** ✅")
    a("- `francotirador_alcista_btc.py` = **SIN CAMBIOS** ✅")
    a("- `auditoria.csv` = **SIN CAMBIOS** ✅")
    a("- `billetera.json` = **SIN CAMBIOS** ✅")
    a("- Candidato en producción = **NO ACTIVADO** ✅")
    a("")
    a("**ESTADO DE PRODUCCIÓN: NO ACTIVADO**")
    a("")
    a("Archivos creados este análisis:")
    a("- `reports/2026-08-14_btc-alcista-robustez-vecindad-sistema-c.md` (este reporte)")
    a("- `btc_robustez_vecindad_sistema_c.py` (script de análisis, no es producción)")

    with open(os.path.expanduser(REPORT), "w") as f:
        f.write("\n".join(lines))

    print()
    print("=" * 60)
    print("RESULTADO ROBUSTEZ DE VECINDAD")
    print("=" * 60)
    print()
    print(f"{'Gate':<10} {'TrainTrades':>12} {'TrainPF':>9} {'ValTrades':>10} {'ValPF':>9} {'ValWR':>7} {'OOS':>15}")
    print("-" * 62)
    for n in EMAs:
        tr = [t for t in resultados[n]["trades"] if t["periodo"] == "TRAIN"]
        vl = [t for t in resultados[n]["trades"] if t["periodo"] == "VAL"]
        mt = metricas(tr); mv = metricas(vl)
        marca = " ←" if n == 200 else ""
        oos = veredicto_wf(mt['pf'], mv['pf'], mv['exp'], mv['n'])
        print(f"EMA{n:<7} {mt['n']:>12} {fpf(mt['pf']):>9} {mv['n']:>10} "
              f"{fpf(mv['pf']):>9} {mv['wr']:>6.0f}% {oos:>15}{marca}")
    print()
    print(f"Bootstrap EMA200 vs:")
    for n in [100, 150, 250]:
        bs = bs_results[n]
        if bs["obs"] is not None:
            lo, hi = bs["ic95"]
            print(f"  EMA{n}: diff {fpl(bs['obs'])} | IC95% [{fpl(lo)}, {fpl(hi)}] | P(diff>0)={bs['p_pos']:.1%}")
    print()
    print(f"EMAs con PF > 1.0 en validación: {pf_positivos_val_count}/4")
    print(f"Veredicto: {veredicto_final}")
    print()
    print(f"Reporte: {REPORT}")

if __name__ == "__main__":
    main()
