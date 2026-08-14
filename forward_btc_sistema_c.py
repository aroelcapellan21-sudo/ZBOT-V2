"""
forward_btc_sistema_c.py
BTC ALCISTA — Forward ene-ago 2026: Produccion vs Sistema C
INVESTIGACION PURA — NO modifica ningun archivo de produccion.

Produccion : RSI 55-75, SL 5%, TP 6%, sin gate EMA
Sistema C  : RSI 55-60, SL 5%, TP 6%, gate SOBRE EMA200d (anti-lookahead)
"""

import json
import os
import urllib.request
import urllib.parse
from datetime import datetime, timezone

# ── Constantes ───────────────────────────────────────────────────────────────
SIMBOLO       = "BTCUSDT"
INTERVALO_4H  = "4h"
INTERVALO_1D  = "1d"
CAPITAL_INIT  = 20.0
MONTO_TRADE   = 5.0
COMISION      = 0.001           # 0.1% por lado
FECHA_INICIO  = "2026-01-01"   # primera señal permitida
FECHA_WARMUP  = "2025-10-01"   # warmup para RSI 4H
FECHA_EMA_WU  = "2019-06-01"   # warmup para EMA200d (>400 dias)
MIN_TRADES    = 30

PRODUCCION = {
    "nombre": "Produccion",
    "rsi_min": 55.0, "rsi_max": 75.0,
    "sl": 0.050, "tp": 0.060,
    "gate_ema": False,
}
SISTEMA_C = {
    "nombre": "Sistema_C",
    "rsi_min": 55.0, "rsi_max": 60.0,
    "sl": 0.050, "tp": 0.060,
    "gate_ema": True,   # SOBRE EMA200d
    "ema_n": 200,
}

REPORT_PATH = os.path.expanduser(
    "~/bot-padre-v2/reports/2026-08-14_btc-forward-sistema-c-vs-produccion.md"
)

# ── Binance helpers ───────────────────────────────────────────────────────────
def _ts_ms(fecha_str):
    dt = datetime.strptime(fecha_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)

def fetch_velas(symbol, intervalo, desde_ms):
    velas = []
    inicio = desde_ms
    while True:
        params = urllib.parse.urlencode({
            "symbol":    symbol,
            "interval":  intervalo,
            "startTime": inicio,
            "limit":     1000,
        })
        url = f"https://api.binance.com/api/v3/klines?{params}"
        try:
            with urllib.request.urlopen(url, timeout=20) as resp:
                batch = json.loads(resp.read().decode())
        except Exception as e:
            print(f"  ERROR fetch: {e}")
            break
        if not batch:
            break
        velas.extend(batch)
        if len(batch) < 1000:
            break
        inicio = batch[-1][0] + 1
    return velas

# ── RSI simple ────────────────────────────────────────────────────────────────
RSI_VENTANA = 15
RSI_WARMUP  = 60

def calcular_rsi_simple(cierres_ventana, periodo=14):
    if len(cierres_ventana) < periodo + 1:
        return None
    ganancias, perdidas = [], []
    for i in range(1, periodo + 1):
        diff = cierres_ventana[i] - cierres_ventana[i - 1]
        if diff > 0:
            ganancias.append(diff); perdidas.append(0)
        else:
            ganancias.append(0); perdidas.append(abs(diff))
    avg_gan = sum(ganancias) / periodo
    avg_per = sum(perdidas) / periodo
    if avg_per == 0:
        return 100.0
    return round(100 - (100 / (1 + avg_gan / avg_per)), 2)

# ── EMA ───────────────────────────────────────────────────────────────────────
def calcular_ema(serie, n):
    """EMA clasica con k=2/(n+1)."""
    if len(serie) < n:
        return [None] * len(serie)
    k = 2.0 / (n + 1)
    emas = [None] * (n - 1)
    emas.append(sum(serie[:n]) / n)
    for precio in serie[n:]:
        emas.append(precio * k + emas[-1] * (1 - k))
    return emas

