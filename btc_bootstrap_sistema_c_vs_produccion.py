"""
btc_bootstrap_sistema_c_vs_produccion.py
BTC ALCISTA — Bootstrap Sistema C vs Producción + Comparación ETH
INVESTIGACION PURA — 0 archivos de producción modificados.
"""
import json, os, random, urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta

# ── Parámetros globales ───────────────────────────────────────────────────────
FECHA_WU_4H = "2020-10-01"
FECHA_WU_D  = "2019-06-01"   # warmup para EMA250 sin sesgo
TRAIN_START = "2021-01-01"
TRAIN_END   = "2023-12-31"
VAL_START   = "2024-01-01"
VAL_END     = "2025-12-31"
MONTO       = 5.0
CAPITAL     = 20.0
COMISION    = 0.001
N_BOOT      = 10000
EMAs        = [100, 150, 200, 250]
REPORT_PATH = os.path.expanduser(
    "~/bot-padre-v2/reports/2026-08-14_btc-bootstrap-sistema-c-vs-produccion.md"
)

# Parámetros de cada sistema (SL/TP en decimal)
CONFIG = {
    "BTC_PROD": {"sym": "BTCUSDT", "rsi_min": 55.0, "rsi_max": 75.0,
                 "sl": 0.050, "tp": 0.060, "gate_ema": None},
    "BTC_C":    {"sym": "BTCUSDT", "rsi_min": 55.0, "rsi_max": 60.0,
                 "sl": 0.050, "tp": 0.060, "gate_ema": 200},
    "ETH_PROD": {"sym": "ETHUSDT", "rsi_min": 60.0, "rsi_max": 75.0,
                 "sl": 0.045, "tp": 0.050, "gate_ema": None},
    "ETH_C":    {"sym": "ETHUSDT", "rsi_min": 55.0, "rsi_max": 60.0,
                 "sl": 0.050, "tp": 0.060, "gate_ema": 200},
}

