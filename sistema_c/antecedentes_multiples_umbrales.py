"""
Extension de sistema_c/antecedentes_movimientos_grandes.py -- Fase 1
exploratoria, mismo analisis pero barriendo el umbral de "evento grande"
(5%, 8%, 10%, 12%, 15%) en vez de un solo punto fijo, ventana 48h.
Objetivo: encontrar el umbral con mejor balance entre n>=30 por moneda y
patron de antecedente consistente (el candidato ya identificado: ATR actual
vs mediana historica de la moneda).

Reusa exactamente las mismas definiciones y funciones de
antecedentes_movimientos_grandes.py (ventana de antecedente 8 velas de 4h,
grupo de referencia del mismo tamano, mismas 5 variables).

Fase 1 exploratoria -- NO se backtestea ningun gate.

Solo lectura. No toca config_cartera.py, francotiradores reales,
auditoria.csv. Sin commits.
"""
import sys, os, json, random
from datetime import datetime
sys.path.insert(0, "/home/ariel/bot-padre-v2")
sys.path.insert(0, "/home/ariel/bot-padre-v2/sistema_c")
import numpy as np
from scipy.stats import linregress
import tp_postergado_atr as m
import antecedentes_movimientos_grandes as a

RAW_DIR = os.path.expanduser("~/bot-padre-v2/reports/raw")
UMBRALES = [5.0, 8.0, 10.0, 12.0, 15.0]
VENTANA_HORAS = 48
VELAS_PREVIAS = a.VELAS_PREVIAS
random.seed(42)


def clasificar_eventos(trades, closes, idx_map, umbral_pct, n_velas):
    eventos, no_eventos = [], []
    for t in trades:
        ts_entrada = t["ts_entrada"]
        if ts_entrada not in idx_map:
            continue
        idx = idx_map[ts_entrada]
        precio_entrada = t["entrada"]
        ventana_closes = closes[idx: idx + n_velas + 1]
        if len(ventana_closes) < 2:
            continue
        ganancia_pct = (max(ventana_closes) - precio_entrada) / precio_entrada * 100
        if ganancia_pct >= umbral_pct:
            eventos.append((t, ts_entrada, idx, round(ganancia_pct, 2)))
        else:
            no_eventos.append((t, ts_entrada, idx))
    return eventos, no_eventos


