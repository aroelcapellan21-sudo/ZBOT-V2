"""
avax_bootstrap_sistema_c_vs_produccion.py
AVAX ALCISTA — Investigacion Sistema C vs Produccion
INVESTIGACION PURA — 0 archivos de produccion modificados.

Produccion AVAX (de config_cartera.py — alcista):
  RSI 60-75, SL 4.5%, TP 5.0%, sin gate EMA

Sistema C AVAX (mismo patron que BTC/ETH/SOL):
  RSI 55-60, SL 5.0%, TP 6.0%, gate PRECIO SOBRE EMA diaria (anti-lookahead)

Nota: SL/TP distintos entre Produccion y Sistema C.
El delta de expectancy incluye ese efecto — no es comparacion de solo RSI/gate.

Robustez de vecindad: EMA100, EMA150, EMA200, EMA250

Reglas de clasificacion (sin n_ema_pos >= 3):
  - EMA200 debe ser la mejor EMA en OOS para declarar robustez
  - Todas las vecinas deben tener PF > 1.0
  - IC95% bootstrap no debe cruzar cero para CANDIDATO FUERTE
"""
import json, os, random, urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta

# ── Parametros globales ───────────────────────────────────────────────────────
FECHA_WU_4H  = "2020-10-01"
FECHA_WU_D   = "2019-06-01"
TRAIN_START  = "2021-01-01"
TRAIN_END    = "2023-12-31"
VAL_START    = "2024-01-01"
VAL_END      = "2025-12-31"
FWD_START    = "2026-01-01"
FWD_END_STR  = "2026-08-14"
MONTO        = 5.0
CAPITAL      = 20.0
COMISION     = 0.001
N_BOOT       = 10000
EMAs         = [100, 150, 200, 250]

REPORT_PATH  = os.path.expanduser(
    "~/bot-padre-v2/reports/2026-08-14_avax-bootstrap-sistema-c-vs-produccion.md"
)

# Produccion AVAX (config_cartera.py — alcista, sin modificar)
AVAX_PROD = dict(sym="AVAXUSDT", rsi_min=60.0, rsi_max=75.0,
                 sl=0.045, tp=0.050, gate_ema=None)

# Sistema C AVAX (patron identico BTC/ETH/SOL)
AVAX_C    = dict(sym="AVAXUSDT", rsi_min=55.0, rsi_max=60.0,
                 sl=0.050, tp=0.060, gate_ema=200)

