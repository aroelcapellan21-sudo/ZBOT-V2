"""
sol_bootstrap_sistema_c_vs_produccion.py
SOL ALCISTA — Investigacion Sistema C vs Produccion
INVESTIGACION PURA — 0 archivos de produccion modificados.

Produccion SOL (de config_cartera.py):
  RSI 50-70, SL 5.0%, TP 6.0%, sin gate EMA

Sistema C SOL (mismo patron que BTC/ETH):
  RSI 55-60, SL 5.0%, TP 6.0%, gate SOBRE EMA diaria (anti-lookahead)

Robustez de vecindad: EMA100, EMA150, EMA200, EMA250

Reglas de clasificacion (sin n_ema_pos >= 3):
  - EMA200 debe ser la mejor EMA en OOS
  - Todas las vecinas deben tener PF > 1.0
  - IC95% bootstrap no debe cruzar cero para ROBUSTO
"""
import json, os, random, urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta

from utils_backtest import export_trades_csv

# ── Parametros globales ───────────────────────────────────────────────────────
FECHA_WU_4H  = "2020-10-01"
FECHA_WU_D   = "2019-06-01"   # warmup para EMA250
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

REPORT_PATH = os.path.expanduser(
    "~/bot-padre-v2/reports/2026-08-14_sol-bootstrap-sistema-c-vs-produccion.md"
)

# SOL Produccion (config_cartera.py — alcista)
SOL_PROD = dict(sym="SOLUSDT", rsi_min=50.0, rsi_max=70.0, sl=0.050, tp=0.060, gate_ema=None)
# SOL Sistema C (patron identico a BTC/ETH — RSI 55-60, mismos SL/TP)
SOL_C    = dict(sym="SOLUSDT", rsi_min=55.0, rsi_max=60.0, sl=0.050, tp=0.060, gate_ema=200)

