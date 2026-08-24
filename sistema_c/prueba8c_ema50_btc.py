"""
Item 7 de Fase 2-B Parte 2: recalculo de la Prueba 8C (gate EMA50-BASE20)
para BTC, con el SL correcto (3.5%, no el 5.0% de config_cartera.py usado
por error en la corrida original de chat sin Code -- ver
~/hallazgo_gate_ema50_ba20.md y ~/CONTEXTO_SESIONES_CLAUDE_SIN_CODE.md
seccion 4). ETH ya tiene el numero correcto de esa investigacion original
(SL 4.5%/TP 5.0%, ya uso los parametros reales) -- no se recalcula, se
reusa el numero ya documentado.

Metodologia (replica lo ya documentado de Prueba 8C, no es un candidato
nuevo -- estrategia de ruptura, NO usa la entrada RSI/EMA real del
francotirador ni los otros 11 gates de produccion):
- Evento base: ruptura del maximo de cierre de las 20 velas previas
  (close[i] > max(close[i-20:i])). Definicion de cierre elegida por no
  tener acceso al script original (hecho en chat sin Code) -- documentado
  aqui como supuesto explicito.
- Gate EMA50-BASE20: PASA si EMA50(cierre) en la vela de ruptura > EMA50
  en la vela anterior.
- Se simulan TODOS los eventos de ruptura (grupo "sin gate") y por separado
  solo los que PASAN el gate (grupo "con gate"), con SL 3.5% / TP 6.0%
  (valores reales BTC ALCISTA, hardcodeados en francotirador_alcista_btc.py,
  confirmado en config_cartera.py-codigo-muerto), comision 0.1%/lado,
  entrada a precio de cierre de la vela de ruptura, sin retardo.
- Salida: se camina vela a vela desde la entrada revisando high/low contra
  TP/SL: si ambos se tocan en la misma vela se asume SL primero (supuesto
  conservador, igual criterio que el proyecto usa en otras simulaciones de
  esta sesion cuando no hay informacion intra-vela mas fina).
- Bootstrap no pareado (5000 resamples, IC95%) comparando "sin gate" vs
  "con gate" en WR/PF/expectativa neta -- mismo formato que Prueba 8B/8C
  original.
- Ventana: 9 anios completos (2017-09 -> hoy), NO solo 2026 como en la
  investigacion original -- muestra mucho mayor.

Solo lectura. No toca config_cartera.py, francotiradores reales,
auditoria.csv. Sin commits. Sin activar nada.
"""
import sys, os, csv, json
import urllib.parse, urllib.request
from datetime import datetime, timezone, timedelta
sys.path.insert(0, "/home/ariel/bot-padre-v2")
import numpy as np

SYMBOL = "BTCUSDT"
BACKUP_CSV = os.path.expanduser(f"~/bot-padre-v3-backup/data/historico_4h/{SYMBOL}_4h.csv")
FECHA_DESDE_FALLBACK = datetime(2017, 8, 17, tzinfo=timezone.utc)
FECHA_FIN = datetime.now(timezone.utc).strftime("%Y-%m-%d 23:59:59")
SL_PCT, TP_PCT = 3.5, 6.0
COMISION = 0.001
BASE = 20
RAW_DIR = os.path.expanduser("~/bot-padre-v2/reports/raw")


def _fetch_klines_real(symbol, start_ms, end_ms, interval="4h"):
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


