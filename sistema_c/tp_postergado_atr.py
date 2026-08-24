"""
TP postergado con detector de "vela fuerte" + trailing dinamico k x ATR(14)
(arista nueva, distinta al trailing de % fijo ya descartado en
reports/2026-08-20_backtest-tp-postergado-detector-fuerza.md,
reports/2026-08-20_backtest-tp-postergado-detector-fuerza-1h.md,
reports/2026-08-20_backtest-tp-postergado-anchos-trailing.md).

Detector de vela fuerte (SIN CAMBIOS respecto a esas investigaciones):
  cuerpo_pct       = |close-open| / (high-low) * 100
  volumen_relativo = volume / promedio(volume de las 20 velas anteriores)
  "vela fuerte" si volumen_relativo >= umbral_x AND cuerpo_pct >= umbral_pct
  Umbrales por moneda (sin tocar): BTC 1.2x/55%, ETH 1.5x/60%, SOL 1.8x/65%

Mecanismo de postergacion (misma arquitectura "con siembra" ya validada,
solo cambia la distancia del trailing):
  - Semilla del maximo: el HIGH real de la propia vela de 4h que disparo el TP.
  - ATR(14) calculado en esa misma vela (formula identica a
    filtro_calidad.calcular_atr: TR = max(h-l, |h-c_prev|, |l-c_prev|),
    promedio simple de los ultimos 14 TR), en UNIDADES DE PRECIO -- se
    calcula UNA VEZ por trade, al momento de la vela fuerte (no se
    recalcula vela a vela durante la postergacion).
  - piso = max(precio_TP_original, maximo_visto - k*ATR)  [floor en el TP
    original, misma convencion que la version de % fijo -- nunca puede,
    en teoria continua, cerrar peor que el TP]
  - Evaluacion con velas de 1h (low/high), no cierre de 4h: en cada vela de
    1h posterior al cierre de la vela de 4h que disparo el TP, si
    low_1h <= piso -> cierra ahi. Si no, maximo_visto = max(maximo_visto,
    high_1h) y el piso sube (nunca baja).
  - k a probar: 1.0, 1.5, 2.0, 2.5.

Baseline (trades TP reales) se REUSA de corridas ya hechas en esta sesion,
sin re-ejecutar evaluar()/revisar_cierres() (ya validado, mismo baseline que
Fase 2 usa para BTC/ETH; SOL LATERAL 2020-2026 ya corrido en investigacion
previa):
  - BTC: reports/raw/btc_fase2_variantes_2026-08-22.json -> "baseline"
  - ETH: reports/raw/eth_fase2_variantes_2026-08-23.json -> "baseline"
  - SOL: reports/raw/sol_lateral_evaluar_literal_2020_2026_baseline_2026-08-22.json

Solo lectura. No toca config_cartera.py, francotiradores reales,
auditoria.csv. Sin commits. Sin activar nada.
"""
import sys, os, json, csv
import urllib.parse, urllib.request
from datetime import datetime, timezone, timedelta
sys.path.insert(0, "/home/ariel/bot-padre-v2")
import numpy as np

RAW_DIR = os.path.expanduser("~/bot-padre-v2/reports/raw")
K_VALUES = [1.0, 1.5, 2.0, 2.5]

MONEDAS = {
    "BTC": dict(symbol="BTCUSDT", backup=os.path.expanduser("~/bot-padre-v3-backup/data/historico_4h/BTCUSDT_4h.csv"),
                fecha_desde=datetime(2017, 8, 17, tzinfo=timezone.utc),
                baseline_json="/home/ariel/bot-padre-v2/reports/raw/btc_fase2_variantes_2026-08-22.json",
                baseline_key="baseline", umbral_x=1.2, umbral_pct=55.0),
    "ETH": dict(symbol="ETHUSDT", backup=os.path.expanduser("~/bot-padre-v3-backup/data/historico_4h/ETHUSDT_4h.csv"),
                fecha_desde=datetime(2017, 8, 17, tzinfo=timezone.utc),
                baseline_json="/home/ariel/bot-padre-v2/reports/raw/eth_fase2_variantes_2026-08-23.json",
                baseline_key="baseline", umbral_x=1.5, umbral_pct=60.0),
    "SOL": dict(symbol="SOLUSDT", backup=os.path.expanduser("~/bot-padre-v3-backup/data/historico_4h/SOLUSDT_4h.csv"),
                fecha_desde=datetime(2020, 8, 25, tzinfo=timezone.utc),
                baseline_json="/home/ariel/bot-padre-v2/reports/raw/sol_lateral_evaluar_literal_2020_2026_baseline_2026-08-22.json",
                baseline_key=None, umbral_x=1.8, umbral_pct=65.0),
}

