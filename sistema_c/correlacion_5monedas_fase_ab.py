"""
Correlacion entre monedas (moneda_operando vs moneda_contexto) -- Fase A
(entradas nuevas) y Fase B (posiciones abiertas). 5 monedas, 9 anios de
4h, comisiones reales 0.1%/lado.

=== ORIGEN DE LOS TRADES ===
config_cartera.py NO marca una fase como "activa" -- es un diccionario de
parametros para las 3 fases de cada moneda, sin flag de estado. La fase
realmente activa hoy (verificado en CLAUDE.md, leyendo dirigir() de cada
director_<moneda>.py) es: BTC ALCISTA, ETH ALCISTA, SOL LATERAL. BNB y AVAX
no tienen ninguna fase activa (director huerfano, nunca llamado por
director_orquesta.py). Para estos dos, se usa ALCISTA -- la fase que
"estaria" activa por convencion (primera entrada del diccionario,
consistente con el torneo de 15 francotiradores del 24-ago) y que ya se
genero con evaluar() literal completo en esa misma investigacion.

Los 5 trade-sets se REUSAN de corridas ya hechas hoy (mismo dia, mismo
metodo evaluar()/revisar_cierres() literal, 9 anios BTC/ETH/BNB/AVAX y 5.9
anios SOL) -- no se regenera nada:
  BTC ALCISTA  -> reports/raw/btc_fase2_variantes_2026-08-22.json[baseline]
  ETH ALCISTA  -> reports/raw/eth_fase2_variantes_2026-08-23.json[baseline]
  SOL LATERAL  -> reports/raw/sol_lateral_evaluar_literal_2020_2026_baseline_2026-08-22.json
  BNB ALCISTA  -> reports/raw/torneo_bnb_alcista_2026-08-23.json[trades]
  AVAX ALCISTA -> reports/raw/torneo_avax_alcista_2026-08-23.json[trades]

Ningun francotirador tuvo problema de dependencia de estado al correr sobre
datos viejos (los 5 sets ya estan generados y validados) -- no hay
limitacion que reportar en ese punto.

=== DEFINICION DE "TENDENCIA FUERTE" ===
Dos criterios, calculados sobre una serie diaria derivada de la propia
serie 4h (cierre de la vela "20:00", que cierra exactamente a las 00:00 UTC
del dia siguiente -- igual convencion que el resto de la sesion), SIEMPRE
anti-lookahead: para cualquier vela de 4h en el dia D, se usa el valor
diario tal como cerro el dia D-1 (nunca el dia en curso).

  Criterio 1 -- posicion vs EMA200 diaria:
    distancia_pct = (precio_actual - EMA200_diaria_asof) / EMA200_diaria_asof * 100
  Criterio 2 -- pendiente de EMA50 diaria (tasa de cambio, no posicion):
    pendiente_pct_dia = (EMA50_diaria_asof - EMA50_diaria_hace_5_dias) / EMA50_diaria_hace_5_dias / 5 * 100

Clasificacion por terciles, calibrados SOLO con datos de anios anteriores
(walk-forward real, nunca mirando el dataset completo de una vez): para
cada anio calendario Y (a partir del 2do anio de datos de esa moneda), los
umbrales de terciles se calculan una vez usando unicamente los valores de
anios < Y, y se aplican fijos durante todo el anio Y. El primer anio de
cada moneda queda sin clasificar (es el periodo de calibracion, no hay
datos previos).

  Tercil inferior (<=P33 de anios previos)  -> BAJISTA_FUERTE
  Tercil superior (>=P67 de anios previos)  -> ALCISTA_FUERTE
  Tercil medio                              -> LATERAL_DEBIL

Fase A usa "fuerte" = ALCISTA_FUERTE u BAJISTA_FUERTE (cualquier direccion)
vs LATERAL_DEBIL. Fase B usa especificamente BAJISTA_FUERTE como condicion
de "alerta" (en contra de una posicion larga).

Solo lectura. No toca config_cartera.py, francotiradores reales,
auditoria.csv. Sin commits.
"""
import sys, os, json, csv, itertools
from datetime import datetime, timezone, timedelta
sys.path.insert(0, "/home/ariel/bot-padre-v2")
import numpy as np

