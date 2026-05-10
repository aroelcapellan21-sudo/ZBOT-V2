#!/usr/bin/env python3
"""Dashboard web para Z-Bot v2 — puerto 8080, solo Python stdlib."""

import csv
import json
import os
import re
import subprocess
import threading
import urllib.request
import urllib.parse
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

BASE = os.path.expanduser("~/bot-padre-v2")
BILLETERA = os.path.join(BASE, "signals/billetera.json")
AUDITORIA = os.path.join(BASE, "auditoria.csv")
PARADA = os.path.join(BASE, "signals/PARADA_EMERGENCIA.txt")
ESTADO_DIARIO = os.path.join(BASE, "signals/estado_diario.json")

CRYPTO_MAP = {
    "BTC": "BTCUSDT",
    "ETH": "ETHUSDT",
    "SOL": "SOLUSDT",
    "BNB": "BNBUSDT",
    "AVAX": "AVAXUSDT",
}

SYMBOLS_DISPARO = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "AVAXUSDT"]

# Idéntico a utils.py — umbrales validados por activo
_UMBRALES_FASE = {
    "BTCUSDT":  {"7d": 1.5, "30d": 2.0},
    "ETHUSDT":  {"7d": 1.5, "30d": 2.0},
    "SOLUSDT":  {"7d": 2.0, "30d": 4.0},
    "BNBUSDT":  {"7d": 1.0, "30d": 1.5},
    "AVAXUSDT": {"7d": 1.5, "30d": 2.5},
}


def _fetch_cierres(symbol, limite=210):
    params = urllib.parse.urlencode({"symbol": symbol, "interval": "4h", "limit": limite})
    url = f"https://api.binance.com/api/v3/klines?{params}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        return [float(k[4]) for k in data]
    except Exception:
        return []


def _rsi(cierres, periodo=14):
    if len(cierres) < periodo + 1:
        return None
    ganancias = [max(cierres[i] - cierres[i-1], 0) for i in range(1, len(cierres))]
    perdidas  = [max(cierres[i-1] - cierres[i], 0) for i in range(1, len(cierres))]
    avg_g = sum(ganancias[:periodo]) / periodo
    avg_p = sum(perdidas[:periodo]) / periodo
    for i in range(periodo, len(ganancias)):
        avg_g = (avg_g * (periodo - 1) + ganancias[i]) / periodo
        avg_p = (avg_p * (periodo - 1) + perdidas[i]) / periodo
    if avg_p == 0:
        return 100.0
    return round(100 - (100 / (1 + avg_g / avg_p)), 2)


def _ema(cierres, periodo):
    if len(cierres) < periodo:
        return None
    k = 2 / (periodo + 1)
    ema = sum(cierres[:periodo]) / periodo
    for precio in cierres[periodo:]:
        ema = precio * k + ema * (1 - k)
    return round(ema, 6)


def _fase(cierres, symbol):
    if len(cierres) < 55:
        return "DESCONOCIDA"
    precio = cierres[-1]
    ema50  = _ema(cierres, 50)
    ema200 = _ema(cierres, 200) if len(cierres) >= 200 else None
    if ema50 is None:
        return "DESCONOCIDA"
    if symbol in _UMBRALES_FASE:
        u7, u30 = _UMBRALES_FASE[symbol]["7d"], _UMBRALES_FASE[symbol]["30d"]
        if len(cierres) >= 180:
            c7  = ((precio - cierres[-42])  / cierres[-42])  * 100
            c30 = ((precio - cierres[-180]) / cierres[-180]) * 100
            if ema200 is not None:
                if precio > ema200 and c7 > u7 and c30 > u30:
                    return "ALCISTA"
                elif precio < ema200 and c7 < -u7 and c30 < -u30:
                    return "BAJISTA"
                else:
                    return "LATERAL"
    cambio = ((precio - cierres[-30]) / cierres[-30]) * 100
    if ema200 is not None:
        if precio > ema50 and precio > ema200 and cambio > 1.0:
            return "ALCISTA"
        elif precio < ema50 and precio < ema200 and cambio < -1.0:
            return "BAJISTA"
    else:
        if precio > ema50 and cambio > 1.0:
            return "ALCISTA"
        elif precio < ema50 and cambio < -1.0:
            return "BAJISTA"
    return "LATERAL"


