"""
eth_bootstrap_sistema_c_vs_produccion.py
ETH ALCISTA — Investigacion exhaustiva Sistema C vs Produccion
INVESTIGACION PURA — 0 archivos de produccion modificados.

RECREADO 2026-08-16: el script original que genero los numeros de ETH en
CLAUDE.md (PF OOS 0.960, 67 trades, 0/4 EMAs) se corrio ad-hoc el 2026-08-14
(commit 839a279) y nunca se commiteo — no quedo en el repo. Este script
reconstruye la misma metodologia (identica a btc_bootstrap_sistema_c_vs_produccion.py)
para poder exportar los trades crudos a reports/raw/ con utils_backtest.py.

Sistemas comparados:
  Produccion ETH : RSI 60-75, SL 4.5%, TP 5.0%, sin gate  (config_cartera.py)
  Sistema C ETH  : RSI 55-60, SL 5.0%, TP 6.0%, gate PRECIO SOBRE EMA diaria

Taxonomia de clasificacion EMA (igual que BTC/BNB/SOL/AVAX):
  ROBUSTA_POSITIVA     : 4/4 EMAs con PF > 1.0 Y EMA200 es la mejor
  PARCIALMENTE_ROBUSTA : algunas EMAs positivas, o EMA200 no es la mejor
  FRAGIL_EMA200_NEGATIVA: EMA200 con PF <= 1.0
  NEGATIVA             : ninguna EMA con PF > 1.0

Veredictos:
  ACTIVABLE   : evidencia OOS fuerte y robusta (IC95 no cruza 0 + vecindad ROBUSTA)
  PROMETEDOR  : OOS positivo pero IC95 cruza 0 o vecindad parcial
  DESCARTADO  : PF OOS <= 1.0 o expectancy <= 0

Anti-lookahead: EMA del dia D-1 se usa para senales del dia D.
Warmup diario desde 2019-06-01 para EMA250.
"""
import json, os, random, urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta

from utils_backtest import export_trades_csv

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
COMISION     = 0.001          # 0.10% por lado
N_BOOT       = 10000
EMAs         = [100, 150, 200, 250]

# Produccion ETH (config_cartera.py — alcista, sin modificar)
ETH_PROD = dict(sym="ETHUSDT", rsi_min=60.0, rsi_max=75.0,
                sl=0.045, tp=0.050, gate_ema=None)
# Sistema C ETH (patron identico BTC/BNB/SOL/AVAX)
ETH_C    = dict(sym="ETHUSDT", rsi_min=55.0, rsi_max=60.0,
                sl=0.050, tp=0.060, gate_ema=200)

# Sensibilidad RSI (descriptiva, sin seleccion OOS)
RSI_SENS = [
    (50.0, 55.0, "RSI 50-55"),
    (55.0, 60.0, "RSI 55-60 (Sistema C)"),
    (60.0, 65.0, "RSI 60-65"),
]

REPORT_PATH = os.path.expanduser(
    "~/bot-padre-v2/reports/2026-08-16_eth-bootstrap-sistema-c-vs-produccion.md"
)

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
    """EMA de n periodos sobre cierres diarios. Retorna {fecha_str: valor}."""
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
    """
    Anti-lookahead: retorna la EMA del ultimo dia cerrado antes de la vela 4H.
    Para una vela 4H abierta en el dia D, busca la EMA de D-1 hasta D-5.
    Nunca usa el dia D (vela diaria aun abierta).
    """
    for d in range(1, 6):
        f = (ts_dt - timedelta(days=d)).strftime("%Y-%m-%d")
        if f in ema_map:
            return ema_map[f]
    return None

# ── RSI (14 periodos, ventana de 15 cierres) ──────────────────────────────────
def rsi_calc(cierres):
    """
    RSI Wilder simplificado: promedio simple de ganancias/perdidas en 14 periodos.
    Requiere al menos 15 cierres (14 diferencias).
    """
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

# ── Simulacion (1 posicion a la vez, sin trailing) ────────────────────────────
def simular(velas_4h, ema_map, rsi_min, rsi_max, sl, tp,
            use_gate=False, desde_str=TRAIN_START, hasta_str=FWD_END_STR):
    """
    Logica de entrada:
      1. RSI 4H cae en [rsi_min, rsi_max)
      2. Si use_gate=True: precio 4H > EMA diaria del dia D-1
      3. Solo si no hay posicion abierta
    Logica de salida:
      - SL: precio <= precio_entrada * (1 - sl)
      - TP: precio >= precio_entrada * (1 + tp)
    Comision: (sl o tp) * MONTO - MONTO * COMISION * 2
    """
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
                    "precio": round(ep, 2),
                    "ema_v": round(e_ema_v, 2) if e_ema_v else None,
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
    pls  = [t["pl"] for t in srt]
    peor5 = min((round(sum(pls[i:i + 5]), 4) for i in range(max(1, len(pls) - 4))),
                default=0.0)
    return dict(n=n, tp=len(tps), sl=len(sls), wr=wr, pf=pf, exp=exp, pl=pl,
                dd=round(mxdd, 1), rsl=mrsl, rsl_d=sd, rtp=mrtp, peor5=peor5)

