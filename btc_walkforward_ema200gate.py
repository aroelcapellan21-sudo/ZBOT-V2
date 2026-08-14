"""
btc_walkforward_ema200gate.py
Walk-forward BTC ALCISTA: gate EMA200d
Train 2021–2023 / Validate 2024–2025
INVESTIGACION PURA — 0 archivos de producción modificados.
"""
import json, os, urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta

SIMBOLO      = "BTCUSDT"
CAPITAL_INIT = 20.0
MONTO_TRADE  = 5.0
COMISION     = 0.001
FECHA_WU_4H  = "2020-10-01"
FECHA_WU_D   = "2020-01-01"
TRAIN_START  = "2021-01-01"
TRAIN_END    = "2023-12-31"
VAL_START    = "2024-01-01"
VAL_END      = "2025-12-31"
RSI_MIN, RSI_MAX = 55.0, 75.0
SL_PCT, TP_PCT   = 0.05, 0.06

REPORT = os.path.expanduser(
    "~/bot-padre-v2/reports/2026-08-14_btc-alcista-walkforward-ema200gate.md"
)

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

def construir_ema_maps(velas_d):
    k = 2/201
    cierres = [float(v[4]) for v in velas_d]
    fechas  = [datetime.fromtimestamp(int(v[0])/1000, tz=timezone.utc).strftime("%Y-%m-%d")
               for v in velas_d]
    ema = [None]*len(cierres)
    if len(cierres) >= 200:
        ema[199] = sum(cierres[:200])/200
        for i in range(200, len(cierres)):
            ema[i] = cierres[i]*k + ema[i-1]*(1-k)
    ema_map = {}
    for i, f in enumerate(fechas):
        if ema[i] is not None:
            ema_map[f] = round(ema[i], 2)
    return ema_map

def ema_entrada(entry_ts, ema_map):
    for d in range(1, 6):
        f = (entry_ts - timedelta(days=d)).strftime("%Y-%m-%d")
        if f in ema_map:
            return ema_map[f]
    return None

def rsi_simple(v, periodo=14):
    if len(v) < periodo+1: return None
    g, p = [], []
    for i in range(1, periodo+1):
        d = v[i]-v[i-1]
        g.append(d if d>0 else 0); p.append(-d if d<0 else 0)
    ag, ap = sum(g)/periodo, sum(p)/periodo
    if ap == 0: return 100.0
    return round(100-(100/(1+ag/ap)), 2)

def metricas(trades_list):
    n = len(trades_list)
    if n == 0:
        return {"n":0,"tp":0,"sl":0,"wr":0.0,"pf":0.0,"exp":0.0,"pl":0.0,"dd":0.0}
    tps = [t for t in trades_list if t["res"]=="TP"]
    sls = [t for t in trades_list if t["res"]=="SL"]
    tg = sum(t["pl"] for t in tps)
    tl = abs(sum(t["pl"] for t in sls))
    pf = round(tg/tl, 3) if tl > 0 else float("inf")
    pl = round(sum(t["pl"] for t in trades_list), 4)
    wr = round(len(tps)/n*100, 1)
    exp = round(pl/n, 4)
    # DD
    cap = CAPITAL_INIT; mxc = cap; mxdd = 0.0
    for t in sorted(trades_list, key=lambda x: x["ts"]):
        cap += t["pl"]; mxc = max(mxc, cap)
        dd = (mxc-cap)/mxc*100; mxdd = max(mxdd, dd)
    return {"n":n,"tp":len(tps),"sl":len(sls),"wr":wr,"pf":pf,"exp":exp,"pl":pl,"dd":round(mxdd,1)}

def simular_todos(velas_4h, ema_map):
    cierres = [float(v[4]) for v in velas_4h]
    ts_list = [int(v[0]) for v in velas_4h]
    TRAIN_MS   = _ts_ms(TRAIN_START)
    VAL_END_MS = _ts_ms(VAL_END) + 86400000

    trades = []
    en_pos = False
    e_precio = e_rsi = sl_p = tp_p = 0.0
    e_ts = None; e_ema = None

    for i in range(60, len(cierres)):
        ventana = cierres[max(0,i-60):i]
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
                bruto = MONTO_TRADE*TP_PCT if res=="TP" else -MONTO_TRADE*SL_PCT
                pl = round(bruto - MONTO_TRADE*COMISION*2, 4)
                regime = ("SOBRE" if e_precio >= e_ema else "BAJO") if e_ema else "UNK"
                rsi_r = ("55-60" if e_rsi < 60 else "60-75")
                anio = str(e_ts.year)
                periodo = "TRAIN" if ts_ms_val <= _ts_ms(TRAIN_END)+86400000 else "VAL"
                trades.append({"ts": e_ts.strftime("%Y-%m-%d %H:%M"),
                                "anio": anio, "periodo": periodo,
                                "rsi": e_rsi, "rsi_r": rsi_r,
                                "precio_e": round(e_precio,2),
                                "ema200": e_ema, "regime": regime,
                                "res": res, "pl": pl})
                en_pos = False

        if (not en_pos and ts_ms_val >= TRAIN_MS
                and ts_ms_val < VAL_END_MS
                and RSI_MIN <= r <= RSI_MAX):
            en_pos = True; e_precio = precio; e_ts = ts_dt; e_rsi = r
            e_ema = ema_entrada(ts_dt, ema_map)
            sl_p = round(e_precio*(1-SL_PCT), 4)
            tp_p = round(e_precio*(1+TP_PCT), 4)

    return trades