def _calcular_readiness(rsi, ema20, ema50, fase):
    """Retorna (pct 0-100, motivo) según qué tan cerca está de disparar."""
    if rsi is None:
        return 0, "Sin datos RSI"
    if fase == "LATERAL":
        rsi_min, rsi_max, ema_weight = 45, 55, 0
        ema_ok = True
    elif fase == "ALCISTA":
        rsi_min, rsi_max, ema_weight = 50, 70, 30
        ema_ok = (ema20 is not None and ema50 is not None and ema20 > ema50)
    elif fase == "BAJISTA":
        rsi_min, rsi_max, ema_weight = 30, 50, 30
        ema_ok = (ema20 is not None and ema50 is not None and ema20 < ema50)
    else:
        return 0, "Fase desconocida — esperando más datos"

    rsi_weight = 100 - ema_weight
    margen = 20
    if rsi_min <= rsi <= rsi_max:
        rsi_score = 100.0
    elif rsi < rsi_min:
        rsi_score = max(0.0, (rsi - (rsi_min - margen)) / margen * 100)
    else:
        rsi_score = max(0.0, ((rsi_max + margen) - rsi) / margen * 100)

    ema_score = 100.0 if ema_ok else 0.0
    pct = int(rsi_score * rsi_weight / 100 + ema_score * ema_weight / 100)
    pct = max(0, min(100, pct))

    rsi_en_zona = rsi_min <= rsi <= rsi_max
    if rsi_en_zona and (ema_weight == 0 or ema_ok):
        motivo = f"Condiciones alineadas — RSI {rsi:.1f} en zona [{rsi_min}–{rsi_max}]"
    elif rsi_en_zona and fase == "ALCISTA":
        motivo = f"RSI OK ({rsi:.1f}), esperar EMA20 cruce arriba de EMA50"
    elif rsi_en_zona and fase == "BAJISTA":
        motivo = f"RSI OK ({rsi:.1f}), esperar EMA20 cruce abajo de EMA50"
    elif rsi < rsi_min:
        motivo = f"RSI {rsi:.1f} bajo — esperar que suba a zona [{rsi_min}–{rsi_max}]"
    else:
        motivo = f"RSI {rsi:.1f} alto — esperar que baje a zona [{rsi_min}–{rsi_max}]"

    return pct, motivo


def _rsi_color_fase(rsi, fase):
    if rsi is None:
        return "#8b949e"
    if fase == "LATERAL" and 45 <= rsi <= 55:
        return "#00e676"
    if fase == "ALCISTA" and 50 <= rsi <= 70:
        return "#00e676"
    if fase == "BAJISTA" and 30 <= rsi <= 50:
        return "#00e676"
    return "#ff1744"


def _bar_color(pct):
    if pct >= 90:
        return "#00e676"
    if pct >= 70:
        return "#58a6ff"
    if pct >= 40:
        return "#f0a500"
    return "#ff1744"


def leer_disparos():
    """RSI(14), EMA20, EMA50, fase y readiness en 4H — misma lógica que utils.py."""
    resultado = []
    for symbol in SYMBOLS_DISPARO:
        cierres = _fetch_cierres(symbol)
        if not cierres:
            resultado.append({"symbol": symbol, "error": True})
            continue
        precio  = cierres[-1]
        rsi_val = _rsi(cierres)
        ema20   = _ema(cierres, 20)
        ema50   = _ema(cierres, 50)
        fase    = _fase(cierres, symbol)
        rd_pct, rd_motivo = _calcular_readiness(rsi_val, ema20, ema50, fase)
        resultado.append({
            "symbol":         symbol,
            "precio":         precio,
            "rsi":            rsi_val,
            "ema20":          ema20,
            "ema50":          ema50,
            "fase":           fase,
            "readiness_pct":  rd_pct,
            "readiness_motivo": rd_motivo,
            "error":          False,
        })
    return resultado


def leer_json(path, default=None):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default if default is not None else {}


def leer_precios():
    """Obtiene precios en vivo de Binance (igual que telegram_engine.py)."""
    precios = {}
    try:
        url = "https://api.binance.com/api/v3/ticker/price"
        with urllib.request.urlopen(url, timeout=10) as r:
            datos = json.loads(r.read().decode())
        tabla = {d["symbol"]: float(d["price"]) for d in datos}
        for moneda, symbol in CRYPTO_MAP.items():
            if symbol in tabla:
                precios[moneda] = tabla[symbol]
    except Exception:
        pass
    return precios


def leer_billetera():
    return leer_json(BILLETERA, {})


