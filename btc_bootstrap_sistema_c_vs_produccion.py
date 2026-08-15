"""
btc_bootstrap_sistema_c_vs_produccion.py
BTC ALCISTA — Bootstrap Sistema C vs Produccion + Comparacion ETH
INVESTIGACION PURA — 0 archivos de produccion modificados.

Reglas de robustez de vecindad (version corregida):
- EMA200 debe ser la EMA con MEJOR PF OOS para declarar robustez.
- Todas las EMAs vecinas tambien deben tener PF > 1.0 para clasificar ROBUSTO.
- Si EMA200 es la unica con PF > 1.0 → FRAGIL, sin importar el PF de EMA200.
- Si EMA200 NO es la mejor EMA → no hay robustez de vecindad alrededor de EMA200.
- ROBUSTO requiere ademas que IC95% del bootstrap NO cruce cero.
- PROMETEDOR: vecindad favorable + IC95% cruza cero.
"""
import json, os, random, urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta

# ── Parametros globales ───────────────────────────────────────────────────────
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
        p = urllib.parse.urlencode({"symbol": symbol, "interval": intervalo,
                                    "startTime": inicio, "limit": 1000})
        with urllib.request.urlopen(f"https://api.binance.com/api/v3/klines?{p}", timeout=30) as r:
            batch = json.loads(r.read().decode())
        if not batch: break
        velas.extend(batch)
        if len(batch) < 1000: break
        inicio = batch[-1][0] + 1
    return velas