def fpf(v): return f"{v:.3f}" if v != float("inf") else "∞"
def fpl(v): return f"+${v:.4f}" if v >= 0 else f"-${abs(v):.4f}"

def tabla_resumen(m):
    return (f"| {m['n']} | {m['tp']}/{m['sl']} | {m['wr']:.1f}% "
            f"| {fpf(m['pf'])} | {fpl(m['exp'])} | {fpl(m['pl'])} | {m['dd']:.1f}% |")

def main():
    print("=" * 55)
    print("BTC ALCISTA — Walk-forward gate EMA200d")
    print("Train: 2021-2023 / Val: 2024-2025")
    print("=" * 55)

    print("[1/3] Descargando datos...")
    ahora_ms = int(datetime.now(timezone.utc).timestamp()*1000)
    velas_d = fetch_velas(SIMBOLO, "1d", _ts_ms(FECHA_WU_D))
    velas_d = [v for v in velas_d if int(v[6]) < ahora_ms]
    ema_map = construir_ema_maps(velas_d)
    velas_4h = fetch_velas(SIMBOLO, "4h", _ts_ms(FECHA_WU_4H))
    velas_4h = [v for v in velas_4h if int(v[6]) < ahora_ms]
    print(f"      Velas 4H: {len(velas_4h)} | EMA dates: {len(ema_map)}")

    print("[2/3] Simulando...")
    trades = simular_todos(velas_4h, ema_map)
    print(f"      Trades totales (train+val): {len(trades)}")

    # Sistemas
    def make_systems(pool):
        prod     = pool  # sin gate
        gate_ema = [t for t in pool if t["regime"] == "SOBRE"]
        gate_r55 = [t for t in pool if t["regime"] == "SOBRE" and t["rsi_r"] == "55-60"]
        return prod, gate_ema, gate_r55

    train = [t for t in trades if t["periodo"] == "TRAIN"]
    val   = [t for t in trades if t["periodo"] == "VAL"]
    all_t = trades  # full train+val (no 2026)

    prod_t, gate_t, r55_t = make_systems(train)
    prod_v, gate_v, r55_v = make_systems(val)

    print("[3/3] Generando reporte...")

    lines = []; a = lines.append

    a("# BTC ALCISTA — Walk-forward gate EMA200d")
    a("## Train 2021–2023 | Validación 2024–2025 | Sin tocar producción")
    a("")
    a("**Fecha:** 2026-08-14  ")
    a("**Hipótesis:** Agregar gate 'solo operar cuando BTC > EMA200d' mejora el sistema.")
    a("**Metodología:** train sobre 2021–2023, evaluar generalización en 2024–2025.")
    a("**Candidatos probados:**")
    a("- A) Producción actual: RSI 55–75, sin gate")
    a("- B) Gate EMA200d: RSI 55–75, solo cuando BTC > EMA200d")
    a("- C) Gate EMA200d + RSI 55–60: solo entradas RSI 55–<60 sobre EMA200d")
    a("")
    a("---")
    a("")
    a("## 1. Entrenamiento 2021–2023")
    a("")
    a("| Sistema | Trades | TP/SL | WR | PF | Exp | P/L | DD |")
    a("|---------|--------|-------|----|----|-----|-----|----|")
    a(f"| **A) Producción** {tabla_resumen(metricas(prod_t))}")
    a(f"| **B) Gate EMA200d** {tabla_resumen(metricas(gate_t))}")
    a(f"| **C) RSI 55–60 + SOBRE** {tabla_resumen(metricas(r55_t))}")
    a("")
    m_prod_t  = metricas(prod_t)
    m_gate_t  = metricas(gate_t)
    m_r55_t   = metricas(r55_t)
    a(f"Producción trades: {m_prod_t['n']} | Gate filtra a: {m_gate_t['n']} ({m_gate_t['n']/max(m_prod_t['n'],1)*100:.0f}%) "
      f"| RSI55-60+SOBRE: {m_r55_t['n']} ({m_r55_t['n']/max(m_prod_t['n'],1)*100:.0f}%)")
    a("")
    a("---")
    a("")
    a("## 2. Validación 2024–2025 (out-of-sample)")
    a("")
    a("| Sistema | Trades | TP/SL | WR | PF | Exp | P/L | DD |")
    a("|---------|--------|-------|----|----|-----|-----|----|")
    a(f"| **A) Producción** {tabla_resumen(metricas(prod_v))}")
    a(f"| **B) Gate EMA200d** {tabla_resumen(metricas(gate_v))}")
    a(f"| **C) RSI 55–60 + SOBRE** {tabla_resumen(metricas(r55_v))}")
    a("")
    m_prod_v = metricas(prod_v)
    m_gate_v = metricas(gate_v)
    m_r55_v  = metricas(r55_v)
    a("")
    a("---")
    a("")
    a("## 3. Comparación train → validación")
    a("")
    a("| Sistema | PF train | PF val | Generaliza | Exp train | Exp val |")
    a("|---------|----------|--------|-----------|-----------|---------|")
    def gen(pft, pfv):
        pft_n = pft if pft != float("inf") else 999
        pfv_n = pfv if pfv != float("inf") else 999
        if pfv_n >= 1.0 and pfv_n >= pft_n*0.7: return "✅ SÍ"
        if pfv_n >= 1.0: return "🟡 PARCIAL"
        return "❌ NO"
    a(f"| **A) Producción** | {fpf(m_prod_t['pf'])} | {fpf(m_prod_v['pf'])} "
      f"| {gen(m_prod_t['pf'], m_prod_v['pf'])} "
      f"| {fpl(m_prod_t['exp'])} | {fpl(m_prod_v['exp'])} |")
    a(f"| **B) Gate EMA200d** | {fpf(m_gate_t['pf'])} | {fpf(m_gate_v['pf'])} "
      f"| {gen(m_gate_t['pf'], m_gate_v['pf'])} "
      f"| {fpl(m_gate_t['exp'])} | {fpl(m_gate_v['exp'])} |")
    a(f"| **C) RSI55-60+SOBRE** | {fpf(m_r55_t['pf'])} | {fpf(m_r55_v['pf'])} "
      f"| {gen(m_r55_t['pf'], m_r55_v['pf'])} "
      f"| {fpl(m_r55_t['exp'])} | {fpl(m_r55_v['exp'])} |")
    a("")
    a("---")
    a("")
    a("## 4. Breakdown anual en validación (2024–2025)")
    a("")
    a("| Año | A) Prod n/PF/Exp | B) Gate n/PF/Exp | C) RSI55+Sobre n/PF/Exp |")
    a("|-----|-----------------|-----------------|------------------------|")
    for anio in ["2024", "2025"]:
        def cell(pool):
            g = [t for t in pool if t["anio"]==anio]
            m = metricas(g)
            if m['n'] == 0: return "0 / — / —"
            pref = "⚠️" if m['n'] < 10 else ""
            return f"{pref}{m['n']} / {fpf(m['pf'])} / {fpl(m['exp'])}"
        a(f"| **{anio}** | {cell(prod_v)} | {cell(gate_v)} | {cell(r55_v)} |")
    a("")
    a("---")
    a("")
    a("## 5. Trades gate B y C en validación")
    a("")
    val_gate = sorted([t for t in gate_v], key=lambda x: x["ts"])
    val_r55  = sorted([t for t in r55_v], key=lambda x: x["ts"])

    a(f"**Gate B (SOBRE EMA200d, RSI 55–75):** {len(val_gate)} trades en 2024–2025")
    a("")
    if val_gate:
        a("| # | Fecha | RSI | Resultado | P/L |")
        a("|---|-------|-----|-----------|-----|")
        for idx, t in enumerate(val_gate, 1):
            a(f"| {idx} | {t['ts']} | {t['rsi']:.1f} | {t['res']} "
              f"| {'+' if t['pl']>=0 else ''}{t['pl']:.2f} |")
    a("")
    a(f"**Gate C (SOBRE EMA200d + RSI 55–60):** {len(val_r55)} trades en 2024–2025")
    a("")
    if val_r55:
        a("| # | Fecha | RSI | Resultado | P/L |")
        a("|---|-------|-----|-----------|-----|")
        for idx, t in enumerate(val_r55, 1):
            a(f"| {idx} | {t['ts']} | {t['rsi']:.1f} | {t['res']} "
              f"| {'+' if t['pl']>=0 else ''}{t['pl']:.2f} |")
    a("")
    a("---")
    a("")
    a("## 6. Veredicto walk-forward")
    a("")

    def pf_num(m):
        return m['pf'] if m['pf'] != float("inf") else 999.0

    # Assess each candidate
    def veredicto(nombre, mt, mv, prod_t_m, prod_v_m):
        pft = pf_num(mt); pfv = pf_num(mv)
        pft_p = pf_num(prod_t_m); pfv_p = pf_num(prod_v_m)
        if pfv >= 1.2 and pfv >= pft*0.7 and pfv > pfv_p:
            return "🟢 A) ROBUSTO — mejora en validación, PF > 1.2"
        elif pfv >= 1.0 and pfv > pfv_p:
            return "🟡 B) PROMETEDOR — mejora en validación, PF > 1.0"
        elif pfv >= 1.0:
            return "🟡 C) INSUFICIENTE — PF > 1.0 pero no supera a Producción"
        else:
            return "🔴 D) DESCARTADO — PF < 1.0 en validación"

    v_gate = veredicto("Gate EMA200d", m_gate_t, m_gate_v, m_prod_t, m_prod_v)
    v_r55  = veredicto("RSI55+Sobre", m_r55_t, m_r55_v, m_prod_t, m_prod_v)

    a(f"- **B) Gate EMA200d:** {v_gate}")
    a(f"- **C) RSI 55–60 + SOBRE:** {v_r55}")
    a("")
    a("**Coherencia con forense histórico:**")
    a(f"- Forense SOBRE: PF 1.390 (155 trades) — candidato B reproduce este resultado?")
    a(f"  Train PF {fpf(m_gate_t['pf'])} → Val PF {fpf(m_gate_v['pf'])}")
    a(f"- Forense RSI55+Sobre: PF 2.310 (43 trades) — candidato C reproduce este resultado?")
    a(f"  Train PF {fpf(m_r55_t['pf'])} → Val PF {fpf(m_r55_v['pf'])}")
    a("")
    a("---")
    a("")
    a("## 7. Interpretación y consecuencia para el Plan Maestro")
    a("")
    if pf_num(m_gate_v) >= 1.0 and pf_num(m_gate_v) > pf_num(m_prod_v):
        a("El gate EMA200d **mejora** el sistema en validación out-of-sample.")
        a("Esto sugiere que la diferencia SOBRE/BAJO no es artefacto de overfitting.")
        a("")
        a("**Implicación:** el gate EMA200d es un candidato válido para investigación adicional.")
        a("Pasos siguientes antes de cualquier implementación:")
        a("1. Robustez de vecindad (EMA100d, EMA150d, EMA200d, EMA250d)")
        a("2. Bootstrap IC95% de la diferencia de expectancy")
        a("3. Acumular trades reales para validar en REAL")
    else:
        a("El gate EMA200d **no generaliza** al período de validación.")
        a("El hallazgo del forense puede ser artefacto del mercado de 2021 (bull extremo).")
        a("Conclusión: gate EMA200d descartado como candidato.")
    a("")
    a("---")
    a("")
    a("## 8. Confirmación de aislamiento")
    a("")
    a("- `config_cartera.py` = **SIN CAMBIOS** ✅")
    a("- `francotirador_alcista_btc.py` = **SIN CAMBIOS** ✅")
    a("- `auditoria.csv` = **SIN CAMBIOS** ✅")
    a("- `billetera.json` = **SIN CAMBIOS** ✅")
    a("- Candidato en producción = **NO ACTIVADO** ✅")
    a(f"")
    a(f"Solo archivos creados: `reports/2026-08-14_btc-alcista-walkforward-ema200gate.md`")

    with open(os.path.expanduser(REPORT), "w") as f:
        f.write("\n".join(lines))

    print()
    print("=" * 55)
    print("RESULTADO WALK-FORWARD")
    print("=" * 55)
    print(f"TRAIN (2021-2023):")
    print(f"  Producción:   {m_prod_t['n']} trades | PF {fpf(m_prod_t['pf'])} | WR {m_prod_t['wr']:.1f}%")
    print(f"  Gate EMA200d: {m_gate_t['n']} trades | PF {fpf(m_gate_t['pf'])} | WR {m_gate_t['wr']:.1f}%")
    print(f"  RSI55+Sobre:  {m_r55_t['n']} trades | PF {fpf(m_r55_t['pf'])} | WR {m_r55_t['wr']:.1f}%")
    print()
    print(f"VALIDACION (2024-2025):")
    print(f"  Producción:   {m_prod_v['n']} trades | PF {fpf(m_prod_v['pf'])} | WR {m_prod_v['wr']:.1f}%")
    print(f"  Gate EMA200d: {m_gate_v['n']} trades | PF {fpf(m_gate_v['pf'])} | WR {m_gate_v['wr']:.1f}%")
    print(f"  RSI55+Sobre:  {m_r55_v['n']} trades | PF {fpf(m_r55_v['pf'])} | WR {m_r55_v['wr']:.1f}%")
    print()
    print(f"VEREDICTOS:")
    print(f"  Gate EMA200d: {v_gate}")
    print(f"  RSI55+Sobre:  {v_r55}")
    print()
    print(f"Reporte: {REPORT}")

if __name__ == "__main__":
    main()