def calcular_capital(billetera, precios):
    """Calcula capital real igual que telegram_engine.obtener_resumen_personal()."""
    usdt = float(billetera.get("USDT", 0))
    try:
        from config_cartera import CAPITAL_BASE
        capital_inicial = CAPITAL_BASE
    except Exception:
        capital_inicial = float(billetera.get("capital_inicial", 1000))

    valor_crypto = 0.0
    for moneda in CRYPTO_MAP:
        qty = float(billetera.get(moneda, 0))
        precio = precios.get(moneda, 0)
        if qty > 0 and precio > 0:
            valor_crypto += qty * precio

    capital_actual = round(usdt + valor_crypto, 2)
    ganancia = round(capital_actual - capital_inicial, 2)
    ganancia_pct = round((ganancia / capital_inicial * 100), 2) if capital_inicial else 0
    return capital_actual, capital_inicial, ganancia, ganancia_pct, usdt


def leer_trades_abiertos(precios):
    """Lee filas con estado==ABIERTA de auditoria.csv. Eso es lo que Telegram muestra."""
    abiertos = []
    try:
        with open(AUDITORIA, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("estado", "").strip() == "ABIERTA":
                    abiertos.append(row)
    except Exception:
        pass

    resultado = []
    ahora = datetime.now()
    for t in abiertos:
        symbol = t.get("symbol", "")
        try:
            precio_entrada = float(t.get("precio", 0))
        except Exception:
            precio_entrada = 0.0

        # Mapear símbolo a moneda para buscar precio actual
        moneda = symbol.replace("USDT", "")
        precio_actual = precios.get(moneda, 0.0)

        pnl_pct = 0.0
        if precio_entrada > 0 and precio_actual > 0:
            pnl_pct = round((precio_actual - precio_entrada) / precio_entrada * 100, 2)

        horas = 0.0
        try:
            ts = datetime.strptime(t.get("timestamp", "")[:19], "%Y-%m-%d %H:%M:%S")
            horas = round((ahora - ts).total_seconds() / 3600, 1)
        except Exception:
            pass

        resultado.append({
            "symbol": symbol,
            "precio_entrada": precio_entrada,
            "precio_actual": precio_actual,
            "pnl_pct": pnl_pct,
            "horas": horas,
            "accion": t.get("accion", ""),
        })
    return resultado


def leer_auditoria():
    trades = []
    try:
        with open(AUDITORIA, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                trades.append(row)
    except Exception:
        pass
    return trades


def calcular_wr(trades, solo_hoy=False):
    hoy = datetime.now().strftime("%Y-%m-%d")
    ganas = perdidas = 0
    for t in trades:
        if solo_hoy and not t.get("timestamp", "").startswith(hoy):
            continue
        estado = t.get("estado", "")
        if estado == "TP":
            ganas += 1
        elif estado == "SL":
            perdidas += 1
    total = ganas + perdidas
    wr = (ganas / total * 100) if total else 0
    return wr, ganas, perdidas, total


def estado_bot():
    if os.path.exists(PARADA):
        return "PARADA DE EMERGENCIA", "red"
    diario = leer_json(ESTADO_DIARIO, {})
    if diario.get("pausado", False):
        return "PAUSADO", "orange"
    return "ACTIVO", "green"


def color_valor(v):
    return "#00e676" if v >= 0 else "#ff1744"


def fmt_numero(v, decimales=2, prefijo=""):
    signo = "+" if v > 0 else ""
    return f"{prefijo}{signo}{v:.{decimales}f}"


def html_seccion(titulo, contenido):
    return f"""
    <div class="card">
      <div class="card-title">{titulo}</div>
      {contenido}
    </div>"""


def build_html():
    billetera = leer_billetera()
    precios = leer_precios()
    trades = leer_auditoria()

    capital_actual, capital_inicial, ganancia, ganancia_pct, usdt = calcular_capital(billetera, precios)
    trades_abiertos = leer_trades_abiertos(precios)
    disparos = leer_disparos()
    wr_general, g_gen, p_gen, t_gen = calcular_wr(trades)
    wr_hoy, g_hoy, p_hoy, t_hoy = calcular_wr(trades, solo_hoy=True)
    estado_txt, estado_color = estado_bot()
    ultimas = trades[-10:][::-1]
    ultima_actualizacion = billetera.get("ultima_actualizacion", "—")
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Sección 1 — Capital
    color_gan = color_valor(ganancia)
    color_pct = color_valor(ganancia_pct)
    sec_capital = f"""
      <div class="row">
        <span class="label">Capital inicial</span>
        <span class="value">{capital_inicial:,.2f} USDT</span>
      </div>
      <div class="row">
        <span class="label">Capital actual</span>
        <span class="value">{capital_actual:,.2f} USDT</span>
      </div>
      <div class="row">
        <span class="label">USDT libre</span>
        <span class="value">{usdt:,.2f} USDT</span>
      </div>
      <div class="row">
        <span class="label">Ganancia $</span>
        <span class="value" style="color:{color_gan}">{fmt_numero(ganancia)} USDT</span>
      </div>
      <div class="row">
        <span class="label">Ganancia %</span>
        <span class="value" style="color:{color_pct}">{fmt_numero(ganancia_pct)}%</span>
      </div>
      <div class="meta">Billetera actualizada: {ultima_actualizacion}</div>"""

    # Sección 2 — Trades abiertos (filas ABIERTA en auditoria.csv)
    if trades_abiertos:
        filas_pos = ""
        for t in trades_abiertos:
            c_pnl = color_valor(t["pnl_pct"])
            signo = "+" if t["pnl_pct"] >= 0 else ""
            precio_actual_txt = f"{t['precio_actual']:,.2f}" if t["precio_actual"] > 0 else "—"
            filas_pos += f"""
        <div class="trade-row">
          <span class="sym">{t['symbol']}</span>
          <span class="detail">Entrada: {t['precio_entrada']:,.2f}</span>
          <span class="detail">Actual: {precio_actual_txt}</span>
          <span class="detail" style="color:{c_pnl}">PNL: {signo}{t['pnl_pct']}%</span>
          <span class="detail" style="color:#8b949e">{t['horas']}h</span>
        </div>"""
        sec_posiciones = filas_pos
    else:
        sec_posiciones = '<div class="empty">Sin trades abiertos</div>'

    # Sección 3 — WR
    color_wr_gen = color_valor(wr_general - 50)
    color_wr_hoy = color_valor(wr_hoy - 50)
    sec_wr = f"""
      <div class="row">
        <span class="label">WR del día</span>
        <span class="value" style="color:{color_wr_hoy}">{wr_hoy:.1f}%
          <span class="meta"> ({g_hoy}G / {p_hoy}P de {t_hoy})</span></span>
      </div>
      <div class="row">
        <span class="label">WR general</span>
        <span class="value" style="color:{color_wr_gen}">{wr_general:.1f}%
          <span class="meta"> ({g_gen}G / {p_gen}P de {t_gen})</span></span>
      </div>"""

    # Sección 4 — Últimas operaciones
    if ultimas:
        filas_op = '<table class="op-table"><thead><tr><th>Fecha</th><th>Símbolo</th><th>Acción</th><th>Precio</th><th>RSI</th><th>Estado</th></tr></thead><tbody>'
        for t in ultimas:
            estado_op = t.get("estado", "")
            if estado_op == "TP":
                c = "#00e676"
            elif estado_op == "SL":
                c = "#ff1744"
            else:
                c = "#8b949e"
            ts = t.get("timestamp", "")[:16]
            filas_op += f"""<tr>
              <td class="meta">{ts}</td>
              <td>{t.get('symbol','')}</td>
              <td>{t.get('accion','')}</td>
              <td>{float(t.get('precio',0)):,.2f}</td>
              <td>{t.get('rsi','')}</td>
              <td style="color:{c}">{estado_op}</td>
            </tr>"""
        filas_op += "</tbody></table>"
        sec_operaciones = filas_op
    else:
        sec_operaciones = '<div class="empty">Sin operaciones registradas</div>'

    # Sección 5 — Estado bot
    diario = leer_json(ESTADO_DIARIO, {})
    ops_hoy = diario.get("operaciones_hoy", 0)
    perdidas_consec = diario.get("perdidas_consecutivas", 0)
    sec_estado = f"""
      <div class="row">
        <span class="label">Estado</span>
        <span class="value" style="color:{estado_color};font-weight:bold">{estado_txt}</span>
      </div>
      <div class="row">
        <span class="label">Operaciones hoy</span>
        <span class="value">{ops_hoy}</span>
      </div>
      <div class="row">
        <span class="label">Pérdidas consecutivas</span>
        <span class="value" style="color:{'#ff1744' if perdidas_consec >= 2 else '#8b949e'}">{perdidas_consec}</span>
      </div>"""

    # Sección 6 — Disparos RSI / EMA / Fase / Readiness
    _fase_color = {"ALCISTA": "#00e676", "BAJISTA": "#ff1744", "LATERAL": "#f0a500", "DESCONOCIDA": "#8b949e"}
    _fase_emoji = {"ALCISTA": "▲", "BAJISTA": "▼", "LATERAL": "◆", "DESCONOCIDA": "?"}

    if disparos:
        cards = ""
        for d in disparos:
            sym = d["symbol"].replace("USDT", "")
            if d.get("error"):
                cards += f'<div class="disparo-card"><span class="sym">{sym}</span> <span class="meta">Sin datos de mercado</span></div>'
                continue
            rsi_v    = d["rsi"]
            ema20v   = d["ema20"]
            ema50v   = d["ema50"]
            precio_v = d["precio"]
            fase_v   = d["fase"]
            pct      = d["readiness_pct"]
            motivo   = d["readiness_motivo"]

            c_rsi    = _rsi_color_fase(rsi_v, fase_v)
            rsi_txt  = f"{rsi_v:.1f}" if rsi_v is not None else "—"
            ema20_txt = f"{ema20v:,.2f}" if ema20v else "—"
            ema50_txt = f"{ema50v:,.2f}" if ema50v else "—"
            fc       = _fase_color.get(fase_v, "#8b949e")
            fe       = _fase_emoji.get(fase_v, "?")
            bc       = _bar_color(pct)

            cards += f"""
            <div class="disparo-card">
              <div class="dc-header">
                <span class="sym">{sym}</span>
                <span class="dc-precio">${precio_v:,.2f}</span>
                <span class="dc-fase" style="color:{fc}">{fe} {fase_v}</span>
              </div>
              <div class="dc-indicadores">
                <span>RSI&nbsp;<strong style="color:{c_rsi}">{rsi_txt}</strong></span>
                <span>EMA20:&nbsp;{ema20_txt}</span>
                <span>EMA50:&nbsp;{ema50_txt}</span>
              </div>
              <div class="dc-barra-wrapper">
                <div class="dc-barra-track">
                  <div class="dc-barra-fill" style="width:{pct}%;background:{bc}"></div>
                </div>
                <span class="dc-pct" style="color:{bc}">{pct}%</span>
              </div>
              <div class="dc-motivo">{motivo}</div>
            </div>"""
        sec_disparos = f'<div class="disparos-grid">{cards}</div>'
    else:
        sec_disparos = '<div class="empty">Sin datos de disparos</div>'

    page = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="refresh" content="60">
  <title>Z-Bot v2 Dashboard</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: #0d1117;
      color: #c9d1d9;
      font-family: 'Courier New', Courier, monospace;
      font-size: 14px;
      min-height: 100vh;
      padding: 24px 16px;
    }}
    h1 {{
      color: #58a6ff;
      font-size: 20px;
      letter-spacing: 2px;
      margin-bottom: 4px;
    }}
    .header-meta {{
      color: #8b949e;
      font-size: 12px;
      margin-bottom: 24px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(340px, 1fr));
      gap: 16px;
    }}
    .card {{
      background: #161b22;
      border: 1px solid #30363d;
      border-radius: 8px;
      padding: 20px;
    }}
    .card-wide {{
      grid-column: 1 / -1;
    }}
    .card-title {{
      color: #58a6ff;
      font-size: 13px;
      letter-spacing: 1px;
      text-transform: uppercase;
      margin-bottom: 16px;
      border-bottom: 1px solid #21262d;
      padding-bottom: 8px;
    }}
    .row {{
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      padding: 6px 0;
      border-bottom: 1px solid #21262d;
    }}
    .row:last-child {{ border-bottom: none; }}
    .label {{ color: #8b949e; }}
    .value {{ color: #e6edf3; font-weight: bold; text-align: right; }}
    .meta {{ color: #8b949e; font-size: 11px; margin-top: 10px; }}
    .empty {{ color: #8b949e; font-style: italic; padding: 10px 0; }}
    .sym {{ color: #f0a500; font-weight: bold; min-width: 90px; }}
    .detail {{ color: #8b949e; font-size: 12px; flex: 1; text-align: center; }}
    .trade-row {{
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 8px 0;
      border-bottom: 1px solid #21262d;
    }}
    .trade-row:last-child {{ border-bottom: none; }}
    .op-table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }}
    .op-table th {{
      color: #8b949e;
      text-align: left;
      padding: 6px 8px;
      border-bottom: 1px solid #30363d;
      font-weight: normal;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 1px;
    }}
    .op-table td {{
      padding: 7px 8px;
      border-bottom: 1px solid #21262d;
      color: #c9d1d9;
    }}
    .op-table tr:last-child td {{ border-bottom: none; }}
    .op-table tr:hover td {{ background: #1c2128; }}
    .disparos-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 12px;
    }}
    .disparo-card {{
      background: #1c2128;
      border: 1px solid #30363d;
      border-radius: 6px;
      padding: 14px 16px;
    }}
    .dc-header {{
      display: flex;
      align-items: baseline;
      gap: 10px;
      margin-bottom: 8px;
    }}
    .dc-precio {{
      color: #e6edf3;
      font-weight: bold;
      flex: 1;
    }}
    .dc-fase {{
      font-size: 12px;
      font-weight: bold;
      letter-spacing: 0.5px;
    }}
    .dc-indicadores {{
      display: flex;
      gap: 14px;
      font-size: 12px;
      color: #8b949e;
      margin-bottom: 10px;
      flex-wrap: wrap;
    }}
    .dc-barra-wrapper {{
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 7px;
    }}
    .dc-barra-track {{
      flex: 1;
      height: 8px;
      background: #21262d;
      border-radius: 4px;
      overflow: hidden;
    }}
    .dc-barra-fill {{
      height: 100%;
      border-radius: 4px;
    }}
    .dc-pct {{
      font-size: 13px;
      font-weight: bold;
      min-width: 36px;
      text-align: right;
    }}
    .dc-motivo {{
      font-size: 11px;
      color: #8b949e;
      font-style: italic;
      line-height: 1.4;
    }}
    .refresh-bar {{
      margin-top: 20px;
      color: #8b949e;
      font-size: 11px;
      text-align: right;
    }}
    .dot {{
      display: inline-block;
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: {estado_color};
      margin-right: 6px;
      animation: {'blink 1.5s infinite' if estado_color == 'green' else 'none'};
    }}
    @keyframes blink {{
      0%, 100% {{ opacity: 1; }}
      50% {{ opacity: 0.3; }}
    }}
  </style>
</head>
<body>
  <h1>&#9711; Z-BOT v2</h1>
  <div class="header-meta">Actualizado: {ahora} &mdash; recarga automática cada 60s</div>

  <div class="grid">

    {html_seccion("01 / Capital", sec_capital)}

    {html_seccion("02 / Posiciones abiertas", sec_posiciones)}

    {html_seccion("03 / Win Rate", sec_wr)}

    {html_seccion("05 / Estado del bot", sec_estado)}

    <div class="card card-wide">
      <div class="card-title">04 / Últimas 10 operaciones</div>
      {sec_operaciones}
    </div>

    <div class="card card-wide">
      <div class="card-title">06 / Disparos — RSI · EMA · Fase (4H)</div>
      {sec_disparos}
    </div>

  </div>

  <div class="refresh-bar"><span class="dot"></span>Auto-refresh activo &mdash; 60s</div>
</body>
</html>"""
    return page


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path not in ("/", "/index.html"):
            self.send_response(404)
            self.end_headers()
            return
        try:
            body = build_html().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(f"Error: {e}".encode())

    def log_message(self, fmt, *args):
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[{ts}] {fmt % args}")


_tunnel_proc = None


def _leer_url_tunnel(proc):
    patron = re.compile(r"https://[a-z0-9\-]+\.trycloudflare\.com")
    url_encontrada = False
    for linea in proc.stderr:
        texto = linea.decode("utf-8", errors="ignore")
        if not url_encontrada:
            m = patron.search(texto)
            if m:
                url = m.group()
                print(f"\n{'='*54}")
                print(f"  TUNNEL ACTIVO")
                print(f"  {url}")
                print(f"{'='*54}\n")
                url_encontrada = True


def iniciar_tunnel():
    global _tunnel_proc
    try:
        _tunnel_proc = subprocess.Popen(
            ["cloudflared", "tunnel", "--url", "http://localhost:8080"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        _leer_url_tunnel(_tunnel_proc)
    except FileNotFoundError:
        print("[tunnel] cloudflared no encontrado — solo acceso local en :8080")
    except Exception as e:
        print(f"[tunnel] Error: {e}")


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 8080), Handler)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[Z-Bot Dashboard] http://localhost:8080  —  {ts}")
    print("[tunnel] Iniciando cloudflared...")

    t = threading.Thread(target=iniciar_tunnel, daemon=True)
    t.start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[Z-Bot Dashboard] Detenido.")
        if _tunnel_proc:
            _tunnel_proc.terminate()
        server.server_close()