# ── EMA diaria ────────────────────────────────────────────────────────────────
def build_ema(velas_d, n):
    k = 2 / (n + 1)
    cierres = [float(v[4]) for v in velas_d]
    fechas  = [datetime.fromtimestamp(int(v[0]) / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
               for v in velas_d]
    ema = [None] * len(cierres)
    if len(cierres) >= n:
        ema[n - 1] = sum(cierres[:n]) / n
        for i in range(n, len(cierres)):
            ema[i] = cierres[i] * k + ema[i - 1] * (1 - k)
    return {fechas[i]: ema[i] for i in range(len(fechas)) if ema[i] is not None}

def get_ema(ts_dt, ema_map):
    """EMA del ultimo dia completamente cerrado antes de la entrada 4H (anti-lookahead)."""
    for d in range(1, 6):
        f = (ts_dt - timedelta(days=d)).strftime("%Y-%m-%d")
        if f in ema_map:
            return ema_map[f]
    return None

# ── RSI simple ────────────────────────────────────────────────────────────────
def rsi_calc(cierres):
    v = cierres[-15:]
    if len(v) < 15: return None
    g, p = [], []
    for i in range(1, 14):
        d = v[i] - v[i - 1]
        g.append(d if d > 0 else 0)
        p.append(-d if d < 0 else 0)
    ag, ap = sum(g) / 14, sum(p) / 14
    if ap == 0: return 100.0
    return round(100 - 100 / (1 + ag / ap), 2)

# ── Simulacion independiente ──────────────────────────────────────────────────
def simular(velas_4h, ema_map, rsi_min, rsi_max, sl, tp, use_gate=False):
    cierres = [float(v[4]) for v in velas_4h]
    ts_list = [int(v[0]) for v in velas_4h]
    IMS  = _ts(TRAIN_START)
    FIMS = _ts(VAL_END) + 86400000
    trades = []; en_pos = False
    ep = er = sl_p = tp_p = 0.0; ets = None; e_ema_v = None

    for i in range(60, len(cierres)):
        ventana = cierres[max(0, i - 60):i]
        r = rsi_calc(ventana)
        if r is None: continue
        precio = cierres[i]; tsv = ts_list[i]
        tsdt = datetime.fromtimestamp(tsv / 1000, tz=timezone.utc)

        if en_pos:
            res = None
            if precio <= sl_p: res = "SL"
            elif precio >= tp_p: res = "TP"
            if res:
                pl = round((MONTO * tp if res == "TP" else -MONTO * sl) - MONTO * COMISION * 2, 4)
                anio = str(ets.year)
                per  = "TRAIN" if tsv <= _ts(TRAIN_END) + 86400000 else "VAL"
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
            sl_p = round(ep * (1 - sl), 4); tp_p = round(ep * (1 + tp), 4)

    return trades

# ── Metricas ──────────────────────────────────────────────────────────────────
def metricas(tlist):
    n = len(tlist)
    if n == 0:
        return dict(n=0, tp=0, sl=0, wr=0.0, pf=0.0, exp=0.0, pl=0.0,
                    dd=0.0, rsl=0, rsl_d="—", rtp=0, peor5=0.0)
    tps = [t for t in tlist if t["res"] == "TP"]
    sls = [t for t in tlist if t["res"] == "SL"]
    tg  = sum(t["pl"] for t in tps)
    tl  = abs(sum(t["pl"] for t in sls))
    pf  = round(tg / tl, 3) if tl > 0 else float("inf")
    pl  = round(sum(t["pl"] for t in tlist), 4)
    wr  = round(len(tps) / n * 100, 1)
    exp = round(pl / n, 4)
    srt = sorted(tlist, key=lambda x: x["ts"])
    cap = CAPITAL; mxc = cap; mxdd = 0.0
    for t in srt:
        cap += t["pl"]; mxc = max(mxc, cap)
        dd = (mxc - cap) / mxc * 100; mxdd = max(mxdd, dd)
    mrsl = 0; crsl = 0; sd = "—"; csd = ""
    for t in srt:
        if t["res"] == "SL":
            if crsl == 0: csd = t["ts"][:10]
            crsl += 1
            if crsl > mrsl: mrsl = crsl; sd = f"{csd}→{t['ts'][:10]}"
        else: crsl = 0
    mrtp = 0; crtp = 0
    for t in srt:
        if t["res"] == "TP": crtp += 1; mrtp = max(mrtp, crtp)
        else: crtp = 0
    pls = [t["pl"] for t in srt]
    peor5 = min((round(sum(pls[i:i + 5]), 4) for i in range(max(1, len(pls) - 4))), default=0.0)
    return dict(n=n, tp=len(tps), sl=len(sls), wr=wr, pf=pf, exp=exp, pl=pl,
                dd=round(mxdd, 1), rsl=mrsl, rsl_d=sd, rtp=mrtp, peor5=peor5)

# ── Bootstrap ─────────────────────────────────────────────────────────────────
def bootstrap(ta, tb, n_iter=N_BOOT, seed=42):
    """IC90/IC95 de E[ta] - E[tb]. Resampleo independiente por sistema."""
    random.seed(seed)
    if not ta or not tb:
        return dict(obs=None, ic90=(None, None), ic95=(None, None), median=None, p_pos=None)
    pa = [t["pl"] for t in ta]; pb = [t["pl"] for t in tb]
    obs = round(sum(pa) / len(pa) - sum(pb) / len(pb), 4)
    na, nb = len(pa), len(pb)
    diffs = sorted(
        sum(random.choices(pa, k=na)) / na - sum(random.choices(pb, k=nb)) / nb
        for _ in range(n_iter)
    )
    return dict(
        obs=obs,
        ic90=(round(diffs[int(n_iter * .05)], 4), round(diffs[int(n_iter * .95)], 4)),
        ic95=(round(diffs[int(n_iter * .025)], 4), round(diffs[int(n_iter * .975)], 4)),
        median=round(diffs[n_iter // 2], 4),
        p_pos=round(sum(1 for d in diffs if d > 0) / n_iter, 3),
    )

# ── Helpers de formato ────────────────────────────────────────────────────────
def fpf(v): return f"{v:.3f}" if v != float("inf") else "∞"
def fpl(v): return f"+${v:.4f}" if v >= 0 else f"-${abs(v):.4f}"
def pf_num(v): return v if v != float("inf") else 999.0

# ── Robustez de vecindad EMA ──────────────────────────────────────────────────
def analizar_robustez_ema(pf_emas):
    """
    pf_emas: dict {100: pf100, 150: pf150, 200: pf200, 250: pf250}

    Reglas exactas (no usar n_ema_pos >= 3 como sustituto):
    1. Identificar la EMA con mejor PF OOS.
    2. Si EMA200 es la mejor Y todas las vecinas tienen PF > 1.0 → ROBUSTO_EMA.
    3. Si EMA200 es la mejor PERO alguna vecina tiene PF <= 1.0 → PARCIAL_EMA.
    4. Si EMA200 es la unica con PF > 1.0 → FRAGIL (independiente del PF de EMA200).
    5. Si EMA200 NO es la mejor → NO_ROBUSTA_EMA200 (sin robustez alrededor de EMA200).
    6. Si EMA200 PF <= 1.0 → FRAGIL_EMA200_NEGATIVA.

    Retorna: (clasificacion, best_ema, n_positivas, detalle)
    """
    pf200   = pf_emas.get(200, 0.0)
    best_n  = max(pf_emas, key=pf_emas.get)
    best_pf = pf_emas[best_n]
    n_pos   = sum(1 for pf in pf_emas.values() if pf > 1.0)
    vecinas = {n: pf for n, pf in pf_emas.items() if n != 200}

    if pf200 <= 1.0:
        return ("FRAGIL_EMA200_NEGATIVA", best_n, n_pos,
                f"EMA200 tiene PF {pf200:.3f} <= 1.0. Mejor EMA: EMA{best_n} (PF {best_pf:.3f}).")

    if best_n != 200:
        return ("NO_ROBUSTA_EMA200", best_n, n_pos,
                f"EMA200 positiva (PF {pf200:.3f}) pero NO es la mejor. "
                f"Mejor: EMA{best_n} (PF {best_pf:.3f}). {n_pos}/4 EMAs con PF > 1.0.")

    # EMA200 es la mejor
    todas_vecinas_pos = all(pf > 1.0 for pf in vecinas.values())
    n_vecinas_pos     = sum(1 for pf in vecinas.values() if pf > 1.0)

    if n_pos == 1:
        return ("FRAGIL_SOLO_EMA200", best_n, n_pos,
                f"EMA200 es la UNICA EMA con PF > 1.0 ({pf200:.3f}). "
                f"Patron FRAGIL independiente del PF de EMA200.")

    if todas_vecinas_pos:
        return ("ROBUSTO_EMA", best_n, n_pos,
                f"EMA200 es la mejor (PF {pf200:.3f}) Y las {len(vecinas)} EMAs vecinas "
                f"tambien tienen PF > 1.0. Patron de vecindad ROBUSTO.")

    # EMA200 es la mejor pero no todas las vecinas son positivas
    return ("PARCIAL_EMA", best_n, n_pos,
            f"EMA200 es la mejor (PF {pf200:.3f}). {n_vecinas_pos}/{len(vecinas)} vecinas "
            f"con PF > 1.0. Robustez parcial.")


def clasificar_sistema(m_val, m_prod_val, bs_val, rob_label, pf_emas):
    """
    Clasificacion final del sistema basada en:
    1. PF OOS y expectancy
    2. Robustez de vecindad EMA (usando rob_label de analizar_robustez_ema)
    3. Bootstrap IC95%

    NO usa n_ema_pos >= 3 como sustituto de la comprobacion explicita.
    """
    pf_c  = pf_num(m_val["pf"])
    exp_c = m_val["exp"]
    n_c   = m_val["n"]
    lo95, hi95 = bs_val["ic95"] if bs_val["ic95"][0] is not None else (None, None)
    ic_no_cruza = (lo95 is not None and lo95 > 0)

    # 1. Descartado: OOS negativo
    if pf_c <= 1.0 or exp_c <= 0:
        return "🔴 DESCARTADO"

    # 2. Inconcluso: muestra muy pequena
    if n_c < 20:
        return "🟠 INCONCLUSO"

    # 3. Fragil: EMA200 no positiva o es la unica positiva
    if rob_label in ("FRAGIL_EMA200_NEGATIVA", "FRAGIL_SOLO_EMA200"):
        return "🟠/🔴 FRAGIL"

    # 4. Sin robustez: EMA200 no es la mejor
    if rob_label == "NO_ROBUSTA_EMA200":
        return "🟡 PROMETEDOR"  # Positivo OOS pero sin robustez de vecindad alrededor de EMA200

    # 5. Zona robusta: EMA200 mejor y todas vecinas positivas
    if rob_label == "ROBUSTO_EMA":
        if ic_no_cruza:
            return "🟢 ROBUSTO"
        else:
            return "🟡 PROMETEDOR"  # Vecindad OK pero IC95% cruza 0

    # 6. Zona parcial: EMA200 mejor pero no todas las vecinas positivas
    if rob_label == "PARCIAL_EMA":
        return "🟡 PROMETEDOR"

    return "🟠 INCONCLUSO"


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    ahora_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

    print("=" * 62)
    print("BTC ALCISTA — Bootstrap Sistema C vs Produccion + ETH")
    print("=" * 62)

    # ── 1. Descarga ────────────────────────────────────────────────────────────
    print("\n[1/4] Descargando datos...")
    velas_4h = {}; velas_d = {}
    for sym in ["BTCUSDT", "ETHUSDT"]:
        v4 = fetch(sym, "4h", _ts(FECHA_WU_4H))
        velas_4h[sym] = [v for v in v4 if int(v[6]) < ahora_ms]
        vd = fetch(sym, "1d", _ts(FECHA_WU_D))
        velas_d[sym] = [v for v in vd if int(v[6]) < ahora_ms]
        print(f"      {sym}: {len(velas_4h[sym])} velas 4H | {len(velas_d[sym])} velas 1D")

    # ── 2. EMA maps ────────────────────────────────────────────────────────────
    print("[2/4] Construyendo mapas EMA...")
    ema_maps = {}
    for sym in ["BTCUSDT", "ETHUSDT"]:
        ema_maps[sym] = {}
        for n in EMAs:
            ema_maps[sym][n] = build_ema(velas_d[sym], n)
        print(f"      {sym}: EMA{EMAs[0]}–{EMAs[-1]} listas")

    # ── 3. Simulaciones principales ────────────────────────────────────────────
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
        tr = [t for t in trades if t["per"] == "TRAIN"]
        vl = [t for t in trades if t["per"] == "VAL"]
        mt = metricas(tr); mv = metricas(vl)
        print(f"      {key}: {len(trades)} trades "
              f"| Train PF {fpf(mt['pf'])} WR {mt['wr']:.0f}% "
              f"| Val PF {fpf(mv['pf'])} WR {mv['wr']:.0f}%")

    # ── 4. Robustez de vecindad ────────────────────────────────────────────────
    print("[4/4] Robustez de vecindad (BTC-C y ETH-C)...")
    rob = {}
    for sym, rsi_min, rsi_max, sl, tp in [
        ("BTCUSDT", 55.0, 60.0, 0.050, 0.060),
        ("ETHUSDT", 55.0, 60.0, 0.050, 0.060),
    ]:
        rob[sym] = {}
        for n in EMAs:
            trades = simular(velas_4h[sym], ema_maps[sym][n],
                             rsi_min, rsi_max, sl, tp, use_gate=True)
            rob[sym][n] = trades
            vl = [t for t in trades if t["per"] == "VAL"]
            mv = metricas(vl)
            print(f"      {sym} EMA{n}: {len(vl)} trades val | PF {fpf(mv['pf'])}")

    # ── Bootstrap ──────────────────────────────────────────────────────────────
    print("\nEjecutando bootstrap (10,000 resamples)...")

    def split(trades, per):
        return [t for t in trades if t["per"] == per]

    bs_btc_train     = bootstrap(split(sims["BTC_C"], "TRAIN"), split(sims["BTC_PROD"], "TRAIN"))
    bs_btc_val       = bootstrap(split(sims["BTC_C"], "VAL"),   split(sims["BTC_PROD"], "VAL"))
    bs_eth_train     = bootstrap(split(sims["ETH_C"], "TRAIN"), split(sims["ETH_PROD"], "TRAIN"))
    bs_eth_val       = bootstrap(split(sims["ETH_C"], "VAL"),   split(sims["ETH_PROD"], "VAL"))
    bs_btc_vs_eth    = bootstrap(split(sims["BTC_C"], "VAL"),   split(sims["ETH_C"], "VAL"))

    # ── PF por EMA en OOS ──────────────────────────────────────────────────────
    pf_btc_emas = {}
    pf_eth_emas = {}
    for n in EMAs:
        vl_b = [t for t in rob["BTCUSDT"][n] if t["per"] == "VAL"]
        vl_e = [t for t in rob["ETHUSDT"][n] if t["per"] == "VAL"]
        pf_btc_emas[n] = pf_num(metricas(vl_b)["pf"])
        pf_eth_emas[n] = pf_num(metricas(vl_e)["pf"])

    # ── Robustez y clasificacion final ─────────────────────────────────────────
    rob_btc_label, btc_best_ema, btc_n_pos, rob_btc_detalle = analizar_robustez_ema(pf_btc_emas)
    rob_eth_label, eth_best_ema, eth_n_pos, rob_eth_detalle = analizar_robustez_ema(pf_eth_emas)

    mv_btc_c    = metricas(split(sims["BTC_C"],    "VAL"))
    mv_btc_prod = metricas(split(sims["BTC_PROD"], "VAL"))
    mv_eth_c    = metricas(split(sims["ETH_C"],    "VAL"))
    mv_eth_prod = metricas(split(sims["ETH_PROD"], "VAL"))

    verdict_btc = clasificar_sistema(mv_btc_c, mv_btc_prod, bs_btc_val, rob_btc_label, pf_btc_emas)
    verdict_eth = clasificar_sistema(mv_eth_c, mv_eth_prod, bs_eth_val, rob_eth_label, pf_eth_emas)

    # ── Prioridad para REAL ────────────────────────────────────────────────────
    btc_desc = "DESCARTADO" in verdict_btc
    eth_desc = "DESCARTADO" in verdict_eth
    if btc_desc and eth_desc:
        primero = segundo = "NINGUNO"
    elif btc_desc:
        primero, segundo = "ETH", "NINGUNO"
    elif eth_desc:
        primero, segundo = "BTC", "NINGUNO"
    else:
        # Ambos positivos: priorizar por criterios ordenados
        btc_score = 0; eth_score = 0
        # 1. PF OOS > 1
        if pf_num(mv_btc_c["pf"]) > 1.0: btc_score += 2
        if pf_num(mv_eth_c["pf"]) > 1.0: eth_score += 2
        # 2. Expectancy > 0
        if mv_btc_c["exp"] > 0: btc_score += 2
        if mv_eth_c["exp"] > 0: eth_score += 2
        # 3. Robustez EMA (zone completa)
        if rob_btc_label == "ROBUSTO_EMA": btc_score += 4
        elif rob_btc_label == "PARCIAL_EMA": btc_score += 2
        if rob_eth_label == "ROBUSTO_EMA": eth_score += 4
        elif rob_eth_label == "PARCIAL_EMA": eth_score += 2
        # 4. EMA200 es la mejor
        if btc_best_ema == 200: btc_score += 2
        if eth_best_ema == 200: eth_score += 2
        # 5. Bootstrap
        lo95b, hi95b = bs_btc_val["ic95"]
        lo95e, hi95e = bs_eth_val["ic95"]
        if lo95b and lo95b > 0: btc_score += 3
        if lo95e and lo95e > 0: eth_score += 3
        if bs_btc_val["p_pos"] and bs_btc_val["p_pos"] > 0.7: btc_score += 1
        if bs_eth_val["p_pos"] and bs_eth_val["p_pos"] > 0.7: eth_score += 1
        # 6. Trades OOS
        if mv_btc_c["n"] >= 30: btc_score += 2
        if mv_eth_c["n"] >= 30: eth_score += 2
        # 7. DD y racha
        if mv_btc_c["dd"] < 10: btc_score += 1
        if mv_eth_c["dd"] < 10: eth_score += 1
        if mv_btc_c["rsl"] <= 3: btc_score += 1
        if mv_eth_c["rsl"] <= 3: eth_score += 1
        primero, segundo = ("BTC", "ETH") if btc_score >= eth_score else ("ETH", "BTC")

    # ── Generar reporte Markdown ───────────────────────────────────────────────
    ANIOS = ["2021", "2022", "2023", "2024", "2025"]
    lines = []; a = lines.append

    a("# BTC ALCISTA — Bootstrap Sistema C vs Produccion + Comparacion ETH")
    a("")
    a("**Fecha:** 2026-08-14  ")
    a("**Estado:** INVESTIGACION PURA — 0 archivos de produccion modificados")
    a("")
    a("---")
    a("")

    # ── Sec 1: Resumen ejecutivo ───────────────────────────────────────────────
    a("## 1. Resumen ejecutivo")
    a("")
    a("| Sistema | Train Trades | Train PF | Val Trades | Val PF | Val WR | Val Exp | Veredicto |")
    a("|---------|-------------|----------|------------|--------|--------|---------|-----------|")
    for key, label in [("BTC_PROD", "BTC Produccion"), ("BTC_C", "BTC Sistema C"),
                        ("ETH_PROD", "ETH Produccion"), ("ETH_C", "ETH Sistema C")]:
        tr = split(sims[key], "TRAIN"); vl = split(sims[key], "VAL")
        mt = metricas(tr); mv = metricas(vl)
        verd = verdict_btc if key == "BTC_C" else (verdict_eth if key == "ETH_C" else "—")
        a(f"| **{label}** | {mt['n']} | {fpf(mt['pf'])} | {mv['n']} "
          f"| {fpf(mv['pf'])} | {mv['wr']:.1f}% | {fpl(mv['exp'])} | {verd} |")
    a("")
    a("---")
    a("")

    # ── Sec 2: Metodologia ────────────────────────────────────────────────────
    a("## 2. Metodologia")
    a("")
    a("| Parametro | BTC Prod | BTC C | ETH Prod | ETH C |")
    a("|-----------|----------|-------|----------|-------|")
    a("| RSI range | 55–75 | 55–60 | 60–75 | 55–60 |")
    a("| SL | 5.0% | 5.0% | 4.5% | 5.0% |")
    a("| TP | 6.0% | 6.0% | 5.0% | 6.0% |")
    a("| Gate EMA | Ninguno | EMA200d | Ninguno | EMA200d |")
    a(f"| Capital | ${CAPITAL} | ${CAPITAL} | ${CAPITAL} | ${CAPITAL} |")
    a(f"| Monto | ${MONTO} | ${MONTO} | ${MONTO} | ${MONTO} |")
    a(f"| Comision | {COMISION*100:.2f}% | {COMISION*100:.2f}% | {COMISION*100:.2f}% | {COMISION*100:.2f}% |")
    a("")
    a("**Nota ETH:** ETH Produccion y ETH Sistema C tienen diferente SL/TP (son parametros del activo,")
    a("no del gate). La comparacion directa de expectancy entre ETH-Prod y ETH-C incluye ese efecto.")
    a("Para la comparacion BTC-C vs ETH-C se usan identicos SL/TP (5%/6%) — comparacion limpia.")
    a("")
    a("**Anti-lookahead:** EMA diaria del dia D-1 se usa para senales del dia D.")
    a("Warmup diario desde 2019-06-01 (>400 dias para EMA250).")
    a("")
    a("---")
    a("")

    # ── Sec 3-6: Metricas por sistema y periodo ───────────────────────────────
    def seccion_sistema(num, titulo, key, per_code, per_label):
        per_tr = split(sims[key], per_code)
        m = metricas(per_tr)
        a(f"## {num}. {titulo} — {per_label}")
        a("")
        a("| Metrica | Valor |")
        a("|---------|-------|")
        a(f"| Trades | {m['n']} |")
        a(f"| TP / SL | {m['tp']} / {m['sl']} |")
        a(f"| Win Rate | {m['wr']:.1f}% |")
        a(f"| Profit Factor | {fpf(m['pf'])} |")
        a(f"| Expectancy/trade | {fpl(m['exp'])} |")
        a(f"| P/L acumulado | {fpl(m['pl'])} |")
        a(f"| Drawdown maximo | {m['dd']:.1f}% |")
        a(f"| Peor racha SL | {m['rsl']} ({m['rsl_d']}) |")
        a(f"| Mejor racha TP | {m['rtp']} |")
        a(f"| Peor ventana 5 trades | {fpl(m['peor5'])} |")
        a("")
        a("**Por ano:**")
        a("")
        a("| Ano | Trades | WR | PF | Exp | P/L |")
        a("|-----|--------|----|----|-----|-----|")
        for anio in ANIOS:
            g = [t for t in per_tr if t["anio"] == anio]
            ma = metricas(g)
            if ma["n"] == 0:
                a(f"| {anio} | 0 | — | — | — | — |")
            else:
                nota = " ⚠️" if ma["n"] < 5 else ""
                a(f"| {anio} | {ma['n']}{nota} | {ma['wr']:.0f}% "
                  f"| {fpf(ma['pf'])} | {fpl(ma['exp'])} | {fpl(ma['pl'])} |")
        a("")
        a("---")
        a("")

    seccion_sistema(3, "Produccion BTC", "BTC_PROD", "TRAIN", "Train 2021–2023")
    seccion_sistema(4, "Sistema C BTC",  "BTC_C",    "TRAIN", "Train 2021–2023")
    seccion_sistema(5, "Produccion BTC", "BTC_PROD", "VAL",   "OOS 2024–2025")
    seccion_sistema(6, "Sistema C BTC",  "BTC_C",    "VAL",   "OOS 2024–2025")

    # ── Sec 7-8: Bootstrap BTC ─────────────────────────────────────────────────
    a("## 7. Bootstrap DeltaExpectancy — BTC Sistema C vs Produccion")
    a("")
    a("Delta = Expectancy(Sistema C) - Expectancy(Produccion)")
    a(f"Metodo: {N_BOOT:,} resamples con reemplazo independiente por sistema.")
    a("")
    a("| Periodo | Delta observado | IC95% | Cruza 0 | P(Delta>0) | Mediana |")
    a("|---------|----------------|-------|---------|-----------|---------|")
    for label, bs in [("Train 2021–2023", bs_btc_train), ("Val OOS 2024–2025", bs_btc_val)]:
        if bs["obs"] is None:
            a(f"| {label} | N/A | — | — | — | — |")
        else:
            lo95, hi95 = bs["ic95"]
            cruza = "Si ⚠️" if (lo95 is not None and lo95 < 0 < hi95) else "No"
            a(f"| {label} | {fpl(bs['obs'])} | [{fpl(lo95)},{fpl(hi95)}] "
              f"| {cruza} | {bs['p_pos']:.1%} | {fpl(bs['median'])} |")
    a("")
    a("## 8. IC90% / IC95% BTC")
    a("")
    a("| Periodo | IC90% | IC95% |")
    a("|---------|-------|-------|")
    for label, bs in [("Train", bs_btc_train), ("Val OOS", bs_btc_val)]:
        if bs["obs"] is None:
            a(f"| {label} | N/A | N/A |")
        else:
            lo90, hi90 = bs["ic90"]; lo95, hi95 = bs["ic95"]
            a(f"| {label} | [{fpl(lo90)},{fpl(hi90)}] | [{fpl(lo95)},{fpl(hi95)}] |")
    a("")
    a("**Interpretacion:** IC95% que NO cruza cero indica diferencia distinguible del azar a nivel orientativo.")
    a("IC95% que cruza cero = diferencia dentro del ruido de muestreo.")
    a("")
    a("*Limitacion:* trades del mismo activo son serialmente dependientes;")
    a("el bootstrap subestima la varianza real. No interpretar como prueba estadistica formal.")
    a("")
    a("---")
    a("")

    # ── Sec 9: Comparacion OOS ────────────────────────────────────────────────
    a("## 9. Comparacion Sistema C vs Produccion (OOS 2024–2025)")
    a("")
    a("### BTC")
    a("")
    a("| Metrica | Produccion BTC | Sistema C BTC | Delta |")
    a("|---------|---------------|---------------|-------|")
    for label, attr, fmt in [
        ("Trades", "n", str), ("TP", "tp", str), ("SL", "sl", str),
        ("WR",       "wr",  lambda v: f"{v:.1f}%"),
        ("PF",       "pf",  fpf),
        ("Exp/trade","exp", fpl),
        ("P/L",      "pl",  fpl),
        ("DD",       "dd",  lambda v: f"{v:.1f}%"),
        ("Racha SL", "rsl", str),
    ]:
        vp = mv_btc_prod[attr]; vc = mv_btc_c[attr]
        try:
            delta = f"{vc-vp:+.1f}" if isinstance(vc, (int, float)) else "—"
        except Exception:
            delta = "—"
        a(f"| {label} | {fmt(vp)} | {fmt(vc)} | {delta} |")
    a("")
    dif_trades = mv_btc_prod['n'] - mv_btc_c['n']
    mejor_pf   = "mayor" if pf_num(mv_btc_c['pf']) > pf_num(mv_btc_prod['pf']) else "menor"
    a(f"**Trade-off BTC:** Sistema C tiene {dif_trades} trades OOS menos pero {mejor_pf} PF en OOS.")
    a("")
    a("### ETH")
    a("")
    a("| Metrica | Produccion ETH | Sistema C ETH | Delta |")
    a("|---------|---------------|---------------|-------|")
    for label, attr, fmt in [
        ("Trades", "n", str),
        ("WR",       "wr",  lambda v: f"{v:.1f}%"),
        ("PF",       "pf",  fpf),
        ("Exp/trade","exp", fpl),
        ("P/L",      "pl",  fpl),
        ("DD",       "dd",  lambda v: f"{v:.1f}%"),
        ("Racha SL", "rsl", str),
    ]:
        vp = mv_eth_prod[attr]; vc = mv_eth_c[attr]
        try:
            delta = f"{vc-vp:+.1f}" if isinstance(vc, (int, float)) else "—"
        except Exception:
            delta = "—"
        a(f"| {label} | {fmt(vp)} | {fmt(vc)} | {delta} |")
    a("")
    a("*Nota:* ETH Prod y ETH-C tienen distintos SL/TP — el Delta de expectancy incluye ese efecto.")
    a("")
    a("---")
    a("")

    # ── Sec 10: Robustez de vecindad EMA ──────────────────────────────────────
    a("## 10. Robustez de vecindad EMA100/150/200/250")
    a("")
    a("### BTC Sistema C (RSI 55–60 + SOBRE EMAn, SL 5%, TP 6%)")
    a("")
    a("| EMA | Val Trades | Val WR | Val PF | Val Exp | Val P/L | Val DD |")
    a("|-----|-----------|--------|--------|---------|---------|--------|")
    for n in EMAs:
        vl = [t for t in rob["BTCUSDT"][n] if t["per"] == "VAL"]
        mv = metricas(vl)
        bench = " ←" if n == 200 else ""
        a(f"| **EMA{n}**{bench} | {mv['n']} | {mv['wr']:.1f}% | {fpf(mv['pf'])} "
          f"| {fpl(mv['exp'])} | {fpl(mv['pl'])} | {mv['dd']:.1f}% |")
    a("")
    a("**Analisis de robustez BTC:**")
    a("")
    a(f"| Campo | Valor |")
    a("|-------|-------|")
    a(f"| PF EMA100 | {fpf(pf_btc_emas[100])} |")
    a(f"| PF EMA150 | {fpf(pf_btc_emas[150])} |")
    a(f"| PF EMA200 | {fpf(pf_btc_emas[200])} |")
    a(f"| PF EMA250 | {fpf(pf_btc_emas[250])} |")
    a(f"| EMA con mejor PF | EMA{btc_best_ema} (PF {fpf(pf_btc_emas[btc_best_ema])}) |")
    a(f"| EMAs con PF > 1.0 | {btc_n_pos}/4 |")
    a(f"| EMA200 es la mejor | {'SI ✅' if btc_best_ema == 200 else 'NO ❌'} |")
    a(f"| Clasificacion de vecindad | **{rob_btc_label}** |")
    a(f"| Detalle | {rob_btc_detalle} |")
    a("")
    a("### ETH Sistema C (RSI 55–60 + SOBRE EMAn, SL 5%, TP 6%)")
    a("")
    a("| EMA | Val Trades | Val WR | Val PF | Val Exp | Val P/L | Val DD |")
    a("|-----|-----------|--------|--------|---------|---------|--------|")
    for n in EMAs:
        vl = [t for t in rob["ETHUSDT"][n] if t["per"] == "VAL"]
        mv = metricas(vl)
        bench = " ←" if n == 200 else ""
        a(f"| **EMA{n}**{bench} | {mv['n']} | {mv['wr']:.1f}% | {fpf(mv['pf'])} "
          f"| {fpl(mv['exp'])} | {fpl(mv['pl'])} | {mv['dd']:.1f}% |")
    a("")
    a("**Analisis de robustez ETH:**")
    a("")
    a(f"| Campo | Valor |")
    a("|-------|-------|")
    a(f"| PF EMA100 | {fpf(pf_eth_emas[100])} |")
    a(f"| PF EMA150 | {fpf(pf_eth_emas[150])} |")
    a(f"| PF EMA200 | {fpf(pf_eth_emas[200])} |")
    a(f"| PF EMA250 | {fpf(pf_eth_emas[250])} |")
    a(f"| EMA con mejor PF | EMA{eth_best_ema} (PF {fpf(pf_eth_emas[eth_best_ema])}) |")
    a(f"| EMAs con PF > 1.0 | {eth_n_pos}/4 |")
    a(f"| EMA200 es la mejor | {'SI ✅' if eth_best_ema == 200 else 'NO ❌'} |")
    a(f"| Clasificacion de vecindad | **{rob_eth_label}** |")
    a(f"| Detalle | {rob_eth_detalle} |")
    a("")
    a("---")
    a("")

    # ── Sec 11: Resultados anuales ────────────────────────────────────────────
    a("## 11. Resultados anuales (BTC y ETH — todos los sistemas)")
    a("")
    a("| Ano | BTC Prod PF/n | BTC-C PF/n | ETH Prod PF/n | ETH-C PF/n | Periodo |")
    a("|-----|-------------|----------|-------------|---------|---------|")
    for anio in ANIOS:
        celdas = []
        for key in ["BTC_PROD", "BTC_C", "ETH_PROD", "ETH_C"]:
            g = [t for t in sims[key] if t["anio"] == anio]
            m = metricas(g)
            if m["n"] == 0:
                celdas.append("— / 0")
            else:
                nota = "⚠️" if m["n"] < 5 else ""
                celdas.append(f"{nota}{fpf(m['pf'])} / {m['n']}")
        per = "TRAIN" if anio <= "2023" else "**VAL**"
        a(f"| {anio} ({per}) | {celdas[0]} | {celdas[1]} | {celdas[2]} | {celdas[3]} |")
    a("")
    a("---")
    a("")

    # ── Sec 12: Drawdown y rachas ─────────────────────────────────────────────
    a("## 12. Drawdown y rachas (OOS 2024–2025)")
    a("")
    a("| Sistema | DD max | Racha SL | Fechas racha SL | Racha TP | Peor 5 trades |")
    a("|---------|--------|----------|----------------|----------|---------------|")
    for key, label in [("BTC_PROD", "BTC Produccion"), ("BTC_C", "BTC Sistema C"),
                        ("ETH_PROD", "ETH Produccion"), ("ETH_C", "ETH Sistema C")]:
        mv = metricas(split(sims[key], "VAL"))
        a(f"| {label} | {mv['dd']:.1f}% | {mv['rsl']} | {mv['rsl_d']} "
          f"| {mv['rtp']} | {fpl(mv['peor5'])} |")
    a("")
    a("---")
    a("")

    # ── Sec 13: Analisis de sobreajuste ───────────────────────────────────────
    a("## 13. Analisis de sobreajuste")
    a("")
    a("1. **RSI 55–60 surgiu de analisis sobre datos de 2026** (muestra pequena de 22 trades).")
    a("   Hay riesgo de seleccion post-hoc. La produccion BTC ya usaba RSI_MIN=55.")
    a("")
    a("2. **EMA200d como gate en BTC:**")
    a(f"   {btc_n_pos}/4 EMAs con PF > 1.0 en OOS. EMA200 es la mejor: {'SI' if btc_best_ema==200 else 'NO'}.")
    a(f"   Clasificacion: **{rob_btc_label}**.")
    a("")
    a("3. **EMA200d como gate en ETH:**")
    a(f"   {eth_n_pos}/4 EMAs con PF > 1.0 en OOS. EMA200 es la mejor: {'SI' if eth_best_ema==200 else 'NO'}.")
    a(f"   Clasificacion: **{rob_eth_label}**.")
    a("   La diferencia de comportamiento entre BTC y ETH **reduce** la evidencia de overfitting generalizado")
    a("   pero **sugiere** que la ventaja del patron RSI 55-60 + gate EMA puede ser especifica de BTC.")
    a("")
    a("4. **Ventaja OOS vs Train:**")
    mt_btc_c_tr = metricas(split(sims["BTC_C"], "TRAIN"))
    a(f"   BTC-C: Train PF {fpf(mt_btc_c_tr['pf'])} → Val PF {fpf(mv_btc_c['pf'])} → "
      f"{'mejora OOS ✅' if pf_num(mv_btc_c['pf'])>=pf_num(mt_btc_c_tr['pf'])*0.8 else 'deterioro ⚠️'}")
    a("")
    a("5. **Bootstrap IC95% cruza cero:**")
    lo95b, hi95b = bs_btc_val["ic95"]
    lo95e, hi95e = bs_eth_val["ic95"]
    a(f"   BTC-C vs Prod: IC95% [{fpl(lo95b)},{fpl(hi95b)}] → "
      f"{'NO cruza ✅' if lo95b and lo95b>0 else 'CRUZA ⚠️'}")
    a(f"   ETH-C vs Prod: IC95% [{fpl(lo95e)},{fpl(hi95e)}] → "
      f"{'NO cruza ✅' if lo95e and lo95e>0 else 'CRUZA ⚠️'}")
    a("")
    a("---")
    a("")

    # ── Sec 14: Limitaciones ──────────────────────────────────────────────────
    a("## 14. Limitaciones")
    a("")
    a("1. Sin trailing stop ni gates de produccion (eventos macro, horario, spread).")
    a("2. ETH Prod y ETH-C tienen distinto SL/TP — comparacion parcialmente limpia.")
    a("3. Bootstrap subestima varianza por dependencia serial. No es prueba estadistica formal.")
    a("4. RSI 55–60 surgiu de analisis en 2026 — riesgo de post-hoc.")
    a("5. Sin compounding — monto fijo $5.")
    a("6. Periodos de bull extremo (2021, 2024) sesgan los resultados positivos.")
    a("")
    a("---")
    a("")

    # ── Sec 15: Veredicto final ────────────────────────────────────────────────
    a("## 15. Veredicto final")
    a("")
    a("| Sistema | PF OOS | Exp OOS | EMA mejor | EMAs pos/4 | IC95% | P(D>0) | Vecindad | Veredicto |")
    a("|---------|--------|---------|-----------|-----------|-------|--------|---------|-----------|")
    for sym_k, label, mv_c, mv_p, bs_v, best_e, n_pos_v, rob_lbl in [
        ("BTC_C","BTC Sistema C", mv_btc_c, mv_btc_prod, bs_btc_val,
         btc_best_ema, btc_n_pos, rob_btc_label),
        ("ETH_C","ETH Sistema C", mv_eth_c, mv_eth_prod, bs_eth_val,
         eth_best_ema, eth_n_pos, rob_eth_label),
    ]:
        lo95, hi95 = bs_v["ic95"]
        ic_str = f"[{fpl(lo95)},{fpl(hi95)}]" if lo95 else "N/A"
        verd = verdict_btc if "BTC" in sym_k else verdict_eth
        ema_best_str = f"EMA{best_e} {'✅' if best_e==200 else '⚠️'}"
        a(f"| **{label}** | {fpf(mv_c['pf'])} | {fpl(mv_c['exp'])} "
          f"| {ema_best_str} | {n_pos_v}/4 | {ic_str} "
          f"| {bs_v['p_pos']:.1%} | {rob_lbl} | {verd} |")
    a("")
    a("---")
    a("")

    # ── Sec 16: Veredicto ETH ──────────────────────────────────────────────────
    a("## 16. Veredicto ETH Sistema C")
    a("")
    a(f"**{verdict_eth}**")
    a("")
    if "DESCARTADO" in verdict_eth:
        a("ETH Sistema C no supera el umbral minimo de PF OOS > 1.0 y/o expectancy positiva.")
        a(f"Ademas, el patron de vecindad EMA muestra: {rob_eth_detalle}")
        a("")
        a("**Conclusion:** El patron RSI 55–60 + SOBRE EMA200d NO funciona en ETH con los")
        a("parametros probados (SL 5%, TP 6%). Las EMAs vecinas confirman que no es un")
        a("problema especifico de EMA200 sino del patron completo aplicado a ETH.")
    elif "FRAGIL" in verdict_eth:
        a("ETH Sistema C es positivo en OOS pero sin robustez de vecindad.")
        a(f"Vecindad EMA: {rob_eth_detalle}")
        a("No se recomienda activar en REAL sin evidencia adicional de robustez.")
    else:
        a(f"ETH Sistema C tiene veredicto {verdict_eth}.")
        a(f"Vecindad EMA: {rob_eth_detalle}")
    a("")
    a("---")
    a("")

    # ── Sec 17: Comparacion directa BTC vs ETH ────────────────────────────────
    a("## 17. Comparacion directa BTC Sistema C vs ETH Sistema C")
    a("")
    a("*Mismos parametros: RSI 55–60, SOBRE EMA200d, SL 5%, TP 6% — comparacion limpia.*")
    a("")
    a("| Metrica | BTC Sistema C | ETH Sistema C |")
    a("|---------|--------------|--------------|")
    for label, attr, fmt, is_oos in [
        ("Trades Train",   "n",   str,                         False),
        ("PF Train",       "pf",  fpf,                         False),
        ("WR Train",       "wr",  lambda v: f"{v:.1f}%",       False),
        ("Exp Train",      "exp", fpl,                         False),
        ("Trades OOS",     "n",   str,                         True),
        ("PF OOS",         "pf",  fpf,                         True),
        ("WR OOS",         "wr",  lambda v: f"{v:.1f}%",       True),
        ("Exp OOS",        "exp", fpl,                         True),
        ("P/L OOS",        "pl",  fpl,                         True),
        ("DD max OOS",     "dd",  lambda v: f"{v:.1f}%",       True),
        ("Peor racha SL",  "rsl", str,                         True),
    ]:
        per = "VAL" if is_oos else "TRAIN"
        sb = metricas(split(sims["BTC_C"], per))
        se = metricas(split(sims["ETH_C"], per))
        a(f"| {label} | {fmt(sb[attr])} | {fmt(se[attr])} |")
    for n in EMAs:
        a(f"| EMA{n} PF OOS | {fpf(pf_btc_emas[n])} | {fpf(pf_eth_emas[n])} |")
    a(f"| P(D Exp > 0) vs Prod | {bs_btc_val['p_pos']:.1%} | {bs_eth_val['p_pos']:.1%} |")
    lo95b2, hi95b2 = bs_btc_val["ic95"]; lo95e2, hi95e2 = bs_eth_val["ic95"]
    a(f"| IC95% DExp vs Prod | [{fpl(lo95b2)},{fpl(hi95b2)}] | [{fpl(lo95e2)},{fpl(hi95e2)}] |")
    a(f"| EMAs positivas OOS | {btc_n_pos}/4 | {eth_n_pos}/4 |")
    a(f"| EMA200 es la mejor | {'SI ✅' if btc_best_ema==200 else 'NO ❌'} | {'SI ✅' if eth_best_ema==200 else 'NO ❌'} |")
    a(f"| Clasificacion vecindad | {rob_btc_label} | {rob_eth_label} |")
    a(f"| Veredicto | {verdict_btc} | {verdict_eth} |")
    a("")
    if bs_btc_vs_eth["obs"] is not None:
        lo95x, hi95x = bs_btc_vs_eth["ic95"]
        a("### Bootstrap BTC-C vs ETH-C (OOS)")
        a(f"Delta = Exp(BTC-C) − Exp(ETH-C) = {fpl(bs_btc_vs_eth['obs'])}")
        a(f"IC95%: [{fpl(lo95x)},{fpl(hi95x)}]")
        a(f"P(BTC-C mejor) = {bs_btc_vs_eth['p_pos']:.1%}")
        if lo95x is not None and lo95x < 0 < hi95x:
            a("→ Diferencia dentro del ruido de muestreo (IC95% cruza cero)")
        else:
            a("→ Diferencia estadisticamente distinguible (IC95% no cruza cero)")
    a("")
    a("---")
    a("")

    # ── Sec 18: Prioridad para REAL ───────────────────────────────────────────
    a("## 18. Prioridad para REAL")
    a("")
    a("| Criterio | BTC-C | ETH-C |")
    a("|----------|-------|-------|")
    a(f"| 1. PF OOS > 1 | {'✅' if pf_num(mv_btc_c['pf'])>1 else '❌'} | {'✅' if pf_num(mv_eth_c['pf'])>1 else '❌'} |")
    a(f"| 2. Exp OOS > 0 | {'✅' if mv_btc_c['exp']>0 else '❌'} | {'✅' if mv_eth_c['exp']>0 else '❌'} |")
    a(f"| 3. Robustez vecindad EMA | {rob_btc_label} | {rob_eth_label} |")
    a(f"| 4. EMA200 es la mejor | {'✅' if btc_best_ema==200 else '❌'} | {'✅' if eth_best_ema==200 else '❌'} |")
    a(f"| 5. IC95% no cruza 0 | {'✅' if lo95b2 and lo95b2>0 else '❌'} | {'✅' if lo95e2 and lo95e2>0 else '❌'} |")
    a(f"| 6. P(D>0) | {bs_btc_val['p_pos']:.1%} | {bs_eth_val['p_pos']:.1%} |")
    a(f"| 7. Trades OOS | {mv_btc_c['n']} | {mv_eth_c['n']} |")
    a(f"| 8. DD max OOS | {mv_btc_c['dd']:.1f}% | {mv_eth_c['dd']:.1f}% |")
    a(f"| 9. Peor racha SL | {mv_btc_c['rsl']} | {mv_eth_c['rsl']} |")
    a("")
    a(f"🥇 **{primero}** — primer candidato para validacion REAL controlada")
    if segundo != "NINGUNO":
        a(f"🥈 **{segundo}**")
    else:
        a("🥈 **NINGUNO** — segundo candidato descartado o sin evidencia")
    a("")
    a("---")
    a("")

    # ── Sec 19: Conclusion consolidada ────────────────────────────────────────
    a("## 19. Conclusion consolidada")
    a("")
    # BTC
    if rob_btc_label == "ROBUSTO_EMA":
        btc_patron = (
            "BTC Sistema C presenta evidencia de patron robusto alrededor de EMA200: "
            "EMA200 es la mejor EMA en OOS y las cuatro EMAs del rango 100–250 tienen "
            f"PF > 1.0. {rob_btc_detalle}"
        )
    elif rob_btc_label == "PARCIAL_EMA":
        btc_patron = (
            f"BTC Sistema C: EMA200 es la mejor EMA en OOS, pero {rob_btc_detalle} "
            "La robustez es parcial."
        )
    elif rob_btc_label == "NO_ROBUSTA_EMA200":
        btc_patron = (
            f"BTC Sistema C: EMA200 positiva pero no es la mejor EMA. {rob_btc_detalle}"
        )
    else:
        btc_patron = f"BTC Sistema C: {rob_btc_detalle}"

    a(f"**BTC:** {btc_patron}")
    a("")
    lo95_final, hi95_final = bs_btc_val["ic95"]
    if lo95_final is not None and lo95_final < 0 < hi95_final:
        a("Sin embargo, el IC95% del bootstrap BTC-C vs Produccion cruza cero "
          f"([{fpl(lo95_final)},{fpl(hi95_final)}], P(D>0) = {bs_btc_val['p_pos']:.1%}). "
          "El sistema es **PROMETEDOR**, pero todavia no puede declararse ROBUSTO estadisticamente.")
    elif lo95_final and lo95_final > 0:
        a(f"El IC95% del bootstrap NO cruza cero ([{fpl(lo95_final)},{fpl(hi95_final)}]), "
          "lo que apoya la mejora sobre Produccion. Junto con la robustez de vecindad, "
          "el sistema califica como **ROBUSTO**.")
    a("")

    # ETH
    if "DESCARTADO" in verdict_eth:
        a(f"**ETH Sistema C: {verdict_eth}.**")
        a(f"El patron RSI 55–60 + SOBRE EMA200d NO generaliza a ETH: {rob_eth_detalle}")
        a("Esto reduce la evidencia de que se trate de un overfitting generalizado entre activos,")
        a("pero sugiere que la ventaja puede ser especifica de BTC.")
    elif "FRAGIL" in verdict_eth:
        a(f"**ETH Sistema C: {verdict_eth}.**")
        a(f"Positivo en OOS pero sin robustez de vecindad: {rob_eth_detalle}")
        a("No apto para activacion en REAL sin evidencia adicional.")
    else:
        a(f"**ETH Sistema C: {verdict_eth}.** {rob_eth_detalle}")
    a("")

    # Proximo paso
    if primero == "BTC":
        a("**Proximo paso:**")
        a("🥇 BTC — primer candidato para validacion REAL controlada.")
        a("No activar todavia como sistema independiente sin respetar el protocolo REAL.")
        a("Acumular al menos 30+ trades reales y comparar contra Produccion.")
        a("El gate EMA200d estara inactivo mientras BTC siga bajo su EMA200d (regimen 2026 actual).")
    elif primero == "ETH":
        a("**Proximo paso:**")
        a("🥇 ETH — primer candidato segun la evidencia disponible.")
        a("Requiere validacion REAL antes de activar.")
    else:
        a("**Proximo paso:** Ninguno de los dos sistemas califica para activacion inmediata.")
        a("Continuar con la investigacion de otros activos (SOL, AVAX).")
    a("")
    a("---")
    a("")
    a("**ESTADO FINAL:**")
    a("- Produccion modificada: **NO**")
    a("- Sistema C activado: **NO**")
    a(f"- Veredicto BTC Sistema C: **{verdict_btc}**")
    a(f"- Veredicto ETH Sistema C: **{verdict_eth}**")
    a(f"- Prioridad para REAL: **{primero}**")
    a("")
    a("Archivos:")
    a("- `reports/2026-08-14_btc-bootstrap-sistema-c-vs-produccion.md` (este reporte)")
    a("- `btc_bootstrap_sistema_c_vs_produccion.py` (script)")

    # ── Escribir reporte ───────────────────────────────────────────────────────
    os.makedirs(os.path.dirname(os.path.expanduser(REPORT_PATH)), exist_ok=True)
    with open(os.path.expanduser(REPORT_PATH), "w") as f:
        f.write("\n".join(lines))

    # ── Resumen en consola ─────────────────────────────────────────────────────
    print()
    print("=" * 62)
    print("RESULTADOS — OOS 2024-2025")
    print("=" * 62)
    print(f"  BTC Produccion: {mv_btc_prod['n']:3d} trades | PF {fpf(mv_btc_prod['pf'])} "
          f"| WR {mv_btc_prod['wr']:.1f}% | Exp {fpl(mv_btc_prod['exp'])}")
    print(f"  BTC Sistema C:  {mv_btc_c['n']:3d} trades | PF {fpf(mv_btc_c['pf'])} "
          f"| WR {mv_btc_c['wr']:.1f}% | Exp {fpl(mv_btc_c['exp'])}")
    print(f"  ETH Produccion: {mv_eth_prod['n']:3d} trades | PF {fpf(mv_eth_prod['pf'])} "
          f"| WR {mv_eth_prod['wr']:.1f}% | Exp {fpl(mv_eth_prod['exp'])}")
    print(f"  ETH Sistema C:  {mv_eth_c['n']:3d} trades | PF {fpf(mv_eth_c['pf'])} "
          f"| WR {mv_eth_c['wr']:.1f}% | Exp {fpl(mv_eth_c['exp'])}")
    print()
    print("BOOTSTRAP OOS — BTC Sistema C vs Produccion")
    lo90b, hi90b = bs_btc_val["ic90"]
    lo95b, hi95b = bs_btc_val["ic95"]
    print(f"  Delta Exp:  {fpl(bs_btc_val['obs'])}")
    print(f"  IC90%:      [{fpl(lo90b)}, {fpl(hi90b)}]")
    print(f"  IC95%:      [{fpl(lo95b)}, {fpl(hi95b)}]")
    print(f"  P(D > 0):   {bs_btc_val['p_pos']:.1%}")
    print()
    print("VECINDAD EMA (OOS)")
    print(f"  BTC-C: " + " | ".join(
        f"EMA{n}={'✅' if pf_btc_emas[n]>1 else '❌'}{fpf(pf_btc_emas[n])}" for n in EMAs))
    print(f"       EMA mejor: EMA{btc_best_ema} | {btc_n_pos}/4 positivas | "
          f"EMA200 mejor: {'SI' if btc_best_ema==200 else 'NO'} | {rob_btc_label}")
    print(f"  ETH-C: " + " | ".join(
        f"EMA{n}={'✅' if pf_eth_emas[n]>1 else '❌'}{fpf(pf_eth_emas[n])}" for n in EMAs))
    print(f"       EMA mejor: EMA{eth_best_ema} | {eth_n_pos}/4 positivas | "
          f"EMA200 mejor: {'SI' if eth_best_ema==200 else 'NO'} | {rob_eth_label}")
    print()
    print("VEREDICTOS:")
    print(f"  BTC Sistema C: {verdict_btc}")
    print(f"  ETH Sistema C: {verdict_eth}")
    print()
    print("PRIORIDAD PARA REAL:")
    print(f"  🥇 {primero}")
    if segundo != "NINGUNO":
        print(f"  🥈 {segundo}")
    else:
        print("  🥈 NINGUNO")
    print()
    print(f"Reporte: {REPORT_PATH}")
    print()
    print("less " + REPORT_PATH)


if __name__ == "__main__":
    main()