# ── Bootstrap DeltaExpectancy ─────────────────────────────────────────────────
def bootstrap(ta, tb, n_iter=N_BOOT, seed=42):
    """
    Resampleo independiente por sistema.
    Delta = E[exp(ta)] - E[exp(tb)]
    Retorna IC90, IC95, P(Delta>0), mediana.
    ADVERTENCIA: subestima varianza real por dependencia serial entre trades.
    """
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

# ── Robustez de vecindad EMA ──────────────────────────────────────────────────
def analizar_robustez_ema(pf_emas):
    """
    ROBUSTA_POSITIVA     : 4/4 EMAs con PF > 1.0 Y EMA200 es la mejor
    PARCIALMENTE_ROBUSTA : EMA200 mejor pero no todas las vecinas positivas,
                           o algunas positivas pero EMA200 no es la mejor
    FRAGIL_EMA200_NEGATIVA: EMA200 tiene PF <= 1.0
    NEGATIVA             : ninguna EMA tiene PF > 1.0
    """
    pf200   = pf_emas.get(200, 0.0)
    best_n  = max(pf_emas, key=pf_emas.get)
    best_pf = pf_emas[best_n]
    n_pos   = sum(1 for pf in pf_emas.values() if pf > 1.0)
    vecinas = {n: pf for n, pf in pf_emas.items() if n != 200}

    if n_pos == 0:
        return ("NEGATIVA", best_n, n_pos,
                f"Ninguna EMA con PF > 1.0. Mejor: EMA{best_n} (PF {best_pf:.3f}).")

    if pf200 <= 1.0:
        return ("FRAGIL_EMA200_NEGATIVA", best_n, n_pos,
                f"EMA200 PF {pf200:.3f} <= 1.0. Mejor: EMA{best_n} (PF {best_pf:.3f}). "
                f"{n_pos}/4 EMAs positivas.")

    if best_n != 200:
        return ("PARCIALMENTE_ROBUSTA", best_n, n_pos,
                f"EMA200 positiva (PF {pf200:.3f}) pero NO es la mejor. "
                f"Mejor: EMA{best_n} (PF {best_pf:.3f}). {n_pos}/4 EMAs positivas.")

    todas_pos = all(pf > 1.0 for pf in vecinas.values())
    n_vec_pos = sum(1 for pf in vecinas.values() if pf > 1.0)

    if todas_pos:
        return ("ROBUSTA_POSITIVA", best_n, n_pos,
                f"EMA200 es la mejor (PF {pf200:.3f}) Y las {len(vecinas)} vecinas "
                f"tambien tienen PF > 1.0. Zona robusta alrededor de EMA200.")

    return ("PARCIALMENTE_ROBUSTA", best_n, n_pos,
            f"EMA200 es la mejor (PF {pf200:.3f}). {n_vec_pos}/{len(vecinas)} vecinas "
            f"con PF > 1.0. Robustez parcial.")