RAW_DIR = os.path.expanduser("~/bot-padre-v2/reports/raw")
COMISION = 0.001
MONTO_FIJO = 5.0
MONEDAS = ["BTC", "ETH", "SOL", "BNB", "AVAX"]
FASE_ACTIVA = {"BTC": "ALCISTA", "ETH": "ALCISTA", "SOL": "LATERAL", "BNB": "ALCISTA", "AVAX": "ALCISTA"}

TRADE_SOURCES = {
    "BTC": ("/home/ariel/bot-padre-v2/reports/raw/btc_fase2_variantes_2026-08-22.json", "baseline"),
    "ETH": ("/home/ariel/bot-padre-v2/reports/raw/eth_fase2_variantes_2026-08-23.json", "baseline"),
    "SOL": ("/home/ariel/bot-padre-v2/reports/raw/sol_lateral_evaluar_literal_2020_2026_baseline_2026-08-22.json", None),
    "BNB": ("/home/ariel/bot-padre-v2/reports/raw/torneo_bnb_alcista_2026-08-23.json", "trades"),
    "AVAX": ("/home/ariel/bot-padre-v2/reports/raw/torneo_avax_alcista_2026-08-23.json", "trades"),
}

FECHA_DESDE_POR_MONEDA = {
    "BTC": datetime(2017, 8, 17, tzinfo=timezone.utc), "ETH": datetime(2017, 8, 17, tzinfo=timezone.utc),
    "BNB": datetime(2017, 11, 5, tzinfo=timezone.utc), "AVAX": datetime(2020, 9, 22, tzinfo=timezone.utc),
    "SOL": datetime(2020, 8, 25, tzinfo=timezone.utc),
}
FECHA_FIN = datetime.now(timezone.utc).strftime("%Y-%m-%d 23:59:59")


def _fetch_klines_real(symbol, start_ms, end_ms, interval="4h"):
    import urllib.parse, urllib.request
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