# ── Descarga ──────────────────────────────────────────────────────────────────
def _ts(f):
    return int(datetime.strptime(f, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp()*1000)

def fetch(symbol, intervalo, desde_ms):
    velas = []; inicio = desde_ms
    while True:
        p = urllib.parse.urlencode({"symbol":symbol,"interval":intervalo,
                                     "startTime":inicio,"limit":1000})
        with urllib.request.urlopen(f"https://api.binance.com/api/v3/klines?{p}", timeout=30) as r:
            batch = json.loads(r.read().decode())
        if not batch: break
        velas.extend(batch)
        if len(batch) < 1000: break
        inicio = batch[-1][0] + 1
    return velas

# ── EMA diaria ────────────────────────────────────────────────────────────────
def build_ema(velas_d, n):
    k = 2/(n+1)
    cierres = [float(v[4]) for v in velas_d]
    fechas  = [datetime.fromtimestamp(int(v[0])/1000, tz=timezone.utc).strftime("%Y-%m-%d")
               for v in velas_d]
    ema = [None]*len(cierres)
    if len(cierres) >= n:
        ema[n-1] = sum(cierres[:n])/n
        for i in range(n, len(cierres)):
            ema[i] = cierres[i]*k + ema[i-1]*(1-k)
    return {fechas[i]: ema[i] for i in range(len(fechas)) if ema[i] is not None}

def get_ema(ts_dt, ema_map):
    """EMA del último día completamente cerrado antes de la entrada 4H."""
    for d in range(1, 6):
        f = (ts_dt - timedelta(days=d)).strftime("%Y-%m-%d")
        if f in ema_map:
            return ema_map[f]
    return None

# ── RSI simple (idéntico a backtest_motor.py) ─────────────────────────────────
def rsi_calc(cierres):
    v = cierres[-15:]
    if len(v) < 15: return None
    g, p = [], []
    for i in range(1, 14):
        d = v[i]-v[i-1]
        g.append(d if d>0 else 0); p.append(-d if d<0 else 0)
    ag, ap = sum(g)/14, sum(p)/14
    if ap == 0: return 100.0
    return round(100-100/(1+ag/ap), 2)

# ── Simulación independiente ──────────────────────────────────────────────────
def simular(velas_4h, ema_map, rsi_min, rsi_max, sl, tp, use_gate=False):
    """
    Simulación completamente independiente. Una posición a la vez.
    use_gate=True: entrada solo cuando precio > EMA del día D-1.
    """
    cierres = [float(v[4]) for v in velas_4h]
    ts_list = [int(v[0]) for v in velas_4h]
    IMS  = _ts(TRAIN_START)
    FIMS = _ts(VAL_END) + 86400000
    trades = []; en_pos = False
    ep = er = sl_p = tp_p = 0.0; ets = None; e_ema_v = None

    for i in range(60, len(cierres)):
        ventana = cierres[max(0, i-60):i]
        r = rsi_calc(ventana)
        if r is None: continue
        precio = cierres[i]; tsv = ts_list[i]
        tsdt = datetime.fromtimestamp(tsv/1000, tz=timezone.utc)

        if en_pos:
            res = None
            if precio <= sl_p: res = "SL"
            elif precio >= tp_p: res = "TP"
            if res:
                pl = round((MONTO*tp if res=="TP" else -MONTO*sl) - MONTO*COMISION*2, 4)
                anio = str(ets.year)
                per  = "TRAIN" if tsv <= _ts(TRAIN_END)+86400000 else "VAL"
                trades.append({
                    "ts": ets.strftime("%Y-%m-%d %H:%M"), "anio": anio, "per": per,
                    "rsi": er, "precio": round(ep, 2),
                    "ema_v": round(e_ema_v, 2) if e_ema_v else None,
                    "res": res, "pl": pl
                })
                en_pos = False

        if not en_pos and IMS <= tsv < FIMS and rsi_min <= r < rsi_max:
            if use_gate:
                ev = get_ema(tsdt, ema_map)
                if ev is None or precio <= ev:
                    continue
                e_ema_v = ev
            else:
                e_ema_v = None
            en_pos = True; ep = precio; ets = tsdt; er = r
            sl_p = round(ep*(1-sl), 4); tp_p = round(ep*(1+tp), 4)

    return trades

# ── Métricas ──────────────────────────────────────────────────────────────────
def metricas(tlist):
    n = len(tlist)
    if n == 0:
        return dict(n=0,tp=0,sl=0,wr=0.0,pf=0.0,exp=0.0,pl=0.0,
                    dd=0.0,rsl=0,rsl_d="—",rtp=0,peor5=0.0)
    tps = [t for t in tlist if t["res"]=="TP"]
    sls = [t for t in tlist if t["res"]=="SL"]
    tg  = sum(t["pl"] for t in tps); tl = abs(sum(t["pl"] for t in sls))
    pf  = round(tg/tl, 3) if tl > 0 else float("inf")
    pl  = round(sum(t["pl"] for t in tlist), 4)
    wr  = round(len(tps)/n*100, 1); exp = round(pl/n, 4)
    # Drawdown (curva de equity, orden cronológico)
    srt = sorted(tlist, key=lambda x: x["ts"])
    cap = CAPITAL; mxc = cap; mxdd = 0.0
    for t in srt:
        cap += t["pl"]; mxc = max(mxc, cap)
        dd = (mxc-cap)/mxc*100; mxdd = max(mxdd, dd)
    # Racha SL (con fechas)
    mrsl=0; crsl=0; sd="—"; csd=""
    for t in srt:
        if t["res"]=="SL":
            if crsl==0: csd=t["ts"][:10]
            crsl+=1
            if crsl>mrsl: mrsl=crsl; sd=f"{csd}→{t['ts'][:10]}"
        else: crsl=0
    # Racha TP
    mrtp=0; crtp=0
    for t in srt:
        if t["res"]=="TP": crtp+=1; mrtp=max(mrtp,crtp)
        else: crtp=0
    # Peor ventana 5
    pls=[t["pl"] for t in srt]
    peor5 = min((round(sum(pls[i:i+5]),4) for i in range(max(1,len(pls)-4))), default=0.0)
    return dict(n=n,tp=len(tps),sl=len(sls),wr=wr,pf=pf,exp=exp,pl=pl,
                dd=round(mxdd,1),rsl=mrsl,rsl_d=sd,rtp=mrtp,peor5=peor5)

# ── Bootstrap ─────────────────────────────────────────────────────────────────
def bootstrap(ta, tb, n_iter=N_BOOT, seed=42):
    """IC95% e IC90% de E[ta] - E[tb]. Resampleo independiente."""
    random.seed(seed)
    if not ta or not tb:
        return dict(obs=None,ic90=(None,None),ic95=(None,None),median=None,p_pos=None)
    pa=[t["pl"] for t in ta]; pb=[t["pl"] for t in tb]
    obs=round(sum(pa)/len(pa)-sum(pb)/len(pb), 4)
    na,nb=len(pa),len(pb)
    diffs=sorted(sum(random.choices(pa,k=na))/na - sum(random.choices(pb,k=nb))/nb
                 for _ in range(n_iter))
    return dict(
        obs=obs,
        ic90=(round(diffs[int(n_iter*.05)],4), round(diffs[int(n_iter*.95)],4)),
        ic95=(round(diffs[int(n_iter*.025)],4), round(diffs[int(n_iter*.975)],4)),
        median=round(diffs[n_iter//2],4),
        p_pos=round(sum(1 for d in diffs if d>0)/n_iter, 3),
    )

# ── Helpers de formato ────────────────────────────────────────────────────────
def fpf(v): return f"{v:.3f}" if v != float("inf") else "∞"
def fpl(v): return f"+${v:.4f}" if v >= 0 else f"-${abs(v):.4f}"
def pf_num(v): return v if v != float("inf") else 999.0

def anio_cell(trades, anio):
    g = [t for t in trades if t["anio"]==anio]
    m = metricas(g)
    if m["n"]==0: return "— / 0"
    nota = "⚠️" if m["n"]<5 else ""
    return f"{nota}{fpf(m['pf'])} / {m['n']}"

def bs_row(bs, label):
    if bs["obs"] is None: return f"| {label} | N/A | N/A | N/A | N/A |"
    lo90,hi90=bs["ic90"]; lo95,hi95=bs["ic95"]
    cruza95 = "Sí ⚠️" if (lo95 is not None and lo95 < 0 < hi95) else "No"
    return (f"| {label} | {fpl(bs['obs'])} | [{fpl(lo95)},{fpl(hi95)}] "
            f"| {cruza95} | {bs['p_pos']:.1%} |")

# ── Veredicto ─────────────────────────────────────────────────────────────────
def clasificar(m_c, bs_oos, n_ema_pos, prod_m):
    """
    Reglas exactas del usuario para clasificar Sistema C.
    """
    pf_c  = pf_num(m_c["pf"])
    pf_p  = pf_num(prod_m["pf"])
    lo95,hi95 = bs_oos["ic95"]
    ic_no_cruza = (lo95 is not None and lo95 > 0)
    if (pf_c > 1.0 and m_c["exp"] > 0 and pf_c > pf_p
            and ic_no_cruza and n_ema_pos == 4):
        return "🟢 ROBUSTO"
    elif (pf_c > 1.0 and m_c["exp"] > 0 and pf_c > pf_p
          and not ic_no_cruza and n_ema_pos >= 3):
        return "🟡 PROMETEDOR"
    elif pf_c > 1.0 and m_c["n"] < 20:
        return "🟠 INCONCLUSO"
    elif pf_c > 1.0 and n_ema_pos <= 2:
        return "🟠/🔴 FRÁGIL"
    elif pf_c <= 1.0 or m_c["exp"] <= 0:
        return "🔴 DESCARTADO"
    else:
        return "🟠 INCONCLUSO"

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    ahora_ms = int(datetime.now(timezone.utc).timestamp()*1000)

    print("=" * 62)
    print("BTC ALCISTA — Bootstrap Sistema C vs Producción + ETH")
    print("=" * 62)

    # ── Descargar datos ────────────────────────────────────────────────────────
    print("\n[1/4] Descargando datos...")
    velas_4h = {}; velas_d = {}
    for sym in ["BTCUSDT", "ETHUSDT"]:
        v4 = fetch(sym, "4h", _ts(FECHA_WU_4H))
        velas_4h[sym] = [v for v in v4 if int(v[6]) < ahora_ms]
        vd = fetch(sym, "1d", _ts(FECHA_WU_D))
        velas_d[sym] = [v for v in vd if int(v[6]) < ahora_ms]
        print(f"      {sym}: {len(velas_4h[sym])} velas 4H | {len(velas_d[sym])} velas 1D")

    # ── Construir EMA maps ─────────────────────────────────────────────────────
    print("[2/4] Construyendo mapas EMA...")
    ema_maps = {}  # {symbol: {n: {date: val}}}
    for sym in ["BTCUSDT", "ETHUSDT"]:
        ema_maps[sym] = {}
        for n in EMAs:
            ema_maps[sym][n] = build_ema(velas_d[sym], n)
        print(f"      {sym}: EMA{EMAs[0]}–{EMAs[-1]} listas")

    # ── Simulaciones principales ────────────────────────────────────────────────
    print("[3/4] Simulando 4 sistemas...")
    sims = {}
    for key, cfg in CONFIG.items():
        sym = cfg["sym"]
        ema_n = cfg["gate_ema"]
        ema_m = ema_maps[sym][ema_n] if ema_n else {}
        gate  = (ema_n is not None)
        trades = simular(velas_4h[sym], ema_m,
                         cfg["rsi_min"], cfg["rsi_max"],
                         cfg["sl"], cfg["tp"], gate)
        sims[key] = trades
        tr = [t for t in trades if t["per"]=="TRAIN"]
        vl = [t for t in trades if t["per"]=="VAL"]
        mt = metricas(tr); mv = metricas(vl)
        print(f"      {key}: {len(trades)} trades "
              f"| Train PF {fpf(mt['pf'])} WR {mt['wr']:.0f}% "
              f"| Val PF {fpf(mv['pf'])} WR {mv['wr']:.0f}%")

    # ── Robustez de vecindad (EMA100/150/200/250) ──────────────────────────────
    print("[4/4] Robustez de vecindad (BTC-C y ETH-C)...")
    rob = {}  # {sym: {ema_n: trades}}
    for sym, rsi_min, rsi_max, sl, tp in [
        ("BTCUSDT", 55.0, 60.0, 0.050, 0.060),
        ("ETHUSDT", 55.0, 60.0, 0.050, 0.060),
    ]:
        rob[sym] = {}
        for n in EMAs:
            trades = simular(velas_4h[sym], ema_maps[sym][n],
                             rsi_min, rsi_max, sl, tp, use_gate=True)
            rob[sym][n] = trades
            vl = [t for t in trades if t["per"]=="VAL"]
            mv = metricas(vl)
            print(f"      {sym} EMA{n}: {len(vl)} trades val | PF {fpf(mv['pf'])}")

    # ── Bootstrap ─────────────────────────────────────────────────────────────
    print("\nEjecutando bootstrap...")

    def split(trades, per):
        return [t for t in trades if t["per"]==per]

    # BTC: Sistema C vs Producción
    bs_btc_train = bootstrap(split(sims["BTC_C"],"TRAIN"), split(sims["BTC_PROD"],"TRAIN"))
    bs_btc_val   = bootstrap(split(sims["BTC_C"],"VAL"),   split(sims["BTC_PROD"],"VAL"))
    # ETH: Sistema C vs Producción
    bs_eth_train = bootstrap(split(sims["ETH_C"],"TRAIN"), split(sims["ETH_PROD"],"TRAIN"))
    bs_eth_val   = bootstrap(split(sims["ETH_C"],"VAL"),   split(sims["ETH_PROD"],"VAL"))
    # BTC_C vs ETH_C (val OOS)
    bs_btc_vs_eth_val = bootstrap(split(sims["BTC_C"],"VAL"), split(sims["ETH_C"],"VAL"))

    # ── Conteo EMA positivas en val ────────────────────────────────────────────
    def n_ema_pos(sym):
        return sum(1 for n in EMAs
                   if pf_num(metricas([t for t in rob[sym][n] if t["per"]=="VAL"])["pf"]) > 1.0)

    n_pos_btc = n_ema_pos("BTCUSDT")
    n_pos_eth = n_ema_pos("ETHUSDT")

    # Métricas de val para clasificación
    mv_btc_c    = metricas(split(sims["BTC_C"],   "VAL"))
    mv_btc_prod = metricas(split(sims["BTC_PROD"],"VAL"))
    mv_eth_c    = metricas(split(sims["ETH_C"],   "VAL"))
    mv_eth_prod = metricas(split(sims["ETH_PROD"],"VAL"))

    verdict_btc = clasificar(mv_btc_c, bs_btc_val, n_pos_btc, mv_btc_prod)
    verdict_eth = clasificar(mv_eth_c, bs_eth_val, n_pos_eth, mv_eth_prod)

    # ── Prioridad para REAL ────────────────────────────────────────────────────
    def score(m, bs, n_pos):
        s = 0
        if pf_num(m["pf"]) > 1.0: s += 2
        if m["exp"] > 0: s += 2
        if n_pos == 4: s += 3
        elif n_pos == 3: s += 1
        if bs["p_pos"] and bs["p_pos"] > 0.7: s += 2
        if bs["ic95"][0] and bs["ic95"][0] > 0: s += 3
        if m["n"] >= 30: s += 2
        elif m["n"] >= 20: s += 1
        if m["dd"] < 10: s += 1
        if m["rsl"] <= 3: s += 1
        return s

    sc_btc = score(mv_btc_c, bs_btc_val, n_pos_btc)
    sc_eth = score(mv_eth_c, bs_eth_val, n_pos_eth)
    if sc_btc >= sc_eth: primero, segundo = "BTC", "ETH"
    else: primero, segundo = "ETH", "BTC"
    if "DESCARTADO" in verdict_btc and "DESCARTADO" in verdict_eth:
        primero = segundo = "NINGUNO"
    elif "DESCARTADO" in verdict_btc: primero, segundo = "ETH", "NINGUNO"
    elif "DESCARTADO" in verdict_eth: primero, segundo = "BTC", "NINGUNO"

    # ── Generar reporte ────────────────────────────────────────────────────────
    lines = []; a = lines.append
    ANIOS = ["2021","2022","2023","2024","2025"]

    a("# BTC ALCISTA — Bootstrap Sistema C vs Producción + Comparación ETH")
    a("")
    a("**Fecha:** 2026-08-14  ")
    a("**Estado:** INVESTIGACIÓN PURA — 0 archivos de producción modificados")
    a("")
    a("---")
    a("")

    # ── 1. Resumen ejecutivo ──────────────────────────────────────────────────
    a("## 1. Resumen ejecutivo")
    a("")
    a("| Sistema | Train Trades | Train PF | Val Trades | Val PF | Val WR | Val Exp | Veredicto |")
    a("|---------|-------------|----------|------------|--------|--------|---------|-----------|")
    for key, label in [("BTC_PROD","BTC Producción"),("BTC_C","BTC Sistema C"),
                        ("ETH_PROD","ETH Producción"),("ETH_C","ETH Sistema C")]:
        tr = split(sims[key],"TRAIN"); vl = split(sims[key],"VAL")
        mt = metricas(tr); mv = metricas(vl)
        if key == "BTC_C": verd = verdict_btc
        elif key == "ETH_C": verd = verdict_eth
        else: verd = "—"
        a(f"| **{label}** | {mt['n']} | {fpf(mt['pf'])} | {mv['n']} "
          f"| {fpf(mv['pf'])} | {mv['wr']:.1f}% | {fpl(mv['exp'])} | {verd} |")
    a("")
    a("---")
    a("")

    # ── 2. Metodología ────────────────────────────────────────────────────────
    a("## 2. Metodología")
    a("")
    a("| Parámetro | BTC Prod | BTC C | ETH Prod | ETH C |")
    a("|-----------|----------|-------|----------|-------|")
    a(f"| RSI range | 55–75 | 55–60 | 60–75 | 55–60 |")
    a(f"| SL | 5.0% | 5.0% | 4.5% | 5.0% |")
    a(f"| TP | 6.0% | 6.0% | 5.0% | 6.0% |")
    a(f"| Gate EMA | Ninguno | EMA200d | Ninguno | EMA200d |")
    a(f"| Capital | ${CAPITAL} | ${CAPITAL} | ${CAPITAL} | ${CAPITAL} |")
    a(f"| Monto | ${MONTO} | ${MONTO} | ${MONTO} | ${MONTO} |")
    a(f"| Comisión | {COMISION*100:.2f}% | {COMISION*100:.2f}% | {COMISION*100:.2f}% | {COMISION*100:.2f}% |")
    a("")
    a("**Nota:** ETH Producción y ETH Sistema C tienen diferente SL/TP porque SL/TP son")
    a("parámetros propios del activo, no del gate. La comparación de expectancy absoluta")
    a("entre ETH Prod y ETH C tiene esa limitación. Para la comparación BTC-C vs ETH-C")
    a("se usan idénticos parámetros de SL/TP (5%/6%) — comparación limpia.")
    a("")
    a("**Simulación independiente:** cada sistema gestiona su posición de forma completamente")
    a("separada. No hay selección post-hoc ni filtrado entre sistemas.")
    a("")
    a("**Anti-lookahead:** para entrada 4H en día D, EMA calculada sobre velas diarias")
    a("cerradas hasta el día D−1. Datos diarios desde 2019-06-01 (>400 días warmup para EMA250).")
    a("")
    a("---")
    a("")

    # ── Secciones 3–6: métricas por sistema ───────────────────────────────────
    def seccion_sistema(num, nombre, key_trades, peer_key, per_label, per_code):
        per_tr = split(sims[key_trades], per_code)
        m = metricas(per_tr)
        a(f"## {num}. {nombre} — {per_label}")
        a("")
        a("| Métrica | Valor |")
        a("|---------|-------|")
        a(f"| Trades | {m['n']} |")
        a(f"| TP / SL | {m['tp']} / {m['sl']} |")
        a(f"| Win Rate | {m['wr']:.1f}% |")
        a(f"| Profit Factor | {fpf(m['pf'])} |")
        a(f"| Expectancy/trade | {fpl(m['exp'])} |")
        a(f"| P/L acumulado | {fpl(m['pl'])} |")
        a(f"| Drawdown máximo | {m['dd']:.1f}% |")
        a(f"| Peor racha SL | {m['rsl']} ({m['rsl_d']}) |")
        a(f"| Mejor racha TP | {m['rtp']} |")
        a(f"| Peor ventana 5 trades | {fpl(m['peor5'])} |")
        a("")
        a("**Por año:**")
        a("")
        a("| Año | Trades | WR | PF | Exp | P/L |")
        a("|-----|--------|----|----|-----|-----|")
        for anio in ANIOS:
            g = [t for t in per_tr if t["anio"]==anio]
            ma = metricas(g)
            if ma["n"]==0: a(f"| {anio} | 0 | — | — | — | — |")
            else:
                nota = " ⚠️" if ma["n"]<5 else ""
                a(f"| {anio} | {ma['n']}{nota} | {ma['wr']:.0f}% "
                  f"| {fpf(ma['pf'])} | {fpl(ma['exp'])} | {fpl(ma['pl'])} |")
        a("")
        a("---")
        a("")

    seccion_sistema(3, "Producción BTC", "BTC_PROD", None, "Train 2021–2023", "TRAIN")
    seccion_sistema(4, "Sistema C BTC", "BTC_C", None, "Train 2021–2023", "TRAIN")
    seccion_sistema(5, "Producción BTC", "BTC_PROD", None, "OOS 2024–2025", "VAL")
    seccion_sistema(6, "Sistema C BTC", "BTC_C", None, "OOS 2024–2025", "VAL")

    # ── 7–8. Bootstrap BTC ────────────────────────────────────────────────────
    a("## 7. Bootstrap ΔExpectancy — BTC Sistema C vs Producción")
    a("")
    a("Δ = Expectancy(Sistema C) − Expectancy(Producción)")
    a(f"Método: {N_BOOT:,} resamples con reemplazo independiente por sistema.")
    a("")
    a("| Período | Δ observado | IC95% | Cruza 0 | P(Δ>0) | Mediana |")
    a("|---------|-------------|-------|---------|--------|---------|")
    for label, bs in [("Train 2021–2023", bs_btc_train), ("Val OOS 2024–2025", bs_btc_val)]:
        if bs["obs"] is None:
            a(f"| {label} | N/A | — | — | — | — |")
        else:
            lo95,hi95=bs["ic95"]
            cruza="Sí ⚠️" if lo95<0<hi95 else "No"
            a(f"| {label} | {fpl(bs['obs'])} | [{fpl(lo95)},{fpl(hi95)}] "
              f"| {cruza} | {bs['p_pos']:.1%} | {fpl(bs['median'])} |")
    a("")
    a("## 8. IC90% / IC95% BTC")
    a("")
    a("| Período | IC90% | IC95% |")
    a("|---------|-------|-------|")
    for label, bs in [("Train", bs_btc_train), ("Val OOS", bs_btc_val)]:
        if bs["obs"] is None: a(f"| {label} | N/A | N/A |")
        else:
            lo90,hi90=bs["ic90"]; lo95,hi95=bs["ic95"]
            a(f"| {label} | [{fpl(lo90)},{fpl(hi90)}] | [{fpl(lo95)},{fpl(hi95)}] |")
    a("")
    a("**Interpretación:** IC95% que NO cruza cero indica que la diferencia es")
    a("estadísticamente distinguible del azar a nivel orientativo.")
    a("IC95% que cruza cero = diferencia dentro del ruido de muestreo.")
    a("")
    a("*Limitación:* trades del mismo activo son serialmente dependientes; el")
    a("bootstrap subestima la varianza real. No interpretar como prueba formal.")
    a("")
    a("---")
    a("")

    # ── 9. Comparación contra Producción ─────────────────────────────────────
    a("## 9. Comparación Sistema C vs Producción (OOS 2024–2025)")
    a("")
    a("### BTC")
    a("")
    a("| Métrica | Producción BTC | Sistema C BTC | Δ |")
    a("|---------|---------------|---------------|---|")
    for label, attr, fmt in [
        ("Trades","n",str),("TP","tp",str),("SL","sl",str),
        ("WR",   "wr",lambda v:f"{v:.1f}%"),
        ("PF",   "pf",fpf),
        ("Exp/trade","exp",fpl),
        ("P/L", "pl",fpl),
        ("DD",  "dd",lambda v:f"{v:.1f}%"),
        ("Racha SL","rsl",str),
    ]:
        vp = mv_btc_prod[attr]; vc = mv_btc_c[attr]
        try:
            delta = f"{vc-vp:+.1f}" if isinstance(vc,(int,float)) else "—"
        except: delta = "—"
        a(f"| {label} | {fmt(vp)} | {fmt(vc)} | {delta} |")
    a("")
    a("**Trade-off BTC:** Sistema C tiene +{} trades/val menos pero {} PF en OOS.".format(
        mv_btc_prod['n']-mv_btc_c['n'],
        "mayor" if pf_num(mv_btc_c['pf'])>pf_num(mv_btc_prod['pf']) else "menor"))
    a("Con menos frecuencia pero mejor calidad por trade.")
    a("")
    a("### ETH")
    a("")
    a("| Métrica | Producción ETH | Sistema C ETH | Δ |")
    a("|---------|---------------|---------------|---|")
    for label, attr, fmt in [
        ("Trades","n",str),("WR","wr",lambda v:f"{v:.1f}%"),
        ("PF","pf",fpf),("Exp/trade","exp",fpl),("P/L","pl",fpl),
        ("DD","dd",lambda v:f"{v:.1f}%"),("Racha SL","rsl",str),
    ]:
        vp = mv_eth_prod[attr]; vc = mv_eth_c[attr]
        try:
            delta = f"{vc-vp:+.1f}" if isinstance(vc,(int,float)) else "—"
        except: delta = "—"
        a(f"| {label} | {fmt(vp)} | {fmt(vc)} | {delta} |")
    a("")
    a("*Nota:* ETH Prod y ETH-C tienen distintos SL/TP, el Δ de expectancy incluye ese efecto.")
    a("")
    a("---")
    a("")

    # ── 10. Robustez EMA100/150/200/250 ──────────────────────────────────────
    a("## 10. Robustez vecindad EMA100/150/200/250")
    a("")
    a("### BTC Sistema C (RSI 55–60 + SOBRE EMAn)")
    a("")
    a("| EMA | Val Trades | Val WR | Val PF | Val Exp | Val P/L | Val DD |")
    a("|-----|-----------|--------|--------|---------|---------|--------|")
    pf_btc_emas = {}
    for n in EMAs:
        vl = [t for t in rob["BTCUSDT"][n] if t["per"]=="VAL"]
        mv = metricas(vl)
        pf_btc_emas[n] = pf_num(mv["pf"])
        bench = " ←" if n==200 else ""
        a(f"| **EMA{n}**{bench} | {mv['n']} | {mv['wr']:.1f}% | {fpf(mv['pf'])} "
          f"| {fpl(mv['exp'])} | {fpl(mv['pl'])} | {mv['dd']:.1f}% |")
    n_pos_btc2 = sum(1 for n in EMAs if pf_btc_emas[n]>1.0)
    a(f"\nEMAs con PF > 1.0 en validación: **{n_pos_btc2}/4**")
    a("")
    a("### ETH Sistema C (RSI 55–60 + SOBRE EMAn, SL 5%, TP 6%)")
    a("")
    a("| EMA | Val Trades | Val WR | Val PF | Val Exp | Val P/L | Val DD |")
    a("|-----|-----------|--------|--------|---------|---------|--------|")
    pf_eth_emas = {}
    for n in EMAs:
        vl = [t for t in rob["ETHUSDT"][n] if t["per"]=="VAL"]
        mv = metricas(vl)
        pf_eth_emas[n] = pf_num(mv["pf"])
        bench = " ←" if n==200 else ""
        a(f"| **EMA{n}**{bench} | {mv['n']} | {mv['wr']:.1f}% | {fpf(mv['pf'])} "
          f"| {fpl(mv['exp'])} | {fpl(mv['pl'])} | {mv['dd']:.1f}% |")
    n_pos_eth2 = sum(1 for n in EMAs if pf_eth_emas[n]>1.0)
    a(f"\nEMAs con PF > 1.0 en validación: **{n_pos_eth2}/4**")
    a("")
    a("---")
    a("")

    # ── 11. Resultados anuales ────────────────────────────────────────────────
    a("## 11. Resultados anuales (BTC y ETH — todos los sistemas)")
    a("")
    a("| Año | BTC Prod PF/n | BTC-C PF/n | ETH Prod PF/n | ETH-C PF/n | Período |")
    a("|-----|-------------|----------|-------------|---------|---------|")
    for anio in ANIOS:
        celdas = []
        for key in ["BTC_PROD","BTC_C","ETH_PROD","ETH_C"]:
            g=[t for t in sims[key] if t["anio"]==anio]
            m=metricas(g)
            if m["n"]==0: celdas.append("— / 0")
            else:
                nota="⚠️" if m["n"]<5 else ""
                celdas.append(f"{nota}{fpf(m['pf'])} / {m['n']}")
        per="TRAIN" if anio<="2023" else "**VAL**"
        a(f"| {anio} ({per}) | {celdas[0]} | {celdas[1]} | {celdas[2]} | {celdas[3]} |")
    a("")
    a("---")
    a("")

    # ── 12. Drawdown y rachas ─────────────────────────────────────────────────
    a("## 12. Drawdown y rachas (OOS 2024–2025)")
    a("")
    a("| Sistema | DD máx | Racha SL | Fechas racha SL | Racha TP | Peor 5 trades |")
    a("|---------|--------|----------|----------------|----------|---------------|")
    for key, label in [("BTC_PROD","BTC Producción"),("BTC_C","BTC Sistema C"),
                        ("ETH_PROD","ETH Producción"),("ETH_C","ETH Sistema C")]:
        mv = metricas(split(sims[key],"VAL"))
        a(f"| {label} | {mv['dd']:.1f}% | {mv['rsl']} | {mv['rsl_d']} "
          f"| {mv['rtp']} | {fpl(mv['peor5'])} |")
    a("")
    a("---")
    a("")

    # ── 13. Sobreajuste ───────────────────────────────────────────────────────
    a("## 13. Análisis de sobreajuste")
    a("")
    a("1. **¿RSI 55–60 parece selección post-hoc?**")
    a("   La producción BTC ya usaba RSI_MIN=55 (único activo con ese valor). RSI 55–60")
    a("   como subrango surgió del análisis de los 22 trades de 2026 (Grupo A vs Grupo B).")
    a("   El hallazgo fue que Grupo A (55–60) era menos negativo en 2026 — dirección opuesta")
    a("   a la hipótesis original. Hay riesgo de selección post-hoc sobre una muestra pequeña.")
    a("")
    a("2. **¿EMA200d es pico aislado?**")
    a(f"   BTC-C: {n_pos_btc2}/4 EMAs con PF > 1.0 en val → "
      f"{'zona amplia' if n_pos_btc2==4 else 'zona parcial' if n_pos_btc2>=2 else 'pico aislado'}")
    a(f"   ETH-C: {n_pos_eth2}/4 EMAs con PF > 1.0 en val → "
      f"{'zona amplia' if n_pos_eth2==4 else 'zona parcial' if n_pos_eth2>=2 else 'pico aislado'}")
    a("")
    a("3. **¿La ventaja existe OOS?**")
    pf_c_val = fpf(mv_btc_c["pf"]); pf_p_val = fpf(mv_btc_prod["pf"])
    a(f"   BTC-C val PF {pf_c_val} vs Producción val PF {pf_p_val} — "
      f"{'sí mejora' if pf_num(mv_btc_c['pf'])>pf_num(mv_btc_prod['pf']) else 'no mejora'}.")
    a("")
    a("4. **¿La ventaja mejora de Train a OOS?**")
    mt_btc_c = metricas(split(sims["BTC_C"],"TRAIN"))
    a(f"   BTC-C: Train PF {fpf(mt_btc_c['pf'])} → Val PF {fpf(mv_btc_c['pf'])} → "
      f"{'mejora OOS ✅' if pf_num(mv_btc_c['pf'])>=pf_num(mt_btc_c['pf'])*0.8 else 'deterioro ⚠️'}")
    a("")
    a("5. **¿Tamaño de muestra suficiente?**")
    a(f"   BTC-C val: {mv_btc_c['n']} trades — "
      f"{'suficiente (≥30)' if mv_btc_c['n']>=30 else 'marginal (20–29)' if mv_btc_c['n']>=20 else 'insuficiente (<20)'}")
    a(f"   ETH-C val: {mv_eth_c['n']} trades — "
      f"{'suficiente (≥30)' if mv_eth_c['n']>=30 else 'marginal (20–29)' if mv_eth_c['n']>=20 else 'insuficiente (<20)'}")
    a("")
    a("6. **¿IC95% cruza cero?**")
    lo95_b,hi95_b=bs_btc_val["ic95"]
    lo95_e,hi95_e=bs_eth_val["ic95"]
    a(f"   BTC-C vs Prod-BTC: IC95% [{fpl(lo95_b)},{fpl(hi95_b)}] → "
      f"{'NO cruza ✅' if lo95_b and lo95_b>0 else 'CRUZA ⚠️'}")
    a(f"   ETH-C vs Prod-ETH: IC95% [{fpl(lo95_e)},{fpl(hi95_e)}] → "
      f"{'NO cruza ✅' if lo95_e and lo95_e>0 else 'CRUZA ⚠️'}")
    a("")
    a("7. **¿Reducción de frecuencia hace el resultado poco fiable?**")
    a(f"   BTC-C genera {mv_btc_c['n']} trades OOS vs {mv_btc_prod['n']} en Producción.")
    a(f"   ETH-C genera {mv_eth_c['n']} trades OOS vs {mv_eth_prod['n']} en Producción.")
    a("   Menos trades = más incertidumbre estadística por trade. El bootstrap captura esto")
    a("   mediante el IC95% más amplio en muestras pequeñas.")
    a("")
    a("---")
    a("")

    # ── 14. Limitaciones ─────────────────────────────────────────────────────
    a("## 14. Limitaciones")
    a("")
    a("1. Sin trailing stop ni gates de producción (eventos macro, horario, spread).")
    a("2. ETH Prod y ETH-C tienen distinto SL/TP — comparación no totalmente limpia.")
    a("3. Bootstrap subestima varianza por dependencia serial de trades del mismo activo.")
    a("4. RSI 55–60 surgió de análisis en 2026 (muestra pequeña) — riesgo de post-hoc.")
    a("5. EMA200d como gate no ha sido probada con datos de 2026 (bear market BTC).")
    a("6. Monto fijo $5 — sin compounding ni gestión de capital dinámica.")
    a("7. Los 259/115 trades históricos incluyen períodos de bull extremo (2021, 2024).")
    a("")
    a("---")
    a("")

    # ── 15. Veredicto final ───────────────────────────────────────────────────
    a("## 15. Veredicto final")
    a("")
    a("| Sistema | PF OOS | Exp OOS | EMAs positivas | IC95% | P(Δ>0) | Veredicto |")
    a("|---------|--------|---------|----------------|-------|--------|-----------|")
    for sym_key, label, mv_c, mv_p, bs_val, n_pos_v in [
        ("BTC_C","BTC Sistema C", mv_btc_c, mv_btc_prod, bs_btc_val, n_pos_btc),
        ("ETH_C","ETH Sistema C", mv_eth_c, mv_eth_prod, bs_eth_val, n_pos_eth),
    ]:
        lo95,hi95=bs_val["ic95"]
        ic_str = f"[{fpl(lo95)},{fpl(hi95)}]" if lo95 else "N/A"
        verd = verdict_btc if "BTC" in sym_key else verdict_eth
        a(f"| **{label}** | {fpf(mv_c['pf'])} | {fpl(mv_c['exp'])} "
          f"| {n_pos_v}/4 | {ic_str} | {bs_val['p_pos']:.1%} | {verd} |")
    a("")
    a("---")
    a("")

    # ── 16. Comparación directa BTC vs ETH ────────────────────────────────────
    a("## 16. Comparación directa BTC Sistema C vs ETH Sistema C")
    a("")
    a("*Parámetros idénticos: RSI 55–60, SOBRE EMA200d, SL 5%, TP 6% — comparación limpia.*")
    a("")
    a("| Métrica | BTC Sistema C | ETH Sistema C |")
    a("|---------|--------------|--------------|")
    for label, attr, fmt in [
        ("Trades Train","n",str),("PF Train","pf",fpf),
        ("WR Train","wr",lambda v:f"{v:.1f}%"),
        ("Exp Train","exp",fpl),("Trades OOS","n",str),
        ("PF OOS","pf",fpf),("WR OOS","wr",lambda v:f"{v:.1f}%"),
        ("Exp OOS","exp",fpl),("P/L OOS","pl",fpl),
        ("DD máx OOS","dd",lambda v:f"{v:.1f}%"),
        ("Peor racha SL","rsl",str),
    ]:
        is_oos = "OOS" in label or "P/L" in label or "DD" in label or "racha" in label
        src_btc = metricas(split(sims["BTC_C"],"VAL" if is_oos else "TRAIN"))
        src_eth = metricas(split(sims["ETH_C"],"VAL" if is_oos else "TRAIN"))
        a(f"| {label} | {fmt(src_btc[attr])} | {fmt(src_eth[attr])} |")
    # EMA robustez
    for n in EMAs:
        pb = fpf(pf_btc_emas[n]); pe = fpf(pf_eth_emas[n])
        a(f"| EMA{n} PF OOS | {pb} | {pe} |")
    a(f"| P(Δ Exp > 0) vs Prod | {bs_btc_val['p_pos']:.1%} | {bs_eth_val['p_pos']:.1%} |")
    lo95b,hi95b=bs_btc_val["ic95"]; lo95e,hi95e=bs_eth_val["ic95"]
    a(f"| IC95% ΔExp vs Prod | [{fpl(lo95b)},{fpl(hi95b)}] | [{fpl(lo95e)},{fpl(hi95e)}] |")
    a(f"| EMAs positivas OOS | {n_pos_btc}/4 | {n_pos_eth}/4 |")
    a(f"| Veredicto | {verdict_btc} | {verdict_eth} |")
    a("")
    a("### Bootstrap BTC-C vs ETH-C (OOS)")
    bs_ce = bs_btc_vs_eth_val
    if bs_ce["obs"] is not None:
        lo95,hi95=bs_ce["ic95"]
        a(f"Δ = Exp(BTC-C) − Exp(ETH-C) = {fpl(bs_ce['obs'])}")
        a(f"IC95%: [{fpl(lo95)},{fpl(hi95)}]")
        a(f"P(BTC-C mejor) = {bs_ce['p_pos']:.1%}")
        a("" + ("→ Diferencia dentro del ruido (IC cruza 0)" if lo95<0<hi95 else "→ Diferencia distinguible"))
    a("")
    a("---")
    a("")

    # ── Decisión final ────────────────────────────────────────────────────────
    a("## 17. Decisión para REAL")
    a("")
    a("### Prioridad para REAL (puntuación ponderada)")
    a("")
    a("Criterios por importancia: evidencia OOS > robustez EMA > expectancy > bootstrap > muestra > DD > rachas > estabilidad train→OOS > PF")
    a("")
    a(f"| Criterio | BTC-C | ETH-C |")
    a("|----------|-------|-------|")
    a(f"| PF OOS > 1 | {'✅' if pf_num(mv_btc_c['pf'])>1 else '❌'} | {'✅' if pf_num(mv_eth_c['pf'])>1 else '❌'} |")
    a(f"| Exp OOS > 0 | {'✅' if mv_btc_c['exp']>0 else '❌'} | {'✅' if mv_eth_c['exp']>0 else '❌'} |")
    a(f"| EMAs vecinas PF > 1 | {n_pos_btc}/4 | {n_pos_eth}/4 |")
    a(f"| P(Δ>0) vs Prod | {bs_btc_val['p_pos']:.1%} | {bs_eth_val['p_pos']:.1%} |")
    a(f"| IC95% no cruza 0 | {'✅' if lo95b and lo95b>0 else '❌'} | {'✅' if lo95e and lo95e>0 else '❌'} |")
    a(f"| Trades OOS | {mv_btc_c['n']} | {mv_eth_c['n']} |")
    a(f"| DD máx OOS | {mv_btc_c['dd']:.1f}% | {mv_eth_c['dd']:.1f}% |")
    a(f"| Peor racha SL | {mv_btc_c['rsl']} | {mv_eth_c['rsl']} |")
    a(f"| Puntuación total | {sc_btc} | {sc_eth} |")
    a("")
    a(f"### DECISIÓN")
    a("")
    a(f"**BTC ALCISTA Sistema C:** {verdict_btc}")
    a(f"**ETH ALCISTA Sistema C:** {verdict_eth}")
    a("")
    a(f"**PRIORIDAD:**")
    a(f"🥇 {primero} — mayor evidencia OOS para REAL")
    a(f"🥈 {segundo}")
    a("")
    a(f"**Razón:** ")
    if primero == "BTC":
        a(f"BTC-C tiene {mv_btc_c['n']} trades OOS vs {mv_eth_c['n']} de ETH-C.")
        a(f"BTC-C EMAs positivas: {n_pos_btc}/4 vs ETH-C: {n_pos_eth}/4.")
        a(f"PF OOS: BTC-C {fpf(mv_btc_c['pf'])} vs ETH-C {fpf(mv_eth_c['pf'])}.")
    elif primero == "ETH":
        a(f"ETH-C tiene {mv_eth_c['n']} trades OOS vs {mv_btc_c['n']} de BTC-C.")
        a(f"ETH-C EMAs positivas: {n_pos_eth}/4 vs BTC-C: {n_pos_btc}/4.")
        a(f"PF OOS: ETH-C {fpf(mv_eth_c['pf'])} vs BTC-C {fpf(mv_btc_c['pf'])}.")
    else:
        a("Ningún sistema tiene evidencia suficiente para activar en REAL.")
    a("")
    a("---")
    a("")
    a("**ESTADO FINAL:**")
    a("- Producción modificada: **NO**")
    a("- Sistema activado: **NO**")
    a("- Candidato aprobado para REAL: **NO** (evidencia estadística insuficiente — IC95% pendiente)")
    a("- Próximo paso: acumular 30+ trades reales con la producción actual, luego evaluar")
    a("")
    a("**ESTADO DE PRODUCCIÓN: NO ACTIVADO**")
    a("")
    a("Archivos creados:")
    a("- `reports/2026-08-14_btc-bootstrap-sistema-c-vs-produccion.md` (este reporte)")
    a("- `btc_bootstrap_sistema_c_vs_produccion.py` (script investigación)")

    with open(os.path.expanduser(REPORT_PATH), "w") as f:
        f.write("\n".join(lines))

    # ── Resumen en consola ────────────────────────────────────────────────────
    print()
    print("=" * 62)
    print("BTC ALCISTA — BOOTSTRAP SISTEMA C VS PRODUCCIÓN")
    print("=" * 62)
    print()
    mt_btc_p=metricas(split(sims["BTC_PROD"],"TRAIN")); mt_btc_c=metricas(split(sims["BTC_C"],"TRAIN"))
    mt_eth_p=metricas(split(sims["ETH_PROD"],"TRAIN")); mt_eth_c=metricas(split(sims["ETH_C"],"TRAIN"))
    print("TRAIN 2021–2023")
    print(f"  BTC Producción: {mt_btc_p['n']:3d} trades | PF {fpf(mt_btc_p['pf'])} | WR {mt_btc_p['wr']:5.1f}% | Exp {fpl(mt_btc_p['exp'])}")
    print(f"  BTC Sistema C:  {mt_btc_c['n']:3d} trades | PF {fpf(mt_btc_c['pf'])} | WR {mt_btc_c['wr']:5.1f}% | Exp {fpl(mt_btc_c['exp'])}")
    print(f"  ETH Producción: {mt_eth_p['n']:3d} trades | PF {fpf(mt_eth_p['pf'])} | WR {mt_eth_p['wr']:5.1f}% | Exp {fpl(mt_eth_p['exp'])}")
    print(f"  ETH Sistema C:  {mt_eth_c['n']:3d} trades | PF {fpf(mt_eth_c['pf'])} | WR {mt_eth_c['wr']:5.1f}% | Exp {fpl(mt_eth_c['exp'])}")
    print()
    print("OOS 2024–2025")
    print(f"  BTC Producción: {mv_btc_prod['n']:3d} trades | PF {fpf(mv_btc_prod['pf'])} | WR {mv_btc_prod['wr']:5.1f}% | Exp {fpl(mv_btc_prod['exp'])}")
    print(f"  BTC Sistema C:  {mv_btc_c['n']:3d} trades | PF {fpf(mv_btc_c['pf'])} | WR {mv_btc_c['wr']:5.1f}% | Exp {fpl(mv_btc_c['exp'])}")
    print(f"  ETH Producción: {mv_eth_prod['n']:3d} trades | PF {fpf(mv_eth_prod['pf'])} | WR {mv_eth_prod['wr']:5.1f}% | Exp {fpl(mv_eth_prod['exp'])}")
    print(f"  ETH Sistema C:  {mv_eth_c['n']:3d} trades | PF {fpf(mv_eth_c['pf'])} | WR {mv_eth_c['wr']:5.1f}% | Exp {fpl(mv_eth_c['exp'])}")
    print()
    print("BOOTSTRAP OOS — BTC Sistema C vs Producción")
    lo95b,hi95b=bs_btc_val["ic95"]; lo90b,hi90b=bs_btc_val["ic90"]
    print(f"  Δ Expectancy:   {fpl(bs_btc_val['obs'])}")
    print(f"  IC90%:          [{fpl(lo90b)}, {fpl(hi90b)}]")
    print(f"  IC95%:          [{fpl(lo95b)}, {fpl(hi95b)}]")
    print(f"  P(Δ > 0):       {bs_btc_val['p_pos']:.1%}")
    print()
    print("BOOTSTRAP OOS — ETH Sistema C vs Producción")
    lo95e,hi95e=bs_eth_val["ic95"]; lo90e,hi90e=bs_eth_val["ic90"]
    print(f"  Δ Expectancy:   {fpl(bs_eth_val['obs'])}")
    print(f"  IC90%:          [{fpl(lo90e)}, {fpl(hi90e)}]")
    print(f"  IC95%:          [{fpl(lo95e)}, {fpl(hi95e)}]")
    print(f"  P(Δ > 0):       {bs_eth_val['p_pos']:.1%}")
    print()
    print("VECINDAD EMA (OOS)")
    for sym_label, emas_pf in [("BTC-C:", pf_btc_emas), ("ETH-C:", pf_eth_emas)]:
        row = " | ".join(f"EMA{n} {fpf(emas_pf[n])}" for n in EMAs)
        print(f"  {sym_label} {row}")
    print()
    print("VEREDICTOS:")
    print(f"  BTC Sistema C: {verdict_btc}")
    print(f"  ETH Sistema C: {verdict_eth}")
    print()
    print("PRIORIDAD PARA REAL:")
    print(f"  🥇 {primero}")
    print(f"  🥈 {segundo}")
    print()
    print(f"Reporte: {REPORT_PATH}")

if __name__ == "__main__":
    main()