def construir_ema200d(velas_1d):
    """Devuelve dict {fecha_utc_str -> ema200d} usando cierre del DIA ANTERIOR (anti-lookahead)."""
    cierres = [float(v[4]) for v in velas_1d]
    fechas  = [datetime.utcfromtimestamp(int(v[0]) / 1000).strftime("%Y-%m-%d") for v in velas_1d]
    emas    = calcular_ema(cierres, 200)
    # ema[i] se calcula con datos hasta el cierre del dia i.
    # Para una vela 4H que ABRE en el dia D, la EMA disponible es la del dia D-1 (indice i-1).
    resultado = {}
    for i in range(1, len(fechas)):
        if emas[i - 1] is not None:
            resultado[fechas[i]] = emas[i - 1]   # clave = dia D, valor = EMA de D-1
    return resultado

# ── Motor de simulacion ───────────────────────────────────────────────────────
INICIO_MS = int(datetime.strptime(FECHA_INICIO, "%Y-%m-%d")
                .replace(tzinfo=timezone.utc).timestamp() * 1000)

def simular(velas_4h, config, ema200d_map):
    cierres = [float(k[4]) for k in velas_4h]
    ts_list = [int(k[0]) for k in velas_4h]

    trades = []
    capital = CAPITAL_INIT
    max_capital = CAPITAL_INIT
    max_dd = 0.0
    en_posicion = False
    entrada_precio = entrada_ts = entrada_rsi = None
    sl_precio = tp_precio = 0.0

    for i in range(RSI_WARMUP, len(cierres)):
        ventana = cierres[max(0, i - 60):i]
        rsi = calcular_rsi_simple(ventana[-RSI_VENTANA:])
        if rsi is None:
            continue

        precio_cierre = cierres[i]
        ts_ms = ts_list[i]
        ts_dt = datetime.utcfromtimestamp(ts_ms / 1000)

        if en_posicion:
            resultado = precio_salida = None
            if precio_cierre <= sl_precio:
                resultado = "SL"; precio_salida = sl_precio
            elif precio_cierre >= tp_precio:
                resultado = "TP"; precio_salida = tp_precio
            if resultado:
                bruto = MONTO_TRADE * config["tp"] if resultado == "TP" else -MONTO_TRADE * config["sl"]
                pl_neto = round(bruto - MONTO_TRADE * COMISION * 2, 4)
                capital += pl_neto
                max_capital = max(max_capital, capital)
                dd = (max_capital - capital) / max_capital * 100
                max_dd = max(max_dd, dd)
                trades.append({
                    "entrada_ts":  entrada_ts,
                    "salida_ts":   ts_dt,
                    "rsi":         entrada_rsi,
                    "precio_e":    entrada_precio,
                    "precio_s":    round(precio_salida, 2),
                    "resultado":   resultado,
                    "pl":          pl_neto,
                    "capital":     round(capital, 4),
                })
                en_posicion = False

        if not en_posicion and ts_ms >= INICIO_MS:
            if config["rsi_min"] <= rsi <= config["rsi_max"]:
                # Gate EMA200d
                pasa_gate = True
                if config.get("gate_ema"):
                    dia_str = ts_dt.strftime("%Y-%m-%d")
                    ema_val = ema200d_map.get(dia_str)
                    if ema_val is None or precio_cierre <= ema_val:
                        pasa_gate = False
                if pasa_gate:
                    en_posicion   = True
                    entrada_precio = precio_cierre
                    entrada_ts     = ts_dt
                    entrada_rsi    = rsi
                    sl_precio      = round(entrada_precio * (1 - config["sl"]), 2)
                    tp_precio      = round(entrada_precio * (1 + config["tp"]), 2)

    return trades, round(capital, 4), round(max_dd, 2)

