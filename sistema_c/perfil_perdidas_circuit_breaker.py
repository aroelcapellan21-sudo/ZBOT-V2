"""
Perfil de operaciones perdedoras (SL) + rachas completas + simulacion de
circuit breaker, sobre las combinaciones A (config actual) y O (con AVAX),
reusando los datasets ya generados esta sesion (9 anios BTC/ETH/AVAX-ALC,
5.9 anios SOL). Capital real $20, MONTO_FIJO=$5/trade.

Parte 1 -- perfil de perdedoras vs ganadoras: velas hasta resolucion, RSI de
entrada (ya en los datos), volumen relativo y ATR% de entrada (calculados
desde la propia serie 4h de cada moneda).

Parte 2 -- distribucion completa de rachas de perdidas consecutivas (no solo
el maximo), $ perdidos por nivel de racha.

Parte 3 -- circuit breaker: tras 3 perdidas seguidas (en la secuencia
combinada de la cartera, no por moneda separada), pausar nuevas entradas
por un tiempo FIJO (7 dias / 42 velas de 4h, elegido de antemano, sin
tunear multiples valores para que se vea bien -- unico valor probado).
Simulacion secuencial: se excluyen los trades cuya entrada cae dentro de la
ventana de pausa: no se "sustituyen" por otra señal, simplemente no ocurren
(igual que si el bot estuviera apagado esos dias).

Solo lectura. No toca config_cartera.py, francotiradores reales,
auditoria.csv. Sin commits.
"""
import sys, os, json, csv
from datetime import datetime, timezone, timedelta
sys.path.insert(0, "/home/ariel/bot-padre-v2")
sys.path.insert(0, "/home/ariel/bot-padre-v2/sistema_c")
import numpy as np
import antecedentes_movimientos_grandes as a
import tp_postergado_atr as m

RAW_DIR = os.path.expanduser("~/bot-padre-v2/reports/raw")
CAPITAL_BASE = 20.0
MONTO_FIJO = 5.0
COMISION = 0.001
PAUSA_HORAS = 24 * 7  # 7 dias, elegido de antemano, no tuneado

COMBOS = {
    "A_actual": [("BTC", "ALCISTA"), ("ETH", "ALCISTA"), ("SOL", "LATERAL")],
    "O_4way":   [("BTC", "ALCISTA"), ("ETH", "ALCISTA"), ("SOL", "ALCISTA"), ("AVAX", "ALCISTA")],
}

TRADE_SOURCES = {
    ("BTC", "ALCISTA"): ("/home/ariel/bot-padre-v2/reports/raw/btc_fase2_variantes_2026-08-22.json", "baseline"),
    ("ETH", "ALCISTA"): ("/home/ariel/bot-padre-v2/reports/raw/eth_fase2_variantes_2026-08-23.json", "baseline"),
    ("SOL", "LATERAL"): ("/home/ariel/bot-padre-v2/reports/raw/sol_lateral_evaluar_literal_2020_2026_baseline_2026-08-22.json", None),
    ("SOL", "ALCISTA"): ("/home/ariel/bot-padre-v2/reports/raw/torneo_sol_alcista_2026-08-23.json", "trades"),
    ("AVAX", "ALCISTA"): ("/home/ariel/bot-padre-v2/reports/raw/torneo_avax_alcista_2026-08-23.json", "trades"),
}


def neto_pct(entrada, salida):
    return ((salida * (1 - COMISION)) / (entrada * (1 + COMISION)) - 1) * 100