# ── Clasificacion final ───────────────────────────────────────────────────────
def clasificar_sistema(m_val, m_prod_val, bs_val, rob_label, pf_emas):
    """
    ACTIVABLE   : ROBUSTA_POSITIVA + IC95 no cruza 0 + PF/Exp positivos
    PROMETEDOR  : PF/Exp positivos, pero IC95 cruza 0 o vecindad parcial
    DESCARTADO  : PF OOS <= 1.0 o Exp <= 0
    INCONCLUSO  : muestra < 20 trades OOS
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
    if rob_label in ("NEGATIVA", "FRAGIL_EMA200_NEGATIVA"):
        return "🔴 DESCARTADO"
    if rob_label == "ROBUSTA_POSITIVA":
        return "🟢 ACTIVABLE" if ic_no_cruza else "🟡 PROMETEDOR"
    return "🟡 PROMETEDOR"

# ── Regimen forward ───────────────────────────────────────────────────────────
def analizar_regimen_forward(velas_4h, ema_map_200):
    fwd_ts_ini = _ts(FWD_START)
    sobre = bajo = sin_ema = 0
    for v in velas_4h:
        tsv = int(v[0])
        if tsv < fwd_ts_ini: continue
        tsdt = datetime.fromtimestamp(tsv / 1000, tz=timezone.utc)
        precio = float(v[4])
        ev = get_ema(tsdt, ema_map_200)
        if ev is None:   sin_ema += 1
        elif precio > ev: sobre += 1
        else:             bajo  += 1
    return sobre, bajo, sin_ema

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    ahora_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    ANIOS = ["2021", "2022", "2023", "2024", "2025", "2026"]

    print("=" * 62)
    print("ETH ALCISTA — Bootstrap Sistema C vs Produccion (exhaustivo)")
    print("=" * 62)

    print("\n[1/5] Descargando datos ETHUSDT...")
    velas_4h_raw = fetch("ETHUSDT", "4h", _ts(FECHA_WU_4H))
    velas_d_raw  = fetch("ETHUSDT", "1d", _ts(FECHA_WU_D))
    velas_4h = [v for v in velas_4h_raw if int(v[6]) < ahora_ms]
    velas_d  = [v for v in velas_d_raw  if int(v[6]) < ahora_ms]
    print(f"      {len(velas_4h)} velas 4H | {len(velas_d)} velas 1D")

    print("[2/5] Construyendo mapas EMA (anti-lookahead)...")
    ema_maps = {}
    for n in EMAs:
        ema_maps[n] = build_ema(velas_d, n)
        print(f"      EMA{n}: {len(ema_maps[n])} fechas")

    print("[3/5] Simulando Produccion y Sistema C...")
    trades_prod = simular(velas_4h, {},
                          ETH_PROD["rsi_min"], ETH_PROD["rsi_max"],
                          ETH_PROD["sl"],      ETH_PROD["tp"], use_gate=False)
    trades_c    = simular(velas_4h, ema_maps[200],
                          ETH_C["rsi_min"], ETH_C["rsi_max"],
                          ETH_C["sl"],      ETH_C["tp"],      use_gate=True)

    def _a_filas_export(trades, sl, tp):
        return [{
            "symbol": "ETHUSDT",
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
        _a_filas_export(trades_prod, ETH_PROD["sl"], ETH_PROD["tp"]),
        "eth_produccion_vs_sistemac")
    ruta_csv_c = export_trades_csv(
        _a_filas_export(trades_c, ETH_C["sl"], ETH_C["tp"]),
        "eth_sistemac_vs_produccion")
    print(f"      CSV crudo Produccion: {ruta_csv_prod}")
    print(f"      CSV crudo Sistema C:  {ruta_csv_c}")

    def split(trades, per): return [t for t in trades if t["per"] == per]

    for lbl, trades in [("Produccion", trades_prod), ("Sistema C", trades_c)]:
        tr = split(trades, "TRAIN"); vl = split(trades, "VAL"); fw = split(trades, "FWD")
        print(f"      ETH {lbl}: Train {metricas(tr)['n']}T PF {fpf(metricas(tr)['pf'])} "
              f"| OOS {metricas(vl)['n']}T PF {fpf(metricas(vl)['pf'])} "
              f"| Fwd {metricas(fw)['n']}T")

    print("[4/5] Robustez EMA100/150/200/250 (OOS)...")
    pf_eth_emas = {}; rob_detalles = {}
    for n in EMAs:
        t_n = simular(velas_4h, ema_maps[n],
                      ETH_C["rsi_min"], ETH_C["rsi_max"],
                      ETH_C["sl"],      ETH_C["tp"],
                      use_gate=True, hasta_str=VAL_END)
        vl_n = split(t_n, "VAL"); mv_n = metricas(vl_n)
        pf_eth_emas[n] = pf_num(mv_n["pf"])
        rob_detalles[n] = {"vl": vl_n, "m": mv_n}
        print(f"      EMA{n}: {mv_n['n']} trades OOS | PF {fpf(mv_n['pf'])} | Exp {fpl(mv_n['exp'])}")

    print("[5/5] Sensibilidad RSI (descriptiva, con gate EMA200)...")
    rsi_sens_results = {}
    for rsi_lo, rsi_hi, label in RSI_SENS:
        t_s = simular(velas_4h, ema_maps[200],
                      rsi_lo, rsi_hi, ETH_C["sl"], ETH_C["tp"],
                      use_gate=True)
        tr_s = split(t_s, "TRAIN"); vl_s = split(t_s, "VAL")
        rsi_sens_results[label] = {
            "train": metricas(tr_s), "val": metricas(vl_s),
            "lo": rsi_lo, "hi": rsi_hi
        }
        mv_s = metricas(vl_s)
        print(f"      {label}: OOS {mv_s['n']} trades | PF {fpf(mv_s['pf'])} | Exp {fpl(mv_s['exp'])}")

    print("\nBootstrap (10,000 resamples)...")
    tr_prod = split(trades_prod, "TRAIN"); vl_prod = split(trades_prod, "VAL")
    tr_c    = split(trades_c,    "TRAIN"); vl_c    = split(trades_c,    "VAL")
    fw_prod = split(trades_prod, "FWD");   fw_c    = split(trades_c,    "FWD")
    bs_train = bootstrap(tr_c, tr_prod)
    bs_val   = bootstrap(vl_c, vl_prod)

    rob_label, best_ema, n_pos, rob_detalle = analizar_robustez_ema(pf_eth_emas)
    mv_prod = metricas(vl_prod); mv_c = metricas(vl_c)
    mt_prod = metricas(tr_prod); mt_c = metricas(tr_c)
    mf_prod = metricas(fw_prod); mf_c = metricas(fw_c)
    verdict = clasificar_sistema(mv_c, mv_prod, bs_val, rob_label, pf_eth_emas)

    sobre_fwd, bajo_fwd, sin_ema_fwd = analizar_regimen_forward(velas_4h, ema_maps[200])
    total_fwd = sobre_fwd + bajo_fwd + sin_ema_fwd
    pct_sobre = sobre_fwd / total_fwd * 100 if total_fwd > 0 else 0
    pct_bajo  = bajo_fwd  / total_fwd * 100 if total_fwd > 0 else 0

    ratio_pf_c    = (pf_num(mv_c["pf"]) / pf_num(mt_c["pf"])
                     if mt_c["n"] > 0 and mt_c["pf"] > 0 else None)
    ratio_pf_prod = (pf_num(mv_prod["pf"]) / pf_num(mt_prod["pf"])
                     if mt_prod["n"] > 0 and mt_prod["pf"] > 0 else None)

    lo95_v, hi95_v = bs_val["ic95"] if bs_val["ic95"][0] is not None else (None, None)
    n_pos_rsi = sum(1 for _, res in rsi_sens_results.items()
                    if pf_num(res["val"]["pf"]) > 1.0)

    # ═════════════════════════════════════════════════════════════════════════
    # REPORTE MARKDOWN
    # ═════════════════════════════════════════════════════════════════════════
    lines = []; a = lines.append

    a("# ETH ALCISTA — Investigacion exhaustiva Sistema C vs Produccion")
    a("")
    a("**Fecha:** 2026-08-16 (script recreado — ver nota de origen mas abajo)  ")
    a("**Estado:** INVESTIGACION PURA — 0 archivos de produccion modificados  ")
    a("**Simbolo:** ETHUSDT")
    a("")
    a("---")
    a("")
    a("## 0. Nota de origen")
    a("")
    a("El script original que produjo los numeros de ETH citados en CLAUDE.md")
    a("(PF OOS 0.960, 67 trades, 0/4 EMAs — commit `839a279`, 2026-08-14) se corrio")
    a("ad-hoc y nunca se commiteo. Este script lo reconstruye con metodologia identica")
    a("(misma logica de `simular()`, mismo bootstrap, mismo gate EMA200d anti-lookahead)")
    a("para poder exportar los trades crudos a `reports/raw/` — si los resultados de mas")
    a("abajo coinciden con los citados en CLAUDE.md, confirma que la reconstruccion es fiel.")
    a("")
    a("---")
    a("")

    a("## 1. Resumen ejecutivo")
    a("")
    a("| Sistema | Train T | Train PF | OOS T | OOS PF | OOS WR | OOS Exp | Fwd T | Veredicto |")
    a("|---------|---------|----------|-------|--------|--------|---------|-------|-----------|")
    for lbl, mt, mv, mf, verd in [
        ("ETH Produccion", mt_prod, mv_prod, mf_prod, "—"),
        ("ETH Sistema C",  mt_c,    mv_c,    mf_c,    verdict),
    ]:
        a(f"| **{lbl}** | {mt['n']} | {fpf(mt['pf'])} | {mv['n']} "
          f"| {fpf(mv['pf'])} | {mv['wr']:.1f}% | {fpl(mv['exp'])} "
          f"| {mf['n']} | {verd} |")
    a("")
    a("---")
    a("")

    a("## 2. Parametros")
    a("")
    a("| Parametro | ETH Produccion | ETH Sistema C |")
    a("|-----------|---------------|--------------|")
    a(f"| RSI rango | {ETH_PROD['rsi_min']:.0f}–{ETH_PROD['rsi_max']:.0f} | {ETH_C['rsi_min']:.0f}–{ETH_C['rsi_max']:.0f} |")
    a(f"| SL | {ETH_PROD['sl']*100:.1f}% | {ETH_C['sl']*100:.1f}% |")
    a(f"| TP | {ETH_PROD['tp']*100:.1f}% | {ETH_C['tp']*100:.1f}% |")
    a("| Gate EMA | Ninguno | PRECIO > EMA diaria D-1 (anti-lookahead) |")
    a(f"| Capital | ${CAPITAL} | ${CAPITAL} |")
    a(f"| Monto | ${MONTO} | ${MONTO} |")
    a(f"| Comision | {COMISION*100:.2f}%×2 | {COMISION*100:.2f}%×2 |")
    a("| Trailing | No | No |")
    a("")
    a("**Nota:** SL/TP DISTINTOS entre sistemas (4.5/5.0% Prod vs 5.0/6.0% Sistema C).")
    a("El delta de expectancy incluye el efecto del gate EMA, RSI mas estrecho Y distinto SL/TP.")
    a("")
    a("---")
    a("")

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
        a(f"| Peor ventana 5 | {fpl(m['peor5'])} |")
        a("")
        a("**Por ano:**")
        a("")
        a("| Ano | Trades | WR | PF | Exp | P/L | Periodo |")
        a("|-----|--------|----|----|-----|-----|---------|")
        for anio in ANIOS:
            g = [t for t in tlist if t["anio"] == anio]; ma = metricas(g)
            per_lbl = "TRAIN" if anio <= "2023" else ("FWD" if anio == "2026" else "VAL")
            if ma["n"] == 0:
                a(f"| {anio} | 0 | — | — | — | — | {per_lbl} |")
            else:
                nota = " ⚠️" if ma["n"] < 10 else ""
                a(f"| {anio} | {ma['n']}{nota} | {ma['wr']:.0f}% "
                  f"| {fpf(ma['pf'])} | {fpl(ma['exp'])} | {fpl(ma['pl'])} | {per_lbl} |")
        a("")
        a("---")
        a("")

    seccion_metricas(3, "ETH Produccion", tr_prod, "Train 2021–2023")
    seccion_metricas(4, "ETH Sistema C",  tr_c,    "Train 2021–2023")
    seccion_metricas(5, "ETH Produccion", vl_prod, "OOS 2024–2025")
    seccion_metricas(6, "ETH Sistema C",  vl_c,    "OOS 2024–2025")

    a("## 7. Comparacion OOS 2024–2025")
    a("")
    a("| Metrica | ETH Produccion | ETH Sistema C | Delta |")
    a("|---------|---------------|--------------|-------|")
    for lbl, attr, fmt in [
        ("Trades","n",str), ("TP","tp",str), ("SL","sl",str),
        ("Win Rate","wr",lambda v: f"{v:.1f}%"), ("PF","pf",fpf),
        ("Exp/trade","exp",fpl), ("P/L","pl",fpl),
        ("DD max","dd",lambda v: f"{v:.1f}%"),
        ("Racha SL","rsl",str), ("Racha TP","rtp",str), ("Peor 5","peor5",fpl),
    ]:
        vp = mv_prod[attr]; vc = mv_c[attr]
        try: delta = f"{vc-vp:+.1f}" if isinstance(vc, (int, float)) else "—"
        except Exception: delta = "—"
        a(f"| {lbl} | {fmt(vp)} | {fmt(vc)} | {delta} |")
    a("")
    a(f"**Delta Expectancy = {fpl(round(mv_c['exp']-mv_prod['exp'], 4))}**")
    a("")
    a("---")
    a("")

    a("## 8. Bootstrap DeltaExpectancy")
    a("")
    a("Δ = Expectancy(Sistema C) − Expectancy(Produccion)")
    a(f"Metodo: {N_BOOT:,} resamples independientes por sistema.")
    a("")
    a("⚠️ *Dependencia serial puede subestimar varianza real. No prueba estadistica formal.*")
    a("")
    a("| Periodo | Delta obs | IC90% | IC95% | IC95 cruza 0 | P(D>0) | Mediana |")
    a("|---------|-----------|-------|-------|-------------|--------|---------|")
    for lbl, bs in [("Train 2021–2023", bs_train), ("OOS 2024–2025", bs_val)]:
        if bs["obs"] is None:
            a(f"| {lbl} | N/A | — | — | — | — | — |")
        else:
            lo90, hi90 = bs["ic90"]; lo95, hi95 = bs["ic95"]
            c95 = "Si ⚠️" if (lo95 is not None and lo95 < 0 < hi95) else "No ✅"
            a(f"| {lbl} | {fpl(bs['obs'])} | [{fpl(lo90)},{fpl(hi90)}] "
              f"| [{fpl(lo95)},{fpl(hi95)}] | {c95} | {bs['p_pos']:.1%} | {fpl(bs['median'])} |")
    a("")
    a("---")
    a("")

    a("## 9. Robustez EMA100/150/200/250 (OOS 2024–2025)")
    a("")
    a("| EMA | Trades OOS | WR | PF | Exp | P/L | DD |")
    a("|-----|-----------|----|----|-----|-----|-----|")
    for n in EMAs:
        mv_n = rob_detalles[n]["m"]; bench = " ←" if n == 200 else ""
        a(f"| **EMA{n}**{bench} | {mv_n['n']} | {mv_n['wr']:.1f}% | {fpf(mv_n['pf'])} "
          f"| {fpl(mv_n['exp'])} | {fpl(mv_n['pl'])} | {mv_n['dd']:.1f}% |")
    a("")
    a("| Campo | Valor |")
    a("|-------|-------|")
    a(f"| EMA con mejor PF OOS | EMA{best_ema} ({fpf(pf_eth_emas[best_ema])}) |")
    a(f"| EMAs con PF > 1.0 | {n_pos}/4 |")
    a(f"| EMA200 es la mejor | {'SI ✅' if best_ema==200 else 'NO ❌'} |")
    a(f"| Clasificacion | **{rob_label}** |")
    a(f"| Detalle | {rob_detalle} |")
    a("")
    a("---")
    a("")

    a("## 10. Sensibilidad RSI (descriptiva — con gate EMA200)")
    a("")
    a("**IMPORTANTE:** Descriptiva. No se usa para seleccionar parametros en OOS.")
    a("")
    a("| Rango RSI | Train T | Train PF | Train Exp | OOS T | OOS PF | OOS Exp |")
    a("|-----------|---------|----------|-----------|-------|--------|---------|")
    for lbl, res in rsi_sens_results.items():
        mt = res["train"]; mv = res["val"]
        marca = " **← Sistema C**" if "55-60" in lbl else ""
        a(f"| **{lbl}**{marca} | {mt['n']} | {fpf(mt['pf'])} | {fpl(mt['exp'])} "
          f"| {mv['n']} | {fpf(mv['pf'])} | {fpl(mv['exp'])} |")
    a("")
    a(f"{n_pos_rsi}/3 rangos RSI con PF OOS > 1.0.")
    a("")
    a("---")
    a("")

    a("## 11. Estabilidad Train → OOS")
    a("")
    a("| Metrica | Prod Train | Prod OOS | SistC Train | SistC OOS |")
    a("|---------|-----------|---------|------------|----------|")
    for lbl, attr, fmt in [("Trades","n",str),("PF","pf",fpf),
                            ("WR","wr",lambda v:f"{v:.1f}%"),("Exp","exp",fpl)]:
        a(f"| {lbl} | {fmt(mt_prod[attr])} | {fmt(mv_prod[attr])} "
          f"| {fmt(mt_c[attr])} | {fmt(mv_c[attr])} |")
    r_c = f"{ratio_pf_c:.2f}" if ratio_pf_c else "N/A"
    r_p = f"{ratio_pf_prod:.2f}" if ratio_pf_prod else "N/A"
    a("")
    a(f"Ratio PF (OOS/Train) — Produccion: {r_p} | Sistema C: {r_c}")
    if ratio_pf_c:
        est = ("Estable" if ratio_pf_c >= 0.85
               else "Degradacion moderada" if ratio_pf_c >= 0.60
               else "Degradacion fuerte")
        a(f"Sistema C ratio PF = {ratio_pf_c:.2f} → {est}.")
    a("")
    a("---")
    a("")

    a("## 12. Forward 2026 (2026-01-01 → 2026-08-14)")
    a("")
    a("| Metrica | ETH Produccion | ETH Sistema C | Delta |")
    a("|---------|---------------|--------------|-------|")
    for lbl, attr, fmt in [
        ("Trades","n",str),("TP","tp",str),("SL","sl",str),
        ("Win Rate","wr",lambda v:f"{v:.1f}%"),("PF","pf",fpf),
        ("Exp","exp",fpl),("P/L","pl",fpl),("DD max","dd",lambda v:f"{v:.1f}%"),
    ]:
        vp = mf_prod[attr]; vc = mf_c[attr]
        try: delta = f"{vc-vp:+.1f}" if isinstance(vc,(int,float)) else "—"
        except Exception: delta = "—"
        a(f"| {lbl} | {fmt(vp)} | {fmt(vc)} | {delta} |")
    a("")
    a("### Regimen ETH vs EMA200d en Forward 2026")
    a("")
    a("| Estado | Velas | % |")
    a("|--------|-------|---|")
    a(f"| ETH SOBRE EMA200d | {sobre_fwd} | {pct_sobre:.1f}% |")
    a(f"| ETH BAJO EMA200d  | {bajo_fwd}  | {pct_bajo:.1f}% |")
    a(f"| Sin EMA | {sin_ema_fwd} | — |")
    a(f"| Total | {total_fwd} | — |")
    a("")
    if mf_c["n"] == 0:
        a(f"**Sistema C: 0 trades.** ETH estuvo {pct_bajo:.0f}% del tiempo bajo su EMA200d "
          f"(o RSI 55-60 no coincidio con precio > EMAd).")
    elif mf_c["n"] > 0:
        a(f"**Sistema C: {mf_c['n']} trades.** PF {fpf(mf_c['pf'])} | Exp {fpl(mf_c['exp'])}.")
    a("")
    if fw_prod:
        a("### Trades Produccion — Forward 2026")
        a("")
        a("| # | Entrada | RSI | Precio | Resultado | P/L |")
        a("|---|---------|-----|--------|-----------|-----|")
        for i, t in enumerate(fw_prod, 1):
            a(f"| {i} | {t['ts']} | {t['rsi']:.1f} | ${t['precio']:,.2f} | {t['res']} | {fpl(t['pl'])} |")
        a("")
    if fw_c:
        a("### Trades Sistema C — Forward 2026")
        a("")
        a("| # | Entrada | RSI | Precio | EMA200d | Resultado | P/L |")
        a("|---|---------|-----|--------|---------|-----------|-----|")
        for i, t in enumerate(fw_c, 1):
            ema_s = f"${t['ema_v']:,.2f}" if t["ema_v"] else "—"
            a(f"| {i} | {t['ts']} | {t['rsi']:.1f} | ${t['precio']:,.2f} "
              f"| {ema_s} | {t['res']} | {fpl(t['pl'])} |")
        a("")
    a("---")
    a("")

    a("## 13. Resultados anuales")
    a("")
    a("| Ano | Prod T | Prod PF | Prod WR | SistC T | SistC PF | SistC WR | Periodo |")
    a("|-----|--------|---------|---------|---------|----------|----------|---------|")
    for anio in ANIOS:
        gp = [t for t in trades_prod if t["anio"]==anio]
        gc = [t for t in trades_c    if t["anio"]==anio]
        mp = metricas(gp); mc2 = metricas(gc)
        per_lbl = "TRAIN" if anio <= "2023" else ("FWD" if anio=="2026" else "**VAL**")
        def fs(m):
            if m["n"]==0: return "0 | — | —"
            return f"{m['n']}{'⚠️' if m['n']<10 else ''} | {fpf(m['pf'])} | {m['wr']:.0f}%"
        a(f"| {anio} | {fs(mp)} | {fs(mc2)} | {per_lbl} |")
    a("")
    a("---")
    a("")

    a("## 14. Analisis de sobreajuste")
    a("")
    preguntas = [
        ("¿PF OOS > 1.0?",
         f"{'SI ✅' if pf_num(mv_c['pf'])>1.0 else 'NO ❌'} — PF OOS: {fpf(mv_c['pf'])}"),
        ("¿Expectancy OOS > 0?",
         f"{'SI ✅' if mv_c['exp']>0 else 'NO ❌'} — Exp: {fpl(mv_c['exp'])}"),
        ("¿>= 30 trades OOS?",
         f"{'SI ✅' if mv_c['n']>=30 else 'NO ⚠️'} — {mv_c['n']} trades"),
        ("¿EMA200 es la mejor?",
         f"{'SI ✅' if best_ema==200 else 'NO ❌ — mejor EMA'+str(best_ema)}"),
        ("¿Robustez vecindad EMA?", f"{rob_label} — {rob_detalle}"),
        ("¿IC95% no cruza cero?",
         (f"SI ✅ — IC95% [{fpl(lo95_v)},{fpl(hi95_v)}]" if lo95_v and lo95_v>0
          else f"NO ⚠️ — IC95% [{fpl(lo95_v)},{fpl(hi95_v)}] cruza cero" if lo95_v is not None
          else "N/A")),
        ("¿P(Delta>0)?",
         f"{bs_val['p_pos']:.1%}" if bs_val["p_pos"] is not None else "N/A"),
        ("¿Estabilidad Train→OOS?",
         f"Ratio PF = {ratio_pf_c:.2f}" if ratio_pf_c else "N/A"),
        ("¿Sensibilidad RSI?",
         f"{n_pos_rsi}/3 rangos con PF OOS > 1.0"),
        ("¿SL/TP distintos entre sistemas?",
         "SI — Prod: SL 4.5%/TP 5.0% vs SistC: SL 5.0%/TP 6.0%. "
         "El delta incluye efecto SL/TP, no solo el gate EMA."),
        ("¿Forward 2026?",
         (f"{mf_c['n']} trades (PF {fpf(mf_c['pf'])})" if mf_c["n"]>0
          else f"0 trades. ETH {pct_bajo:.0f}% bajo EMA200d o sin coincidencia RSI/gate.")),
    ]
    for i, (q, r) in enumerate(preguntas, 1):
        a(f"{i}. **{q}**")
        a(f"   {r}")
        a("")
    a("---")
    a("")

    a("## 15. Limitaciones")
    a("")
    a("1. SL/TP distintos entre sistemas — el delta incluye efecto SL/TP además del gate EMA.")
    a("2. Sin trailing, sin gates de produccion (horario, eventos, guardian).")
    a("3. Bootstrap subestima varianza real por dependencia serial.")
    a("4. RSI 55–60 tiene raices en analisis de BTC — riesgo moderado de sobreajuste al activo,")
    a("   aplicado igual a ETH/BNB/SOL/AVAX sin calibracion especifica.")
    a("5. Comision VIP0 taker 0.1% — produccion real puede diferir.")
    a("6. Warmup 4H desde 2020-10 — solo 1 año de train 2021 (sin 2020).")
    a("7. Script recreado 2026-08-16 — validar que coincide con los numeros originales")
    a("   de CLAUDE.md (PF OOS 0.960, 67 trades, 0/4 EMAs) antes de confiar en el detalle.")
    a("")
    a("---")
    a("")

    a("## 16. Veredicto final")
    a("")
    a("| Criterio | Estado |")
    a("|----------|--------|")
    a(f"| 1. PF OOS > 1.0 | {'✅ '+fpf(mv_c['pf']) if pf_num(mv_c['pf'])>1.0 else '❌ '+fpf(mv_c['pf'])} |")
    a(f"| 2. Expectancy OOS > 0 | {'✅ '+fpl(mv_c['exp']) if mv_c['exp']>0 else '❌ '+fpl(mv_c['exp'])} |")
    a(f"| 3. >= 30 trades OOS | {'✅ '+str(mv_c['n']) if mv_c['n']>=30 else '⚠️ '+str(mv_c['n'])} |")
    a(f"| 4. EMA200 la mejor | {'✅' if best_ema==200 else '❌ EMA'+str(best_ema)} |")
    a(f"| 5. Robustez EMA | **{rob_label}** |")
    a(f"| 6. IC95% no cruza 0 | {'✅' if lo95_v and lo95_v>0 else '❌ cruza 0'} |")
    p_pos_str = f"{bs_val['p_pos']:.1%}" if bs_val["p_pos"] is not None else "N/A"
    a(f"| 7. P(Delta>0) | {p_pos_str} |")
    rat_str = f"{ratio_pf_c:.2f}" if ratio_pf_c else "N/A"
    a(f"| 8. Estabilidad Train→OOS | {rat_str} |")
    a(f"| 9. Sensibilidad RSI | {n_pos_rsi}/3 rangos PF > 1.0 |")
    fwd_s = (f"{mf_c['n']} trades (PF {fpf(mf_c['pf'])})" if mf_c["n"]>0
             else f"0 trades ({pct_bajo:.0f}% bajo EMA200d)")
    a(f"| 10. Forward 2026 | {fwd_s} |")
    a("")
    a(f"### **{verdict}**")
    a("")
    if "ACTIVABLE" in verdict:
        a("Todos los criterios se cumplen: PF OOS > 1.0, expectancy positiva,")
        a("vecindad ROBUSTA_POSITIVA e IC95% no cruza cero.")
        a("Evidencia suficiente para considerar validacion REAL controlada.")
    elif "PROMETEDOR" in verdict:
        a("OOS positivo y vecindad EMA favorable, pero:")
        if lo95_v is not None and lo95_v < 0 < hi95_v:
            a(f"- IC95% cruza cero [{fpl(lo95_v)},{fpl(hi95_v)}]. "
              f"P(D>0)={bs_val['p_pos']:.1%} — dentro del ruido de muestreo.")
        if rob_label == "PARCIALMENTE_ROBUSTA":
            a(f"- Vecindad: {rob_detalle}")
        a("**No activar sin >= 30 trades reales.**")
    elif "DESCARTADO" in verdict:
        a("PF OOS <= 1.0 y/o expectancy <= 0. Sistema C no supera a Produccion.")
    a("")
    a("---")
    a("")

    a("## 17. Comparacion global BTC / ETH / SOL / AVAX / BNB")
    a("")
    a("| Activo | PF OOS | Exp OOS | EMAs>1 | Trades OOS | Forward | Veredicto |")
    a("|--------|--------|---------|--------|-----------|---------|-----------|")
    a("| **BTC** | 1.322 | +$0.0383 | 4/4 | 59 | 0 (100% bajo EMA200d) | 🟡 PROMETEDOR |")
    fwd_eth_str = (f"{mf_c['n']} trades" if mf_c["n"]>0 else f"0 ({pct_bajo:.0f}% bajo EMA200d)")
    a(f"| **ETH** | {fpf(mv_c['pf'])} | {fpl(mv_c['exp'])} | {n_pos}/4 | {mv_c['n']} | {fwd_eth_str} | {verdict} |")
    a("| **SOL** | 0.984 | -$0.0022 | 0/4 | 96 | 0 trades | 🔴 DESCARTADO |")
    a("| **AVAX** | 0.707 | -$0.0466 | 0/4 | 67 | 0 trades | 🔴 DESCARTADO |")
    a("| **BNB** | 1.318 | +$0.0379 | 4/4 | 72 | 3 trades | 🟡 PROMETEDOR |")
    a("")
    a("---")
    a("")

    a("## 18. Estado final")
    a("")
    a("| Campo | Estado |")
    a("|-------|--------|")
    a("| config_cartera.py | **SIN CAMBIOS** |")
    a("| auditoria.csv | **SIN CAMBIOS** |")
    a("| billetera.json | **SIN CAMBIOS** |")
    a("| Produccion ETH | **SIN CAMBIOS** |")
    a(f"| Veredicto ETH Sistema C | **{verdict}** |")
    a("| Sistema C ETH activado | **NO** |")
    a("")
    a("**PRODUCCION NO MODIFICADA.**")

    os.makedirs(os.path.dirname(os.path.expanduser(REPORT_PATH)), exist_ok=True)
    with open(os.path.expanduser(REPORT_PATH), "w") as f:
        f.write("\n".join(lines))

    # ── Consola ────────────────────────────────────────────────────────────────
    print()
    print("=" * 62)
    print("RESUMEN EJECUTIVO — OOS 2024-2025")
    print("=" * 62)
    print(f"  Produccion: {mv_prod['n']:3d} T | PF {fpf(mv_prod['pf'])} "
          f"| WR {mv_prod['wr']:.1f}% | Exp {fpl(mv_prod['exp'])}")
    print(f"  Sistema C:  {mv_c['n']:3d} T | PF {fpf(mv_c['pf'])} "
          f"| WR {mv_c['wr']:.1f}% | Exp {fpl(mv_c['exp'])}")
    print()
    print("FORWARD 2026")
    print(f"  Produccion: {mf_prod['n']:3d} T | PF {fpf(mf_prod['pf'])}")
    print(f"  Sistema C:  {mf_c['n']:3d} T | "
          f"Regimen: {pct_sobre:.0f}% sobre / {pct_bajo:.0f}% bajo EMA200d")
    print()
    print("VECINDAD EMA (OOS)")
    print("  " + " | ".join(
        f"EMA{n}={'✅' if pf_eth_emas[n]>1 else '❌'}{fpf(pf_eth_emas[n])}" for n in EMAs))
    print(f"  Mejor: EMA{best_ema} | {n_pos}/4 positivas | "
          f"EMA200 mejor: {'SI' if best_ema==200 else 'NO'} | {rob_label}")
    print()
    print("SENSIBILIDAD RSI (OOS)")
    for lbl, res in rsi_sens_results.items():
        mv_s = res["val"]
        print(f"  {lbl}: {mv_s['n']} T | PF {fpf(mv_s['pf'])} | Exp {fpl(mv_s['exp'])}")
    print()
    print("BOOTSTRAP OOS")
    if bs_val["obs"] is not None:
        lo90, hi90 = bs_val["ic90"]; lo95, hi95 = bs_val["ic95"]
        print(f"  Delta Exp: {fpl(bs_val['obs'])}")
        print(f"  IC90%: [{fpl(lo90)},{fpl(hi90)}]")
        print(f"  IC95%: [{fpl(lo95)},{fpl(hi95)}]")
        print(f"  P(D>0): {bs_val['p_pos']:.1%}")
    print()
    print("=" * 62)
    print(f"VEREDICTO ETH SISTEMA C: {verdict}")
    print("PRODUCCION:               NO MODIFICADA")
    print("SISTEMA C:                NO ACTIVADO")
    print("=" * 62)
    print()
    print(f"Resultado en: {REPORT_PATH}")
    print()
    print("less " + REPORT_PATH)


if __name__ == "__main__":
    main()
