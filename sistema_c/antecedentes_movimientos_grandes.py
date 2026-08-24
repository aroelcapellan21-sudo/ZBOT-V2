"""
Fase 1 (exploratoria) -- antecedentes de movimientos grandes.

Distinto de las 5 aristas ya cerradas de "TP postergado": en vez de mirar la
vela del TP, busca patrones en las velas PREVIAS a una entrada real que fue
seguida de una subida fuerte (>=15% en 36h/48h/72h desde la entrada).

Definicion operativa de "evento grande" (documentada explicitamente por la
ambiguedad del pedido): para cada entrada real del bot (TP+SL+TRAILING_SL+BE,
no solo TP), se mide el maximo close alcanzado dentro de las N horas
siguientes A PARTIR DE LA PROPIA VELA DE ENTRADA (no una ventana flotante
en cualquier punto de la vida del trade). Si ese maximo implica una suba
>=15% sobre el precio de entrada, se marca como evento grande para esa
ventana (36h=9 velas de 4h, 48h=12 velas, 72h=18 velas).

Para cada evento (ventana de referencia: 48h), se reconstruyen las 8 velas
de 4h previas a la propia vela de entrada (no la del TP) y se mide:
  - tendencia del volumen relativo (pendiente de regresion lineal sobre las
    8 velas, volumen_relativo = volume / promedio_20)
  - tendencia del cuerpo de vela (misma pendiente, sobre cuerpo_pct)
  - ATR% de la ultima de esas 8 velas vs mediana historica de ATR% de la
    moneda completa
  - movimiento simultaneo de BTC en la misma ventana previa (solo para
    ETH/SOL -- BTC es la moneda ancla del proyecto, no tiene "lider" propio
    en este alcance)

Grupo de referencia: muestra aleatoria (mismo tamaño que los eventos) de
entradas que NO calificaron como evento grande en ninguna de las 3
ventanas, con las mismas variables calculadas.

Exploratorio -- NO se backtestea ningun gate. Solo identifica patrones
candidatos.

Solo lectura. No toca config_cartera.py, francotiradores reales,
auditoria.csv. Sin commits.
"""
import sys, os, json, random
from datetime import datetime, timedelta
sys.path.insert(0, "/home/ariel/bot-padre-v2")
sys.path.insert(0, "/home/ariel/bot-padre-v2/sistema_c")
import numpy as np
from scipy.stats import linregress
import tp_postergado_atr as m

RAW_DIR = os.path.expanduser("~/bot-padre-v2/reports/raw")
VENTANAS_HORAS = [36, 48, 72]
VENTANA_PRINCIPAL = 48
UMBRAL_PCT = 15.0
VELAS_PREVIAS = 8
random.seed(42)


def cuerpo_pct_de(v):
    rango = v["high"] - v["low"]
    return abs(v["close"] - v["open"]) / rango * 100 if rango > 0 else 0.0


def vol_rel_de(velas_4h, ts_sorted, idx):
    if idx < 20:
        return None
    v = velas_4h[ts_sorted[idx]]
    vols_prev = [velas_4h[ts_sorted[i]]["volume"] for i in range(idx - 20, idx)]
    vol_prom = sum(vols_prev) / 20
    return v["volume"] / vol_prom if vol_prom > 0 else None


def atr_pct_de(velas_4h, ts_sorted, idx):
    atr = m.calcular_atr14(velas_4h, ts_sorted, idx)
    if atr is None:
        return None
    return atr / velas_4h[ts_sorted[idx]]["close"] * 100


def cargar_todos_los_trades(cfg):
    if cfg["baseline_key"]:
        raw = json.load(open(cfg["baseline_json"]))[cfg["baseline_key"]]
        trades = [t for t in raw if t["estado"] in ("TP", "SL", "TRAILING_SL", "BE")]
    else:
        raw = json.load(open(cfg["baseline_json"]))
        trades = [t for t in raw if t["estado"] in ("TP", "SL", "TRAILING_SL", "BE")]
    return trades