def cargar_trades(moneda, fase):
    ruta, key = TRADE_SOURCES[(moneda, fase)]
    data = json.load(open(ruta))
    raw = data[key] if key else data
    out = []
    for t in raw:
        if t["estado"] not in ("TP", "SL", "TRAILING_SL", "BE"):
            continue
        if "ts_salida" not in t:
            dt_e = datetime.strptime(t["ts_entrada"], "%Y-%m-%d %H:%M:%S")
            dt_s = dt_e + timedelta(hours=4 * int(t["velas"]))
            t = dict(t); t["ts_salida"] = dt_s.strftime("%Y-%m-%d %H:%M:%S")
        neto = neto_pct(t["entrada"], t["salida"])
        out.append(dict(moneda=moneda, fase=fase, ts_entrada=t["ts_entrada"], ts_salida=t["ts_salida"],
                         entrada=t["entrada"], salida=t["salida"], estado=t["estado"],
                         rsi=float(t["rsi"]) if t.get("rsi") not in (None, "") else None,
                         velas=int(t["velas"]) if "velas" in t else None,
                         neto=neto, pnl_usd=round(MONTO_FIJO * neto / 100, 4), gano=1 if neto > 0 else 0))
    return out


if __name__ == "__main__":
    print("[cargar] series 4h para features de entrada (RSI ya viene en los datos; vol_rel/ATR se calculan)...")
    CFG_MONEDAS = dict(m.MONEDAS)
    CFG_MONEDAS["AVAX"] = dict(symbol="AVAXUSDT",
                                backup=os.path.expanduser("~/bot-padre-v3-backup/data/historico_4h/AVAXUSDT_4h.csv"),
                                fecha_desde=datetime(2020, 9, 22, tzinfo=timezone.utc))
    velas_por_moneda, ts_por_moneda, idx_por_moneda = {}, {}, {}
    for moneda in ["BTC", "ETH", "SOL", "AVAX"]:
        cfg = CFG_MONEDAS[moneda]
        velas_4h, ts_sorted = m.cargar_4h(cfg["symbol"], cfg["backup"], cfg["fecha_desde"])
        velas_por_moneda[moneda] = velas_4h
        ts_por_moneda[moneda] = ts_sorted
        idx_por_moneda[moneda] = {t: i for i, t in enumerate(ts_sorted)}
        print(f"  {moneda}: {len(ts_sorted)} velas")

    def features_entrada(moneda, ts_entrada):
        velas_4h, ts_sorted = velas_por_moneda[moneda], ts_por_moneda[moneda]
        idx = idx_por_moneda[moneda].get(ts_entrada)
        if idx is None:
            return None, None
        vol_rel = a.vol_rel_de(velas_4h, ts_sorted, idx)
        atr_pct = a.atr_pct_de(velas_4h, ts_sorted, idx)
        return vol_rel, atr_pct

    print("\n[cargar] trades de cada combinacion...")
    trades_combo = {}
    for nombre, comps in COMBOS.items():
        todos = []
        for moneda, fase in comps:
            todos.extend(cargar_trades(moneda, fase))
        todos.sort(key=lambda t: t["ts_entrada"])
        # agregar features de entrada
        for t in todos:
            vol_rel, atr_pct = features_entrada(t["moneda"], t["ts_entrada"])
            t["vol_rel_entrada"] = vol_rel
            t["atr_pct_entrada"] = atr_pct
        trades_combo[nombre] = todos
        print(f"  {nombre}: {len(todos)} trades")

    resultados = {}

    # ============ PARTE 1: perfil ganadoras vs perdedoras ============
    print("\n" + "=" * 70 + "\nPARTE 1 -- perfil de perdedoras vs ganadoras\n" + "=" * 70)
    for nombre, trades in trades_combo.items():
        ganadoras = [t for t in trades if t["gano"] == 1]
        perdedoras = [t for t in trades if t["gano"] == 0]

        def stats(campo, lista):
            vals = [t[campo] for t in lista if t.get(campo) is not None]
            if not vals:
                return None
            return dict(n=len(vals), mediana=round(float(np.median(vals)), 3),
                        p25=round(float(np.percentile(vals, 25)), 3), p75=round(float(np.percentile(vals, 75)), 3))

        perfil = {}
        for campo in ["velas", "rsi", "vol_rel_entrada", "atr_pct_entrada"]:
            perfil[campo] = dict(ganadoras=stats(campo, ganadoras), perdedoras=stats(campo, perdedoras))

        neto_perdedoras = [t["neto"] for t in perdedoras]
        resultados[f"{nombre}_perfil"] = dict(n_ganadoras=len(ganadoras), n_perdedoras=len(perdedoras),
                                               perfil=perfil,
                                               neto_perdedoras_mediana=round(float(np.median(neto_perdedoras)), 3),
                                               neto_perdedoras_p10_p90=[round(float(np.percentile(neto_perdedoras, 10)), 3),
                                                                        round(float(np.percentile(neto_perdedoras, 90)), 3)])
        print(f"\n--- {nombre} ---  ganadoras={len(ganadoras)}  perdedoras={len(perdedoras)}")
        for campo in ["velas", "rsi", "vol_rel_entrada", "atr_pct_entrada"]:
            g, p = perfil[campo]["ganadoras"], perfil[campo]["perdedoras"]
            print(f"  {campo:18s} ganadoras: mediana={g['mediana'] if g else 'NA'} [{g['p25'] if g else '-'},{g['p75'] if g else '-'}]  "
                  f"perdedoras: mediana={p['mediana'] if p else 'NA'} [{p['p25'] if p else '-'},{p['p75'] if p else '-'}]")
        print(f"  neto% de perdedoras: mediana={resultados[f'{nombre}_perfil']['neto_perdedoras_mediana']} "
              f"p10-p90={resultados[f'{nombre}_perfil']['neto_perdedoras_p10_p90']}")

    # ============ PARTE 2: rachas completas ============
    print("\n" + "=" * 70 + "\nPARTE 2 -- distribucion completa de rachas de perdidas\n" + "=" * 70)
    for nombre, trades in trades_combo.items():
        racha_actual, rachas = 0, []
        pnl_racha_actual = 0.0
        for t in trades:
            if t["gano"] == 0:
                racha_actual += 1
                pnl_racha_actual += t["pnl_usd"]
            else:
                if racha_actual > 0:
                    rachas.append((racha_actual, round(pnl_racha_actual, 4)))
                racha_actual, pnl_racha_actual = 0, 0.0
        if racha_actual > 0:
            rachas.append((racha_actual, round(pnl_racha_actual, 4)))

        buckets = {"1": [], "2": [], "3": [], "4": [], "5-7": [], "8+": []}
        for longitud, pnl in rachas:
            clave = str(longitud) if longitud <= 4 else ("5-7" if longitud <= 7 else "8+")
            buckets[clave].append(pnl)

        resumen_buckets = {k: dict(ocurrencias=len(v), pnl_total=round(sum(v), 2),
                                    pnl_promedio=round(sum(v) / len(v), 2) if v else None) for k, v in buckets.items()}
        resultados[f"{nombre}_rachas"] = dict(total_rachas=len(rachas), racha_maxima=max((l for l, _ in rachas), default=0),
                                               buckets=resumen_buckets, detalle=rachas)
        print(f"\n--- {nombre} --- {len(rachas)} rachas de perdidas en total, maxima={max((l for l,_ in rachas), default=0)}")
        for k, v in resumen_buckets.items():
            print(f"  racha de {k}: {v['ocurrencias']} veces, $ total perdido={v['pnl_total']}, promedio por racha=${v['pnl_promedio']}")

    # ============ PARTE 3: circuit breaker ============
    print("\n" + "=" * 70 + f"\nPARTE 3 -- circuit breaker (3 perdidas seguidas -> pausa {PAUSA_HORAS}h)\n" + "=" * 70)

    def metricas(trades, capital_inicial=CAPITAL_BASE):
        n = len(trades)
        if n == 0:
            return dict(n=0)
        pnl = np.array([t["pnl_usd"] for t in trades])
        wr = round((pnl > 0).mean() * 100, 1)
        ganadores, perdedores = pnl[pnl > 0], pnl[pnl <= 0]
        pf = round(ganadores.sum() / -perdedores.sum(), 3) if len(perdedores) and perdedores.sum() != 0 else None
        racha, racha_max = 0, 0
        for p in pnl:
            if p <= 0:
                racha += 1; racha_max = max(racha_max, racha)
            else:
                racha = 0
        eq = capital_inicial + np.cumsum(pnl)
        peak = np.maximum.accumulate(np.concatenate([[capital_inicial], eq]))
        eq_full = np.concatenate([[capital_inicial], eq])
        dd = (eq_full - peak) / peak * 100
        return dict(n=n, wr=wr, pf=pf, racha_max=racha_max, pnl_total=round(float(pnl.sum()), 2),
                    capital_final=round(capital_inicial + float(pnl.sum()), 2), dd_max=round(float(dd.min()), 2))

    for nombre, trades in trades_combo.items():
        con_cb = []
        racha_actual = 0
        pausado_hasta = None
        for t in trades:
            ts_e = datetime.strptime(t["ts_entrada"], "%Y-%m-%d %H:%M:%S")
            if pausado_hasta is not None and ts_e < pausado_hasta:
                continue  # trade excluido: bot pausado en ese momento
            pausado_hasta = None
            con_cb.append(t)
            if t["gano"] == 0:
                racha_actual += 1
                if racha_actual >= 3:
                    ts_s = datetime.strptime(t["ts_salida"], "%Y-%m-%d %H:%M:%S")
                    pausado_hasta = ts_s + timedelta(hours=PAUSA_HORAS)
                    racha_actual = 0  # se resetea el contador al activar la pausa
            else:
                racha_actual = 0

        m_sin = metricas(trades)
        m_con = metricas(con_cb)
        n_excluidos = len(trades) - len(con_cb)
        resultados[f"{nombre}_circuit_breaker"] = dict(pausa_horas=PAUSA_HORAS, n_excluidos=n_excluidos,
                                                          sin_cb=m_sin, con_cb=m_con)
        print(f"\n--- {nombre} --- trades excluidos por la pausa: {n_excluidos}")
        print(f"  SIN circuit breaker: n={m_sin['n']} WR={m_sin['wr']}% PF={m_sin['pf']} racha_max={m_sin['racha_max']} "
              f"PnL=${m_sin['pnl_total']} capital_final=${m_sin['capital_final']} DD={m_sin['dd_max']}%")
        print(f"  CON circuit breaker: n={m_con['n']} WR={m_con['wr']}% PF={m_con['pf']} racha_max={m_con['racha_max']} "
              f"PnL=${m_con['pnl_total']} capital_final=${m_con['capital_final']} DD={m_con['dd_max']}%")

        # walk-forward: 3 ventanas sobre la version CON circuit breaker, comparado contra las mismas ventanas SIN
        wf = []
        n_trades_sin = len(trades)
        tercio = n_trades_sin // 3
        for i in range(3):
            lo, hi = i * tercio, (i + 1) * tercio if i < 2 else n_trades_sin
            sub_sin = trades[lo:hi]
            if not sub_sin:
                continue
            ts_ini, ts_fin = sub_sin[0]["ts_entrada"], sub_sin[-1]["ts_entrada"]
            sub_con = [t for t in con_cb if ts_ini <= t["ts_entrada"] <= ts_fin]
            m_sin_v = metricas(sub_sin, capital_inicial=CAPITAL_BASE)
            m_con_v = metricas(sub_con, capital_inicial=CAPITAL_BASE)
            wf.append(dict(rango=f"{ts_ini[:10]}->{ts_fin[:10]}", sin_cb=m_sin_v, con_cb=m_con_v))
            print(f"    ventana {ts_ini[:10]}->{ts_fin[:10]}: SIN n={m_sin_v['n']} PnL=${m_sin_v['pnl_total']} | "
                  f"CON n={m_con_v['n']} PnL=${m_con_v['pnl_total']}")
        resultados[f"{nombre}_circuit_breaker"]["walkforward"] = wf

    ruta = os.path.join(RAW_DIR, f"perfil_perdidas_cb_{datetime.now().strftime('%Y-%m-%d')}.json")
    with open(ruta, "w") as f:
        json.dump(resultados, f, indent=2, default=str)
    print(f"\n[output] {ruta}")
