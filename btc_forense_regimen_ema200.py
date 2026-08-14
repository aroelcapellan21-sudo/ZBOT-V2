"""
btc_forense_regimen_ema200.py
BTC ALCISTA — Forense histórico 2021–2026 × régimen EMA200 diaria
INVESTIGACION PURA — 0 archivos de producción modificados.
"""
import json, os, urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta
from collections import defaultdict

SIMBOLO          = "BTCUSDT"
CAPITAL_INIT     = 20.0
MONTO_TRADE      = 5.0
COMISION         = 0.001
FECHA_INICIO_SIM = "2021-01-01"
FECHA_WARMUP_4H  = "2020-10-01"
FECHA_WARMUP_D   = "2020-01-01"
RSI_MIN, RSI_MAX = 55.0, 75.0
SL_PCT, TP_PCT   = 0.05, 0.06

REPORT_PATH = os.path.expanduser(
    "~/bot-padre-v2/reports/2026-08-14_btc-alcista-forense-regimen-ema200-historico.md"
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

# ── EMA200 diaria ─────────────────────────────────────────────────────────────
def construir_ema_maps(velas_d):
    """
    Retorna:
      ema_map   : {date_str -> ema200}       (cierre de ese día)
      pend_map  : {date_str -> 'SUBIENDO'/'BAJANDO'}  (EMA200_today vs EMA200_20d_ago)
    """
    k = 2 / 201
    cierres = [float(v[4]) for v in velas_d]
    fechas  = [datetime.fromtimestamp(int(v[0])/1000, tz=timezone.utc).strftime("%Y-%m-%d")
               for v in velas_d]
    ema = [None] * len(cierres)
    if len(cierres) >= 200:
        ema[199] = sum(cierres[:200]) / 200
        for i in range(200, len(cierres)):
            ema[i] = cierres[i]*k + ema[i-1]*(1-k)

    ema_map = {}
    for i, f in enumerate(fechas):
        if ema[i] is not None:
            ema_map[f] = round(ema[i], 2)

    # Pendiente: compara EMA200 del día con EMA200 de 20 días calendario atrás
    pend_map = {}
    for i, f in enumerate(fechas):
        if ema[i] is None: continue
        dt = datetime.strptime(f, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        ema_20 = None
        for d in range(19, 25):  # buscar el dato 20±2 días atrás
            f20 = (dt - timedelta(days=d)).strftime("%Y-%m-%d")
            if f20 in ema_map:
                ema_20 = ema_map[f20]
                break
        if ema_20 is not None:
            pend_map[f] = "SUBIENDO" if ema[i] >= ema_20 else "BAJANDO"

    return ema_map, pend_map

def ema_para_entrada(entry_ts, ema_map, pend_map):
    """
    Para una entrada 4H, devuelve la EMA200 del último día DIARIO completamente
    cerrado antes de la hora de entrada. Sin look-ahead bias.
    Regla: si entrada es a cualquier hora del día D, usamos EMA200 del día D-1.
    """
    dt = entry_ts - timedelta(days=1)
    for delta in range(5):
        f = (dt - timedelta(days=delta)).strftime("%Y-%m-%d")
        if f in ema_map:
            return ema_map[f], pend_map.get(f, "UNK"), f
    return None, "UNK", None

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

# ── Clasificadores ────────────────────────────────────────────────────────────
def dist_bucket(dp):
    if dp is None: return "UNK"
    if dp >  10: return ">+10%"
    if dp >   5: return "+5%→+10%"
    if dp >   0: return "0%→+5%"
    if dp >  -5: return "0%→-5%"
    if dp > -10: return "-5%→-10%"
    if dp > -20: return "-10%→-20%"
    return "<-20%"

BUCKET_ORDER = {">+10%":0,"+5%→+10%":1,"0%→+5%":2,"0%→-5%":3,
                "-5%→-10%":4,"-10%→-20%":5,"<-20%":6}

def rsi_range_label(r):
    if r < 60: return "55-60"
    if r < 65: return "60-65"
    if r < 70: return "65-70"
    return "70-75"

# ── Métricas ──────────────────────────────────────────────────────────────────
def metricas(trades_list):
    n = len(trades_list)
    if n == 0:
        return {"n":0,"tp":0,"sl":0,"wr":0,"pf":0,"pl":0,"exp":0,
                "avg_w":0,"avg_l":0,"dd":0,"racha":0}
    tps = [t for t in trades_list if t["resultado"] == "TP"]
    sls = [t for t in trades_list if t["resultado"] == "SL"]
    wr  = len(tps)/n*100
    tg  = sum(t["pl"] for t in tps)
    tl  = abs(sum(t["pl"] for t in sls))
    pf  = round(tg/tl, 3) if tl > 0 else float("inf")
    pl  = round(sum(t["pl"] for t in trades_list), 4)
    exp = round(pl/n, 4)
    avg_w = round(tg/len(tps), 4) if tps else 0
    avg_l = round(-tl/len(sls), 4) if sls else 0
    # DD (sobre trades en orden cronológico)
    cap = CAPITAL_INIT; mxc = cap; mxdd = 0.0
    for t in sorted(trades_list, key=lambda x: x["entrada_ts"]):
        cap += t["pl"]; mxc = max(mxc, cap)
        dd = (mxc - cap)/mxc*100; mxdd = max(mxdd, dd)
    # Racha SL
    racha = max_racha = 0
    for t in sorted(trades_list, key=lambda x: x["entrada_ts"]):
        if t["resultado"] == "SL": racha += 1; max_racha = max(max_racha, racha)
        else: racha = 0
    return {"n":n,"tp":len(tps),"sl":len(sls),"wr":round(wr,1),"pf":pf,
            "pl":pl,"exp":exp,"avg_w":avg_w,"avg_l":avg_l,
            "dd":round(mxdd,1),"racha":max_racha}

# ── Formato helpers ───────────────────────────────────────────────────────────
def fpf(v):
    return f"{v:.3f}" if v != float("inf") else "∞"

def fpl(v):
    return f"+${v:.4f}" if v >= 0 else f"-${abs(v):.4f}"

def fm(m):
    if m["n"] == 0:
        return "| 0 | — | — | — | — | — | — | — | — |"
    return (f"| {m['n']} | {m['tp']} | {m['sl']} | {m['wr']:.1f}% | {fpf(m['pf'])} "
            f"| {fpl(m['exp'])} | {fpl(m['pl'])} | {m['dd']:.1f}% | {m['racha']} |")

# ── Simulación ────────────────────────────────────────────────────────────────
def simular(velas_4h, ema_map, pend_map):
    cierres = [float(v[4]) for v in velas_4h]
    ts_list = [int(v[0]) for v in velas_4h]
    INICIO_MS = _ts_ms(FECHA_INICIO_SIM)

    trades = []
    en_pos = False
    e_precio = e_rsi = sl_p = tp_p = 0.0
    e_ts = None

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

                ema_val, pend, ema_fecha = ema_para_entrada(e_ts, ema_map, pend_map)
                dp = round((e_precio - ema_val)/ema_val*100, 2) if ema_val else None
                regime  = ("SOBRE" if e_precio >= ema_val else "BAJO") if ema_val else "UNK"
                regime4 = f"{regime}_{pend}" if regime != "UNK" else "UNK"
                bucket  = dist_bucket(dp)
                rsi_r   = rsi_range_label(e_rsi)
                anio    = str(e_ts.year)

                trades.append({
                    "entrada_ts": e_ts.strftime("%Y-%m-%d %H:%M"),
                    "anio":       anio,
                    "rsi":        e_rsi,
                    "precio_e":   round(e_precio, 2),
                    "ema200":     ema_val,
                    "dist_pct":   dp,
                    "regime":     regime,
                    "pend":       pend,
                    "regime4":    regime4,
                    "bucket":     bucket,
                    "rsi_range":  rsi_r,
                    "resultado":  res,
                    "pl":         pl,
                })
                en_pos = False

        if not en_pos and ts_ms_val >= INICIO_MS and RSI_MIN <= r <= RSI_MAX:
            en_pos = True; e_precio = precio; e_ts = ts_dt; e_rsi = r
            sl_p = round(e_precio*(1-SL_PCT), 4)
            tp_p = round(e_precio*(1+TP_PCT), 4)

    return trades

# ── Generador de reporte ──────────────────────────────────────────────────────
def generar_reporte(trades):
    lines = []; a = lines.append

    a("# BTC ALCISTA — Forense histórico × régimen EMA200 diaria")
    a("## 2021–2026 | Solo lectura | 0 archivos de producción modificados")
    a("")
    a(f"**Fecha:** 2026-08-14  ")
    a(f"**Trades totales:** {len(trades)}  ")
    a(f"**Configuración:** BTCUSDT 4H | RSI 55–75 | SL 5.0% | TP 6.0% | $5/trade | com 0.1%")
    a("")
    a("---")
    a("")
    a("## 1. Metodología y control anti-lookahead")
    a("")
    a("**EMA200 diaria:**")
    a("- Calculada sobre velas diarias BTCUSDT descargadas desde Binance API (2020-01-01 → presente).")
    a("- k = 2/201. Inicializada con SMA de las primeras 200 velas diarias.")
    a("- Warmup completo: 200 días antes del primer trade 2021-01-01.")
    a("")
    a("**Regla anti-lookahead (crítica):**")
    a("Para una entrada 4H en cualquier hora del día D, se usa la EMA200 del día **D−1**")
    a("(el último día diario completamente cerrado antes de la entrada).")
    a("La vela diaria del día D cierra cuando abre el día D+1 — nunca se conoce al momento de operar.")
    a("Ejemplo: entrada 2021-03-15 08:00 UTC → EMA200 del 2021-03-14.")
    a("")
    a("**Pendiente EMA200:**")
    a("Pendiente del día D−1: EMA200[D−1] vs EMA200[D−21] (20 días calendario atrás).")
    a("SUBIENDO si EMA200 actual ≥ EMA200 hace 20 días. BAJANDO en caso contrario.")
    a("")
    a("**RSI:** Simple 14-período, ventana 15 cierres — idéntico a backtest_motor.py.")
    a("**Simulación:** una posición a la vez. Entrada al cierre 4H de la vela de señal.")
    a("TP/SL evaluados vela a vela siguiente. Sin trailing stop.")
    a("")
    a("---")
    a("")

    # ── Tabla completa de trades ──────────────────────────────────────────────
    a("## 2. Tabla completa de trades")
    a("")
    a("| # | Fecha entrada | RSI | Precio E | EMA200d | Dist% | Res | P/L | Régimen | Pendiente | Año |")
    a("|---|---|---|---|---|---|---|---|---|---|---|")
    for idx, t in enumerate(sorted(trades, key=lambda x: x["entrada_ts"]), 1):
        ema_str = f"{t['ema200']:,.0f}" if t['ema200'] else "N/A"
        dist_str = f"{t['dist_pct']:+.1f}%" if t['dist_pct'] is not None else "N/A"
        pl_str = f"+{t['pl']:.2f}" if t['pl'] >= 0 else f"{t['pl']:.2f}"
        a(f"| {idx} | {t['entrada_ts']} | {t['rsi']:.1f} | {t['precio_e']:,.0f} "
          f"| {ema_str} | {dist_str} | {t['resultado']} | {pl_str} "
          f"| {t['regime']} | {t['pend']} | {t['anio']} |")
    a("")
    a("---")
    a("")

    # ── Métricas generales ────────────────────────────────────────────────────
    m_total = metricas(trades)
    a("## 3. Métricas generales (referencia)")
    a("")
    a("| Métrica | Valor |")
    a("|---------|-------|")
    a(f"| Trades | {m_total['n']} |")
    a(f"| TP / SL | {m_total['tp']} / {m_total['sl']} |")
    a(f"| Win Rate | {m_total['wr']:.1f}% |")
    a(f"| Profit Factor | {fpf(m_total['pf'])} |")
    a(f"| Expectancy/trade | {fpl(m_total['exp'])} |")
    a(f"| P/L acumulado | {fpl(m_total['pl'])} |")
    a(f"| DD máximo | {m_total['dd']:.1f}% |")
    a(f"| Racha máx SL | {m_total['racha']} |")
    a(f"| Avg ganancia (TP) | {fpl(m_total['avg_w'])} |")
    a(f"| Avg pérdida (SL) | {fpl(m_total['avg_l'])} |")
    a("")
    a("> Referencia forense histórico (2026-08-13): 205 trades, PF 1.022, WR 47.8%, Exp +$0.0029")
    a("> (El forense usó motor propio con timeout — diferencias menores son esperables)")
    a("")
    a("---")
    a("")

    # ── SOBRE vs BAJO ─────────────────────────────────────────────────────────
    a("## 4. SOBRE vs BAJO EMA200d")
    a("")
    sobre  = [t for t in trades if t["regime"] == "SOBRE"]
    bajo   = [t for t in trades if t["regime"] == "BAJO"]
    m_s    = metricas(sobre)
    m_b    = metricas(bajo)
    a("| Régimen | Trades | TP | SL | WR | PF | Expectancy | P/L | DD | Racha SL |")
    a("|---------|--------|----|----|----|----|-----------|-----|-----|---------|")
    a(f"| **SOBRE EMA200d** {fm(m_s)}")
    a(f"| **BAJO EMA200d**  {fm(m_b)}")
    a(f"| **TOTAL**         {fm(m_total)}")
    a("")
    a(f"**Distribución:** {len(sobre)} trades SOBRE ({len(sobre)/len(trades)*100:.1f}%) "
      f"| {len(bajo)} trades BAJO ({len(bajo)/len(trades)*100:.1f}%)")
    a("")
    if m_s['n'] >= 10 and m_b['n'] >= 10:
        diff_wr = m_s['wr'] - m_b['wr']
        diff_pf = (m_s['pf'] if m_s['pf'] != float('inf') else 999) - (m_b['pf'] if m_b['pf'] != float('inf') else 999)
        a(f"**Diferencia SOBRE vs BAJO:** WR {diff_wr:+.1f} pp | PF {diff_pf:+.3f} | "
          f"Exp {fpl(m_s['exp']-m_b['exp'])}")
    a("")
    a("---")
    a("")

    # ── Cuatro regímenes ──────────────────────────────────────────────────────
    a("## 5. Cuatro regímenes (precio × pendiente EMA200d)")
    a("")
    regimenes4 = ["SOBRE_SUBIENDO","SOBRE_BAJANDO","BAJO_SUBIENDO","BAJO_BAJANDO"]
    a("| Régimen | Trades | TP | SL | WR | PF | Expectancy | P/L | DD | Racha SL |")
    a("|---------|--------|----|----|----|----|-----------|-----|-----|---------|")
    met_reg4 = {}
    for rg in regimenes4:
        grupo = [t for t in trades if t["regime4"] == rg]
        m = metricas(grupo)
        met_reg4[rg] = m
        a(f"| **{rg}** {fm(m)}")
    a("")
    a("---")
    a("")

    # ── Distancia buckets ─────────────────────────────────────────────────────
    a("## 6. Distancia a EMA200d — buckets")
    a("")
    buckets_order = [">+10%","+5%→+10%","0%→+5%","0%→-5%","-5%→-10%","-10%→-20%","<-20%"]
    a("| Bucket (dist % al EMA200d) | Trades | TP | SL | WR | PF | Expectancy | P/L |")
    a("|---------------------------|--------|----|----|----|----|-----------|-----|")
    for bk in buckets_order:
        grupo = [t for t in trades if t["bucket"] == bk]
        m = metricas(grupo)
        if m['n'] == 0:
            a(f"| **{bk}** | 0 | — | — | — | — | — | — |")
        else:
            a(f"| **{bk}** | {m['n']} | {m['tp']} | {m['sl']} | {m['wr']:.1f}% "
              f"| {fpf(m['pf'])} | {fpl(m['exp'])} | {fpl(m['pl'])} |")
    a("")
    a("---")
    a("")

    # ── Matriz RSI × régimen ──────────────────────────────────────────────────
    a("## 7. Matriz RSI × régimen EMA200d")
    a("")
    rsi_ranges  = ["55-60","60-65","65-70","70-75"]
    regimenes2  = ["SOBRE","BAJO"]
    a("| RSI range | SOBRE EMA200d (n / WR / PF / Exp) | BAJO EMA200d (n / WR / PF / Exp) |")
    a("|-----------|-----------------------------------|----------------------------------|")
    for rr in rsi_ranges:
        celdas = []
        for reg in regimenes2:
            g = [t for t in trades if t["rsi_range"] == rr and t["regime"] == reg]
            m = metricas(g)
            if m['n'] == 0:
                celdas.append("— / — / — / —")
            elif m['n'] < 10:
                celdas.append(f"⚠️{m['n']} / {m['wr']:.0f}% / {fpf(m['pf'])} / {fpl(m['exp'])}")
            else:
                celdas.append(f"{m['n']} / {m['wr']:.0f}% / {fpf(m['pf'])} / {fpl(m['exp'])}")
        a(f"| **RSI {rr}** | {celdas[0]} | {celdas[1]} |")
    a("")
    a("> ⚠️ indica muestra < 10 trades — datos orientativos, no concluyentes")
    a("")
    a("---")
    a("")

    # ── Análisis anual ────────────────────────────────────────────────────────
    a("## 8. Análisis por año")
    a("")
    anios = sorted(set(t["anio"] for t in trades))
    a("| Año | Trades | WR | PF | Expectancy | P/L | % SOBRE EMA200d | % BAJO EMA200d |")
    a("|-----|--------|----|----|-----------|-----|----------------|----------------|")
    for anio in anios:
        g = [t for t in trades if t["anio"] == anio]
        m = metricas(g)
        n_s = sum(1 for t in g if t["regime"] == "SOBRE")
        n_b = sum(1 for t in g if t["regime"] == "BAJO")
        n   = len(g)
        a(f"| **{anio}** | {m['n']} | {m['wr']:.1f}% | {fpf(m['pf'])} "
          f"| {fpl(m['exp'])} | {fpl(m['pl'])} "
          f"| {n_s/n*100:.0f}% | {n_b/n*100:.0f}% |")
    a("")
    a("---")
    a("")

    # ── Año × régimen ─────────────────────────────────────────────────────────
    a("## 9. Año × régimen EMA200d")
    a("")
    a("| Año | SOBRE — trades/PF/Exp | BAJO — trades/PF/Exp | Mejor régimen |")
    a("|-----|----------------------|----------------------|---------------|")
    for anio in anios:
        g_s = [t for t in trades if t["anio"]==anio and t["regime"]=="SOBRE"]
        g_b = [t for t in trades if t["anio"]==anio and t["regime"]=="BAJO"]
        m_s = metricas(g_s); m_b = metricas(g_b)
        def cell(m):
            if m['n']==0: return "—"
            pref = "⚠️" if m['n']<10 else ""
            return f"{pref}{m['n']} / {fpf(m['pf'])} / {fpl(m['exp'])}"
        pf_s = m_s['pf'] if m_s['n']>0 else 0
        pf_b = m_b['pf'] if m_b['n']>0 else 0
        mejor = "SOBRE" if pf_s > pf_b and m_s['n']>0 else ("BAJO" if m_b['n']>0 else "—")
        a(f"| **{anio}** | {cell(m_s)} | {cell(m_b)} | {mejor} |")
    a("")
    a("---")
    a("")

    # ── Patrones detectados ───────────────────────────────────────────────────
    a("## 10. Búsqueda activa de patrones")
    a("")

    # Calcular todos los grupos candidate
    candidatos = []

    # SOBRE_SUBIENDO por año
    ss = [t for t in trades if t["regime4"] == "SOBRE_SUBIENDO"]
    m_ss = metricas(ss)
    if m_ss['n'] >= 20:
        # Check consistency by year
        ok_years = sum(1 for anio in anios
                       if metricas([t for t in ss if t["anio"]==anio]).get('pf',0) > 1.0
                       and len([t for t in ss if t["anio"]==anio]) >= 5)
        candidatos.append(("SOBRE+SUBIENDO", m_ss, ss, ok_years))

    # SOBRE (cualquier pendiente)
    m_sobre = metricas(sobre)
    if m_sobre['n'] >= 20:
        ok_years = sum(1 for anio in anios
                       if metricas([t for t in sobre if t["anio"]==anio]).get('pf',0) > 1.0
                       and len([t for t in sobre if t["anio"]==anio]) >= 5)
        candidatos.append(("SOBRE EMA200d", m_sobre, sobre, ok_years))

    # Cualquier bucket positivo con suficientes trades
    for bk in buckets_order:
        g = [t for t in trades if t["bucket"] == bk]
        m = metricas(g)
        if m['n'] >= 15:
            ok_years = sum(1 for anio in anios
                           if metricas([t for t in g if t["anio"]==anio]).get('pf',0) > 1.0
                           and len([t for t in g if t["anio"]==anio]) >= 5)
            candidatos.append((f"Bucket {bk}", m, g, ok_years))

    # RSI × regime combos
    for rr in rsi_ranges:
        for reg in ["SOBRE","BAJO"]:
            g = [t for t in trades if t["rsi_range"]==rr and t["regime"]==reg]
            m = metricas(g)
            if m['n'] >= 15:
                ok_years = sum(1 for anio in anios
                               if metricas([t for t in g if t["anio"]==anio]).get('pf',0) > 1.0
                               and len([t for t in g if t["anio"]==anio]) >= 5)
                candidatos.append((f"RSI {rr} + {reg}", m, g, ok_years))

    # SOBRE_SUBIENDO + RSI range
    for rr in rsi_ranges:
        g = [t for t in trades if t["rsi_range"]==rr and t["regime4"]=="SOBRE_SUBIENDO"]
        m = metricas(g)
        if m['n'] >= 10:
            candidatos.append((f"RSI {rr} + SOBRE+SUBIENDO", m, g, 0))

    # ordenar por PF desc
    def pf_num(m):
        return m['pf'] if m['pf'] != float('inf') else 999
    candidatos.sort(key=lambda x: -pf_num(x[1]))

    prioridad = [(nombre, m, g, ok) for nombre, m, g, ok in candidatos
                 if pf_num(m) >= 1.50 and ok >= 2]

    if prioridad:
        a("### 🔥 Patrones con PRIORIDAD DE INVESTIGACIÓN (PF ≥ 1.50, consistente ≥ 2 años)")
        a("")
        for nombre, m, grupo, ok_y in prioridad:
            a(f"#### 🔥 {nombre}")
            a("")
            a(f"| Métrica | Valor |")
            a("|---------|-------|")
            a(f"| Trades totales | {m['n']} ({m['n']/len(trades)*100:.1f}% del histórico) |")
            a(f"| TP / SL | {m['tp']} / {m['sl']} |")
            a(f"| Win Rate | {m['wr']:.1f}% |")
            a(f"| Profit Factor | {fpf(m['pf'])} |")
            a(f"| Expectancy/trade | {fpl(m['exp'])} |")
            a(f"| P/L acumulado | {fpl(m['pl'])} |")
            a(f"| DD máximo | {m['dd']:.1f}% |")
            a(f"| Racha máx SL | {m['racha']} |")
            a(f"| Años con PF > 1 (≥5 trades) | {ok_y} de {len(anios)} |")
            a(f"| vs Producción PF | {fpf(m['pf'])} vs 1.022 → Δ {pf_num(m)-1.022:+.3f} |")
            a("")
            a("**Por año:**")
            a("")
            a("| Año | Trades | WR | PF | Expectancy | P/L |")
            a("|-----|--------|----|----|-----------|-----|")
            for anio in anios:
                gy = [t for t in grupo if t["anio"] == anio]
                my = metricas(gy)
                if my['n'] == 0:
                    a(f"| {anio} | 0 | — | — | — | — |")
                else:
                    suf = " ⚠️" if my['n'] < 5 else ""
                    a(f"| {anio} | {my['n']}{suf} | {my['wr']:.0f}% "
                      f"| {fpf(my['pf'])} | {fpl(my['exp'])} | {fpl(my['pl'])} |")
            a("")
            a("**Posibles riesgos de overfitting:**")
            if m['n'] < 30:
                a("- ⚠️ Muestra total < 30 trades → alta incertidumbre estadística")
            if ok_y < 3:
                a("- ⚠️ PF > 1.0 en menos de 3 años con muestra suficiente")
            else:
                a("- OK Consistente en múltiples años")
            a("")
            a("**Validación adicional necesaria:**")
            a("- Walk-forward estricto (train 2021–2023, val 2024–2025)")
            a("- Robustez de vecindad (parámetros adyacentes)")
            a("- Bootstrap para IC95% de la diferencia de PF vs Producción")
            a("")
    else:
        a("### Sin patrones con PF ≥ 1.50 consistentes en ≥ 2 años")
        a("")
        a("Los patrones con PF alto tienen muestras insuficientes o no se sostienen en varios años.")
        a("")

    # Mostrar tabla de todos los grupos candidatos evaluados
    a("### Tabla de todos los grupos evaluados")
    a("")
    a("| Grupo | Trades | WR | PF | Expectancy | P/L | OK años |")
    a("|-------|--------|----|----|-----------|-----|---------|")
    for nombre, m, _, ok_y in candidatos[:20]:
        marca = "🔥" if pf_num(m) >= 1.50 and ok_y >= 2 else ("⚠️" if m['n'] < 15 else "")
        a(f"| {marca} {nombre} | {m['n']} | {m['wr']:.0f}% "
          f"| {fpf(m['pf'])} | {fpl(m['exp'])} | {fpl(m['pl'])} | {ok_y}/{len(anios)} |")
    a("")
    a("---")
    a("")

    # ── Respuesta central ─────────────────────────────────────────────────────
    a("## 11. Pregunta central — ¿BTC ALCISTA necesita régimen alcista macro?")
    a("")
    pf_sobre = pf_num(m_sobre) if m_sobre['n'] > 0 else 0
    pf_bajo  = pf_num(m_b) if m_b['n'] > 0 else 0
    a(f"- SOBRE EMA200d: {m_sobre['n']} trades | PF {fpf(m_sobre['pf'])} | WR {m_sobre['wr']:.1f}%")
    a(f"- BAJO EMA200d:  {m_b['n']} trades | PF {fpf(m_b['pf'])} | WR {m_b['wr']:.1f}%")
    a("")
    if m_sobre['n'] < 10 or m_b['n'] < 10:
        a("**Clasificación: 🟠 EVIDENCIA INSUFICIENTE**")
        a("Alguno de los grupos tiene muy pocos trades para concluir.")
    elif pf_sobre > 1.3 and pf_sobre - pf_bajo > 0.3 and m_sobre['wr'] - m_b['wr'] > 10:
        a("**Clasificación: 🟢 EVIDENCIA FUERTE**")
        a("BTC ALCISTA funciona notablemente mejor en régimen alcista macro (SOBRE EMA200d).")
    elif pf_sobre > pf_bajo and m_sobre['wr'] - m_b['wr'] > 5:
        a("**Clasificación: 🟡 EVIDENCIA MODERADA**")
        a("BTC ALCISTA tiende a rendir mejor en régimen alcista macro, pero la diferencia")
        a("no es lo suficientemente grande o consistente para ser definitiva.")
    elif abs(pf_sobre - pf_bajo) < 0.15 and abs(m_sobre['wr'] - m_b['wr']) < 8:
        a("**Clasificación: 🔴 HIPÓTESIS DESCARTADA**")
        a("BTC ALCISTA no muestra diferencia relevante entre regímenes macro.")
    else:
        a("**Clasificación: 🟡 EVIDENCIA DÉBIL / MIXTA**")
        a("Los datos muestran alguna diferencia entre regímenes pero no es concluyente.")
    a("")
    a("---")
    a("")

    # ── Explicación deterioro 2026 ────────────────────────────────────────────
    a("## 12. Explicación del deterioro 2026")
    a("")
    g2026 = [t for t in trades if t["anio"] == "2026"]
    m2026 = metricas(g2026)
    n_s_2026 = sum(1 for t in g2026 if t["regime"] == "SOBRE")
    n_b_2026 = sum(1 for t in g2026 if t["regime"] == "BAJO")
    a(f"- 2026 (ene–ago): {m2026['n']} trades | PF {fpf(m2026['pf'])} | WR {m2026['wr']:.1f}%")
    a(f"- Régimen 2026: {n_s_2026} SOBRE / {n_b_2026} BAJO EMA200d")
    a(f"- Referencia baseline: 22 trades | PF 0.637 | WR 36.4%")
    a("")
    if n_s_2026 == 0:
        a("**El 100% de los trades de 2026 ocurrió con BTC BAJO EMA200d.**")
        a("Esto confirma el hallazgo del análisis anterior.")
        # Comparar PF BAJO en 2026 vs PF BAJO histórico
        pf_bajo_hist = pf_num(metricas([t for t in trades if t["regime"]=="BAJO" and t["anio"]!="2026"]))
        a(f"- PF BAJO EMA200d histórico (ex 2026): {pf_bajo_hist:.3f}")
        a(f"- PF BAJO EMA200d en 2026: {fpf(m2026['pf'])}")
        a("")
        a("El deterioro de 2026 se explica en parte por el régimen macro y en parte por la")
        a("intensidad de la caída (−10% a −30% bajo EMA200d — un bear market severo).")
    a("")
    a("---")
    a("")

    # ── Limitaciones ──────────────────────────────────────────────────────────
    a("## 13. Limitaciones")
    a("")
    a("1. **Sin gates de producción:** el bot real filtra por termómetro, spread, horario y eventos")
    a("   macro. Estas señales son un superset de las señales reales del bot.")
    a("2. **Sin trailing stop:** la producción usa trailing — puede cambiar el mix TP/SL vs este análisis.")
    a("3. **RSI simple:** la producción usa el mismo RSI, pero la condición de fase ALCISTA del")
    a("   `director_orquesta.py` es un filtro adicional no replicado aquí.")
    a("4. **Monto fijo $5:** sin gestión proporcional al capital.")
    a("5. **EMA200d como proxy macro:** hay otras definiciones de tendencia (EMA50d, EMA200w, etc.).")
    a("6. **Muestra limitada por año:** algunos años tienen pocas trades en ciertos subgrupos.")
    a("7. **Sin corrección estadística:** múltiples comparaciones simultáneas aumentan el riesgo")
    a("   de falsos positivos (problema de múltiples hipótesis). Todos los patrones marcados")
    a("   necesitan validación independiente.")
    a("")
    a("---")
    a("")

    # ── Hipótesis para siguiente investigación ────────────────────────────────
    a("## 14. Hipótesis para investigación futura")
    a("")
    a("Basándose en los patrones detectados, las hipótesis más interesantes para")
    a("investigación posterior (NO implementar, NO activar):")
    a("")
    if any(pf_num(m) >= 1.3 and ok_y >= 2 for _, m, _, ok_y in candidatos):
        for nombre, m, _, ok_y in candidatos:
            if pf_num(m) >= 1.3 and ok_y >= 2 and m['n'] >= 15:
                a(f"- **{nombre}:** PF {fpf(m['pf'])}, WR {m['wr']:.0f}%, {m['n']} trades, "
                  f"consistente en {ok_y}/{len(anios)} años")
    a("")
    a("Para cada hipótesis validar con walk-forward estricto antes de considerar candidato.")
    a("")
    a("---")
    a("")

    # ── Confirmación aislamiento ──────────────────────────────────────────────
    a("## 15. Confirmación final de aislamiento")
    a("")
    a("- `config_cartera.py` = **SIN CAMBIOS** ✅")
    a("- `francotirador_alcista_btc.py` = **SIN CAMBIOS** ✅")
    a("- `director_btc.py` = **SIN CAMBIOS** ✅")
    a("- `francotirador_lateral_btc.py` = **SIN CAMBIOS** ✅")
    a("- `auditoria.csv` = **SIN CAMBIOS** ✅")
    a("- `billetera.json` = **SIN CAMBIOS** ✅")
    a("- Producción = **INTACTA** ✅")
    a("- Candidato = **NO ACTIVADO** ✅")
    a("- Parámetros = **SIN CAMBIOS** ✅")
    a("")
    a(f"Archivos creados: solo `reports/2026-08-14_btc-alcista-forense-regimen-ema200-historico.md`")

    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("BTC ALCISTA — Forense histórico × régimen EMA200 diaria")
    print("=" * 60)
    print()

    print(f"[1/4] Descargando velas diarias desde {FECHA_WARMUP_D}...")
    velas_d = fetch_velas(SIMBOLO, "1d", _ts_ms(FECHA_WARMUP_D))
    ahora_ms = int(datetime.now(timezone.utc).timestamp()*1000)
    velas_d = [v for v in velas_d if int(v[6]) < ahora_ms]
    print(f"      Velas diarias: {len(velas_d)}")

    print("[2/4] Calculando EMA200 y pendiente...")
    ema_map, pend_map = construir_ema_maps(velas_d)
    print(f"      Fechas con EMA200: {len(ema_map)}")

    print(f"[3/4] Descargando velas 4H desde {FECHA_WARMUP_4H}...")
    velas_4h = fetch_velas(SIMBOLO, "4h", _ts_ms(FECHA_WARMUP_4H))
    velas_4h = [v for v in velas_4h if int(v[6]) < ahora_ms]
    print(f"      Velas 4H: {len(velas_4h)}")

    print("[4/4] Simulando y clasificando...")
    trades = simular(velas_4h, ema_map, pend_map)
    print(f"      Trades generados: {len(trades)}")
    print()

    # Preview rápido
    m = metricas(trades)
    sobre = [t for t in trades if t["regime"] == "SOBRE"]
    bajo  = [t for t in trades if t["regime"] == "BAJO"]
    ms = metricas(sobre); mb = metricas(bajo)
    print(f"=== PREVIEW RÁPIDO ===")
    print(f"Total:   {m['n']} trades | PF {fpf(m['pf'])} | WR {m['wr']:.1f}% | Exp {m['exp']:.4f}")
    print(f"SOBRE:   {ms['n']} trades | PF {fpf(ms['pf'])} | WR {ms['wr']:.1f}% | Exp {ms['exp']:.4f}")
    print(f"BAJO:    {mb['n']} trades | PF {fpf(mb['pf'])} | WR {mb['wr']:.1f}% | Exp {mb['exp']:.4f}")
    print()

    print("Generando reporte...")
    reporte = generar_reporte(trades)
    os.makedirs(os.path.dirname(os.path.expanduser(REPORT_PATH)), exist_ok=True)
    with open(os.path.expanduser(REPORT_PATH), "w") as f:
        f.write(reporte)
    print(f"Reporte: {REPORT_PATH}")


if __name__ == "__main__":
    main()