# ── Descarga ──────────────────────────────────────────────────────────────────
def _ts(f):
    return int(datetime.strptime(f, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000)

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
    """EMA del ultimo dia cerrado antes de la vela 4H (anti-lookahead: D-1 a D-5)."""
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

# ── Simulacion (1 posicion a la vez) ─────────────────────────────────────────
def simular(velas_4h, ema_map, rsi_min, rsi_max, sl, tp, use_gate=False,
            desde_str=TRAIN_START, hasta_str=VAL_END):
    cierres = [float(v[4]) for v in velas_4h]
    ts_list = [int(v[0]) for v in velas_4h]
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
                pl  = round((MONTO * tp if res == "TP" else -MONTO * sl) - MONTO * COMISION * 2, 4)
                per = "TRAIN" if tsv <= _ts(TRAIN_END) + 86400000 else (
                      "FWD"   if tsv >= _ts(FWD_START) else "VAL")
                trades.append({
                    "ts":    ets.strftime("%Y-%m-%d %H:%M"),
                    "anio":  str(ets.year),
                    "per":   per,
                    "rsi":   er,
                    "precio": round(ep, 4),
                    "ema_v": round(e_ema_v, 4) if e_ema_v else None,
                    "res":   res,
                    "pl":    pl,
                    "exit_ts": tsdt.strftime("%Y-%m-%d %H:%M"),
                    "exit_price": round(tp_p if res == "TP" else sl_p, 4),
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
def fpf(v): return f"{v:.3f}" if v != float("inf") else "inf"
def fpl(v): return f"+${v:.4f}" if v >= 0 else f"-${abs(v):.4f}"
def pf_num(v): return v if v != float("inf") else 999.0

# ── Robustez de vecindad EMA (reglas estrictas — sin n_ema_pos >= 3) ─────────
def analizar_robustez_ema(pf_emas):
    """
    pf_emas: dict {100: pf100, 150: pf150, 200: pf200, 250: pf250}

    Reglas exactas:
    1. Si EMA200 PF <= 1.0 → FRAGIL_EMA200_NEGATIVA
    2. Si best_ema != 200 → NO_ROBUSTA_EMA200 (EMA200 no es la mejor)
    3. Si EMA200 es la mejor pero es la unica positiva → FRAGIL_SOLO_EMA200
    4. Si EMA200 es la mejor y todas las vecinas positivas → ROBUSTO_EMA
    5. Si EMA200 es la mejor y algunas vecinas positivas → PARCIAL_EMA
    """
    pf200   = pf_emas.get(200, 0.0)
    best_n  = max(pf_emas, key=pf_emas.get)
    best_pf = pf_emas[best_n]
    n_pos   = sum(1 for pf in pf_emas.values() if pf > 1.0)
    vecinas = {n: pf for n, pf in pf_emas.items() if n != 200}

    if pf200 <= 1.0:
        return ("FRAGIL_EMA200_NEGATIVA", best_n, n_pos,
                f"EMA200 PF {pf200:.3f} <= 1.0. Mejor: EMA{best_n} (PF {best_pf:.3f}).")

    if best_n != 200:
        return ("NO_ROBUSTA_EMA200", best_n, n_pos,
                f"EMA200 positiva (PF {pf200:.3f}) pero NO es la mejor. "
                f"Mejor: EMA{best_n} (PF {best_pf:.3f}). {n_pos}/4 EMAs con PF > 1.0.")

    # EMA200 es la mejor
    todas_pos = all(pf > 1.0 for pf in vecinas.values())
    n_vec_pos = sum(1 for pf in vecinas.values() if pf > 1.0)

    if n_pos == 1:
        return ("FRAGIL_SOLO_EMA200", best_n, n_pos,
                f"EMA200 es la UNICA EMA con PF > 1.0 (PF {pf200:.3f}). "
                "Patron FRAGIL — independiente de lo alto que sea el PF.")

    if todas_pos:
        return ("ROBUSTO_EMA", best_n, n_pos,
                f"EMA200 es la mejor (PF {pf200:.3f}) Y las {len(vecinas)} EMAs vecinas "
                f"tambien tienen PF > 1.0. Patron de vecindad ROBUSTO.")

    return ("PARCIAL_EMA", best_n, n_pos,
            f"EMA200 es la mejor (PF {pf200:.3f}). {n_vec_pos}/{len(vecinas)} vecinas "
            f"con PF > 1.0. Robustez parcial.")


# ── Clasificacion final del sistema ──────────────────────────────────────────
def clasificar_sistema(m_val, m_prod_val, bs_val, rob_label, pf_emas):
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
        return "🟡 PROMETEDOR"  # OOS positivo pero EMA200 no es la mejor
    if rob_label == "ROBUSTO_EMA":
        return "🟢 ROBUSTO" if ic_no_cruza else "🟡 PROMETEDOR"
    if rob_label == "PARCIAL_EMA":
        return "🟡 PROMETEDOR"
    return "🟠 INCONCLUSO"


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    ahora_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

    print("=" * 62)
    print("SOL ALCISTA — Bootstrap Sistema C vs Produccion")
    print("=" * 62)

    # ── 1. Descarga ────────────────────────────────────────────────────────────
    print("\n[1/4] Descargando datos SOLUSDT...")
    velas_4h_raw = fetch("SOLUSDT", "4h",  _ts(FECHA_WU_4H))
    velas_d_raw  = fetch("SOLUSDT", "1d",  _ts(FECHA_WU_D))
    velas_4h = [v for v in velas_4h_raw if int(v[6]) < ahora_ms]
    velas_d  = [v for v in velas_d_raw  if int(v[6]) < ahora_ms]
    print(f"      SOLUSDT: {len(velas_4h)} velas 4H | {len(velas_d)} velas 1D")

    # Verificar datos minimos
    if len(velas_4h) < 1000:
        print("ERROR: datos 4H insuficientes para simulacion.")
        return
    if len(velas_d) < 260:
        print("ERROR: datos diarios insuficientes para EMA250.")
        return

    # ── 2. Mapas EMA ───────────────────────────────────────────────────────────
    print("[2/4] Construyendo mapas EMA diarios (anti-lookahead)...")
    ema_maps = {}
    for n in EMAs:
        ema_maps[n] = build_ema(velas_d, n)
        print(f"      EMA{n}: {len(ema_maps[n])} fechas diarias")

    # ── 3. Simulaciones principales ────────────────────────────────────────────
    print("[3/4] Simulando Produccion y Sistema C...")
    FWD_HASTA = FWD_END_STR

    trades_prod = simular(velas_4h, {},
                          SOL_PROD["rsi_min"], SOL_PROD["rsi_max"],
                          SOL_PROD["sl"], SOL_PROD["tp"],
                          use_gate=False,
                          desde_str=TRAIN_START, hasta_str=FWD_HASTA)

    trades_c = simular(velas_4h, ema_maps[200],
                       SOL_C["rsi_min"], SOL_C["rsi_max"],
                       SOL_C["sl"], SOL_C["tp"],
                       use_gate=True,
                       desde_str=TRAIN_START, hasta_str=FWD_HASTA)

    def _a_filas_export(trades, sl, tp):
        return [{
            "symbol": "SOLUSDT",
            "entry_timestamp": t["ts"],
            "exit_timestamp": t["exit_ts"],
            "entry_price": t["precio"],
            "exit_price": t["exit_price"],
            "cantidad": round(MONTO / t["precio"], 8),
            "fee_entrada": round(MONTO * COMISION, 4),
            "fee_salida": round(MONTO * COMISION, 4),
            "pnl_bruto": round(MONTO * tp if t["res"] == "TP" else -MONTO * sl, 4),
            "pnl_neto": t["pl"],
            "resultado": t["res"],
            "fase": "ALCISTA",
        } for t in trades]

    ruta_csv_prod = export_trades_csv(
        _a_filas_export(trades_prod, SOL_PROD["sl"], SOL_PROD["tp"]),
        "sol_produccion_vs_sistemac")
    ruta_csv_c = export_trades_csv(
        _a_filas_export(trades_c, SOL_C["sl"], SOL_C["tp"]),
        "sol_sistemac_vs_produccion")
    print(f"      CSV crudo Produccion: {ruta_csv_prod}")
    print(f"      CSV crudo Sistema C:  {ruta_csv_c}")

    def split(trades, per): return [t for t in trades if t["per"] == per]

    for key, trades in [("Produccion", trades_prod), ("Sistema C", trades_c)]:
        tr = split(trades, "TRAIN"); vl = split(trades, "VAL"); fw = split(trades, "FWD")
        mt = metricas(tr); mv = metricas(vl); mf = metricas(fw)
        print(f"      SOL {key}:")
        print(f"        Train: {mt['n']} trades | PF {fpf(mt['pf'])} | WR {mt['wr']:.0f}%")
        print(f"        OOS:   {mv['n']} trades | PF {fpf(mv['pf'])} | WR {mv['wr']:.0f}%")
        print(f"        Fwd:   {mf['n']} trades | PF {fpf(mf['pf'])} | WR {mf['wr']:.0f}%")

    # ── 4. Robustez de vecindad ────────────────────────────────────────────────
    print("[4/4] Robustez EMA100/150/200/250 (OOS 2024-2025)...")
    pf_sol_emas = {}
    rob_detalles = {}
    for n in EMAs:
        trades_n = simular(velas_4h, ema_maps[n],
                           SOL_C["rsi_min"], SOL_C["rsi_max"],
                           SOL_C["sl"], SOL_C["tp"],
                           use_gate=True,
                           desde_str=TRAIN_START, hasta_str=VAL_END)
        vl_n = split(trades_n, "VAL")
        mv_n = metricas(vl_n)
        pf_sol_emas[n] = pf_num(mv_n["pf"])
        rob_detalles[n] = {
            "trades": trades_n,
            "vl": vl_n,
            "m": mv_n,
        }
        print(f"      EMA{n}: {mv_n['n']} trades OOS | PF {fpf(mv_n['pf'])} "
              f"| WR {mv_n['wr']:.1f}% | Exp {fpl(mv_n['exp'])}")

    # ── Bootstrap ──────────────────────────────────────────────────────────────
    print("\nEjecutando bootstrap (10,000 resamples)...")
    vl_prod = split(trades_prod, "VAL")
    vl_c    = split(trades_c,    "VAL")
    tr_prod = split(trades_prod, "TRAIN")
    tr_c    = split(trades_c,    "TRAIN")

    bs_train = bootstrap(tr_c,    tr_prod)
    bs_val   = bootstrap(vl_c,    vl_prod)

    # ── Clasificacion final ────────────────────────────────────────────────────
    rob_label, best_ema, n_pos, rob_detalle = analizar_robustez_ema(pf_sol_emas)

    mv_prod = metricas(vl_prod)
    mv_c    = metricas(vl_c)
    verdict = clasificar_sistema(mv_c, mv_prod, bs_val, rob_label, pf_sol_emas)

    # ── Forward ────────────────────────────────────────────────────────────────
    fw_prod = split(trades_prod, "FWD")
    fw_c    = split(trades_c,    "FWD")
    mf_prod = metricas(fw_prod)
    mf_c    = metricas(fw_c)

    # ── Generar reporte ────────────────────────────────────────────────────────
    ANIOS = ["2021", "2022", "2023", "2024", "2025", "2026"]
    lines = []; a = lines.append

    a("# SOL ALCISTA — Bootstrap Sistema C vs Produccion")
    a("")
    a("**Fecha:** 2026-08-14  ")
    a("**Estado:** INVESTIGACION PURA — 0 archivos de produccion modificados  ")
    a("**Simbolo:** SOLUSDT  ")
    a("**Metodologia:** identica a BTC/ETH Sistema C")
    a("")
    a("---")
    a("")

    # ── Sec 1: Resumen ejecutivo ───────────────────────────────────────────────
    a("## 1. Resumen ejecutivo")
    a("")
    a("| Sistema | Train Trades | Train PF | OOS Trades | OOS PF | OOS WR | OOS Exp | Fwd Trades | Veredicto |")
    a("|---------|-------------|----------|-----------|--------|--------|---------|-----------|-----------|")
    for label, trades in [("SOL Produccion", trades_prod), ("SOL Sistema C", trades_c)]:
        tr = split(trades, "TRAIN"); vl = split(trades, "VAL"); fw = split(trades, "FWD")
        mt = metricas(tr); mv = metricas(vl); mf = metricas(fw)
        verd = verdict if "Sistema" in label else "—"
        a(f"| **{label}** | {mt['n']} | {fpf(mt['pf'])} | {mv['n']} "
          f"| {fpf(mv['pf'])} | {mv['wr']:.1f}% | {fpl(mv['exp'])} "
          f"| {mf['n']} | {verd} |")
    a("")
    a("---")
    a("")

    # ── Sec 2: Metodologia ────────────────────────────────────────────────────
    a("## 2. Metodologia")
    a("")
    a("| Parametro | SOL Produccion | SOL Sistema C |")
    a("|-----------|---------------|--------------|")
    a("| Simbolo | SOLUSDT | SOLUSDT |")
    a("| RSI rango | 50–70 | 55–60 |")
    a(f"| SL | {SOL_PROD['sl']*100:.1f}% | {SOL_C['sl']*100:.1f}% |")
    a(f"| TP | {SOL_PROD['tp']*100:.1f}% | {SOL_C['tp']*100:.1f}% |")
    a("| Gate EMA | Ninguno | SOBRE EMAd (anti-lookahead) |")
    a(f"| Capital | ${CAPITAL} | ${CAPITAL} |")
    a(f"| Monto | ${MONTO} | ${MONTO} |")
    a(f"| Comision | {COMISION*100:.2f}% × 2 | {COMISION*100:.2f}% × 2 |")
    a("| Train | 2021-01-01 – 2023-12-31 | 2021-01-01 – 2023-12-31 |")
    a("| OOS (validacion) | 2024-01-01 – 2025-12-31 | 2024-01-01 – 2025-12-31 |")
    a("| Forward | 2026-01-01 – 2026-08-14 | 2026-01-01 – 2026-08-14 |")
    a("")
    a("**Fuente de parametros SOL Produccion:** `config_cartera.py` — SOL alcista, sin modificar.")
    a("**Anti-lookahead:** EMA diaria del dia D-1 para senales del dia D.")
    a("Warmup diario desde 2019-06-01 para EMA250 sin sesgo.")
    a("**RSI 55–60:** mismo patron que BTC/ETH Sistema C. No seleccionado post-hoc sobre SOL.")
    a("**SL/TP identicos** entre Produccion y Sistema C — el Delta de expectancy es limpio.")
    a("")
    a("---")
    a("")

    # ── Sec 3: SOL Produccion Train ────────────────────────────────────────────
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
        anios_validos = [y for y in ANIOS if any(t["anio"] == y for t in tlist)]
        if anios_validos:
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
                    nota = " ⚠️" if ma["n"] < 5 else ""
                    a(f"| {anio} | {ma['n']}{nota} | {ma['wr']:.0f}% "
                      f"| {fpf(ma['pf'])} | {fpl(ma['exp'])} | {fpl(ma['pl'])} |")
        a("")
        a("---")
        a("")

    seccion_metricas(3, "SOL Produccion", tr_prod, "Train 2021–2023")
    seccion_metricas(4, "SOL Sistema C",  tr_c,    "Train 2021–2023")
    seccion_metricas(5, "SOL Produccion", vl_prod, "OOS 2024–2025")
    seccion_metricas(6, "SOL Sistema C",  vl_c,    "OOS 2024–2025")

    # ── Sec 7: Comparacion OOS ─────────────────────────────────────────────────
    a("## 7. Comparacion OOS 2024–2025")
    a("")
    a("| Metrica | SOL Produccion | SOL Sistema C | Delta |")
    a("|---------|---------------|--------------|-------|")
    for label, attr, fmt in [
        ("Trades",      "n",   str),
        ("TP",          "tp",  str),
        ("SL",          "sl",  str),
        ("Win Rate",    "wr",  lambda v: f"{v:.1f}%"),
        ("PF",          "pf",  fpf),
        ("Exp/trade",   "exp", fpl),
        ("P/L",         "pl",  fpl),
        ("DD max",      "dd",  lambda v: f"{v:.1f}%"),
        ("Racha SL max","rsl", str),
        ("Racha TP max","rtp", str),
        ("Peor 5 trd",  "peor5", fpl),
    ]:
        vp = mv_prod[attr]; vc = mv_c[attr]
        try:
            delta = f"{vc-vp:+.1f}" if isinstance(vc, (int, float)) else "—"
        except Exception:
            delta = "—"
        a(f"| {label} | {fmt(vp)} | {fmt(vc)} | {delta} |")
    a("")
    if mv_c["n"] == 0:
        a("**SOL Sistema C no genero trades en OOS.** El gate EMA bloqueó todas las senales.")
        a("Esto puede indicar que SOL estuvo bajo sus EMAs de referencia durante 2024-2025,")
        a("o que RSI 55-60 no coincidio con precio > EMAd.")
    else:
        diff_n = mv_prod["n"] - mv_c["n"]
        mejor  = "mayor" if pf_num(mv_c["pf"]) > pf_num(mv_prod["pf"]) else "menor"
        a(f"Sistema C tiene {diff_n} trades menos en OOS pero PF {mejor} respecto a Produccion.")
    a("")
    a("---")
    a("")

    # ── Sec 8: Bootstrap ───────────────────────────────────────────────────────
    a("## 8. Bootstrap DeltaExpectancy — Sistema C vs Produccion")
    a("")
    a(f"Delta = Expectancy(Sistema C) - Expectancy(Produccion)")
    a(f"Metodo: {N_BOOT:,} resamples independientes por sistema.")
    a("")
    a("| Periodo | Delta obs | IC90% | IC95% | Cruza 0 | P(D>0) | Mediana |")
    a("|---------|-----------|-------|-------|---------|--------|---------|")
    for label, bs in [("Train 2021–2023", bs_train), ("OOS 2024–2025", bs_val)]:
        if bs["obs"] is None:
            a(f"| {label} | N/A | — | — | — | — | — |")
        else:
            lo90, hi90 = bs["ic90"]; lo95, hi95 = bs["ic95"]
            cruza = "Si ⚠️" if (lo95 is not None and lo95 < 0 < hi95) else "No"
            a(f"| {label} | {fpl(bs['obs'])} "
              f"| [{fpl(lo90)},{fpl(hi90)}] "
              f"| [{fpl(lo95)},{fpl(hi95)}] "
              f"| {cruza} | {bs['p_pos']:.1%} | {fpl(bs['median'])} |")
    a("")
    a("## 9. IC90% / IC95% detallado")
    a("")
    a("| Periodo | IC90% lo | IC90% hi | IC95% lo | IC95% hi |")
    a("|---------|----------|----------|----------|----------|")
    for label, bs in [("Train", bs_train), ("OOS", bs_val)]:
        if bs["obs"] is None:
            a(f"| {label} | N/A | N/A | N/A | N/A |")
        else:
            lo90, hi90 = bs["ic90"]; lo95, hi95 = bs["ic95"]
            a(f"| {label} | {fpl(lo90)} | {fpl(hi90)} | {fpl(lo95)} | {fpl(hi95)} |")
    a("")
    a("**Nota:** IC95% cruzando cero = varianza dentro del ruido de muestreo.")
    a("Bootstrap subestima varianza real por dependencia serial — no interpretar como prueba")
    a("estadistica formal.")
    a("")
    a("---")
    a("")

    # ── Sec 10: Robustez de vecindad ───────────────────────────────────────────
    a("## 10. Robustez de vecindad EMA100/150/200/250 (OOS 2024–2025)")
    a("")
    a("### Tabla de resultados por EMA")
    a("")
    a("| EMA | Val Trades | Val WR | Val PF | Val Exp | Val P/L | Val DD |")
    a("|-----|-----------|--------|--------|---------|---------|--------|")
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
    a(f"| PF OOS EMA100 | {fpf(pf_sol_emas[100])} |")
    a(f"| PF OOS EMA150 | {fpf(pf_sol_emas[150])} |")
    a(f"| PF OOS EMA200 | {fpf(pf_sol_emas[200])} |")
    a(f"| PF OOS EMA250 | {fpf(pf_sol_emas[250])} |")
    a(f"| EMA con mejor PF | EMA{best_ema} (PF {fpf(pf_sol_emas[best_ema])}) |")
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
    a("| Metrica | SOL Produccion | SOL Sistema C | Delta |")
    a("|---------|---------------|--------------|-------|")
    for label, attr, fmt in [
        ("Trades",    "n",   str),
        ("TP",        "tp",  str),
        ("SL",        "sl",  str),
        ("Win Rate",  "wr",  lambda v: f"{v:.1f}%"),
        ("PF",        "pf",  fpf),
        ("Exp/trade", "exp", fpl),
        ("P/L",       "pl",  fpl),
        ("DD max",    "dd",  lambda v: f"{v:.1f}%"),
        ("Racha SL",  "rsl", str),
    ]:
        vp = mf_prod[attr]; vc = mf_c[attr]
        try:
            delta = f"{vc-vp:+.1f}" if isinstance(vc, (int, float)) else "—"
        except Exception:
            delta = "—"
        a(f"| {label} | {fmt(vp)} | {fmt(vc)} | {delta} |")
    a("")

    # Explicar regimen forward
    if mf_c["n"] == 0 and mf_prod["n"] > 0:
        # Analizar por que Sistema C tiene 0 trades en forward
        # Revisar si SOL estuvo bajo EMA200d
        cierres_d = [float(v[4]) for v in velas_d]
        fechas_d  = [datetime.fromtimestamp(int(v[0]) / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
                     for v in velas_d]
        ema200_map = ema_maps[200]
        fwd_ts_ini = _ts(FWD_START)
        # Contar velas 4H en forward donde SOL < EMA200d
        bajo_ema = 0; sobre_ema = 0; sin_ema = 0
        for v in velas_4h:
            tsv = int(v[0])
            if tsv < fwd_ts_ini: continue
            tsdt = datetime.fromtimestamp(tsv / 1000, tz=timezone.utc)
            precio_sol = float(v[4])
            ev = get_ema(tsdt, ema200_map)
            if ev is None: sin_ema += 1
            elif precio_sol > ev: sobre_ema += 1
            else: bajo_ema += 1
        total_fwd = bajo_ema + sobre_ema + sin_ema
        pct_bajo  = bajo_ema / total_fwd * 100 if total_fwd > 0 else 0
        pct_sobre = sobre_ema / total_fwd * 100 if total_fwd > 0 else 0
        a(f"**Analisis de regimen SOL en 2026 (velas 4H):**")
        a("")
        a(f"| Estado vs EMA200d | Velas | Porcentaje |")
        a("|-------------------|-------|-----------|")
        a(f"| SOL SOBRE EMA200d | {sobre_ema} | {pct_sobre:.1f}% |")
        a(f"| SOL BAJO EMA200d | {bajo_ema} | {pct_bajo:.1f}% |")
        a(f"| Sin EMA disponible | {sin_ema} | — |")
        a(f"| Total velas forward | {total_fwd} | — |")
        a("")
        if pct_bajo > 60:
            a("**Conclusion de regimen:** SOL estuvo mayoritariamente BAJO su EMA200d en 2026.")
            a("Sistema C correctamente inactivo — esta disenado para operar solo en regimen alcista macro.")
            a("Igual que BTC Sistema C en 2026: la inactividad es una caracteristica de diseno, no un fallo.")
        elif pct_sobre > 60:
            a("**Conclusion de regimen:** SOL estuvo mayoritariamente SOBRE su EMA200d en 2026.")
            a("El gate no bloqueo por regimen — las 0 senales se deben a que RSI 55-60 no coincidio con")
            a("precio > EMAd en los momentos en que ambas condiciones podrian haberse dado.")
        else:
            a("**Conclusion de regimen:** SOL estuvo en regimen mixto en 2026 (sin dominancia clara).")
            a("Sistema C puede haber tenido periodos potencialmente activos pero sin coincidencia RSI/EMA.")
    elif mf_c["n"] == 0 and mf_prod["n"] == 0:
        a("**Ambos sistemas sin trades en forward 2026.** RSI 55-70 no toco el rango en el periodo.")
    elif mf_c["n"] > 0:
        a(f"**Sistema C activo en forward 2026:** {mf_c['n']} trades generados.")
        if pf_num(mf_c["pf"]) > 1.0:
            a(f"Resultado positivo en forward: PF {fpf(mf_c['pf'])}, Exp {fpl(mf_c['exp'])}.")
        else:
            a(f"Resultado negativo en forward: PF {fpf(mf_c['pf'])}, Exp {fpl(mf_c['exp'])}.")
        a("Forward con muestra < 30 trades — no usar como criterio de veredicto definitivo.")
    a("")

    # Trades forward individuales
    if fw_prod:
        a("### Trades Produccion — Forward 2026")
        a("")
        a("| # | Entrada | RSI | Precio E | Resultado | P/L |")
        a("|---|---------|-----|----------|-----------|-----|")
        for i, t in enumerate(fw_prod, 1):
            a(f"| {i} | {t['ts']} | {t['rsi']:.1f} | {t['precio']:.2f} | {t['res']} | {fpl(t['pl'])} |")
        a("")
    else:
        a("_SOL Produccion: sin trades en forward 2026._")
        a("")

    if fw_c:
        a("### Trades Sistema C — Forward 2026")
        a("")
        a("| # | Entrada | RSI | Precio E | EMA200d | Resultado | P/L |")
        a("|---|---------|-----|----------|---------|-----------|-----|")
        for i, t in enumerate(fw_c, 1):
            ema_str = f"{t['ema_v']:.2f}" if t["ema_v"] else "—"
            a(f"| {i} | {t['ts']} | {t['rsi']:.1f} | {t['precio']:.2f} "
              f"| {ema_str} | {t['res']} | {fpl(t['pl'])} |")
        a("")
    else:
        a("_SOL Sistema C: sin trades en forward 2026._")
        a("")

    a("---")
    a("")

    # ── Sec 12: Resultados anuales ────────────────────────────────────────────
    a("## 12. Resultados anuales (todos los sistemas)")
    a("")
    a("| Ano | Prod Trades | Prod PF | Prod WR | SistC Trades | SistC PF | SistC WR | Periodo |")
    a("|-----|------------|---------|---------|-------------|----------|----------|---------|")
    for anio in ANIOS:
        gp = [t for t in trades_prod if t["anio"] == anio]
        gc = [t for t in trades_c    if t["anio"] == anio]
        mp = metricas(gp); mc = metricas(gc)
        per_label = "TRAIN" if anio <= "2023" else ("FWD" if anio == "2026" else "**VAL**")
        np_s = str(mp["n"]) + (" ⚠️" if 0 < mp["n"] < 5 else "")
        nc_s = str(mc["n"]) + (" ⚠️" if 0 < mc["n"] < 5 else "")
        a(f"| {anio} | {np_s} | {fpf(mp['pf']) if mp['n']>0 else '—'} "
          f"| {mp['wr']:.0f}% if mp['n']>0 else '—' "
          f"| {nc_s} | {fpf(mc['pf']) if mc['n']>0 else '—'} "
          f"| {mc['wr']:.0f}% if mc['n']>0 else '—' "
          f"| {per_label} |")
    # Generar de nuevo correctamente (sin la interpolacion de f-string dentro de otra f-string)
    lines.pop()  # quitar la ultima fila incorrecta
    for anio in ANIOS:
        gp = [t for t in trades_prod if t["anio"] == anio]
        gc = [t for t in trades_c    if t["anio"] == anio]
        mp = metricas(gp); mc = metricas(gc)
        per_label = "TRAIN" if anio <= "2023" else ("FWD" if anio == "2026" else "**VAL**")
        pf_p = fpf(mp["pf"]) if mp["n"] > 0 else "—"
        wr_p = f"{mp['wr']:.0f}%" if mp["n"] > 0 else "—"
        pf_c = fpf(mc["pf"]) if mc["n"] > 0 else "—"
        wr_c = f"{mc['wr']:.0f}%" if mc["n"] > 0 else "—"
        np_s = f"{mp['n']}" + (" ⚠️" if 0 < mp["n"] < 5 else "")
        nc_s = f"{mc['n']}" + (" ⚠️" if 0 < mc["n"] < 5 else "")
        a(f"| {anio} | {np_s} | {pf_p} | {wr_p} | {nc_s} | {pf_c} | {wr_c} | {per_label} |")
    a("")
    a("---")
    a("")

    # ── Sec 13: Drawdown y rachas ─────────────────────────────────────────────
    a("## 13. Drawdown y rachas (OOS 2024–2025)")
    a("")
    a("| Sistema | DD max | Racha SL | Fechas | Racha TP | Peor 5 trades |")
    a("|---------|--------|----------|--------|----------|---------------|")
    for label, mv in [("SOL Produccion", mv_prod), ("SOL Sistema C", mv_c)]:
        a(f"| {label} | {mv['dd']:.1f}% | {mv['rsl']} | {mv['rsl_d']} "
          f"| {mv['rtp']} | {fpl(mv['peor5'])} |")
    a("")
    a("---")
    a("")

    # ── Sec 14: Sobreajuste ────────────────────────────────────────────────────
    a("## 14. Analisis de sobreajuste")
    a("")
    a("1. **RSI 55–60:** patron importado desde la investigacion BTC/ETH — NO seleccionado post-hoc")
    a("   sobre datos de SOL. Reduce el riesgo de mineria de datos especifica al activo.")
    a("")
    a(f"2. **EMA200d en OOS SOL:** PF {fpf(pf_sol_emas[200])}.")
    a(f"   Comportamiento de las 4 EMAs en OOS: {n_pos}/4 tienen PF > 1.0.")
    a(f"   EMA200 es la mejor: {'SI' if best_ema==200 else 'NO'}.")
    a(f"   Clasificacion de vecindad: **{rob_label}**.")
    a("")
    a(f"3. **Estabilidad Train → OOS:**")
    mt_prod_tr = metricas(tr_prod); mt_c_tr = metricas(tr_c)
    a(f"   Produccion: Train PF {fpf(mt_prod_tr['pf'])} → OOS PF {fpf(mv_prod['pf'])}")
    a(f"   Sistema C:  Train PF {fpf(mt_c_tr['pf'])}  → OOS PF {fpf(mv_c['pf'])}")
    if mt_c_tr["n"] > 0 and mv_c["n"] > 0:
        ratio_c = pf_num(mv_c["pf"]) / pf_num(mt_c_tr["pf"]) if pf_num(mt_c_tr["pf"]) > 0 else 0
        a(f"   Ratio PF (OOS/Train) Sistema C: {ratio_c:.2f} "
          f"({'estable ✅' if 0.7 <= ratio_c <= 1.5 else 'degradacion significativa ⚠️'})")
    a("")
    lo95v, hi95v = bs_val["ic95"] if bs_val["ic95"][0] is not None else (None, None)
    a(f"4. **Bootstrap OOS IC95%:** [{fpl(lo95v) if lo95v else 'N/A'},{fpl(hi95v) if hi95v else 'N/A'}]")
    if lo95v is not None and lo95v < 0 < hi95v:
        a("   Cruza cero: la diferencia esta dentro del ruido de muestreo.")
    elif lo95v and lo95v > 0:
        a("   No cruza cero: diferencia compatible con mejora estadisticamente clara.")
    elif bs_val["obs"] is None:
        a("   Bootstrap no calculable — muestra insuficiente en alguno de los sistemas.")
    a("")
    a(f"5. **Numero de trades OOS Sistema C:** {mv_c['n']}")
    if mv_c["n"] < 20:
        a("   Muestra OOS insuficiente (< 20) — veredicto INCONCLUSO por diseno.")
    elif mv_c["n"] < 30:
        a("   Muestra OOS limitada (20-29) — veredicto posible pero con baja confianza.")
    else:
        a("   Muestra OOS aceptable (>= 30) para emitir un veredicto preliminar.")
    a("")
    a("---")
    a("")

    # ── Sec 15: Limitaciones ──────────────────────────────────────────────────
    a("## 15. Limitaciones")
    a("")
    a("1. Sin trailing stop ni gates de produccion (eventos macro, horario, spread, guardian).")
    a("2. Sin compounding — monto fijo $5 por trade.")
    a("3. Bootstrap subestima varianza por dependencia serial. No es prueba estadistica formal.")
    a("4. RSI 55–60 no fue calibrado sobre SOL — se aplica el patron de BTC/ETH. Puede ser")
    a("   suboptimo o supraoptimo para SOL especificamente.")
    a("5. SOL tuvo un regimen de mercado muy distinto al de BTC/ETH (lanzamiento masivo 2021,")
    a("   caida FTX nov 2022, recuperacion 2023-2024). La EMA puede capturar ciclos diferentes.")
    a("6. Monto fijo $5 sin gestion de capital dinamica.")
    a("7. El gate EMA solo filtra entradas; las salidas (SL/TP) son identicas en ambos sistemas.")
    a("")
    a("---")
    a("")

    # ── Sec 16: Veredicto final ────────────────────────────────────────────────
    a("## 16. Veredicto final")
    a("")
    lo95_final, hi95_final = bs_val["ic95"] if bs_val["ic95"][0] else (None, None)
    a("### Tabla de criterios")
    a("")
    a("| Criterio | Estado |")
    a("|----------|--------|")
    a(f"| PF OOS > 1.0 | {'✅ ' + fpf(mv_c['pf']) if pf_num(mv_c['pf']) > 1.0 else '❌ ' + fpf(mv_c['pf'])} |")
    a(f"| Exp OOS > 0 | {'✅ ' + fpl(mv_c['exp']) if mv_c['exp'] > 0 else '❌ ' + fpl(mv_c['exp'])} |")
    a(f"| Trades OOS suficientes | {'✅ ' + str(mv_c['n']) if mv_c['n'] >= 20 else '⚠️ ' + str(mv_c['n'])} |")
    a(f"| EMA200 es la mejor | {'✅' if best_ema == 200 else '❌ (mejor: EMA' + str(best_ema) + ')'} |")
    a(f"| Vecinas todas con PF > 1.0 | {'✅' if rob_label == 'ROBUSTO_EMA' else '❌'} |")
    a(f"| EMAs positivas en OOS | {n_pos}/4 |")
    a(f"| Clasificacion vecindad | {rob_label} |")
    a(f"| Bootstrap IC95% no cruza 0 | {'✅' if lo95_final and lo95_final > 0 else '❌ (cruza 0)'} |")
    a(f"| P(D>0) bootstrap | {bs_val['p_pos']:.1%} if bs_val['p_pos'] is not None else 'N/A' |")
    a("")
    # Corregir la fila con condicional dentro de f-string
    lines.pop()
    p_pos_str = f"{bs_val['p_pos']:.1%}" if bs_val["p_pos"] is not None else "N/A"
    a(f"| P(D>0) bootstrap | {p_pos_str} |")
    a("")
    a(f"### Veredicto: **{verdict}**")
    a("")

    # Explicacion del veredicto
    if "ROBUSTO" in verdict and "🟢" in verdict:
        a("Todos los criterios de robustez se cumplen: PF OOS > 1.0, expectancy positiva,")
        a("EMA200 es la mejor EMA, todas las vecinas positivas, y IC95% no cruza cero.")
        a("El patron de vecindad es ROBUSTO y la evidencia estadistica es favorable.")
    elif "PROMETEDOR" in verdict:
        a("El sistema es positivo en OOS pero alguno de los criterios mas exigentes no se cumple:")
        a("el IC95% del bootstrap cruza cero, o la vecindad no es completamente robusta,")
        a("o EMA200 no es la mejor EMA. La evidencia es favorable pero no concluyente.")
    elif "FRAGIL" in verdict:
        a("El sistema es positivo en OOS pero el patron de vecindad EMA es fragil:")
        if rob_label == "FRAGIL_SOLO_EMA200":
            a("EMA200 es la unica EMA con PF > 1.0. El resultado puede ser especifico")
            a("de ese valor y no generalizable a otros horizontes temporales de EMA.")
        elif rob_label == "FRAGIL_EMA200_NEGATIVA":
            a("EMA200 tiene PF <= 1.0 en OOS.")
        a("No se recomienda activar en REAL sin evidencia adicional.")
    elif "INCONCLUSO" in verdict:
        a(f"Muestra OOS insuficiente ({mv_c['n']} trades) para emitir un veredicto formal.")
        a("Umbral minimo orientativo: 20 trades. Continuar acumulando datos.")
    elif "DESCARTADO" in verdict:
        a("PF OOS <= 1.0 y/o expectancy OOS <= 0. Sistema C no supera a Produccion en OOS.")
        a("No se recomienda activar. Posibles causas: RSI 55-60 no aplica a SOL, ")
        a("o EMA gate excluye las senales rentables.")
    a("")
    a("---")
    a("")

    # ── Sec 17: Decision para REAL ────────────────────────────────────────────
    a("## 17. Decision para REAL")
    a("")
    a("| Campo | Estado |")
    a("|-------|--------|")
    a("| Produccion SOL modificada | **NO** |")
    a("| Sistema C SOL activado | **NO** |")
    a("| config_cartera.py | **SIN CAMBIOS** |")
    a("| auditoria.csv | **SIN CAMBIOS** |")
    a("| billetera.json | **SIN CAMBIOS** |")
    a(f"| Veredicto | **{verdict}** |")
    a("")
    if "ROBUSTO" in verdict and "🟢" in verdict:
        a("**Proximo paso:** Sistema C SOL es candidato para validacion REAL controlada.")
        a("Requiere >= 30 trades reales antes de cualquier decision de activacion permanente.")
        a("Respetar el protocolo REAL establecido.")
    elif "PROMETEDOR" in verdict:
        a("**Proximo paso:** Sistema C SOL es prometedor pero insuficientemente concluyente.")
        a("Acumular >= 30 trades reales para elevar la confianza. No activar todavia.")
    elif "FRAGIL" in verdict or "INCONCLUSO" in verdict:
        a("**Proximo paso:** No activar Sistema C SOL. Requiere mas evidencia o ajuste de")
        a("parametros con nuevo backtest documentado antes de cualquier cambio.")
    else:
        a("**Proximo paso:** Sistema C SOL descartado con la configuracion actual.")
        a("Produccion SOL permanece sin cambios.")
    a("")
    a("**Siguiente investigacion:** AVAX ALCISTA (pendiente segun Plan Maestro).")
    a("")
    a("---")
    a("")
    a("**ESTADO FINAL:**")
    a("- Produccion modificada: **NO**")
    a(f"- Veredicto SOL Sistema C: **{verdict}**")
    a("- Sistema C activado: **NO**")
    a("")
    a("Archivos:")
    a("- `reports/2026-08-14_sol-bootstrap-sistema-c-vs-produccion.md` (este reporte)")
    a("- `sol_bootstrap_sistema_c_vs_produccion.py` (script)")

    # ── Escribir reporte ───────────────────────────────────────────────────────
    os.makedirs(os.path.dirname(os.path.expanduser(REPORT_PATH)), exist_ok=True)
    with open(os.path.expanduser(REPORT_PATH), "w") as f:
        f.write("\n".join(lines))

    # ── Consola ────────────────────────────────────────────────────────────────
    print()
    print("=" * 62)
    print("RESULTADOS SOL — OOS 2024-2025")
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
    print()
    print("VECINDAD EMA (OOS)")
    print("  " + " | ".join(
        f"EMA{n}={'✅' if pf_sol_emas[n]>1 else '❌'}{fpf(pf_sol_emas[n])}"
        for n in EMAs
    ))
    print(f"  EMA mejor: EMA{best_ema} | {n_pos}/4 positivas | "
          f"EMA200 mejor: {'SI' if best_ema==200 else 'NO'} | {rob_label}")
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
    print(f"VEREDICTO SOL SISTEMA C: {verdict}")
    print("ESTADO PRODUCCION:        NO MODIFICADA")
    print("SISTEMA C:                NO ACTIVADO")
    print("=" * 62)
    print()
    print(f"Reporte: {REPORT_PATH}")
    print()
    print("less " + REPORT_PATH)


if __name__ == "__main__":
    main()