FECHA_FIN = datetime.now(timezone.utc).strftime("%Y-%m-%d 23:59:59")
COMISION = 0.001


def _fetch_klines_real(symbol, start_ms, end_ms, interval):
    out, cur = [], start_ms
    while cur < end_ms:
        params = urllib.parse.urlencode({"symbol": symbol, "interval": interval,
                                          "startTime": cur, "endTime": end_ms, "limit": 1000})
        url = f"https://api.binance.com/api/v3/klines?{params}"
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        if not data:
            break
        out.extend(data)
        cur = data[-1][0] + 1
        if len(data) < 1000:
            break
    return out


def cargar_4h(symbol, backup_csv, fecha_desde):
    velas = {}
    if os.path.exists(backup_csv):
        with open(backup_csv) as f:
            for row in csv.DictReader(f):
                velas[row["timestamp"]] = (row["open"], row["high"], row["low"], row["close"], row["volume"])
        ultimo_ts = max(velas.keys())
        start_relleno = datetime.strptime(ultimo_ts, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    else:
        start_relleno = fecha_desde
    end_relleno = datetime.strptime(FECHA_FIN, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    kl = _fetch_klines_real(symbol, int(start_relleno.timestamp() * 1000), int(end_relleno.timestamp() * 1000), "4h")
    for k in kl:
        ts = datetime.fromtimestamp(k[0] / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        velas[ts] = (str(k[1]), str(k[2]), str(k[3]), str(k[4]), str(k[5]))
    ts_sorted = sorted(velas.keys())
    out = {ts: dict(open=float(velas[ts][0]), high=float(velas[ts][1]), low=float(velas[ts][2]),
                     close=float(velas[ts][3]), volume=float(velas[ts][4])) for ts in ts_sorted}
    return out, ts_sorted


def cargar_1h(symbol, fecha_desde):
    print(f"  [1h] Descargando {symbol} 1h desde {fecha_desde}...")
    end_relleno = datetime.strptime(FECHA_FIN, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    kl = _fetch_klines_real(symbol, int(fecha_desde.timestamp() * 1000), int(end_relleno.timestamp() * 1000), "1h")
    velas = {}
    for k in kl:
        ts = datetime.fromtimestamp(k[0] / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        velas[ts] = dict(open=float(k[1]), high=float(k[2]), low=float(k[3]), close=float(k[4]), volume=float(k[5]))
    ts_sorted = sorted(velas.keys())
    print(f"  [1h] {symbol}: {len(ts_sorted)} velas de 1h, {ts_sorted[0]} -> {ts_sorted[-1]}")
    return velas, ts_sorted


def calcular_atr14(velas_4h, ts_sorted, idx):
    """Identico a filtro_calidad.calcular_atr: TR = max(h-l, |h-c_prev|, |l-c_prev|), promedio de 14."""
    if idx < 14:
        return None
    trs = []
    for i in range(idx - 13, idx + 1):
        v = velas_4h[ts_sorted[i]]
        c_prev = velas_4h[ts_sorted[i - 1]]["close"]
        tr = max(v["high"] - v["low"], abs(v["high"] - c_prev), abs(v["low"] - c_prev))
        trs.append(tr)
    return sum(trs) / 14


def clasificar_vela_fuerte(velas_4h, ts_sorted, idx, umbral_x, umbral_pct):
    v = velas_4h[ts_sorted[idx]]
    rango = v["high"] - v["low"]
    cuerpo_pct = abs(v["close"] - v["open"]) / rango * 100 if rango > 0 else 0.0
    if idx < 20:
        return False, cuerpo_pct, None
    vols_prev = [velas_4h[ts_sorted[i]]["volume"] for i in range(idx - 20, idx)]
    vol_promedio = sum(vols_prev) / 20
    volumen_relativo = v["volume"] / vol_promedio if vol_promedio > 0 else 0.0
    es_fuerte = volumen_relativo >= umbral_x and cuerpo_pct >= umbral_pct
    return es_fuerte, cuerpo_pct, volumen_relativo


def neto_pct(entrada, salida):
    return ((salida * (1 - COMISION)) / (entrada * (1 + COMISION)) - 1) * 100


def simular_postergacion(velas_1h, ts_1h_sorted, ts_salida_4h, precio_tp, maximo_semilla, atr_valor, k):
    """Camina 1h a partir de ts_salida_4h (close de la vela 4h que disparo el TP). Retorna
    (precio_cierre, ts_cierre, velas_1h_recorridas) o (None, None, None) si nunca cierra (abierta)."""
    piso_distancia = k * atr_valor
    maximo_visto = maximo_semilla
    piso = max(precio_tp, maximo_visto - piso_distancia)

    import bisect
    idx_1h = bisect.bisect_left(ts_1h_sorted, ts_salida_4h)
    n = len(ts_1h_sorted)
    velas_recorridas = 0
    while idx_1h < n:
        ts = ts_1h_sorted[idx_1h]
        v = velas_1h[ts]
        if v["low"] <= piso:
            return piso, ts, velas_recorridas
        maximo_visto = max(maximo_visto, v["high"])
        piso = max(precio_tp, maximo_visto - piso_distancia)
        idx_1h += 1
        velas_recorridas += 1
    return None, None, velas_recorridas


def bootstrap_media(deltas, n_boot=10000, seed=42):
    rng = np.random.default_rng(seed)
    d = np.array(deltas)
    n = len(d)
    boot = np.empty(n_boot)
    for i in range(n_boot):
        boot[i] = rng.choice(d, size=n, replace=True).mean()
    lo, hi = np.percentile(boot, [2.5, 97.5])
    return dict(media=round(float(d.mean()), 4), mediana=round(float(np.median(d)), 4),
                ic95=[round(float(lo), 4), round(float(hi), 4)], cruza_cero=bool(lo < 0 < hi))


if __name__ == "__main__":
    resultados = {}
    for moneda, cfg in MONEDAS.items():
        print(f"\n{'='*70}\n{moneda}\n{'='*70}")
        velas_4h, ts_4h_sorted = cargar_4h(cfg["symbol"], cfg["backup"], cfg["fecha_desde"])
        print(f"  [4h] {len(ts_4h_sorted)} velas, {ts_4h_sorted[0]} -> {ts_4h_sorted[-1]}")
        velas_1h, ts_1h_sorted = cargar_1h(cfg["symbol"], cfg["fecha_desde"])

        # Cargar trades TP del baseline
        if cfg["baseline_key"]:
            raw = json.load(open(cfg["baseline_json"]))[cfg["baseline_key"]]
            tps_raw = [t for t in raw if t["estado"] == "TP"]
        else:
            raw = json.load(open(cfg["baseline_json"]))
            tps_raw = []
            for t in raw:
                if t["estado"] != "TP":
                    continue
                dt_entrada = datetime.strptime(t["ts_entrada"], "%Y-%m-%d %H:%M:%S")
                dt_salida = dt_entrada + timedelta(hours=4 * int(t["velas"]))
                t2 = dict(t)
                t2["ts_salida"] = dt_salida.strftime("%Y-%m-%d %H:%M:%S")
                tps_raw.append(t2)
        print(f"  [TP] {len(tps_raw)} trades TP en el baseline")

        idx_4h_map = {ts: i for i, ts in enumerate(ts_4h_sorted)}
        afectados = []
        no_clasificables = 0
        for t in tps_raw:
            ts_salida = t["ts_salida"]
            if ts_salida not in idx_4h_map:
                no_clasificables += 1
                continue
            idx = idx_4h_map[ts_salida]
            es_fuerte, cuerpo_pct, vol_rel = clasificar_vela_fuerte(velas_4h, ts_4h_sorted, idx, cfg["umbral_x"], cfg["umbral_pct"])
            if not es_fuerte:
                continue
            atr_valor = calcular_atr14(velas_4h, ts_4h_sorted, idx)
            if atr_valor is None:
                continue
            precio_tp = t["salida"]
            precio_entrada = t["entrada"]
            maximo_semilla = velas_4h[ts_salida]["high"]
            afectados.append(dict(ts_entrada=t["ts_entrada"], ts_salida=ts_salida, precio_entrada=precio_entrada,
                                   precio_tp=precio_tp, maximo_semilla=maximo_semilla, atr_valor=atr_valor,
                                   cuerpo_pct=round(cuerpo_pct, 2), vol_rel=round(vol_rel, 3) if vol_rel else None))
        print(f"  [DETECTOR] {len(afectados)}/{len(tps_raw)} TP clasifican como vela fuerte "
              f"({no_clasificables} sin vela 4h correspondiente, excluidos)")

        neto_actual_por_trade = {a["ts_entrada"]: neto_pct(a["precio_entrada"], a["precio_tp"]) for a in afectados}
        pnl_total_actual_afectados = sum(neto_actual_por_trade.values())

        resultados[moneda] = dict(n_tp_total=len(tps_raw), n_afectados=len(afectados), por_k={})

        for k in K_VALUES:
            deltas, resultados_trade, flips = [], [], 0
            for a in afectados:
                precio_cierre, ts_cierre, velas_recorridas = simular_postergacion(
                    velas_1h, ts_1h_sorted, a["ts_salida"], a["precio_tp"], a["maximo_semilla"], a["atr_valor"], k)
                if precio_cierre is None:
                    continue  # sigue abierta al final de la serie, excluida (misma convencion de siempre)
                neto_nuevo = neto_pct(a["precio_entrada"], precio_cierre)
                neto_orig = neto_actual_por_trade[a["ts_entrada"]]
                delta = neto_nuevo - neto_orig
                deltas.append(delta)
                if neto_orig > 0 and neto_nuevo <= 0:
                    flips += 1
                resultados_trade.append(dict(ts_entrada=a["ts_entrada"], neto_original=round(neto_orig, 4),
                                              neto_nuevo=round(neto_nuevo, 4), delta=round(delta, 4),
                                              velas_1h=velas_recorridas))

            n_ev = len(deltas)
            pos = sum(1 for d in deltas if d > 1e-9)
            neg = sum(1 for d in deltas if d < -1e-9)
            cero = n_ev - pos - neg
            boot = bootstrap_media(deltas) if n_ev >= 5 else None
            pnl_actual = sum(resultados_trade[i]["neto_original"] for i in range(n_ev))
            pnl_nuevo = sum(resultados_trade[i]["neto_nuevo"] for i in range(n_ev))
            top5 = sorted(resultados_trade, key=lambda x: -x["delta"])[:5]

            print(f"\n  --- k={k} ---")
            print(f"  n evaluado={n_ev} (de {len(afectados)} afectados, resto sigue abierto)")
            print(f"  delta>0={pos} delta<0={neg} delta==0={cero} flips_ganador_perdedor={flips}")
            if boot:
                print(f"  media={boot['media']}pp mediana={boot['mediana']}pp IC95%={boot['ic95']} cruza_cero={boot['cruza_cero']}")
            print(f"  PnL total actual(afectados evaluados)={round(pnl_actual,2)}pp -> con mecanismo={round(pnl_nuevo,2)}pp (delta {round(pnl_nuevo-pnl_actual,2)}pp)")
            print(f"  top5 mejores deltas: {[round(t['delta'],2) for t in top5]}")

            resultados[moneda]["por_k"][str(k)] = dict(
                n_evaluado=n_ev, delta_pos=pos, delta_neg=neg, delta_cero=cero, flips=flips,
                bootstrap=boot, pnl_actual=round(pnl_actual, 3), pnl_nuevo=round(pnl_nuevo, 3),
                pnl_delta=round(pnl_nuevo - pnl_actual, 3), trades=resultados_trade)

        fecha = datetime.now().strftime("%Y-%m-%d")
        os.makedirs(RAW_DIR, exist_ok=True)

    ruta = os.path.join(RAW_DIR, f"tp_postergado_atr_{datetime.now().strftime('%Y-%m-%d')}.json")
    with open(ruta, "w") as f:
        json.dump(resultados, f, indent=2, default=str)
    print(f"\n[output] {ruta}")