def cargar_4h(moneda):
    symbol = f"{moneda}USDT"
    backup = os.path.expanduser(f"~/bot-padre-v3-backup/data/historico_4h/{symbol}_4h.csv")
    velas = {}
    if os.path.exists(backup):
        with open(backup) as f:
            for row in csv.DictReader(f):
                velas[row["timestamp"]] = (row["open"], row["high"], row["low"], row["close"], row["volume"])
        ultimo_ts = max(velas.keys())
        start_relleno = datetime.strptime(ultimo_ts, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    else:
        start_relleno = FECHA_DESDE_POR_MONEDA[moneda]
    end_relleno = datetime.strptime(FECHA_FIN, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    kl = _fetch_klines_real(symbol, int(start_relleno.timestamp() * 1000), int(end_relleno.timestamp() * 1000))
    for k in kl:
        ts = datetime.fromtimestamp(k[0] / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        velas[ts] = (str(k[1]), str(k[2]), str(k[3]), str(k[4]), str(k[5]))
    ts_sorted = sorted(velas.keys())
    out = {ts: dict(open=float(velas[ts][0]), high=float(velas[ts][1]), low=float(velas[ts][2]),
                     close=float(velas[ts][3]), volume=float(velas[ts][4])) for ts in ts_sorted}
    return out, ts_sorted


def calcular_ema_serie(closes, periodo):
    ema = [None] * len(closes)
    if len(closes) < periodo:
        return ema
    valor = sum(closes[:periodo]) / periodo
    ema[periodo - 1] = valor
    k = 2 / (periodo + 1)
    for i in range(periodo, len(closes)):
        valor = closes[i] * k + valor * (1 - k)
        ema[i] = valor
    return ema


def neto_pct(entrada, salida):
    return ((salida * (1 - COMISION)) / (entrada * (1 + COMISION)) - 1) * 100


def cargar_trades(moneda):
    ruta, key = TRADE_SOURCES[moneda]
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
        out.append(dict(ts_entrada=t["ts_entrada"], ts_salida=t["ts_salida"],
                         entrada=t["entrada"], salida=t["salida"],
                         gano=1 if t["estado"] in ("TP", "TRAILING_SL", "BE") else 0,
                         neto=neto_pct(t["entrada"], t["salida"])))
    out.sort(key=lambda x: x["ts_entrada"])
    return out


class SerieMoneda:
    """Serie 4h + serie diaria derivada (EMA200/EMA50 diarias, anti-lookahead) + clasificacion
    por terciles calibrados anio a anio (walk-forward), para una moneda de CONTEXTO."""

    def __init__(self, moneda):
        self.moneda = moneda
        self.velas, self.ts = cargar_4h(moneda)
        self.closes = [self.velas[t]["close"] for t in self.ts]
        self.idx_map = {t: i for i, t in enumerate(self.ts)}
        # serie diaria: velas "20:00:00" (cierran a las 00:00 UTC del dia siguiente)
        self.dias = [(t[:10], self.velas[t]["close"]) for t in self.ts if t[11:] == "20:00:00"]
        self.dias.sort(key=lambda x: x[0])
        self.fechas_dia = [d for d, _ in self.dias]
        self.closes_dia = [c for _, c in self.dias]
        self.ema200_dia = calcular_ema_serie(self.closes_dia, 200)
        self.ema50_dia = calcular_ema_serie(self.closes_dia, 50)
        self._build_series_4h()
        self._build_clasificacion()

    def _idx_dia_asof(self, fecha_yyyy_mm_dd):
        """Indice del ultimo dia CERRADO estrictamente antes de fecha_yyyy_mm_dd."""
        import bisect
        idx = bisect.bisect_left(self.fechas_dia, fecha_yyyy_mm_dd) - 1
        return idx

    def _build_series_4h(self):
        n = len(self.ts)
        self.distancia_pct = np.full(n, np.nan)
        self.pendiente_pct = np.full(n, np.nan)
        self.anio = np.array([int(t[:4]) for t in self.ts])
        for i, t in enumerate(self.ts):
            idx_d = self._idx_dia_asof(t[:10])
            if idx_d < 200 or self.ema200_dia[idx_d] is None:
                continue
            self.distancia_pct[i] = (self.closes[i] - self.ema200_dia[idx_d]) / self.ema200_dia[idx_d] * 100
            if idx_d >= 55 and self.ema50_dia[idx_d] is not None and self.ema50_dia[idx_d - 5] is not None:
                ema_now, ema_5ago = self.ema50_dia[idx_d], self.ema50_dia[idx_d - 5]
                self.pendiente_pct[i] = (ema_now - ema_5ago) / ema_5ago / 5 * 100

    def _build_clasificacion(self):
        """Terciles calibrados con anios ESTRICTAMENTE anteriores, aplicados fijos dentro de cada anio."""
        n = len(self.ts)
        self.clase_c1 = np.array([""] * n, dtype=object)  # criterio 1 (EMA200 distancia)
        self.clase_c2 = np.array([""] * n, dtype=object)  # criterio 2 (pendiente EMA50)
        anios_unicos = sorted(set(self.anio.tolist()))
        for y in anios_unicos:
            mask_prev = self.anio < y
            mask_actual = self.anio == y
            if not mask_prev.any():
                continue  # primer anio de la moneda: sin calibracion previa, queda sin clasificar
            for serie, clase in [(self.distancia_pct, self.clase_c1), (self.pendiente_pct, self.clase_c2)]:
                prev_vals = serie[mask_prev]
                prev_vals = prev_vals[~np.isnan(prev_vals)]
                if len(prev_vals) < 30:
                    continue
                p33, p67 = np.percentile(prev_vals, [33, 67])
                vals_actual = serie[mask_actual]
                idxs_actual = np.where(mask_actual)[0]
                for j, v in zip(idxs_actual, vals_actual):
                    if np.isnan(v):
                        continue
                    if v <= p33:
                        clase[j] = "BAJISTA_FUERTE"
                    elif v >= p67:
                        clase[j] = "ALCISTA_FUERTE"
                    else:
                        clase[j] = "LATERAL_DEBIL"
        # episodios (clusters) por criterio: incrementa cada vez que la clase relevante cambia
        self.episodio_c1 = self._episodios(self.clase_c1)
        self.episodio_c2 = self._episodios(self.clase_c2)

    @staticmethod
    def _episodios(clase_arr):
        ep = np.full(len(clase_arr), -1, dtype=int)
        actual = None
        contador = -1
        for i, c in enumerate(clase_arr):
            if c == "":
                continue
            if c != actual:
                contador += 1
                actual = c
            ep[i] = contador
        return ep

    def estado_en(self, ts, criterio):
        idx = self.idx_map.get(ts)
        if idx is None:
            return None, None
        clase = self.clase_c1 if criterio == 1 else self.clase_c2
        episodio = self.episodio_c1 if criterio == 1 else self.episodio_c2
        c = clase[idx]
        if c == "":
            return None, None
        return c, episodio[idx]


def bootstrap_delta_prop(exitos_a, n_a, exitos_b, n_b, n_boot=5000, seed=42, alpha=0.00125):
    rng = np.random.default_rng(seed)
    a = np.array([1] * exitos_a + [0] * (n_a - exitos_a))
    b = np.array([1] * exitos_b + [0] * (n_b - exitos_b))
    diffs = np.empty(n_boot)
    for i in range(n_boot):
        diffs[i] = rng.choice(b, size=n_b, replace=True).mean() - rng.choice(a, size=n_a, replace=True).mean()
    lo, hi = np.percentile(diffs, [alpha / 2 * 100, (1 - alpha / 2) * 100])
    return dict(media=round(float(diffs.mean()), 4), ic=[round(float(lo), 4), round(float(hi), 4)],
                significativo=bool(not (lo < 0 < hi)))


def bootstrap_delta_media(vals_a, vals_b, n_boot=5000, seed=42, alpha=0.00125):
    rng = np.random.default_rng(seed)
    a, b = np.array(vals_a), np.array(vals_b)
    diffs = np.empty(n_boot)
    for i in range(n_boot):
        diffs[i] = rng.choice(b, size=len(b), replace=True).mean() - rng.choice(a, size=len(a), replace=True).mean()
    lo, hi = np.percentile(diffs, [alpha / 2 * 100, (1 - alpha / 2) * 100])
    return dict(media=round(float(diffs.mean()), 4), ic=[round(float(lo), 4), round(float(hi), 4)],
                significativo=bool(not (lo < 0 < hi)))


if __name__ == "__main__":
    print("[cargar] series de contexto (4h + diaria + clasificacion por terciles)...")
    series = {}
    for m in MONEDAS:
        print(f"  {m}...")
        series[m] = SerieMoneda(m)

    print("[cargar] trade sets (reusados de corridas de hoy)...")
    trades = {}
    for m in MONEDAS:
        trades[m] = cargar_trades(m)
        print(f"  {m} ({FASE_ACTIVA[m]}): {len(trades[m])} trades")

    N_COMPARACIONES = 40
    ALPHA = min(0.01, 0.05 / N_COMPARACIONES)
    print(f"\n[config] alpha corregido (Bonferroni/40, min con 0.01) = {ALPHA}")

    # =========================== FASE A ===========================
    resultados_A = {}
    for m_op in MONEDAS:
        for m_ctx in MONEDAS:
            if m_op == m_ctx:
                continue
            for criterio in (1, 2):
                clave = f"{m_op}_vs_{m_ctx}_c{criterio}"
                grupo_fuerte, grupo_debil = [], []
                episodios_fuerte, episodios_debil = set(), set()
                for tr in trades[m_op]:
                    clase, ep = series[m_ctx].estado_en(tr["ts_entrada"], criterio)
                    if clase is None:
                        continue
                    if clase == "LATERAL_DEBIL":
                        grupo_debil.append(tr["gano"])
                        episodios_debil.add(ep)
                    else:
                        grupo_fuerte.append(tr["gano"])
                        episodios_fuerte.add(ep)
                n_f, n_d = len(grupo_fuerte), len(grupo_debil)
                if n_f == 0 or n_d == 0:
                    continue
                wr_f = round(sum(grupo_fuerte) / n_f * 100, 1)
                wr_d = round(sum(grupo_debil) / n_d * 100, 1)
                resultados_A[clave] = dict(m_op=m_op, m_ctx=m_ctx, criterio=criterio,
                                            n_fuerte=n_f, n_debil=n_d, wr_fuerte=wr_f, wr_debil=wr_d,
                                            n_clusters_fuerte=len(episodios_fuerte), n_clusters_debil=len(episodios_debil),
                                            delta_wr=round(wr_f - wr_d, 1))
    print(f"\n[Fase A] {len(resultados_A)} combinaciones con datos (de 40 posibles)")

    # A1: filtro rapido
    A1_sobreviven = {k: v for k, v in resultados_A.items()
                      if v["n_fuerte"] >= 30 and v["n_debil"] >= 30 and abs(v["delta_wr"]) >= 5.0}
    print(f"[Fase A1] sobreviven al filtro (n>=30 ambos grupos, |delta WR|>=5pp): {len(A1_sobreviven)}")
    for k, v in sorted(A1_sobreviven.items(), key=lambda x: -abs(x[1]["delta_wr"])):
        print(f"   {k}: n_fuerte={v['n_fuerte']} n_debil={v['n_debil']} WR_fuerte={v['wr_fuerte']}% "
              f"WR_debil={v['wr_debil']}% delta={v['delta_wr']}pp clusters={v['n_clusters_fuerte']}/{v['n_clusters_debil']}")

    # A2: validacion de los sobrevivientes -- bootstrap + walk-forward anual
    A2_resultados = {}
    for clave, v in A1_sobreviven.items():
        m_op, m_ctx, criterio = v["m_op"], v["m_ctx"], v["criterio"]
        exitos_f = int(round(v["wr_fuerte"] / 100 * v["n_fuerte"]))
        exitos_d = int(round(v["wr_debil"] / 100 * v["n_debil"]))
        boot = bootstrap_delta_prop(exitos_d, v["n_debil"], exitos_f, v["n_fuerte"], alpha=ALPHA)
        # consistencia anio a anio
        por_anio = {}
        for tr in trades[m_op]:
            clase, ep = series[m_ctx].estado_en(tr["ts_entrada"], criterio)
            if clase is None:
                continue
            anio = int(tr["ts_entrada"][:4])
            grupo = "debil" if clase == "LATERAL_DEBIL" else "fuerte"
            por_anio.setdefault(anio, {"fuerte": [], "debil": []})[grupo].append(tr["gano"])
        consistencia = []
        for anio in sorted(por_anio):
            f, d = por_anio[anio]["fuerte"], por_anio[anio]["debil"]
            if len(f) >= 3 and len(d) >= 3:
                wrf = sum(f) / len(f) * 100
                wrd = sum(d) / len(d) * 100
                consistencia.append(dict(anio=anio, n_fuerte=len(f), n_debil=len(d),
                                          delta=round(wrf - wrd, 1), misma_direccion=bool((wrf - wrd) * v["delta_wr"] > 0)))
        n_anios_misma_dir = sum(1 for c in consistencia if c["misma_direccion"])
        A2_resultados[clave] = dict(**v, bootstrap=boot, consistencia_anual=consistencia,
                                     anios_evaluables=len(consistencia), anios_misma_direccion=n_anios_misma_dir)
        print(f"[A2] {clave}: bootstrap_delta={boot['media']} IC={boot['ic']} sig={boot['significativo']} "
              f"| {n_anios_misma_dir}/{len(consistencia)} anios misma direccion")

    # =========================== FASE B ===========================
    print("\n[Fase B] evaluando posiciones abiertas, vela a vela...")
    resultados_B = {}
    for m_op in MONEDAS:
        serie_op = series[m_op]
        for m_ctx in MONEDAS:
            if m_op == m_ctx:
                continue
            serie_ctx = series[m_ctx]
            for criterio in (1, 2):
                con_alerta, sin_alerta, excluidos_ventana = [], [], 0
                for tr in trades[m_op]:
                    idx_e = serie_op.idx_map.get(tr["ts_entrada"])
                    idx_s = serie_op.idx_map.get(tr["ts_salida"])
                    if idx_e is None or idx_s is None or idx_s <= idx_e:
                        continue
                    velas_vida = serie_op.ts[idx_e:idx_s + 1]
                    idx_alerta_local = None
                    for j, ts_v in enumerate(velas_vida):
                        clase, _ = serie_ctx.estado_en(ts_v, criterio)
                        if clase == "BAJISTA_FUERTE":
                            idx_alerta_local = j
                            break
                    if idx_alerta_local is None:
                        # SIN alerta -- grupo control: WR y PnL/vela del trade completo
                        n_velas_total = idx_s - idx_e
                        if n_velas_total < 1:
                            continue
                        sin_alerta.append(dict(gano=tr["gano"], neto=tr["neto"],
                                                pnl_vela=tr["neto"] / n_velas_total))
                        continue
                    velas_antes = idx_alerta_local
                    velas_despues = len(velas_vida) - 1 - idx_alerta_local
                    if velas_antes < 3 or velas_despues < 3:
                        excluidos_ventana += 1
                        continue
                    precio_alerta = serie_op.closes[idx_e + idx_alerta_local]
                    precio_entrada = tr["entrada"]
                    precio_salida = tr["salida"]
                    pct_antes = (precio_alerta - precio_entrada) / precio_entrada * 100
                    pct_despues_bruto = (precio_salida - precio_alerta) / precio_alerta * 100
                    con_alerta.append(dict(
                        ts_entrada=tr["ts_entrada"], velas_antes=velas_antes, velas_despues=velas_despues,
                        pnl_vela_antes=pct_antes / velas_antes, pnl_vela_despues=pct_despues_bruto / velas_despues,
                        episodio=serie_ctx.estado_en(velas_vida[idx_alerta_local], criterio)[1]))
                clave = f"{m_op}_vs_{m_ctx}_c{criterio}"
                resultados_B[clave] = dict(m_op=m_op, m_ctx=m_ctx, criterio=criterio,
                                            n_con_alerta=len(con_alerta), n_sin_alerta=len(sin_alerta),
                                            excluidos_ventana=excluidos_ventana,
                                            con_alerta=con_alerta, sin_alerta=sin_alerta)
    print(f"[Fase B] {len(resultados_B)} combinaciones calculadas")

    # Diagnostico completo de las 40 combinaciones (para reportar por que sobreviven o no)
    B_diagnostico = {}
    for k, v in resultados_B.items():
        antes = [c["pnl_vela_antes"] for c in v["con_alerta"]]
        despues = [c["pnl_vela_despues"] for c in v["con_alerta"]]
        delta_simple = round(float(np.mean(despues) - np.mean(antes)), 4) if antes else None
        B_diagnostico[k] = dict(m_op=v["m_op"], m_ctx=v["m_ctx"], criterio=v["criterio"],
                                 n_con_alerta=v["n_con_alerta"], n_sin_alerta=v["n_sin_alerta"],
                                 excluidos_ventana=v["excluidos_ventana"], delta_simple=delta_simple)

    # B1: filtro rapido
    B1_sobreviven = {}
    for k, v in resultados_B.items():
        if v["n_con_alerta"] < 30:
            continue
        antes = [c["pnl_vela_antes"] for c in v["con_alerta"]]
        despues = [c["pnl_vela_despues"] for c in v["con_alerta"]]
        delta_simple = round(float(np.mean(despues) - np.mean(antes)), 4)
        if abs(delta_simple) < 0.05:  # filtro rapido: diferencia visible minima 0.05pp/vela
            continue
        B1_sobreviven[k] = dict(**v, delta_simple=delta_simple)
    print(f"[Fase B1] sobreviven al filtro (n_con_alerta>=30, diferencia visible): {len(B1_sobreviven)}")
    for k, v in sorted(B1_sobreviven.items(), key=lambda x: -abs(x[1]["delta_simple"])):
        print(f"   {k}: n_con_alerta={v['n_con_alerta']} n_sin_alerta={v['n_sin_alerta']} "
              f"excluidos_ventana={v['excluidos_ventana']} delta_pnl_vela={v['delta_simple']}pp")

    # B2: validacion
    B2_resultados = {}
    for k, v in B1_sobreviven.items():
        antes = [c["pnl_vela_antes"] for c in v["con_alerta"]]
        despues = [c["pnl_vela_despues"] for c in v["con_alerta"]]
        boot_antes_despues = bootstrap_delta_media(antes, despues, alpha=ALPHA)
        pnl_vela_sin_alerta = [c["pnl_vela"] for c in v["sin_alerta"]] if v["sin_alerta"] else []
        boot_vs_control = bootstrap_delta_media(pnl_vela_sin_alerta, despues, alpha=ALPHA) if len(pnl_vela_sin_alerta) >= 5 else None
        episodios_unicos = len(set(c["episodio"] for c in v["con_alerta"]))
        por_anio = {}
        for c in v["con_alerta"]:
            anio = int(c["ts_entrada"][:4])
            por_anio.setdefault(anio, []).append(c["pnl_vela_despues"] - c["pnl_vela_antes"])
        consistencia = []
        for anio in sorted(por_anio):
            deltas = por_anio[anio]
            if len(deltas) >= 3:
                consistencia.append(dict(anio=anio, n=len(deltas), delta_medio=round(float(np.mean(deltas)), 4),
                                          misma_direccion=bool(np.mean(deltas) * v["delta_simple"] > 0)))
        n_misma_dir = sum(1 for c in consistencia if c["misma_direccion"])
        B2_resultados[k] = dict(**v, bootstrap_antes_despues=boot_antes_despues, bootstrap_vs_control=boot_vs_control,
                                 n_clusters=episodios_unicos, consistencia_anual=consistencia,
                                 anios_evaluables=len(consistencia), anios_misma_direccion=n_misma_dir)
        print(f"[B2] {k}: antes_vs_despues delta={boot_antes_despues['media']} IC={boot_antes_despues['ic']} "
              f"sig={boot_antes_despues['significativo']} | clusters={episodios_unicos} | "
              f"{n_misma_dir}/{len(consistencia)} anios misma direccion")

    out = dict(alpha=ALPHA, fase_A_todas=resultados_A, fase_A1=list(A1_sobreviven.keys()), fase_A2=A2_resultados,
               fase_B_diagnostico=B_diagnostico, fase_B1=list(B1_sobreviven.keys()), fase_B2=B2_resultados)
    ruta = os.path.join(RAW_DIR, f"correlacion_5monedas_fase_ab_{datetime.now().strftime('%Y-%m-%d')}.json")
    with open(ruta, "w") as f:
        json.dump(out, f, indent=2, default=str)
    print(f"\n[output] {ruta}")