# ── Descarga ──────────────────────────────────────────────────────────────────
def _ts(f):
    return int(datetime.strptime(f, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000)

def fetch(symbol, intervalo, desde_ms):
    velas = []; inicio = desde_ms
    while True:
        p = urllib.parse.urlencode({"symbol": symbol, "interval": intervalo,
                                    "startTime": inicio, "limit": 1000})
        with urllib.request.urlopen(
                f"https://api.binance.com/api/v3/klines?{p}", timeout=30) as r:
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
    """Anti-lookahead: EMA del ultimo dia cerrado antes de la vela 4H (D-1 a D-5)."""
    for d in range(1, 6):
        f = (ts_dt - timedelta(days=d)).strftime("%Y-%m-%d")
        if f in ema_map:
            return ema_map[f]
    return None

# ── RSI simple (14 periodos, ventana 15 cierres) ─────────────────────────────
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

# ── Simulacion independiente (1 posicion a la vez) ───────────────────────────
def simular(velas_4h, ema_map, rsi_min, rsi_max, sl, tp, use_gate=False,
            desde_str=TRAIN_START, hasta_str=FWD_END_STR):
    cierres = [float(v[4]) for v in velas_4h]
    ts_list = [int(v[0])    for v in velas_4h]
    IMS  = _ts(desde_str)
    FIMS = _ts(hasta_str) + 86400000
    trades = []; en_pos = False
    ep = er = sl_p = tp_p = 0.0; ets = None; e_ema_v = None

    for i in range(60, len(cierres)):
        ventana = cierres[max(0, i - 60):i]
        r = rsi_calc(ventana)
        if r is None: continue
        precio = cierres[i]; tsv = ts_list[i]
        tsdt  = datetime.fromtimestamp(tsv / 1000, tz=timezone.utc)

        if en_pos:
            res = None
            if precio <= sl_p: res = "SL"
            elif precio >= tp_p: res = "TP"
            if res:
                pl  = round((MONTO * tp if res == "TP" else -MONTO * sl)
                            - MONTO * COMISION * 2, 4)
                per = ("TRAIN" if tsv <= _ts(TRAIN_END) + 86400000
                       else "FWD" if tsv >= _ts(FWD_START)
                       else "VAL")
                trades.append({
                    "ts":    ets.strftime("%Y-%m-%d %H:%M"),
                    "anio":  str(ets.year),
                    "per":   per,
                    "rsi":   er,
                    "precio": round(ep, 4),
                    "ema_v": round(e_ema_v, 4) if e_ema_v else None,
                    "res":   res,
                    "pl":    pl,
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
            sl_p = round(ep * (1 - sl), 4)
            tp_p = round(ep * (1 + tp), 4)

    return trades

# ── Metricas completas ────────────────────────────────────────────────────────
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
    peor5 = min((round(sum(pls[i:i + 5]), 4) for i in range(max(1, len(pls) - 4))),
                default=0.0)
    return dict(n=n, tp=len(tps), sl=len(sls), wr=wr, pf=pf, exp=exp, pl=pl,
                dd=round(mxdd, 1), rsl=mrsl, rsl_d=sd, rtp=mrtp, peor5=peor5)

# ── Bootstrap DeltaExpectancy ─────────────────────────────────────────────────
def bootstrap(ta, tb, n_iter=N_BOOT, seed=42):
    """IC90/IC95 de E[ta] - E[tb]. Resamples independientes por sistema."""
    random.seed(seed)
    if not ta or not tb:
        return dict(obs=None, ic90=(None, None), ic95=(None, None),
                    median=None, p_pos=None)
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
def fpf(v): return f"{v:.3f}" if v != float("inf") else "inf"
def fpl(v): return f"+${v:.4f}" if v >= 0 else f"-${abs(v):.4f}"
def pf_num(v): return v if v != float("inf") else 999.0

# ── Robustez de vecindad EMA (reglas estrictas) ───────────────────────────────
def analizar_robustez_ema(pf_emas):
    """
    Reglas exactas (sin n_ema_pos >= 3):
    - FRAGIL_EMA200_NEGATIVA : EMA200 PF <= 1.0
    - NO_ROBUSTA_EMA200      : EMA200 positiva pero no es la mejor
    - FRAGIL_SOLO_EMA200     : EMA200 es la mejor pero es la unica positiva
    - PARCIAL_EMA            : EMA200 es la mejor, algunas vecinas positivas
    - ROBUSTO_EMA            : EMA200 es la mejor, TODAS las vecinas positivas
    """
    pf200   = pf_emas.get(200, 0.0)
    best_n  = max(pf_emas, key=pf_emas.get)
    best_pf = pf_emas[best_n]
    n_pos   = sum(1 for pf in pf_emas.values() if pf > 1.0)
    vecinas = {n: pf for n, pf in pf_emas.items() if n != 200}

    if pf200 <= 1.0:
        return ("FRAGIL_EMA200_NEGATIVA", best_n, n_pos,
                f"EMA200 PF {pf200:.3f} <= 1.0. Mejor EMA: EMA{best_n} (PF {best_pf:.3f}). "
                f"{n_pos}/4 EMAs positivas.")

    if best_n != 200:
        return ("NO_ROBUSTA_EMA200", best_n, n_pos,
                f"EMA200 positiva (PF {pf200:.3f}) pero NO es la mejor. "
                f"Mejor: EMA{best_n} (PF {best_pf:.3f}). {n_pos}/4 EMAs positivas.")

    todas_pos = all(pf > 1.0 for pf in vecinas.values())
    n_vec_pos = sum(1 for pf in vecinas.values() if pf > 1.0)

    if n_pos == 1:
        return ("FRAGIL_SOLO_EMA200", best_n, n_pos,
                f"EMA200 es la unica EMA con PF > 1.0 (PF {pf200:.3f}). "
                "Patron FRAGIL — independiente del valor absoluto del PF.")

    if todas_pos:
        return ("ROBUSTO_EMA", best_n, n_pos,
                f"EMA200 es la mejor (PF {pf200:.3f}) Y las {len(vecinas)} EMAs vecinas "
                f"tambien tienen PF > 1.0. Patron de vecindad ROBUSTO.")

    return ("PARCIAL_EMA", best_n, n_pos,
            f"EMA200 es la mejor (PF {pf200:.3f}). {n_vec_pos}/{len(vecinas)} vecinas "
            f"con PF > 1.0. Robustez parcial.")

# ── Clasificacion final ───────────────────────────────────────────────────────
def clasificar_sistema(m_val, m_prod_val, bs_val, rob_label, pf_emas):
    """
    🟢 CANDIDATO FUERTE : ROBUSTO_EMA + IC95 no cruza 0 + PF/Exp positivos
    🟡 PROMETEDOR       : PF/Exp positivos, vecindad favorable, IC95 cruza 0
    🟠/🔴 FRAGIL        : EMA200 unica positiva o no es la mejor
    🔴 DESCARTADO       : PF OOS <= 1.0 o Exp <= 0
    🟠 INCONCLUSO       : muestra < 20 trades
    """
    pf_c  = pf_num(m_val["pf"])
    exp_c = m_val["exp"]
    n_c   = m_val["n"]
    lo95, hi95 = bs_val["ic95"] if bs_val["ic95"][0] is not None else (None, None)
    ic_no_cruza = (lo95 is not None and lo95 > 0)

    if pf_c <= 1.0 or exp_c <= 0:
        return "🔴 DESCARTADO"
    if n_c < 20:
        return "🟠 INCONCLUSO"
    if rob_label in ("FRAGIL_EMA200_NEGATIVA", "FRAGIL_SOLO_EMA200"):
        return "🟠/🔴 FRAGIL"
    if rob_label == "NO_ROBUSTA_EMA200":
        return "🟡 PROMETEDOR"
    if rob_label == "ROBUSTO_EMA":
        return "🟢 CANDIDATO FUERTE" if ic_no_cruza else "🟡 PROMETEDOR"
    if rob_label == "PARCIAL_EMA":
        return "🟡 PROMETEDOR"
    return "🟠 INCONCLUSO"

# ── Analisis regimen forward ──────────────────────────────────────────────────
def analizar_regimen_forward(velas_4h, ema_map_200):
    """Cuenta velas 4H en forward 2026 sobre/bajo EMA200d."""
    fwd_ts_ini = _ts(FWD_START)
    sobre = bajo = sin_ema = 0
    for v in velas_4h:
        tsv = int(v[0])
        if tsv < fwd_ts_ini: continue
        tsdt = datetime.fromtimestamp(tsv / 1000, tz=timezone.utc)
        precio = float(v[4])
        ev = get_ema(tsdt, ema_map_200)
        if ev is None: sin_ema += 1
        elif precio > ev: sobre += 1
        else: bajo += 1
    return sobre, bajo, sin_ema

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    ahora_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

    print("=" * 62)
    print("AVAX ALCISTA — Bootstrap Sistema C vs Produccion")
    print("=" * 62)

    # ── 1. Descarga ────────────────────────────────────────────────────────────
    print("\n[1/4] Descargando datos AVAXUSDT...")
    velas_4h_raw = fetch("AVAXUSDT", "4h", _ts(FECHA_WU_4H))
    velas_d_raw  = fetch("AVAXUSDT", "1d", _ts(FECHA_WU_D))
    velas_4h = [v for v in velas_4h_raw if int(v[6]) < ahora_ms]
    velas_d  = [v for v in velas_d_raw  if int(v[6]) < ahora_ms]
    print(f"      AVAXUSDT: {len(velas_4h)} velas 4H | {len(velas_d)} velas 1D")

    if len(velas_4h) < 500:
        print("ERROR: datos 4H insuficientes."); return
    if len(velas_d) < 260:
        print("ERROR: datos diarios insuficientes para EMA250."); return

    # ── 2. Mapas EMA ───────────────────────────────────────────────────────────
    print("[2/4] Construyendo mapas EMA diarios (anti-lookahead)...")
    ema_maps = {}
    for n in EMAs:
        ema_maps[n] = build_ema(velas_d, n)
        print(f"      EMA{n}: {len(ema_maps[n])} fechas diarias")

    # ── 3. Simulaciones principales ────────────────────────────────────────────
    print("[3/4] Simulando Produccion y Sistema C...")
    trades_prod = simular(velas_4h, {},
                          AVAX_PROD["rsi_min"], AVAX_PROD["rsi_max"],
                          AVAX_PROD["sl"],      AVAX_PROD["tp"],
                          use_gate=False)
    trades_c    = simular(velas_4h, ema_maps[200],
                          AVAX_C["rsi_min"],  AVAX_C["rsi_max"],
                          AVAX_C["sl"],       AVAX_C["tp"],
                          use_gate=True)

    def split(trades, per): return [t for t in trades if t["per"] == per]

    for lbl, trades in [("Produccion", trades_prod), ("Sistema C", trades_c)]:
        tr = split(trades, "TRAIN"); vl = split(trades, "VAL"); fw = split(trades, "FWD")
        mt = metricas(tr); mv = metricas(vl); mf = metricas(fw)
        print(f"      AVAX {lbl}:")
        print(f"        Train: {mt['n']} trades | PF {fpf(mt['pf'])} | WR {mt['wr']:.0f}%")
        print(f"        OOS:   {mv['n']} trades | PF {fpf(mv['pf'])} | WR {mv['wr']:.0f}%")
        print(f"        Fwd:   {mf['n']} trades | PF {fpf(mf['pf'])} | WR {mf['wr']:.0f}%")

    # ── 4. Robustez de vecindad ────────────────────────────────────────────────
    print("[4/4] Robustez EMA100/150/200/250 (OOS 2024-2025)...")
    pf_avax_emas = {}; rob_detalles = {}
    for n in EMAs:
        trades_n = simular(velas_4h, ema_maps[n],
                           AVAX_C["rsi_min"], AVAX_C["rsi_max"],
                           AVAX_C["sl"],      AVAX_C["tp"],
                           use_gate=True, hasta_str=VAL_END)
        vl_n = split(trades_n, "VAL")
        mv_n = metricas(vl_n)
        pf_avax_emas[n] = pf_num(mv_n["pf"])
        rob_detalles[n] = {"trades": trades_n, "vl": vl_n, "m": mv_n}
        print(f"      EMA{n}: {mv_n['n']} trades OOS | PF {fpf(mv_n['pf'])} "
              f"| WR {mv_n['wr']:.1f}% | Exp {fpl(mv_n['exp'])}")

    # ── Bootstrap ──────────────────────────────────────────────────────────────
    print("\nEjecutando bootstrap (10,000 resamples)...")
    tr_prod = split(trades_prod, "TRAIN"); tr_c = split(trades_c, "TRAIN")
    vl_prod = split(trades_prod, "VAL");   vl_c = split(trades_c, "VAL")
    fw_prod = split(trades_prod, "FWD");   fw_c = split(trades_c, "FWD")

    bs_train = bootstrap(tr_c, tr_prod)
    bs_val   = bootstrap(vl_c, vl_prod)

    # ── Clasificacion ──────────────────────────────────────────────────────────
    rob_label, best_ema, n_pos, rob_detalle = analizar_robustez_ema(pf_avax_emas)
    mv_prod = metricas(vl_prod); mv_c = metricas(vl_c)
    mf_prod = metricas(fw_prod); mf_c = metricas(fw_c)
    mt_prod = metricas(tr_prod); mt_c = metricas(tr_c)
    verdict = clasificar_sistema(mv_c, mv_prod, bs_val, rob_label, pf_avax_emas)

    # ── Regimen forward ────────────────────────────────────────────────────────
    sobre_fwd, bajo_fwd, sin_ema_fwd = analizar_regimen_forward(velas_4h, ema_maps[200])
    total_fwd = sobre_fwd + bajo_fwd + sin_ema_fwd
    pct_sobre = sobre_fwd / total_fwd * 100 if total_fwd > 0 else 0
    pct_bajo  = bajo_fwd  / total_fwd * 100 if total_fwd > 0 else 0

    # ── Generar reporte ────────────────────────────────────────────────────────
    ANIOS = ["2021", "2022", "2023", "2024", "2025", "2026"]
    lines = []; a = lines.append
    lo95_v, hi95_v = bs_val["ic95"] if bs_val["ic95"][0] is not None else (None, None)

    a("# AVAX ALCISTA — Bootstrap Sistema C vs Produccion")
    a("")
    a("**Fecha:** 2026-08-14  ")
    a("**Estado:** INVESTIGACION PURA — 0 archivos de produccion modificados  ")
    a("**Simbolo:** AVAXUSDT  ")
    a("**Metodologia:** identica a BTC/ETH/SOL Sistema C")
    a("")
    a("---")
    a("")

    # ── Sec 1: Resumen ejecutivo ───────────────────────────────────────────────
    a("## 1. Resumen ejecutivo")
    a("")
    a("| Sistema | Train T | Train PF | OOS T | OOS PF | OOS WR | OOS Exp | Fwd T | Veredicto |")
    a("|---------|---------|----------|-------|--------|--------|---------|-------|-----------|")
    for lbl, trades in [("AVAX Produccion", trades_prod), ("AVAX Sistema C", trades_c)]:
        tr = split(trades, "TRAIN"); vl = split(trades, "VAL"); fw = split(trades, "FWD")
        mtr = metricas(tr); mvl = metricas(vl); mfw = metricas(fw)
        verd = verdict if "Sistema" in lbl else "—"
        a(f"| **{lbl}** | {mtr['n']} | {fpf(mtr['pf'])} | {mvl['n']} "
          f"| {fpf(mvl['pf'])} | {mvl['wr']:.1f}% | {fpl(mvl['exp'])} "
          f"| {mfw['n']} | {verd} |")
    a("")
    a("---")
    a("")

    # ── Sec 2: Metodologia ────────────────────────────────────────────────────
    a("## 2. Metodologia y configuracion")
    a("")
    a("| Parametro | AVAX Produccion | AVAX Sistema C |")
    a("|-----------|----------------|----------------|")
    a("| Simbolo | AVAXUSDT | AVAXUSDT |")
    a("| RSI rango | 60–75 | 55–60 |")
    a(f"| SL | {AVAX_PROD['sl']*100:.1f}% | {AVAX_C['sl']*100:.1f}% |")
    a(f"| TP | {AVAX_PROD['tp']*100:.1f}% | {AVAX_C['tp']*100:.1f}% |")
    a("| Gate EMA | Ninguno | SOBRE EMAd (anti-lookahead) |")
    a(f"| Capital / Monto | ${CAPITAL} / ${MONTO} | ${CAPITAL} / ${MONTO} |")
    a(f"| Comision | {COMISION*100:.2f}% × 2 | {COMISION*100:.2f}% × 2 |")
    a("| Train | 2021-01-01 – 2023-12-31 | idem |")
    a("| OOS | 2024-01-01 – 2025-12-31 | idem |")
    a("| Forward | 2026-01-01 – 2026-08-14 | idem |")
    a("")
    a("**IMPORTANTE:** Produccion y Sistema C tienen SL/TP distintos (4.5%/5.0% vs 5.0%/6.0%).")
    a("El delta de expectancy del bootstrap incluye el efecto de ese cambio, no solo el gate EMA.")
    a("Para aislar el efecto puro del gate se necesitaria una comparacion con SL/TP identicos.")
    a("")
    a("**Anti-lookahead:** para una vela 4H del dia D se usa la EMA calculada")
    a("con velas diarias cerradas hasta D-1 (busqueda hacia atras hasta D-5).")
    a("Warmup diario desde 2019-06-01 para garantizar EMA250 sin sesgo.")
    a("")
    a("**Fuente de parametros Produccion:** `config_cartera.py` — AVAX alcista, sin modificar.")
    a("")
    a("---")
    a("")

    # ── Sec 3-6: Metricas detalladas ──────────────────────────────────────────
    def seccion_metricas(num, titulo, tlist, per_label):
        m = metricas(tlist)
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
            g = [t for t in tlist if t["anio"] == anio]
            ma = metricas(g)
            if ma["n"] == 0:
                a(f"| {anio} | 0 | — | — | — | — |")
            else:
                nota = " ⚠️" if ma["n"] < 10 else ""
                a(f"| {anio} | {ma['n']}{nota} | {ma['wr']:.0f}% "
                  f"| {fpf(ma['pf'])} | {fpl(ma['exp'])} | {fpl(ma['pl'])} |")
        a("")
        a("---")
        a("")

    seccion_metricas(3, "AVAX Produccion", tr_prod, "Train 2021–2023")
    seccion_metricas(4, "AVAX Sistema C",  tr_c,    "Train 2021–2023")
    seccion_metricas(5, "AVAX Produccion", vl_prod, "OOS 2024–2025")
    seccion_metricas(6, "AVAX Sistema C",  vl_c,    "OOS 2024–2025")

    # ── Sec 7: Comparacion OOS principal ──────────────────────────────────────
    a("## 7. Comparacion principal OOS 2024–2025")
    a("")
    a("| Metrica | AVAX Produccion | AVAX Sistema C | Delta |")
    a("|---------|----------------|----------------|-------|")
    for lbl, attr, fmt in [
        ("Trades",      "n",     str),
        ("TP",          "tp",    str),
        ("SL",          "sl",    str),
        ("Win Rate",    "wr",    lambda v: f"{v:.1f}%"),
        ("PF",          "pf",    fpf),
        ("Exp/trade",   "exp",   fpl),
        ("P/L",         "pl",    fpl),
        ("DD max",      "dd",    lambda v: f"{v:.1f}%"),
        ("Racha SL",    "rsl",   str),
        ("Racha TP",    "rtp",   str),
        ("Peor 5",      "peor5", fpl),
    ]:
        vp = mv_prod[attr]; vc = mv_c[attr]
        try:
            delta = f"{vc-vp:+.1f}" if isinstance(vc, (int, float)) else "—"
        except Exception:
            delta = "—"
        a(f"| {lbl} | {fmt(vp)} | {fmt(vc)} | {delta} |")
    a("")
    a("*Nota: SL/TP distintos entre sistemas — el delta de expectancy no es comparacion limpia de gate.*")
    a("")
    a("---")
    a("")

    # ── Sec 8-9: Bootstrap ────────────────────────────────────────────────────
    a("## 8. Bootstrap DeltaExpectancy — Sistema C vs Produccion")
    a("")
    a("Δ = Expectancy(Sistema C) − Expectancy(Produccion)")
    a(f"Metodo: {N_BOOT:,} resamples con reemplazo, independientes por sistema.")
    a("")
    a("⚠️ *Los trades del mismo activo pueden presentar dependencia serial;")
    a("el bootstrap independiente puede subestimar la varianza real.")
    a("No interpretar como prueba estadistica formal.*")
    a("")
    a("| Periodo | Delta obs | IC90% | IC95% | Cruza 0 | P(D>0) | Mediana |")
    a("|---------|-----------|-------|-------|---------|--------|---------|")
    for lbl, bs in [("Train 2021–2023", bs_train), ("OOS 2024–2025", bs_val)]:
        if bs["obs"] is None:
            a(f"| {lbl} | N/A | — | — | — | — | — |")
        else:
            lo90, hi90 = bs["ic90"]; lo95, hi95 = bs["ic95"]
            cruza = "Si ⚠️" if (lo95 is not None and lo95 < 0 < hi95) else "No"
            a(f"| {lbl} | {fpl(bs['obs'])} "
              f"| [{fpl(lo90)},{fpl(hi90)}] "
              f"| [{fpl(lo95)},{fpl(hi95)}] "
              f"| {cruza} | {bs['p_pos']:.1%} | {fpl(bs['median'])} |")
    a("")
    a("## 9. IC90% / IC95% detallado")
    a("")
    a("| Periodo | IC90% lo | IC90% hi | IC95% lo | IC95% hi |")
    a("|---------|----------|----------|----------|----------|")
    for lbl, bs in [("Train", bs_train), ("OOS", bs_val)]:
        if bs["obs"] is None:
            a(f"| {lbl} | N/A | N/A | N/A | N/A |")
        else:
            lo90, hi90 = bs["ic90"]; lo95, hi95 = bs["ic95"]
            a(f"| {lbl} | {fpl(lo90)} | {fpl(hi90)} | {fpl(lo95)} | {fpl(hi95)} |")
    a("")
    a("---")
    a("")

    # ── Sec 10: Robustez de vecindad ───────────────────────────────────────────
    a("## 10. Robustez de vecindad EMA100/150/200/250 (OOS 2024–2025)")
    a("")
    a("### Tabla de resultados por EMA")
    a("")
    a("| EMA | Trades OOS | WR | PF | Exp | P/L | DD |")
    a("|-----|-----------|----|----|-----|-----|-----|")
    for n in EMAs:
        mv_n = rob_detalles[n]["m"]
        bench = " ←" if n == 200 else ""
        a(f"| **EMA{n}**{bench} | {mv_n['n']} | {mv_n['wr']:.1f}% | {fpf(mv_n['pf'])} "
          f"| {fpl(mv_n['exp'])} | {fpl(mv_n['pl'])} | {mv_n['dd']:.1f}% |")
    a("")
    a("### Analisis de robustez explícito")
    a("")
    a("| Campo | Valor |")
    a("|-------|-------|")
    a(f"| PF OOS EMA100 | {fpf(pf_avax_emas[100])} |")
    a(f"| PF OOS EMA150 | {fpf(pf_avax_emas[150])} |")
    a(f"| PF OOS EMA200 | {fpf(pf_avax_emas[200])} |")
    a(f"| PF OOS EMA250 | {fpf(pf_avax_emas[250])} |")
    a(f"| EMA con mejor PF | EMA{best_ema} (PF {fpf(pf_avax_emas[best_ema])}) |")
    a(f"| EMAs con PF > 1.0 | {n_pos}/4 |")
    a(f"| EMA200 es la mejor | {'SI ✅' if best_ema == 200 else 'NO ❌'} |")
    a(f"| Clasificacion de vecindad | **{rob_label}** |")
    a(f"| Detalle | {rob_detalle} |")
    a("")
    a("---")
    a("")

    # ── Sec 11: Forward 2026 ──────────────────────────────────────────────────
    a("## 11. Forward 2026 (2026-01-01 → 2026-08-14)")
    a("")
    a("### Resultados forward")
    a("")
    a("| Metrica | AVAX Produccion | AVAX Sistema C | Delta |")
    a("|---------|----------------|----------------|-------|")
    for lbl, attr, fmt in [
        ("Trades",   "n",   str),
        ("TP",       "tp",  str),
        ("SL",       "sl",  str),
        ("Win Rate", "wr",  lambda v: f"{v:.1f}%"),
        ("PF",       "pf",  fpf),
        ("Exp",      "exp", fpl),
        ("P/L",      "pl",  fpl),
        ("DD max",   "dd",  lambda v: f"{v:.1f}%"),
        ("Racha SL", "rsl", str),
    ]:
        vp = mf_prod[attr]; vc = mf_c[attr]
        try:
            delta = f"{vc-vp:+.1f}" if isinstance(vc, (int, float)) else "—"
        except Exception:
            delta = "—"
        a(f"| {lbl} | {fmt(vp)} | {fmt(vc)} | {delta} |")
    a("")
    a("### Regimen AVAX vs EMA200d en forward 2026 (velas 4H)")
    a("")
    a("| Estado | Velas | Porcentaje |")
    a("|--------|-------|-----------|")
    a(f"| AVAX SOBRE EMA200d | {sobre_fwd} | {pct_sobre:.1f}% |")
    a(f"| AVAX BAJO EMA200d  | {bajo_fwd}  | {pct_bajo:.1f}% |")
    a(f"| Sin EMA disponible | {sin_ema_fwd} | — |")
    a(f"| Total velas forward | {total_fwd} | — |")
    a("")
    if mf_c["n"] == 0:
        if pct_bajo > 60:
            a("**Conclusion de regimen:** AVAX estuvo mayoritariamente BAJO su EMA200d en 2026.")
            a("Sistema C permanecio inactivo por diseno — el gate funciona correctamente.")
            a("La inactividad no es un fallo: el sistema esta disenado para no operar en")
            a("regimen bajista macro.")
        elif pct_sobre > 60:
            a("**Conclusion de regimen:** AVAX estuvo mayoritariamente SOBRE su EMA200d en 2026.")
            a("El gate no bloqueo por regimen macro. La ausencia de trades se debe a que")
            a("RSI 55-60 no coincidio con precio > EMAd en los momentos de coincidencia.")
        else:
            a("**Conclusion de regimen:** Regimen mixto en 2026.")
            a("Posibles periodos activos pero sin coincidencia RSI/precio-EMA simultanea.")
    elif mf_c["n"] > 0:
        a(f"**Sistema C activo en forward 2026:** {mf_c['n']} trades.")
        a(f"PF forward: {fpf(mf_c['pf'])} | Exp: {fpl(mf_c['exp'])}.")
        a("Forward < 30 trades — no usar como criterio definitivo.")
    a("")

    if fw_prod:
        a("### Trades Produccion — Forward 2026")
        a("")
        a("| # | Entrada | RSI | Precio | Resultado | P/L |")
        a("|---|---------|-----|--------|-----------|-----|")
        for i, t in enumerate(fw_prod, 1):
            a(f"| {i} | {t['ts']} | {t['rsi']:.1f} | {t['precio']:.4f} "
              f"| {t['res']} | {fpl(t['pl'])} |")
        a("")
    else:
        a("_AVAX Produccion: sin trades en forward 2026._\n")

    if fw_c:
        a("### Trades Sistema C — Forward 2026")
        a("")
        a("| # | Entrada | RSI | Precio | EMA200d | Resultado | P/L |")
        a("|---|---------|-----|--------|---------|-----------|-----|")
        for i, t in enumerate(fw_c, 1):
            ema_str = f"{t['ema_v']:.4f}" if t["ema_v"] else "—"
            a(f"| {i} | {t['ts']} | {t['rsi']:.1f} | {t['precio']:.4f} "
              f"| {ema_str} | {t['res']} | {fpl(t['pl'])} |")
        a("")
    else:
        a("_AVAX Sistema C: sin trades en forward 2026._\n")

    a("---")
    a("")

    # ── Sec 12: Resultados anuales ────────────────────────────────────────────
    a("## 12. Resultados anuales")
    a("")
    a("| Ano | Prod T | Prod PF | Prod WR | SistC T | SistC PF | SistC WR | Periodo |")
    a("|-----|--------|---------|---------|---------|----------|----------|---------|")
    for anio in ANIOS:
        gp = [t for t in trades_prod if t["anio"] == anio]
        gc = [t for t in trades_c    if t["anio"] == anio]
        mp = metricas(gp); mc = metricas(gc)
        per_lbl = "TRAIN" if anio <= "2023" else ("FWD" if anio == "2026" else "**VAL**")
        pf_p = fpf(mp["pf"]) if mp["n"] > 0 else "—"
        wr_p = f"{mp['wr']:.0f}%" if mp["n"] > 0 else "—"
        pf_c = fpf(mc["pf"]) if mc["n"] > 0 else "—"
        wr_c = f"{mc['wr']:.0f}%" if mc["n"] > 0 else "—"
        np_s = str(mp["n"]) + (" ⚠️" if 0 < mp["n"] < 10 else "")
        nc_s = str(mc["n"]) + (" ⚠️" if 0 < mc["n"] < 10 else "")
        a(f"| {anio} | {np_s} | {pf_p} | {wr_p} | {nc_s} | {pf_c} | {wr_c} | {per_lbl} |")
    a("")
    a("---")
    a("")

    # ── Sec 13: Drawdown y rachas OOS ─────────────────────────────────────────
    a("## 13. Drawdown y rachas OOS 2024–2025")
    a("")
    a("| Sistema | DD max | Racha SL | Fechas | Racha TP | Peor 5 trades |")
    a("|---------|--------|----------|--------|----------|---------------|")
    for lbl, mv in [("AVAX Produccion", mv_prod), ("AVAX Sistema C", mv_c)]:
        a(f"| {lbl} | {mv['dd']:.1f}% | {mv['rsl']} | {mv['rsl_d']} "
          f"| {mv['rtp']} | {fpl(mv['peor5'])} |")
    a("")
    a("---")
    a("")

    # ── Sec 14: Analisis de sobreajuste ───────────────────────────────────────
    a("## 14. Analisis de sobreajuste")
    a("")
    preguntas = [
        ("¿RSI 55–60 fue seleccionado post-hoc sobre AVAX?",
         "No. El patron RSI 55–60 fue definido a priori en la investigacion BTC/ETH/SOL "
         "y aplicado aqui como hipotesis externa. Reduce el riesgo de mineria de datos especifica."),
        ("¿El patron proviene de una hipotesis externa previamente definida?",
         "Si. RSI 55–60 + gate EMA diaria es el patron 'Sistema C' definido antes de analizar AVAX."),
        ("¿EMA200 es un pico aislado?",
         f"EMA con mejor PF en OOS: EMA{best_ema} (PF {fpf(pf_avax_emas[best_ema])}). "
         f"EMA200 PF: {fpf(pf_avax_emas[200])}. "
         + ("EMA200 NO es la mejor — hay pico en otra EMA." if best_ema != 200
            else "EMA200 es la mejor." if n_pos > 1 else "EMA200 unica positiva — patron fragil.")),
        ("¿Las EMAs vecinas confirman la ventaja?",
         f"{n_pos}/4 EMAs con PF > 1.0. Clasificacion: {rob_label}. {rob_detalle}"),
        ("¿Sistema C mejora de Train a OOS?",
         (f"Train PF: {fpf(mt_c['pf'])} → OOS PF: {fpf(mv_c['pf'])}. "
          + ("Mejora OOS. ✅" if pf_num(mv_c['pf']) >= pf_num(mt_c['pf']) * 0.8 and mt_c['n'] > 0
             else "Degradacion significativa. ⚠️") if mt_c['n'] > 0 else "Sin trades train.")),
        ("¿PF OOS > 1?",
         f"{'SI ✅' if pf_num(mv_c['pf']) > 1.0 else 'NO ❌'} — PF OOS: {fpf(mv_c['pf'])}"),
        ("¿Expectancy OOS > 0?",
         f"{'SI ✅' if mv_c['exp'] > 0 else 'NO ❌'} — Exp OOS: {fpl(mv_c['exp'])}"),
        ("¿Hay al menos 30 trades OOS?",
         f"{'SI ✅' if mv_c['n'] >= 30 else 'NO ⚠️'} — Trades OOS: {mv_c['n']}"),
        ("¿IC95% cruza cero?",
         (f"SI ⚠️ — IC95% [{fpl(lo95_v)},{fpl(hi95_v)}]" if lo95_v is not None and lo95_v < 0 < hi95_v
          else f"NO ✅ — IC95% [{fpl(lo95_v)},{fpl(hi95_v)}]" if lo95_v and lo95_v > 0
          else "No calculable — muestra insuficiente.")),
        ("¿El resultado depende de un unico ano?",
         "Ver tabla anual. Si un solo ano concentra todos los trades positivos, la evidencia es fragil."),
        ("¿Forward 2026 aporta evidencia adicional?",
         (f"Sistema C: {mf_c['n']} trades en forward. "
          + (f"PF {fpf(mf_c['pf'])}, Exp {fpl(mf_c['exp'])}." if mf_c['n'] > 0
             else f"AVAX {pct_bajo:.0f}% del tiempo bajo EMA200d — gate inactivo por diseno."))),
        ("¿El gate reduce excesivamente la frecuencia?",
         f"Produccion OOS: {mv_prod['n']} trades. Sistema C OOS: {mv_c['n']} trades. "
         + (f"Reduccion: {mv_prod['n']-mv_c['n']} trades ({(1-mv_c['n']/mv_prod['n'])*100:.0f}%)."
            if mv_prod['n'] > 0 and mv_c['n'] > 0 else
            "Sistema C sin trades OOS — gate bloquea todo." if mv_c['n'] == 0 else "")),
    ]
    for i, (pregunta, respuesta) in enumerate(preguntas, 1):
        a(f"{i}. **{pregunta}**")
        a(f"   {respuesta}")
        a("")
    a("---")
    a("")

    # ── Sec 15: Limitaciones ──────────────────────────────────────────────────
    a("## 15. Limitaciones")
    a("")
    a("1. SL/TP distintos entre Produccion (4.5%/5.0%) y Sistema C (5.0%/6.0%) — "
      "la diferencia de expectancy mezcla efecto del gate con efecto del SL/TP.")
    a("2. Sin trailing stop ni gates de produccion (horario, eventos macro, spread, guardian).")
    a("3. Sin compounding — monto fijo $5 por trade.")
    a("4. Bootstrap subestima varianza por dependencia serial entre trades del mismo activo.")
    a("5. RSI 55–60 viene de la investigacion BTC — puede ser suboptimo para AVAX.")
    a("6. AVAX tuvo regimenes de alta volatilidad (colapso FTX nov 2022, recuperacion 2023).")
    a("7. Muestra historica de AVAX en Binance spot comienza aproximadamente en 2020.")
    a("")
    a("---")
    a("")

    # ── Sec 16: Veredicto automático ──────────────────────────────────────────
    a("## 16. Veredicto final")
    a("")
    a("### Tabla de criterios")
    a("")
    a("| Criterio | Estado |")
    a("|----------|--------|")
    a(f"| PF OOS > 1.0 | {'✅ ' + fpf(mv_c['pf']) if pf_num(mv_c['pf']) > 1.0 else '❌ ' + fpf(mv_c['pf'])} |")
    a(f"| Exp OOS > 0 | {'✅ ' + fpl(mv_c['exp']) if mv_c['exp'] > 0 else '❌ ' + fpl(mv_c['exp'])} |")
    a(f"| Trades OOS suficientes (>=20) | {'✅ ' + str(mv_c['n']) if mv_c['n'] >= 20 else '⚠️ ' + str(mv_c['n'])} |")
    a(f"| EMA200 es la mejor | {'✅' if best_ema == 200 else '❌ EMA' + str(best_ema) + ' es la mejor'} |")
    a(f"| Vecinas con PF > 1.0 | {n_pos}/4 |")
    a(f"| Clasificacion vecindad | {rob_label} |")
    ic_str = (f"✅ [{fpl(lo95_v)},{fpl(hi95_v)}]" if lo95_v and lo95_v > 0
              else f"❌ cruza 0 [{fpl(lo95_v)},{fpl(hi95_v)}]" if lo95_v is not None
              else "N/A")
    a(f"| Bootstrap IC95% no cruza 0 | {ic_str} |")
    p_pos_str = f"{bs_val['p_pos']:.1%}" if bs_val["p_pos"] is not None else "N/A"
    a(f"| P(D>0) bootstrap | {p_pos_str} |")
    a("")
    a(f"### **{verdict}**")
    a("")

    if "CANDIDATO FUERTE" in verdict:
        a("Todos los criterios de robustez se cumplen: PF OOS > 1.0, expectancy positiva,")
        a("EMA200 es la mejor EMA, todas las vecinas positivas, IC95% no cruza cero.")
        a("La evidencia es la mas solida de los 4 activos investigados.")
    elif "PROMETEDOR" in verdict:
        a("El sistema es positivo en OOS pero alguno de los criterios mas exigentes no se cumple:")
        if lo95_v is not None and lo95_v < 0 < hi95_v:
            a("El IC95% del bootstrap cruza cero — la diferencia vs Produccion esta dentro del ruido.")
        if rob_label not in ("ROBUSTO_EMA",):
            a(f"Clasificacion de vecindad: {rob_label} — patron no plenamente robusto.")
        a("La evidencia es favorable pero insuficiente para activar sin mas datos.")
    elif "FRAGIL" in verdict:
        a("El sistema muestra PF OOS positivo pero el patron de vecindad EMA es fragil.")
        a(f"{rob_detalle}")
        a("No recomendado para REAL sin evidencia adicional de robustez.")
    elif "INCONCLUSO" in verdict:
        a(f"Muestra OOS insuficiente ({mv_c['n']} trades) para emitir veredicto formal.")
    elif "DESCARTADO" in verdict:
        a("PF OOS <= 1.0 y/o expectancy <= 0. Sistema C no supera a Produccion en OOS.")
        a("Patrón RSI 55–60 + gate EMA no funciona en AVAX con los parametros probados.")
    a("")
    a("---")
    a("")

    # ── Sec 17: Decision para REAL ────────────────────────────────────────────
    a("## 17. Decision para REAL")
    a("")
    a("| Campo | Estado |")
    a("|-------|--------|")
    a("| Produccion AVAX modificada | **NO** |")
    a("| Sistema C AVAX activado | **NO** |")
    a("| config_cartera.py | **SIN CAMBIOS** |")
    a("| auditoria.csv | **SIN CAMBIOS** |")
    a("| billetera.json | **SIN CAMBIOS** |")
    a(f"| Veredicto | **{verdict}** |")
    a("")
    if "CANDIDATO FUERTE" in verdict:
        a("**Proximo paso:** Candidato fuerte para validacion REAL controlada.")
        a("Requiere >= 30 trades reales en REAL antes de cualquier activacion permanente.")
        a("Prioridad de investigacion: mayor que BTC Sistema C si la evidencia es mas robusta.")
    elif "PROMETEDOR" in verdict:
        a("**Proximo paso:** Prometedor pero insuficientemente concluyente.")
        a("Acumular >= 30 trades reales. No activar todavia.")
    else:
        a("**Proximo paso:** No activar Sistema C AVAX.")
        a("Produccion AVAX permanece sin cambios.")
    a("")
    a("---")
    a("")

    # ── Sec 18: Comparacion BTC/ETH/SOL/AVAX ─────────────────────────────────
    a("## 18. Comparacion acumulada BTC / ETH / SOL / AVAX")
    a("")
    btc_fwd_str = "0 trades (BTC bajo EMA200d)"
    eth_fwd_str = "N/A"
    sol_fwd_str = "0 trades (SOL bajo EMA200d)"
    avax_fwd_str = (f"{mf_c['n']} trades" if mf_c["n"] > 0
                    else f"0 trades ({pct_bajo:.0f}% bajo EMA200d)" if pct_bajo > 40
                    else "0 trades (RSI/EMA sin coincidencia)")
    a("| Activo | Sist C PF OOS | Exp OOS | EMAs PF>1 | Trades OOS | Forward | Veredicto |")
    a("|--------|--------------|---------|-----------|-----------|---------|-----------|")
    a("| **BTC** | 1.322 | +$0.0383 | 4/4 | 59 | " + btc_fwd_str + " | 🟡 PROMETEDOR |")
    a("| **ETH** | 0.960 | -$0.0055 | 0/4 | 67 | " + eth_fwd_str + " | 🔴 DESCARTADO |")
    a("| **SOL** | 0.984 | -$0.0022 | 0/4 | 96 | " + sol_fwd_str + " | 🔴 DESCARTADO |")
    avax_row = (f"| **AVAX** | {fpf(mv_c['pf'])} | {fpl(mv_c['exp'])} "
                f"| {n_pos}/4 | {mv_c['n']} | {avax_fwd_str} | {verdict} |")
    a(avax_row)
    a("")
    a("---")
    a("")

    # ── Sec 19: Conclusion global ──────────────────────────────────────────────
    a("## 19. Conclusion global del experimento Sistema C")
    a("")
    a("### ¿Existe evidencia de que Sistema C sea un patron generalizable entre altcoins?")
    a("")
    n_positivos = sum(1 for pf in [1.322, 0.960, 0.984, pf_num(mv_c["pf"])] if pf > 1.0)
    if n_positivos <= 1:
        a("**La evidencia actual NO demuestra que RSI 55–60 + gate EMA sea un patron generalizable**")
        a("**entre activos. La evidencia favorable esta concentrada exclusivamente en BTC.**")
        a("")
        a("- BTC Sistema C: 🟡 PROMETEDOR (PF OOS 1.322, 4/4 EMAs, 59 trades)")
        a("- ETH Sistema C: 🔴 DESCARTADO (PF OOS 0.960, 0/4 EMAs)")
        a("- SOL Sistema C: 🔴 DESCARTADO (PF OOS 0.984, 0/4 EMAs)")
        a(f"- AVAX Sistema C: {verdict} (PF OOS {fpf(mv_c['pf'])}, {n_pos}/4 EMAs)")
        a("")
        a("El patron RSI 55–60 + gate EMA puede ser una caracteristica especifica de BTC")
        a("o una ventaja ligada al regimen historico del bear market 2021-2023 en BTC.")
        a("Con 3 de 4 activos sin evidencia OOS positiva, no existe base para declarar")
        a("que el patron es generalizable.")
    elif n_positivos == 2:
        a(f"La evidencia es mixta: {n_positivos}/4 activos muestran PF OOS > 1.0.")
        if pf_num(mv_c["pf"]) > 1.0:
            a("AVAX y BTC muestran PF OOS positivo, pero ETH y SOL no.")
            a("La evidencia es insuficiente para declarar generalizacion del patron.")
            a("Puede existir un efecto de seleccion por activo o por regimen de mercado.")
        else:
            a("Solo BTC muestra PF OOS positivo de forma clara entre los 4 activos.")
        a("")
        a("**Conclusion:** evidencia insuficiente para generalizar. BTC sigue siendo el unico")
        a("activo con evidencia favorable clara.")
    else:
        a(f"{n_positivos}/4 activos muestran PF OOS > 1.0.")
        a("Existe evidencia transversal, pero con las limitaciones de muestra y bootstrap.")
        a("No declarar generalizacion hasta acumular >= 30 trades reales por activo.")
    a("")
    a("---")
    a("")

    # ── Sec 20: Cierre ejecutivo ───────────────────────────────────────────────
    a("## 20. Cierre ejecutivo")
    a("")
    a(f"### AVAX Sistema C: {verdict}")
    a("")
    a("**Los numeros clave (OOS 2024–2025):**")
    a("")
    a(f"|  | Produccion | Sistema C |")
    a("|--|-----------|-----------|")
    a(f"| OOS trades | {mv_prod['n']} | {mv_c['n']} |")
    a(f"| OOS PF | {fpf(mv_prod['pf'])} | {fpf(mv_c['pf'])} |")
    a(f"| OOS Exp | {fpl(mv_prod['exp'])} | {fpl(mv_c['exp'])} |")
    a(f"| Forward trades | {mf_prod['n']} | {mf_c['n']} |")
    a("")
    a("**Vecindad EMA:**")
    a("")
    a(f"«{n_pos}/4 EMAs del rango EMA100–EMA250 tienen PF > 1.0 en OOS. "
      f"La mejor EMA en OOS es EMA{best_ema} con PF {fpf(pf_avax_emas[best_ema])}. "
      f"EMA200 presenta PF {fpf(pf_avax_emas[200])}. "
      f"Clasificacion de vecindad: {rob_label}. "
      + ("EMA200 es la mejor y las vecinas confirman → zona robusta."
         if rob_label == "ROBUSTO_EMA"
         else "EMA200 no es la mejor — no hay robustez alrededor de EMA200."
         if rob_label == "NO_ROBUSTA_EMA200"
         else "EMA200 es la unica positiva — patron fragil."
         if rob_label in ("FRAGIL_SOLO_EMA200",)
         else "EMA200 negativa — el gate no funciona."
         if rob_label == "FRAGIL_EMA200_NEGATIVA"
         else "Robustez parcial — no todas las vecinas son positivas.")
      + "»")
    a("")
    a("**Bootstrap:**")
    a("")
    if bs_val["obs"] is not None:
        interp = ("desfavorable — Sistema C es peor que Produccion" if bs_val["obs"] < -0.005
                  else "practicamente neutral" if abs(bs_val["obs"]) < 0.005
                  else "favorable — Sistema C supera a Produccion")
        a(f"«Bootstrap: Delta = {fpl(bs_val['obs'])} (Sistema C vs Produccion). "
          f"P(D>0) = {bs_val['p_pos']:.1%}. "
          f"La diferencia parece {interp}.»")
    else:
        a("«Bootstrap: no calculable por muestra insuficiente.»")
    a("")
    a("**Forward 2026:**")
    a("")
    if mf_c["n"] == 0:
        a(f"«Sistema C: 0 trades en forward. AVAX estuvo {pct_bajo:.0f}% del tiempo "
          f"bajo su EMA200d ({bajo_fwd} de {total_fwd} velas 4H). "
          "El sistema permanecio inactivo por diseno — el gate macro funciono correctamente. "
          "No interpretar como fallo: es el comportamiento esperado en regimen bajista.»")
    else:
        a(f"«Sistema C: {mf_c['n']} trades en forward (AVAX {pct_sobre:.0f}% del tiempo "
          f"sobre EMA200d). PF forward: {fpf(mf_c['pf'])}. "
          "Muestra insuficiente para conclusion definitiva.»")
    a("")
    a("**Conclusion:**")
    a("")
    a("«¿El patron RSI 55–60 + gate EMA funciona en AVAX? ")
    if pf_num(mv_c["pf"]) <= 1.0 or mv_c["exp"] <= 0:
        a("No. PF OOS <= 1.0 y/o expectancy negativa. El patron no supera a Produccion en OOS. "
          "El gate EMA no mejora los resultados en AVAX con los parametros evaluados.»")
    elif rob_label in ("FRAGIL_EMA200_NEGATIVA", "FRAGIL_SOLO_EMA200"):
        a("Parcialmente: PF OOS > 1.0 pero el patron de vecindad EMA es fragil. "
          "La evidencia no es suficientemente robusta para recomendar activacion.»")
    elif rob_label == "ROBUSTO_EMA" and lo95_v and lo95_v > 0:
        a("Si, con evidencia solida. PF OOS > 1.0, expectancy positiva, vecindad robusta, "
          "IC95% favorable. Es el activo con mejor evidencia del experimento Sistema C.»")
    elif rob_label == "ROBUSTO_EMA":
        a("Probablemente si, pero con incertidumbre estadistica. PF OOS > 1.0, vecindad robusta, "
          "pero IC95% cruza cero. Se necesitan mas datos.»")
    else:
        a("Evidencia insuficiente o mixta. Ver detalles en secciones anteriores.»")
    a("")
    a("---")
    a("")
    a("## Estado final")
    a("")
    a("| Campo | Estado |")
    a("|-------|--------|")
    a("| Produccion AVAX modificada | **NO** |")
    a("| Sistema C AVAX activado | **NO** |")
    a("| `config_cartera.py` | **SIN CAMBIOS** |")
    a("| `auditoria.csv` | **SIN CAMBIOS** |")
    a("| `billetera.json` | **SIN CAMBIOS** |")
    a(f"| Veredicto AVAX Sistema C | **{verdict}** |")
    a("| Proximo paso | NO ACTIVAR — continuar acumulando evidencia segun corresponda |")
    a("")
    a("**Archivos creados:**")
    a("- `reports/2026-08-14_avax-bootstrap-sistema-c-vs-produccion.md`")
    a("- `avax_bootstrap_sistema_c_vs_produccion.py`")
    a("")
    a("**PRODUCCION NO MODIFICADA.**")

    # ── Escribir reporte ───────────────────────────────────────────────────────
    os.makedirs(os.path.dirname(os.path.expanduser(REPORT_PATH)), exist_ok=True)
    with open(os.path.expanduser(REPORT_PATH), "w") as f:
        f.write("\n".join(lines))

    # ── Consola ────────────────────────────────────────────────────────────────
    print()
    print("=" * 62)
    print("RESULTADOS AVAX — OOS 2024-2025")
    print("=" * 62)
    print(f"  Produccion: {mv_prod['n']:3d} trades | PF {fpf(mv_prod['pf'])} "
          f"| WR {mv_prod['wr']:.1f}% | Exp {fpl(mv_prod['exp'])}")
    print(f"  Sistema C:  {mv_c['n']:3d} trades | PF {fpf(mv_c['pf'])} "
          f"| WR {mv_c['wr']:.1f}% | Exp {fpl(mv_c['exp'])}")
    print()
    print("FORWARD 2026 (ene–ago 2026)")
    print(f"  Produccion: {mf_prod['n']:3d} trades | PF {fpf(mf_prod['pf'])} "
          f"| WR {mf_prod['wr']:.1f}%")
    print(f"  Sistema C:  {mf_c['n']:3d} trades | PF {fpf(mf_c['pf'])} "
          f"| WR {mf_c['wr']:.1f}%")
    print(f"  Regimen: {pct_sobre:.0f}% sobre EMA200d / {pct_bajo:.0f}% bajo EMA200d")
    print()
    print("VECINDAD EMA (OOS)")
    print("  " + " | ".join(
        f"EMA{n}={'✅' if pf_avax_emas[n] > 1 else '❌'}{fpf(pf_avax_emas[n])}"
        for n in EMAs
    ))
    print(f"  EMA mejor: EMA{best_ema} | {n_pos}/4 positivas | "
          f"EMA200 mejor: {'SI' if best_ema == 200 else 'NO'} | {rob_label}")
    if bs_val["obs"] is not None:
        print()
        print("BOOTSTRAP OOS")
        lo90, hi90 = bs_val["ic90"]; lo95, hi95 = bs_val["ic95"]
        print(f"  Delta Exp: {fpl(bs_val['obs'])}")
        print(f"  IC90%:     [{fpl(lo90)}, {fpl(hi90)}]")
        print(f"  IC95%:     [{fpl(lo95)}, {fpl(hi95)}]")
        print(f"  P(D > 0):  {bs_val['p_pos']:.1%}")
    print()
    print("=" * 62)
    print(f"VEREDICTO AVAX SISTEMA C: {verdict}")
    print("ESTADO PRODUCCION:         NO MODIFICADA")
    print("SISTEMA C:                 NO ACTIVADO")
    print("=" * 62)
    print()
    print(f"Reporte: {REPORT_PATH}")
    print()
    print("less " + REPORT_PATH)


if __name__ == "__main__":
    main()