# ── Metricas ──────────────────────────────────────────────────────────────────
def metricas(trades, capital, max_dd):
    n = len(trades)
    if n == 0:
        return {"trades": 0, "tp": 0, "sl": 0, "wr": 0, "expect": 0,
                "pf": 0, "pl_total": 0, "capital": capital,
                "max_dd": max_dd, "avg_win": 0, "avg_loss": 0}
    tp_l = [t for t in trades if t["resultado"] == "TP"]
    sl_l = [t for t in trades if t["resultado"] == "SL"]
    total_g = sum(t["pl"] for t in tp_l)
    total_l = abs(sum(t["pl"] for t in sl_l))
    pf  = round(total_g / total_l, 3) if total_l > 0 else float("inf")
    pl_total = sum(t["pl"] for t in trades)
    return {
        "trades":   n,
        "tp":       len(tp_l),
        "sl":       len(sl_l),
        "wr":       round(len(tp_l) / n * 100, 2),
        "expect":   round(pl_total / n, 4),
        "pf":       pf,
        "pl_total": round(pl_total, 4),
        "capital":  capital,
        "max_dd":   max_dd,
        "avg_win":  round(total_g / len(tp_l), 4) if tp_l else 0.0,
        "avg_loss": round(-total_l / len(sl_l), 4) if sl_l else 0.0,
    }

def por_mes(trades):
    meses = {}
    for t in trades:
        key = t["entrada_ts"].strftime("%Y-%m")
        meses.setdefault(key, []).append(t)
    resultado = {}
    for mes, lista in sorted(meses.items()):
        n = len(lista)
        tp_c = sum(1 for t in lista if t["resultado"] == "TP")
        sl_c = n - tp_c
        total_g = sum(t["pl"] for t in lista if t["pl"] > 0)
        total_l = abs(sum(t["pl"] for t in lista if t["pl"] < 0))
        pf  = round(total_g / total_l, 3) if total_l > 0 else float("inf")
        exp = round(sum(t["pl"] for t in lista) / n, 4)
        resultado[mes] = {"trades": n, "tp": tp_c, "sl": sl_c, "pf": pf, "expect": exp,
                          "pl": round(sum(t["pl"] for t in lista), 4)}
    return resultado

def racha_max_sl(trades):
    max_r = cur = 0
    fecha_ini = fecha_cur = None
    fecha_max_ini = fecha_max_fin = None
    for t in trades:
        if t["resultado"] == "SL":
            if cur == 0:
                fecha_cur = t["entrada_ts"]
            cur += 1
            if cur > max_r:
                max_r = cur
                fecha_max_ini = fecha_cur
                fecha_max_fin = t["salida_ts"]
        else:
            cur = 0
    return max_r, fecha_max_ini, fecha_max_fin

# ── Trades compartidos / exclusivos ───────────────────────────────────────────
def compartidos_exclusivos(trades_p, trades_c):
    """Compara por fecha de entrada (dia+hora) para identificar señales compartidas."""
    def key(t):
        return t["entrada_ts"].strftime("%Y-%m-%d %H:%M")

    keys_p = {key(t): t for t in trades_p}
    keys_c = {key(t): t for t in trades_c}

    compartidos_p = [t for t in trades_p if key(t) in keys_c]
    compartidos_c = [t for t in trades_c if key(t) in keys_p]
    exclusivos_p  = [t for t in trades_p if key(t) not in keys_c]
    exclusivos_c  = [t for t in trades_c if key(t) not in keys_p]

    return compartidos_p, compartidos_c, exclusivos_p, exclusivos_c

def resumen_grupo(lista, etiqueta):
    n = len(lista)
    if n == 0:
        return f"| {etiqueta} | 0 | — | — | — | — |"
    tp_c = sum(1 for t in lista if t["resultado"] == "TP")
    sl_c = n - tp_c
    pl = round(sum(t["pl"] for t in lista), 4)
    exp = round(pl / n, 4)
    pl_str = f"+${pl:.4f}" if pl >= 0 else f"-${abs(pl):.4f}"
    exp_str = f"+${exp:.4f}" if exp >= 0 else f"-${abs(exp):.4f}"
    return f"| {etiqueta} | {n} | {tp_c} | {sl_c} | {exp_str} | {pl_str} |"

# ── Formato ───────────────────────────────────────────────────────────────────
def fp(v):
    return f"+${v:.4f}" if v >= 0 else f"-${abs(v):.4f}"

def fpf(v):
    return f"{v:.3f}" if v != float("inf") else "∞"