def cargar_serie():
    velas = {}
    if os.path.exists(BACKUP_CSV):
        with open(BACKUP_CSV) as f:
            for row in csv.DictReader(f):
                velas[row["timestamp"]] = (row["open"], row["high"], row["low"], row["close"], row["volume"])
        ultimo_ts = max(velas.keys())
        start_relleno = datetime.strptime(ultimo_ts, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    else:
        start_relleno = FECHA_DESDE_FALLBACK
    end_relleno = datetime.strptime(FECHA_FIN, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    kl = _fetch_klines_real(SYMBOL, int(start_relleno.timestamp() * 1000), int(end_relleno.timestamp() * 1000))
    for k in kl:
        ts = datetime.fromtimestamp(k[0] / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        velas[ts] = (str(k[1]), str(k[2]), str(k[3]), str(k[4]), str(k[5]))
    ts_sorted = sorted(velas.keys())
    return [(ts, float(velas[ts][0]), float(velas[ts][1]), float(velas[ts][2]),
             float(velas[ts][3]), float(velas[ts][4])) for ts in ts_sorted]


def calcular_ema_serie(closes, periodo):
    """EMA vectorizada -- retorna lista alineada con closes (None donde no hay suficiente historia)."""
    ema = [None] * len(closes)
    if len(closes) < periodo:
        return ema
    k = 2 / (periodo + 1)
    valor = sum(closes[:periodo]) / periodo
    ema[periodo - 1] = valor
    for i in range(periodo, len(closes)):
        valor = closes[i] * k + valor * (1 - k)
        ema[i] = valor
    return ema


def simular_trade(serie, idx_entrada, precio_entrada):
    sl_precio = precio_entrada * (1 - SL_PCT / 100)
    tp_precio = precio_entrada * (1 + TP_PCT / 100)
    for j in range(idx_entrada + 1, len(serie)):
        _, o, h, l, c, v = serie[j]
        toco_sl = l <= sl_precio
        toco_tp = h >= tp_precio
        if toco_sl and toco_tp:
            return "SL", sl_precio, j  # supuesto conservador: SL primero si ambos en la misma vela
        if toco_sl:
            return "SL", sl_precio, j
        if toco_tp:
            return "TP", tp_precio, j
    return None, None, None  # sigue abierta al final de la serie


def neto_pct(entrada, salida):
    return ((salida * (1 - COMISION)) / (entrada * (1 + COMISION)) - 1) * 100


def metricas(netos):
    n = len(netos)
    if n == 0:
        return dict(n=0)
    arr = np.array(netos)
    wr = round(float((arr > 0).mean() * 100), 1)
    ganadores = arr[arr > 0].sum()
    perdedores = -arr[arr <= 0].sum()
    pf = round(float(ganadores / perdedores), 3) if perdedores > 0 else (999.0 if ganadores > 0 else 0)
    return dict(n=n, wr=wr, pf=pf, exp_media=round(float(arr.mean()), 4), exp_mediana=round(float(np.median(arr)), 4))


def bootstrap_no_pareado(netos_a, netos_b, n_boot=5000, seed=42):
    rng = np.random.default_rng(seed)
    a, b = np.array(netos_a), np.array(netos_b)
    diffs = np.empty(n_boot)
    for k in range(n_boot):
        sa = rng.choice(a, size=len(a), replace=True)
        sb = rng.choice(b, size=len(b), replace=True)
        diffs[k] = sb.mean() - sa.mean()
    lo95, hi95 = np.percentile(diffs, [2.5, 97.5])
    return dict(media=round(float(diffs.mean()), 4), ic95=[round(float(lo95), 4), round(float(hi95), 4)],
                significativo_p05=not (lo95 < 0 < hi95))


if __name__ == "__main__":
    print("[datos] Descargando/completando serie BTCUSDT 9 años...")
    serie = cargar_serie()
    closes = [v[4] for v in serie]
    print(f"[datos] {len(serie)} velas: {serie[0][0]} -> {serie[-1][0]}")

    ema50 = calcular_ema_serie(closes, 50)

    eventos = []  # (idx, pasa_gate)
    for i in range(BASE, len(closes)):
        if closes[i] > max(closes[i - BASE:i]):
            pasa = ema50[i] is not None and ema50[i - 1] is not None and ema50[i] > ema50[i - 1]
            eventos.append((i, pasa))
    print(f"[eventos] {len(eventos)} rupturas de {BASE} velas detectadas | PASAN gate: {sum(1 for _, p in eventos if p)}")

    resultados_sin_gate, resultados_con_gate = [], []
    detalle = []
    for idx, pasa in eventos:
        precio_entrada = closes[idx]
        estado, precio_salida, idx_salida = simular_trade(serie, idx, precio_entrada)
        if estado is None:
            continue  # posicion sigue abierta al final de la serie, se excluye del cierre resuelto
        neto = neto_pct(precio_entrada, precio_salida)
        resultados_sin_gate.append(neto)
        if pasa:
            resultados_con_gate.append(neto)
        detalle.append(dict(ts_entrada=serie[idx][0], pasa_gate=pasa, estado=estado, neto_pct=round(neto, 4)))

    m_sin = metricas(resultados_sin_gate)
    m_con = metricas(resultados_con_gate)
    print(f"\nSIN GATE (todas las rupturas): n={m_sin['n']} WR={m_sin['wr']}% PF={m_sin['pf']} exp={m_sin['exp_media']}%")
    print(f"CON GATE (solo EMA50 subiendo): n={m_con['n']} WR={m_con['wr']}% PF={m_con['pf']} exp={m_con['exp_media']}%")

    boot = bootstrap_no_pareado(resultados_sin_gate, resultados_con_gate)
    print(f"\nBootstrap con-gate vs sin-gate: delta media={boot['media']}% IC95%={boot['ic95']} "
          f"significativo(p<0.05)={boot['significativo_p05']}")

    os.makedirs(RAW_DIR, exist_ok=True)
    fecha = datetime.now().strftime("%Y-%m-%d")
    ruta = os.path.join(RAW_DIR, f"btc_prueba8c_ema50_9anios_{fecha}.json")
    with open(ruta, "w") as f:
        json.dump(dict(sin_gate=dict(metricas=m_sin, netos=resultados_sin_gate),
                        con_gate=dict(metricas=m_con, netos=resultados_con_gate),
                        bootstrap=boot, detalle=detalle,
                        sl_pct=SL_PCT, tp_pct=TP_PCT, base=BASE), f, indent=2, default=str)
    print(f"\n[output] {ruta}")