if __name__ == "__main__":
    velas_por_moneda, ts_por_moneda, closes_por_moneda = {}, {}, {}
    for moneda, cfg in m.MONEDAS.items():
        print(f"[cargar] {moneda}...")
        velas_4h, ts_4h_sorted = m.cargar_4h(cfg["symbol"], cfg["backup"], cfg["fecha_desde"])
        velas_por_moneda[moneda] = velas_4h
        ts_por_moneda[moneda] = ts_4h_sorted
        closes_por_moneda[moneda] = [velas_4h[ts]["close"] for ts in ts_4h_sorted]

    atr_hist_por_moneda = {}
    for moneda in m.MONEDAS:
        velas_4h, ts_sorted = velas_por_moneda[moneda], ts_por_moneda[moneda]
        muestreo = range(14, len(ts_sorted), 6)
        vals = [a.atr_pct_de(velas_4h, ts_sorted, i) for i in muestreo]
        vals = [v for v in vals if v is not None]
        atr_hist_por_moneda[moneda] = float(np.median(vals))

    n_velas_48h = VENTANA_HORAS // 4
    reporte = {}

    for umbral in UMBRALES:
        print(f"\n{'#'*70}\nUMBRAL {umbral}%\n{'#'*70}")
        reporte[str(umbral)] = {}
        fechas_todas = set()

        for moneda, cfg in m.MONEDAS.items():
            velas_4h, ts_sorted = velas_por_moneda[moneda], ts_por_moneda[moneda]
            closes = closes_por_moneda[moneda]
            idx_map = {ts: i for i, ts in enumerate(ts_sorted)}
            trades = a.cargar_todos_los_trades(cfg)

            eventos, no_eventos = clasificar_eventos(trades, closes, idx_map, umbral, n_velas_48h)
            muestra_ref = random.sample(no_eventos, min(len(eventos), len(no_eventos))) if eventos else []

            def features_de(idx, moneda_actual):
                velas_4h_m, ts_sorted_m = velas_por_moneda[moneda_actual], ts_por_moneda[moneda_actual]
                if idx < VELAS_PREVIAS + 20:
                    return None
                idxs_prev = list(range(idx - VELAS_PREVIAS, idx))
                vol_rels = [a.vol_rel_de(velas_4h_m, ts_sorted_m, i) for i in idxs_prev]
                cuerpos = [a.cuerpo_pct_de(velas_4h_m[ts_sorted_m[i]]) for i in idxs_prev]
                if any(v is None for v in vol_rels):
                    return None
                x = list(range(VELAS_PREVIAS))
                slope_vol = linregress(x, vol_rels).slope
                slope_cuerpo = linregress(x, cuerpos).slope
                atr_pct_ultima = a.atr_pct_de(velas_4h_m, ts_sorted_m, idx - 1)
                atr_vs_hist = round(atr_pct_ultima / atr_hist_por_moneda[moneda_actual], 3) if atr_pct_ultima else None
                return dict(slope_vol_rel=round(float(slope_vol), 4), slope_cuerpo_pct=round(float(slope_cuerpo), 3),
                            vol_rel_prom=round(float(np.mean(vol_rels)), 2), cuerpo_prom=round(float(np.mean(cuerpos)), 1),
                            atr_vs_historico=atr_vs_hist)

            ev_detalle = []
            for t, ts_entrada, idx, ganancia in eventos:
                feat = features_de(idx, moneda)
                if feat:
                    feat["ts_entrada"] = ts_entrada
                    ev_detalle.append(feat)
            ref_detalle = []
            for t, ts_entrada, idx in muestra_ref:
                feat = features_de(idx, moneda)
                if feat:
                    ref_detalle.append(feat)

            fechas_todas.update(ts for _, ts, _, _ in eventos)

            medianas = {}
            for campo in ["slope_vol_rel", "slope_cuerpo_pct", "vol_rel_prom", "cuerpo_prom", "atr_vs_historico"]:
                ev_vals = [x[campo] for x in ev_detalle if x[campo] is not None]
                ref_vals = [x[campo] for x in ref_detalle if x[campo] is not None]
                medianas[campo] = dict(
                    eventos=round(float(np.median(ev_vals)), 4) if ev_vals else None,
                    referencia=round(float(np.median(ref_vals)), 4) if ref_vals else None)

            reporte[str(umbral)][moneda] = dict(n_eventos=len(eventos), n_no_eventos=len(no_eventos),
                                                 medianas=medianas, eventos_detalle=ev_detalle,
                                                 referencia_detalle=ref_detalle)
            atr_ev = medianas["atr_vs_historico"]["eventos"]
            atr_ref = medianas["atr_vs_historico"]["referencia"]
            ratio = round(atr_ev / atr_ref, 2) if atr_ev and atr_ref else None
            print(f"  {moneda}: n_eventos={len(eventos)} {'✅ n>=30' if len(eventos)>=30 else ''} | "
                  f"ATR_vs_hist eventos={atr_ev} ref={atr_ref} ratio={ratio}")

        print(f"  >> eventos de calendario unicos (3 monedas, umbral {umbral}%): {len(fechas_todas)}")
        reporte[str(umbral)]["_fechas_unicas"] = len(fechas_todas)

    ruta = os.path.join(RAW_DIR, f"antecedentes_multiples_umbrales_{datetime.now().strftime('%Y-%m-%d')}.json")
    with open(ruta, "w") as f:
        json.dump(reporte, f, indent=2, default=str)
    print(f"\n[output] {ruta}")