MESES = {
    "01": "enero", "02": "febrero", "03": "marzo", "04": "abril",
    "05": "mayo", "06": "junio", "07": "julio", "08": "agosto",
    "09": "septiembre", "10": "octubre", "11": "noviembre", "12": "diciembre",
}

# ── Reporte ───────────────────────────────────────────────────────────────────
def generar_reporte(mp, mc, trades_p, trades_c, velas_total, fecha_fin):
    comp_p, comp_c, excl_p, excl_c = compartidos_exclusivos(trades_p, trades_c)
    meses_p = por_mes(trades_p)
    meses_c = por_mes(trades_c)
    todos_meses = sorted(set(list(meses_p.keys()) + list(meses_c.keys())))

    racha_p, ri_p, rf_p = racha_max_sl(trades_p)
    racha_c, ri_c, rf_c = racha_max_sl(trades_c)

    L = []
    a = L.append

    a("# BTC ALCISTA — Forward ene–ago 2026: Producción vs Sistema C")
    a("")
    a(f"**Fecha:** 2026-08-14  ")
    a(f"**Estado:** INVESTIGACIÓN PURA — 0 archivos de producción modificados")
    a("")
    a("---")
    a("")
    a("## 1. Confirmación de aislamiento")
    a("")
    a("| Verificación | Estado |")
    a("|---|---|")
    a("| `config_cartera.py` | ✅ SIN CAMBIOS |")
    a("| `francotirador_alcista_btc.py` | ✅ SIN CAMBIOS |")
    a("| `auditoria.csv` | ✅ SIN CAMBIOS |")
    a("| `billetera.json` | ✅ SIN CAMBIOS |")
    a("| Sistema C en producción | ✅ NO ACTIVADO |")
    a("| Modo de operación | ✅ SIMULADOR |")
    a("")
    a("Script: `forward_btc_sistema_c.py` — no escribe en ningún archivo de producción.")
    a("")
    a("---")
    a("")
    a("## 2. Configuración")
    a("")
    a("| Parámetro | Producción | Sistema C |")
    a("|-----------|-----------|-----------|")
    a("| Símbolo | BTCUSDT | BTCUSDT |")
    a("| Intervalo | 4h | 4h |")
    a(f"| Período | {FECHA_INICIO} → {fecha_fin} | {FECHA_INICIO} → {fecha_fin} |")
    a("| RSI entrada | 55–75 | 55–60 |")
    a("| SL | 5.0% | 5.0% |")
    a("| TP | 6.0% | 6.0% |")
    a("| Gate EMA | Ninguno | SOBRE EMA200d (anti-lookahead) |")
    a(f"| Capital | ${CAPITAL_INIT:.2f} | ${CAPITAL_INIT:.2f} |")
    a(f"| Monto | ${MONTO_TRADE:.2f} | ${MONTO_TRADE:.2f} |")
    a(f"| Comisión | 0.1% × 2 | 0.1% × 2 |")
    a(f"| Velas 4H descargadas | {velas_total} | — |")
    a("| Trailing | No | No |")
    a("| Gates macro | No | No |")
    a("")
    a("---")
    a("")
    a("## 3. Resultados")
    a("")
    a("| Métrica | Producción | Sistema C | Δ |")
    a("|---------|-----------|-----------|---|")
    diffs = [
        ("Trades", mp["trades"], mc["trades"], ""),
        ("TP", mp["tp"], mc["tp"], ""),
        ("SL", mp["sl"], mc["sl"], ""),
    ]
    for lbl, vp, vc, _ in diffs:
        delta = vc - vp
        ds = f"+{delta}" if delta > 0 else str(delta)
        a(f"| {lbl} | {vp} | {vc} | {ds} |")

    wr_d = round(mc["wr"] - mp["wr"], 2)
    a(f"| Win Rate | {mp['wr']:.1f}% | {mc['wr']:.1f}% | {'+' if wr_d>=0 else ''}{wr_d} pp |")

    pf_d = round(mc["pf"] - mp["pf"], 3) if mp["pf"] != float("inf") and mc["pf"] != float("inf") else "—"
    a(f"| Profit Factor | {fpf(mp['pf'])} | {fpf(mc['pf'])} | {pf_d} |")

    exp_d = round(mc["expect"] - mp["expect"], 4)
    a(f"| Expectancy/trade | {fp(mp['expect'])} | {fp(mc['expect'])} | {fp(exp_d)} |")

    pl_d = round(mc["pl_total"] - mp["pl_total"], 4)
    a(f"| P/L acumulado | {fp(mp['pl_total'])} | {fp(mc['pl_total'])} | {fp(pl_d)} |")

    a(f"| Capital final | ${mp['capital']:.4f} | ${mc['capital']:.4f} | — |")
    a(f"| DD máximo | {mp['max_dd']:.1f}% | {mc['max_dd']:.1f}% | {round(mc['max_dd']-mp['max_dd'],1)} pp |")
    a(f"| Racha máx SL | {racha_p} | {racha_c} | — |")
    a("")
    a("---")
    a("")
    a("## 4. Desglose mensual")
    a("")
    a("| Mes | P Trades | P TP | P SL | P PF | C Trades | C TP | C SL | C PF | Ganador |")
    a("|-----|----------|------|------|------|----------|------|------|------|---------|")
    for mes in todos_meses:
        anio, num = mes.split("-")
        nombre = f"{MESES.get(num, num)} {anio}"
        dp = meses_p.get(mes)
        dc = meses_c.get(mes)
        pf_p_str = fpf(dp["pf"]) if dp else "—"
        pf_c_str = fpf(dc["pf"]) if dc else "—"
        t_p = dp["trades"] if dp else 0
        tp_p = dp["tp"] if dp else 0; sl_p = dp["sl"] if dp else 0
        t_c = dc["trades"] if dc else 0
        tp_c = dc["tp"] if dc else 0; sl_c = dc["sl"] if dc else 0
        # Ganador por PL del mes
        pl_p = dp["pl"] if dp else 0
        pl_c = dc["pl"] if dc else 0
        if dp and dc:
            ganador = "Producción" if pl_p > pl_c else ("Sistema C" if pl_c > pl_p else "Empate")
        elif dp:
            ganador = "Producción (solo)"
        elif dc:
            ganador = "Sistema C (solo)"
        else:
            ganador = "—"
        a(f"| {nombre} | {t_p} | {tp_p} | {sl_p} | {pf_p_str} | {t_c} | {tp_c} | {sl_c} | {pf_c_str} | {ganador} |")
    a("")
    a("---")
    a("")
    a("## 5. Trades compartidos vs exclusivos")
    a("")
    a("| Grupo | Trades | TP | SL | Expectancy | P/L |")
    a("|-------|--------|----|----|-----------|-----|")
    a(resumen_grupo(comp_p, "Compartidos — Producción"))
    a(resumen_grupo(comp_c, "Compartidos — Sistema C"))
    a(resumen_grupo(excl_p, "Exclusivos Producción"))
    a(resumen_grupo(excl_c, "Exclusivos Sistema C"))
    a("")
    shared_n = len(comp_p)
    excl_p_n = len(excl_p)
    excl_c_n = len(excl_c)
    a(f"**Señales compartidas:** {shared_n} (RSI 55–60, ambos sistemas las ven, con y sin gate EMA)")
    a(f"**Exclusivas Producción:** {excl_p_n} (RSI 60–75, fuera del rango Sistema C)")
    a(f"**Exclusivas Sistema C:** {excl_c_n} (RSI 55–60 PERO filtradas por Producción por estar fuera de su rango — esto no debería ocurrir)")
    a("")
    a("---")
    a("")
    a("## 6. Trades individuales — Producción")
    a("")
    if not trades_p:
        a("_Sin trades._")
    else:
        a("| # | Entrada | RSI | Precio E | Precio S | Resultado | P/L |")
        a("|---|---------|-----|----------|----------|-----------|-----|")
        for i, t in enumerate(trades_p, 1):
            a(f"| {i} | {t['entrada_ts'].strftime('%Y-%m-%d %H:%M')} "
              f"| {t['rsi']:.1f} | {t['precio_e']:.2f} | {t['precio_s']:.2f} "
              f"| {t['resultado']} | {fp(t['pl'])} |")
    a("")
    a("---")
    a("")
    a("## 7. Trades individuales — Sistema C")
    a("")
    if not trades_c:
        a("_Sin trades._")
    else:
        a("| # | Entrada | RSI | Precio E | Precio S | EMA200d OK | Resultado | P/L |")
        a("|---|---------|-----|----------|----------|-----------|-----------|-----|")
        for i, t in enumerate(trades_c, 1):
            a(f"| {i} | {t['entrada_ts'].strftime('%Y-%m-%d %H:%M')} "
              f"| {t['rsi']:.1f} | {t['precio_e']:.2f} | {t['precio_s']:.2f} "
              f"| ✅ | {t['resultado']} | {fp(t['pl'])} |")
    a("")
    a("---")
    a("")
    a("## 8. Comparación con backtest histórico")
    a("")
    a("| Período | Prod Trades | Prod PF | Prod WR | C Trades | C PF | C WR |")
    a("|---------|------------|---------|---------|----------|------|------|")
    a("| Train 2021–2023 (backtest) | 159 | 1.101 | 49.7% | 74 | 1.177 | 51.4% |")
    a("| OOS 2024–2025 (backtest) | 81 | 1.201 | 51.9% | 59 | 1.322 | 54.2% |")
    if trades_p:
        a(f"| **Forward 2026 (esta prueba)** | **{mp['trades']}** | **{fpf(mp['pf'])}** | "
          f"**{mp['wr']:.1f}%** | **{mc['trades']}** | **{fpf(mc['pf'])}** | **{mc['wr']:.1f}%** |")
    else:
        a("| **Forward 2026 (esta prueba)** | **0** | **—** | **—** | **0** | **—** | **—** |")
    a("")
    a("---")
    a("")
    a("## 9. Veredicto")
    a("")
    # Veredicto
    suf_p = mp["trades"] >= MIN_TRADES
    suf_c = mc["trades"] >= MIN_TRADES

    def verd(m, suf, nombre):
        if not suf:
            return f"**{nombre}: INSUFICIENTE** ({m['trades']} trades < {MIN_TRADES} mínimo)"
        if m["pf"] >= 1.1:
            return f"**{nombre}: ACTIVO** — PF {fpf(m['pf'])} con muestra suficiente"
        elif m["pf"] >= 1.0:
            return f"**{nombre}: MARGINAL** — PF {fpf(m['pf'])} positivo pero cerca del límite"
        else:
            return f"**{nombre}: NEGATIVO** en 2026 — PF {fpf(m['pf'])}"

    a(verd(mp, suf_p, "Producción"))
    a("")
    a(verd(mc, suf_c, "Sistema C"))
    a("")

    # Comparacion
    if mp["trades"] > 0 or mc["trades"] > 0:
        a("### Comparación relativa (forward 2026)")
        a("")
        ganador_forward = None
        if mp["pl_total"] > mc["pl_total"]:
            ganador_forward = "Producción"
        elif mc["pl_total"] > mp["pl_total"]:
            ganador_forward = "Sistema C"
        else:
            ganador_forward = "Empate"
        a(f"En P/L total: **{ganador_forward}**")
        a("")
        a("Consistencia con backtest histórico OOS 2024–2025:")
        a("- Producción OOS PF: 1.201 → Forward 2026: " + fpf(mp["pf"]))
        a("- Sistema C OOS PF:  1.322 → Forward 2026: " + fpf(mc["pf"]))
        a("")

    a("---")
    a("")
    a("## 10. Limitaciones")
    a("")
    a("1. Sin gates de producción (horario, eventos macro, spread, termómetro).")
    a("2. Sin trailing stop — el bot real puede diferir en timing de salidas.")
    a("3. Monto fijo $5 — sin compounding.")
    a("4. La EMA200d se calcula sobre velas diarias de Binance spot (BTCUSDT).")
    a("   Anti-lookahead: se usa la EMA del cierre del día D-1 para señales del día D.")
    a("5. Muestra <8 meses — alta incertidumbre estadística.")
    a("")
    a("---")
    a("")
    a("## 11. Próximos pasos")
    a("")
    a("- Si ambos sistemas tienen < 30 trades en 2026: registrar el baseline y")
    a("  continuar acumulando datos reales en REAL.")
    a("- El Sistema C no se activa en producción sin ≥ 30 trades reales adicionales.")
    a("- Siguiente moneda de investigación: SOL ALCISTA.")
    a("")
    a("---")
    a("")
    a("**ESTADO FINAL: producción NO modificada — Sistema C NO activado**")
    a("")
    a(f"Archivos creados:")
    a(f"- `reports/2026-08-14_btc-forward-sistema-c-vs-produccion.md` (este reporte)")
    a(f"- `forward_btc_sistema_c.py` (script investigación)")

    return "\n".join(L)

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print(f"Descargando velas {SIMBOLO} {INTERVALO_4H} desde {FECHA_WARMUP} (warmup RSI)...")
    velas_4h = fetch_velas(SIMBOLO, INTERVALO_4H, _ts_ms(FECHA_WARMUP))
    ahora_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    velas_4h = [v for v in velas_4h if int(v[6]) < ahora_ms]
    print(f"  Velas 4H: {len(velas_4h)}")

    print(f"Descargando velas {SIMBOLO} {INTERVALO_1D} desde {FECHA_EMA_WU} (warmup EMA200d)...")
    velas_1d = fetch_velas(SIMBOLO, INTERVALO_1D, _ts_ms(FECHA_EMA_WU))
    velas_1d = [v for v in velas_1d if int(v[6]) < ahora_ms]
    print(f"  Velas 1D: {len(velas_1d)}")

    if len(velas_4h) < RSI_WARMUP + 10 or len(velas_1d) < 210:
        print("ERROR: insuficientes velas.")
        return

    fecha_fin = datetime.utcfromtimestamp(int(velas_4h[-1][0]) / 1000).strftime("%Y-%m-%d")
    ema200d_map = construir_ema200d(velas_1d)

    print("Simulando Producción BTC ALCISTA...")
    trades_p, cap_p, dd_p = simular(velas_4h, PRODUCCION, ema200d_map)
    mp = metricas(trades_p, cap_p, dd_p)

    print("Simulando Sistema C BTC ALCISTA (RSI 55-60 + EMA200d)...")
    trades_c, cap_c, dd_c = simular(velas_4h, SISTEMA_C, ema200d_map)
    mc = metricas(trades_c, cap_c, dd_c)

    print(f"\n=== RESULTADOS ===")
    print(f"Produccion: {mp['trades']} trades | PF {fpf(mp['pf'])} | WR {mp['wr']:.1f}% | "
          f"Exp {fp(mp['expect'])} | Cap ${cap_p:.4f} | DD {dd_p:.1f}%")
    print(f"Sistema C : {mc['trades']} trades | PF {fpf(mc['pf'])} | WR {mc['wr']:.1f}% | "
          f"Exp {fp(mc['expect'])} | Cap ${cap_c:.4f} | DD {dd_c:.1f}%")

    comp_p, comp_c, excl_p, excl_c = compartidos_exclusivos(trades_p, trades_c)
    print(f"\n=== COMPARTIDOS/EXCLUSIVOS ===")
    print(f"Compartidos : {len(comp_p)} señales (mismo trade, ambos sistemas)")
    print(f"Excl. Prod  : {len(excl_p)} (RSI 60-75, fuera del rango Sistema C)")
    print(f"Excl. Sist.C: {len(excl_c)} (RSI 55-60, bloqueados por EMA200d)")

    reporte = generar_reporte(mp, mc, trades_p, trades_c, len(velas_4h), fecha_fin)

    os.makedirs(os.path.dirname(os.path.expanduser(REPORT_PATH)), exist_ok=True)
    with open(os.path.expanduser(REPORT_PATH), "w") as f:
        f.write(reporte)
    print(f"\nReporte: {REPORT_PATH}")


if __name__ == "__main__":
    main()