if __name__ == "__main__":
    velas_por_moneda, ts_por_moneda, closes_por_moneda = {}, {}, {}
    for moneda, cfg in m.MONEDAS.items():
        print(f"[cargar] {moneda}...")
        velas_4h, ts_4h_sorted = m.cargar_4h(cfg["symbol"], cfg["backup"], cfg["fecha_desde"])
        velas_por_moneda[moneda] = velas_4h
        ts_por_moneda[moneda] = ts_4h_sorted
        closes_por_moneda[moneda] = [velas_4h[ts]["close"] for ts in ts_4h_sorted]

    # ATR% historico completo por moneda (para comparar "vs promedio historico")
    atr_hist_por_moneda = {}
    for moneda in m.MONEDAS:
        velas_4h, ts_sorted = velas_por_moneda[moneda], ts_por_moneda[moneda]
        muestreo = range(14, len(ts_sorted), 6)  # cada 6ta vela (1/dia) para no recalcular 20k ATRs
        vals = [atr_pct_de(velas_4h, ts_sorted, i) for i in muestreo]
        vals = [v for v in vals if v is not None]
        atr_hist_por_moneda[moneda] = float(np.median(vals))
        print(f"  ATR% historico mediano {moneda}: {atr_hist_por_moneda[moneda]:.3f}%")

    reporte = {}
    n_eventos_por_ventana = {h: {} for h in VENTANAS_HORAS}

    for moneda, cfg in m.MONEDAS.items():
        print(f"\n{'='*70}\n{moneda}\n{'='*70}")
        velas_4h, ts_sorted = velas_por_moneda[moneda], ts_por_moneda[moneda]
        closes = closes_por_moneda[moneda]
        idx_map = {ts: i for i, ts in enumerate(ts_sorted)}
        trades = cargar_todos_los_trades(cfg)
        print(f"  {len(trades)} entradas reales (TP+SL+TRAILING_SL+BE)")

        clasificacion = {h: [] for h in VENTANAS_HORAS}  # lista de (trade, ganancia_max_pct)
        no_eventos_ningun_h = []

        for t in trades:
            ts_entrada = t["ts_entrada"]
            if ts_entrada not in idx_map:
                continue
            idx = idx_map[ts_entrada]
            precio_entrada = t["entrada"]  # fill real del trade, no el close recalculado del 4h reconsultado
            es_evento_alguna_ventana = False
            for h in VENTANAS_HORAS:
                n_velas = h // 4
                ventana_closes = closes[idx: idx + n_velas + 1]
                if len(ventana_closes) < 2:
                    continue
                max_close = max(ventana_closes)
                ganancia_pct = (max_close - precio_entrada) / precio_entrada * 100
                if ganancia_pct >= UMBRAL_PCT:
                    clasificacion[h].append((t, ts_entrada, idx, round(ganancia_pct, 2)))
                    es_evento_alguna_ventana = True
            if not es_evento_alguna_ventana:
                no_eventos_ningun_h.append((t, ts_entrada, idx))

        for h in VENTANAS_HORAS:
            n_eventos_por_ventana[h][moneda] = len(clasificacion[h])
            print(f"  Ventana {h}h: {len(clasificacion[h])} eventos grandes (>= {UMBRAL_PCT}%)")

        # Deep-dive solo sobre la ventana principal (48h)
        eventos_48h = clasificacion[VENTANA_PRINCIPAL]
        n_ev = len(eventos_48h)
        muestra_ref = random.sample(no_eventos_ningun_h, min(n_ev, len(no_eventos_ningun_h))) if n_ev > 0 else []

        def features_de(idx, moneda_actual):
            velas_4h_m, ts_sorted_m = velas_por_moneda[moneda_actual], ts_por_moneda[moneda_actual]
            if idx < VELAS_PREVIAS + 20:
                return None
            idxs_prev = list(range(idx - VELAS_PREVIAS, idx))
            vol_rels = [vol_rel_de(velas_4h_m, ts_sorted_m, i) for i in idxs_prev]
            cuerpos = [cuerpo_pct_de(velas_4h_m[ts_sorted_m[i]]) for i in idxs_prev]
            if any(v is None for v in vol_rels):
                return None
            x = list(range(VELAS_PREVIAS))
            slope_vol = linregress(x, vol_rels).slope
            slope_cuerpo = linregress(x, cuerpos).slope
            atr_pct_ultima = atr_pct_de(velas_4h_m, ts_sorted_m, idx - 1)
            atr_vs_hist = round(atr_pct_ultima / atr_hist_por_moneda[moneda_actual], 3) if atr_pct_ultima else None
            # movimiento simultaneo de BTC en la misma ventana previa (solo ETH/SOL)
            btc_delta_pct = None
            if moneda_actual != "BTC":
                ts_ini = ts_sorted_m[idx - VELAS_PREVIAS]
                ts_fin = ts_sorted_m[idx - 1]
                ts_btc = ts_por_moneda["BTC"]
                if ts_ini in ts_btc and ts_fin in ts_btc:
                    idx_btc_map = {ts: i for i, ts in enumerate(ts_btc)}
                    c_ini = closes_por_moneda["BTC"][idx_btc_map[ts_ini]]
                    c_fin = closes_por_moneda["BTC"][idx_btc_map[ts_fin]]
                    btc_delta_pct = round((c_fin - c_ini) / c_ini * 100, 2)
            return dict(slope_vol_rel=round(float(slope_vol), 4), slope_cuerpo_pct=round(float(slope_cuerpo), 3),
                        vol_rel_prom=round(float(np.mean(vol_rels)), 2), cuerpo_prom=round(float(np.mean(cuerpos)), 1),
                        atr_pct_ultima=round(atr_pct_ultima, 3) if atr_pct_ultima else None,
                        atr_vs_historico=atr_vs_hist, btc_delta_pct_simultaneo=btc_delta_pct)

        eventos_detalle = []
        for t, ts_entrada, idx, ganancia in eventos_48h:
            feat = features_de(idx, moneda)
            if feat:
                feat.update(ts_entrada=ts_entrada, ganancia_48h_pct=ganancia)
                eventos_detalle.append(feat)

        ref_detalle = []
        for t, ts_entrada, idx in muestra_ref:
            feat = features_de(idx, moneda)
            if feat:
                feat.update(ts_entrada=ts_entrada)
                ref_detalle.append(feat)

        print(f"\n  --- Eventos 48h con features completos: {len(eventos_detalle)} ---")
        for e in eventos_detalle:
            print(f"    {e}")
        print(f"\n  --- Referencia (n={len(ref_detalle)}) ---")
        if ref_detalle:
            for campo in ["slope_vol_rel", "slope_cuerpo_pct", "vol_rel_prom", "cuerpo_prom", "atr_vs_historico"]:
                vals = [r[campo] for r in ref_detalle if r[campo] is not None]
                if vals:
                    print(f"    {campo}: mediana={np.median(vals):.4f} rango=[{min(vals):.4f},{max(vals):.4f}]")

        reporte[moneda] = dict(n_trades_totales=len(trades), n_eventos_por_ventana={h: len(clasificacion[h]) for h in VENTANAS_HORAS},
                                eventos_48h_detalle=eventos_detalle, referencia_48h_detalle=ref_detalle)

    # Solapamiento de calendario entre monedas para la ventana principal (48h)
    fechas_por_moneda = {moneda: {e["ts_entrada"] for e in reporte[moneda]["eventos_48h_detalle"]} for moneda in m.MONEDAS}
    todas_fechas = set()
    for s in fechas_por_moneda.values():
        todas_fechas |= s
    print(f"\n>> Eventos 48h -- fechas de entrada unicas combinando las 3 monedas: {len(todas_fechas)} "
          f"(suma individual: {sum(len(s) for s in fechas_por_moneda.values())})")

    ruta = os.path.join(RAW_DIR, f"antecedentes_movimientos_grandes_{datetime.now().strftime('%Y-%m-%d')}.json")
    with open(ruta, "w") as f:
        json.dump(dict(reporte=reporte, n_eventos_por_ventana=n_eventos_por_ventana,
                        fechas_unicas_48h=len(todas_fechas), atr_hist_por_moneda=atr_hist_por_moneda), f, indent=2, default=str)
    print(f"\n[output] {ruta}")
