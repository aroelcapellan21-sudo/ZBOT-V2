from flask import Flask, request, jsonify, render_template_string, session
import anthropic, os, json
from historial_precios import leer_historial_formateado as _historial_precios

app = Flask(__name__, static_folder='static')
app.secret_key = 'zbot_padre_v2_secreto'
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

BOT_DIR = "/home/ariel/bot-padre-v2"

ARCHIVOS_POR_MONEDA = {
    'sol': ['francotirador_alcista_sol.py', 'francotirador_bajista_sol.py', 'francotirador_lateral_sol.py', 'director_sol.py'],
    'btc': ['francotirador_alcista_btc.py', 'francotirador_bajista_btc.py', 'francotirador_lateral_btc.py', 'director_btc.py'],
    'eth': ['francotirador_alcista_eth.py', 'francotirador_bajista_eth.py', 'francotirador_lateral_eth.py', 'director_eth.py'],
    'bnb': ['francotirador_alcista_bnb.py', 'francotirador_bajista_bnb.py', 'francotirador_lateral_bnb.py', 'director_bnb.py'],
    'avax': ['francotirador_alcista_avax.py', 'francotirador_bajista_avax.py', 'francotirador_lateral_avax.py', 'director_avax.py'],
}

ARCHIVOS_GLOBALES = [
    'main.py', 'director_orquesta.py', 'consejero.py', 'config_cartera.py',
    'filtro_calidad.py', 'filtro_horario.py', 'filtro_eventos.py',
    'detector_multitimeframe.py', 'guardian_riesgo.py', 'termometro.py',
    'limitador_diario.py', 'medidor_spread.py', 'gestor_billetera.py',
    'memoria_propia.py', 'trailing_stop.py', 'utils.py'
]

def leer_codigo_especifico(archivos):
    if not archivos:
        return ""
    codigo = "CÓDIGO RELEVANTE:\n"
    for archivo in archivos:
        ruta = os.path.join(BOT_DIR, archivo)
        if os.path.exists(ruta):
            codigo += f"\n=== {archivo} ===\n{open(ruta).read()[:3000]}\n"
    return codigo

def leer_contexto_proyecto():
    ruta = os.path.join(BOT_DIR, 'contexto_proyecto.json')
    if not os.path.exists(ruta):
        return ""
    with open(ruta) as f:
        c = json.load(f)
    texto = "\nCONTEXTO DEL PROYECTO:\n"
    texto += f"- Dueño: {c.get('dueño')}\n"
    texto += f"- Estado: {c.get('estado_actual')}\n"
    texto += f"- Capital inicial: ${c.get('capital_inicial')}\n"
    texto += f"- Meses en testing: {c.get('meses_en_testing')}\n"
    texto += "\nCONDICIONES PARA PASAR A REAL:\n"
    for cond in c.get('condiciones_para_pasar_a_real', []):
        texto += f"  - {cond}\n"
    texto += "\nPREOCUPACIONES ACTUALES:\n"
    for p in c.get('preocupaciones_actuales', []):
        texto += f"  - {p}\n"
    texto += f"\nNOTAS: {c.get('notas', '')}\n"
    return texto

def leer_billetera():
    try:
        with open(os.path.join(BOT_DIR, 'signals/billetera.json')) as f:
            b = json.load(f)
        capital_actual = float(b.get('USDT', 0))
        capital_inicial = float(b.get('capital_inicial', 1000))
        ganancia = round(capital_actual - capital_inicial, 2)
        pct = round((ganancia / capital_inicial) * 100, 2)
        texto = f"\nBILLETERA:\n"
        texto += f"- Capital inicial: ${capital_inicial}\n"
        texto += f"- Capital actual: ${capital_actual} USDT\n"
        texto += f"- Ganancia/Pérdida: ${ganancia} ({pct}%)\n"
        texto += f"- Última actualización: {b.get('ultima_actualizacion', 'N/A')}\n"
        for moneda in ['BTC', 'ETH', 'SOL', 'BNB', 'AVAX']:
            cantidad = float(b.get(moneda, 0))
            if cantidad > 0:
                texto += f"- {moneda} en posición: {cantidad}\n"
        return texto
    except Exception as e:
        return f"Error leyendo billetera: {e}\n"

def leer_auditoria():
    try:
        ruta = os.path.join(BOT_DIR, 'auditoria.csv')
        with open(ruta) as f:
            lineas = f.readlines()
        total = len(lineas) - 1
        tp = sum(1 for l in lineas if ',TP,' in l or l.strip().endswith(',TP'))
        sl = sum(1 for l in lineas if ',SL,' in l or l.strip().endswith(',SL'))
        be = sum(1 for l in lineas if ',BE,' in l or l.strip().endswith(',BE'))
        abiertas = sum(1 for l in lineas if 'ABIERTA' in l)
        texto = f"\nHISTORIAL DE OPERACIONES:\n"
        texto += f"- Total operaciones: {total}\n"
        texto += f"- Take Profit (TP): {tp}\n"
        texto += f"- Stop Loss (SL): {sl}\n"
        texto += f"- Breakeven (BE): {be}\n"
        texto += f"- Abiertas ahora: {abiertas}\n"
        texto += f"\nÚltimas 10 operaciones:\n"
        for l in lineas[-10:]:
            texto += f"  {l.strip()}\n"
        return texto
    except Exception as e:
        return f"Error leyendo auditoría: {e}\n"

def interpretar_diagnostico():
    diag_path = os.path.join(BOT_DIR, 'estado_diagnostico.json')
    if not os.path.exists(diag_path):
        return "No hay diagnóstico disponible.\n"
    with open(diag_path) as f:
        d = json.load(f)
    texto = f"\nREPORTE DEL BOT ({d['timestamp']}):\n"
    texto += f"- Fase global: {d['fase_global']} ({d['conteo_fases']['ALCISTA']} alcistas, {d['conteo_fases']['BAJISTA']} bajistas, {d['conteo_fases']['LATERAL']} laterales)\n"
    fg = d['filtros_globales']
    bloqueados = [k for k, v in fg.items() if not v]
    nombres = {
        "guardian_riesgo": "Guardián de riesgo",
        "termometro": "Termómetro de mercado",
        "horario": "Horario de operación (4AM-9PM)",
        "limite_diario": "Límite diario de operaciones",
        "eventos_macro": "Eventos macroeconómicos"
    }
    if bloqueados:
        texto += "- Filtros bloqueando: " + ", ".join([nombres.get(b, b) for b in bloqueados]) + "\n"
    else:
        texto += "- Filtros globales: todos OK\n"
    texto += "\nESTADO DETALLADO POR MONEDA:\n"
    for symbol, m in d['monedas'].items():
        texto += f"\n{symbol} — Precio ${m['precio']} — Fase {m['fase']}\n"
        texto += f"  RSI: {m['rsi']} — {m.get('rsi_estado', '')}\n"
        texto += f"  EMA: {m.get('ema_estado', '')}\n"
        texto += f"  Calidad señal: {'OK' if m.get('calidad_ok') else 'NO OK'}\n"
        texto += f"  Multitimeframe: {'OK' if m.get('multitf_ok') else 'NO OK'}\n"
        if m.get('listo'):
            texto += f"  ESTADO: LISTA PARA DISPARAR\n"
        else:
            texto += f"  ESTADO: NO LISTA — {', '.join(m.get('razones_bloqueado', []))}\n"
    listas = [s for s, m in d['monedas'].items() if m.get('listo')]
    texto += f"\nRESUMEN: {len(listas)} moneda(s) lista(s): {', '.join(listas) if listas else 'ninguna'}\n"
    return texto

def interpretar_screens():
    screens_path = os.path.join(BOT_DIR, 'estado_screens.json')
    if not os.path.exists(screens_path):
        return "No hay información de screens disponible.\n"
    with open(screens_path) as f:
        s = json.load(f)
    texto = f"\nESTADO DE PROCESOS ({s['timestamp']}):\n"
    texto += f"- Corriendo: {s['total_activos']} de {s['total_esperados']}\n"
    if s['caidos']:
        texto += f"- CAÍDOS: {', '.join(s['caidos'])}\n"
    else:
        texto += "- Todo corriendo correctamente\n"
    return texto

def leer_parada_emergencia():
    ruta = os.path.join(BOT_DIR, 'signals/PARADA_EMERGENCIA.txt')
    if not os.path.exists(ruta):
        return ""
    try:
        contenido = open(ruta).read().strip()
        return f"\n⚠️ PARADA DE EMERGENCIA ACTIVA:\n{contenido}\n"
    except Exception as e:
        return f"\nError leyendo PARADA_EMERGENCIA.txt: {e}\n"

def leer_estado_mercado():
    ruta = os.path.join(BOT_DIR, 'signals/estado_mercado.json')
    if not os.path.exists(ruta):
        return ""
    try:
        with open(ruta) as f:
            d = json.load(f)
        texto = "\nESTADO DE MERCADO:\n"
        for k, v in d.items():
            texto += f"- {k}: {v}\n"
        return texto
    except Exception as e:
        return f"\nError leyendo estado_mercado.json: {e}\n"

def leer_memoria_propia():
    ruta = os.path.join(BOT_DIR, 'data/memoria_propia.json')
    if not os.path.exists(ruta):
        return "\nMEMORIA PROPIA: sin datos aún.\n"
    try:
        with open(ruta) as f:
            m = json.load(f)
        texto = "\nMEMORIA PROPIA DEL BOT:\n"
        texto += f"- WR global: {m.get('wr_global', 'N/A')}%\n"
        texto += f"- Total trades cerrados: {m.get('total_trades', 0)}\n"
        texto += f"- Pérdidas últimos 5 trades: {m.get('perdidas_ultimos_5', 0)}\n"
        texto += f"- Actualizado: {m.get('actualizado', 'N/A')}\n"
        texto += "- WR por símbolo:\n"
        for moneda in ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'AVAXUSDT']:
            wr_key = f"{moneda}_wr"
            tr_key = f"{moneda}_trades"
            if wr_key in m:
                texto += f"    {moneda}: {m[wr_key]}% ({m.get(tr_key, '?')} trades)\n"
        return texto
    except Exception as e:
        return f"\nError leyendo memoria_propia.json: {e}\n"

def leer_log_rechazos():
    ruta = os.path.join(BOT_DIR, 'log_rechazos_calidad.csv')
    if not os.path.exists(ruta):
        return "\nRECHAZOS DE CALIDAD: sin registros aún.\n"
    try:
        lineas = open(ruta).readlines()
        total = max(0, len(lineas) - 1)
        texto = f"\nRECHAZOS DE CALIDAD (últimos 20 de {total} total):\n"
        for l in lineas[-20:]:
            texto += f"  {l.strip()}\n"
        return texto
    except Exception as e:
        return f"\nError leyendo log_rechazos_calidad.csv: {e}\n"

def leer_historial_billetera():
    ruta = os.path.join(BOT_DIR, 'historial_billetera.csv')
    if not os.path.exists(ruta):
        return "\nHISTORIAL BILLETERA: sin registros aún.\n"
    try:
        lineas = open(ruta).readlines()
        if len(lineas) < 2:
            return "\nHISTORIAL BILLETERA: sin entradas aún.\n"
        cabecera = lineas[0].strip()
        ultima = lineas[-1].strip()
        texto = "\nHISTORIAL BILLETERA (último snapshot):\n"
        texto += f"  Columnas: {cabecera}\n"
        texto += f"  Último:   {ultima}\n"
        return texto
    except Exception as e:
        return f"\nError leyendo historial_billetera.csv: {e}\n"

def leer_historial_precios():
    try:
        return _historial_precios(horas=24)
    except Exception as e:
        return f"\nHISTORIAL DE PRECIOS: error ({e})\n"

def leer_url_tunel():
    ruta = os.path.join(BOT_DIR, 'signals/tunnel_url.txt')
    if not os.path.exists(ruta):
        return "\nURL ASISTENTE: tunel no activo o sin URL guardada.\n"
    try:
        url = open(ruta).read().strip()
        return f"\nURL ASISTENTE: {url}\n"
    except Exception:
        return ""

def leer_estados_internos():
    """Lee termómetro, guardian, limitador diario, eventos macro y trailing desde SQLite."""
    try:
        import db
        texto = "\nESTADOS INTERNOS DEL BOT:\n"

        t = db.json_get("estado_termometro")
        if t:
            operar = t.get("parametros", {}).get("operar", True)
            texto += (
                f"\nTermómetro: {t.get('estado','N/A')} "
                f"({'puede operar' if operar else 'SUSPENDIDO'})\n"
                f"  Volatilidad: {t.get('volatilidad_promedio','N/A')}% | "
                f"Tendencia: {t.get('tendencia_promedio','N/A')}% | "
                f"Última medición: {t.get('timestamp','N/A')}\n"
            )
        else:
            texto += "\nTermómetro: sin datos aún\n"

        g = db.json_get("estado_riesgo")
        if g:
            bloq = "SÍ ⛔" if g.get("bloqueado") else "No"
            bloq_dia = "SÍ ⛔" if g.get("bloqueado_dia") else "No"
            texto += (
                f"\nGuardian de Riesgo:\n"
                f"  Bloqueado (drawdown total): {bloq}\n"
                f"  Bloqueado (día): {bloq_dia}\n"
                f"  Capital máx histórico: ${g.get('capital_maximo_historico','N/A')}\n"
                f"  Capital inicio hoy: ${g.get('capital_inicio_dia','N/A')}\n"
            )
        else:
            texto += "\nGuardian de Riesgo: sin datos aún\n"

        l = db.json_get("estado_diario")
        if l:
            pausado = "SÍ ⛔" if l.get("pausado") else "No"
            texto += (
                f"\nLimitador Diario:\n"
                f"  Operaciones hoy: {l.get('operaciones_hoy', 0)}\n"
                f"  Pérdidas consecutivas: {l.get('perdidas_consecutivas', 0)}\n"
                f"  Pausado: {pausado}\n"
            )
        else:
            texto += "\nLimitador Diario: sin datos aún\n"

        e = db.json_get("eventos_macro")
        if e and e.get("evento_activo"):
            texto += (
                f"\nEvento Macro ACTIVO ⛔:\n"
                f"  Descripción: {e.get('descripcion','N/A')}\n"
                f"  Hasta: {e.get('hasta','N/A')} UTC\n"
            )
        else:
            texto += "\nEventos Macro: ninguno activo\n"

        tr = db.json_get("trailing_data")
        if tr:
            abiertos = [(k, v) for k, v in tr.items() if not v.get("cerrado")]
            if abiertos:
                texto += f"\nTrailing Stops activos ({len(abiertos)}):\n"
                for _, op in abiertos:
                    texto += (
                        f"  {op['symbol']}: entrada ${op['precio_entrada']} | "
                        f"SL ${op.get('trailing_sl','N/A')} | "
                        f"máx ${op.get('precio_maximo','N/A')} | "
                        f"activo: {'Sí' if op.get('trailing_activo') else 'No'}\n"
                    )
            else:
                texto += "\nTrailing Stops: ninguno activo\n"
        else:
            texto += "\nTrailing Stops: sin datos\n"

        return texto
    except Exception as e:
        return f"\nESTADOS INTERNOS: error ({e})\n"

def leer_config_cartera_resumida():
    """Muestra parámetros RSI, TP, SL activos por símbolo y fase."""
    try:
        from config_cartera import PARAMETROS, CAPITAL_BASE, CAPITAL_MAX_POR_OP, PESOS_CARTERA
        texto = "\nCONFIGURACIÓN ACTIVA DE LA CARTERA:\n"
        texto += (
            f"  Capital base: ${CAPITAL_BASE} | "
            f"Capital máx/op: {round(CAPITAL_MAX_POR_OP*100, 1)}%\n"
            f"  Pesos: "
            + " | ".join(f"{s.replace('USDT','')} {p}%" for s, p in PESOS_CARTERA.items())
            + "\n"
        )
        texto += "\n  Parámetros (RSI_min-max | TP% | SL% | EC | EL):\n"
        for symbol, fases in PARAMETROS.items():
            sym = symbol.replace("USDT", "")
            for fase, p in fases.items():
                texto += (
                    f"    {sym} {fase:8s}: RSI {p['rsi_min']}-{p['rsi_max']} | "
                    f"TP {p['tp']}% | SL {p['sl']}% | EC {p['ec']} | EL {p['el']}\n"
                )
        return texto
    except Exception as e:
        return f"\nCONFIGURACIÓN: error ({e})\n"

def leer_archivos():
    datos = leer_parada_emergencia()
    datos += leer_contexto_proyecto()
    datos += interpretar_diagnostico()
    datos += leer_billetera()
    datos += leer_historial_billetera()
    datos += leer_auditoria()
    datos += leer_memoria_propia()
    datos += leer_log_rechazos()
    datos += leer_estado_mercado()
    datos += leer_historial_precios()
    datos += leer_url_tunel()
    datos += leer_estados_internos()
    datos += leer_config_cartera_resumida()
    datos += interpretar_screens()
    ev = os.path.join(BOT_DIR, 'memoria/eventos.log')
    if os.path.exists(ev):
        lineas = open(ev).readlines()
        datos += f"\nÚLTIMOS EVENTOS (últimas 50 líneas):\n{''.join(lineas[-50:])}\n"
    return datos

HTML = '''<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Asistente del Bot</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; transition: background 0.3s, color 0.3s; }
        body.dark { background: #202020; color: #e0e0e0; font-family: "Segoe UI", Arial, sans-serif; }
        body.light { background: #f3f3f3; color: #1a1a1a; font-family: "Segoe UI", Arial, sans-serif; }
        .titlebar { display: flex; align-items: center; justify-content: space-between; padding: 12px 20px; }
        body.dark .titlebar { background: #2d2d2d; border-bottom: 1px solid #3a3a3a; }
        body.light .titlebar { background: #ffffff; border-bottom: 1px solid #d0d0d0; }
        .titlebar-left { display: flex; align-items: center; gap: 10px; }
        .titlebar-left span { font-size: 15px; font-weight: 600; }
        .bot-dot { width: 10px; height: 10px; border-radius: 50%; background: #00c853; box-shadow: 0 0 6px #00c853; }
        .theme-toggle { background: none; border: none; cursor: pointer; font-size: 20px; padding: 4px 8px; border-radius: 6px; }
        body.dark .theme-toggle:hover { background: #3a3a3a; }
        body.light .theme-toggle:hover { background: #e0e0e0; }
        .acciones { display: flex; gap: 8px; flex-wrap: wrap; padding: 8px 20px; }
        body.dark .acciones { background: #252525; border-bottom: 1px solid #3a3a3a; }
        body.light .acciones { background: #f8f8f8; border-bottom: 1px solid #d0d0d0; }
        .accion-btn { padding: 5px 12px; border-radius: 6px; border: none; cursor: pointer; font-size: 12px; font-weight: 500; }
        .accion-btn.danger { background: #c0392b; color: #fff; }
        .accion-btn.danger:hover { background: #a93226; }
        .accion-btn.safe { background: #27ae60; color: #fff; }
        .accion-btn.safe:hover { background: #229954; }
        .accion-btn.warn { background: #e67e22; color: #fff; }
        .accion-btn.warn:hover { background: #ca6f1e; }
        .accion-toast { position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%); padding: 10px 20px; border-radius: 8px; font-size: 14px; z-index: 999; display: none; }
        body.dark .accion-toast { background: #383838; color: #e0e0e0; }
        body.light .accion-toast { background: #333; color: #fff; }
        .container { max-width: 860px; margin: 0 auto; padding: 20px 16px; height: calc(100vh - 100px); display: flex; flex-direction: column; }
        .chat-window { flex: 1; overflow-y: auto; padding: 16px; border-radius: 12px; margin-bottom: 16px; display: flex; flex-direction: column; gap: 12px; }
        body.dark .chat-window { background: #2d2d2d; border: 1px solid #3a3a3a; }
        body.light .chat-window { background: #ffffff; border: 1px solid #d0d0d0; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
        .msg { display: flex; gap: 10px; align-items: flex-start; max-width: 85%; }
        .msg.user { align-self: flex-end; flex-direction: row-reverse; }
        .msg.bot { align-self: flex-start; }
        .avatar { width: 34px; height: 34px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 16px; flex-shrink: 0; overflow: hidden; }
        .avatar img { width: 34px; height: 34px; object-fit: cover; border-radius: 50%; }
        .msg.bot .avatar { background: #5c2d91; }
        .bubble { padding: 10px 14px; border-radius: 12px; font-size: 14px; line-height: 1.6; max-width: 100%; word-wrap: break-word; }
        body.dark .msg.user .bubble { background: #0078d4; color: #fff; border-bottom-right-radius: 4px; }
        body.light .msg.user .bubble { background: #0078d4; color: #fff; border-bottom-right-radius: 4px; }
        body.dark .msg.bot .bubble { background: #383838; color: #e0e0e0; border-bottom-left-radius: 4px; }
        body.light .msg.bot .bubble { background: #f0f0f0; color: #1a1a1a; border-bottom-left-radius: 4px; }
        .typing { display: flex; gap: 4px; align-items: center; padding: 10px 14px; }
        .typing span { width: 7px; height: 7px; border-radius: 50%; background: #888; animation: bounce 1.2s infinite; }
        .typing span:nth-child(2) { animation-delay: 0.2s; }
        .typing span:nth-child(3) { animation-delay: 0.4s; }
        @keyframes bounce { 0%,60%,100%{transform:translateY(0)} 30%{transform:translateY(-6px)} }
        .input-bar { display: flex; gap: 10px; align-items: center; padding: 10px 14px; border-radius: 12px; }
        body.dark .input-bar { background: #2d2d2d; border: 1px solid #3a3a3a; }
        body.light .input-bar { background: #ffffff; border: 1px solid #d0d0d0; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
        #pregunta { flex: 1; background: none; border: none; outline: none; font-size: 14px; font-family: "Segoe UI", Arial, sans-serif; }
        body.dark #pregunta { color: #e0e0e0; }
        body.light #pregunta { color: #1a1a1a; }
        body.dark #pregunta::placeholder { color: #666; }
        body.light #pregunta::placeholder { color: #999; }
        .send-btn { width: 36px; height: 36px; border-radius: 8px; border: none; cursor: pointer; background: #0078d4; color: white; font-size: 16px; display: flex; align-items: center; justify-content: center; }
        .send-btn:hover { background: #006cbf; }
        .chat-window::-webkit-scrollbar { width: 6px; }
        .chat-window::-webkit-scrollbar-track { background: transparent; }
        body.dark .chat-window::-webkit-scrollbar-thumb { background: #444; border-radius: 3px; }
        body.light .chat-window::-webkit-scrollbar-thumb { background: #ccc; border-radius: 3px; }
    </style>
</head>
<body class="dark">
<div class="titlebar">
    <div class="titlebar-left">
        <div class="bot-dot"></div>
        <span>🤖 Asistente del Bot</span>
    </div>
    <button class="theme-toggle" onclick="toggleTheme()">🌙</button>
</div>
<div class="acciones">
    <button class="accion-btn danger" onclick="ejecutar(\'parada_activar\')">⛔ Activar Parada</button>
    <button class="accion-btn safe"   onclick="ejecutar(\'parada_desactivar\')">✅ Desactivar Parada</button>
    <button class="accion-btn warn"   onclick="pedirEvento()">📰 Activar Evento Macro</button>
    <button class="accion-btn safe"   onclick="ejecutar(\'evento_desactivar\')">✅ Desactivar Evento</button>
</div>
<div id="toast" class="accion-toast"></div>
<div class="container">
    <div class="chat-window" id="chat">
        <div class="msg bot">
            <div class="avatar">🤖</div>
            <div class="bubble">Hola Ariel, soy el asistente de tu bot impulsado por Claude Sonnet. Recuerdo todo lo que hablamos en esta sesión. Pregúntame lo que quieras.</div>
        </div>
    </div>
    <div class="input-bar">
        <input id="pregunta" placeholder="Escribe tu pregunta..." onkeypress="if(event.key===\'Enter\')preguntar()">
        <button class="send-btn" onclick="preguntar()">➤</button>
    </div>
</div>
<script>
    function toggleTheme() {
        const body = document.body;
        const btn = document.querySelector('.theme-toggle');
        if (body.classList.contains('dark')) {
            body.classList.replace('dark', 'light');
            btn.textContent = '☀️';
        } else {
            body.classList.replace('light', 'dark');
            btn.textContent = '🌙';
        }
    }

    function mostrarToast(msg, ms=3500) {
        const t = document.getElementById(\'toast\');
        t.textContent = msg;
        t.style.display = \'block\';
        setTimeout(() => t.style.display = \'none\', ms);
    }

    async function ejecutar(comando, extra={}) {
        const payload = {comando, ...extra};
        const r = await fetch(\'/ejecutar\', {method:\'POST\', headers:{\'Content-Type\':\'application/json\'}, body: JSON.stringify(payload)});
        const d = await r.json();
        mostrarToast(d.msg);
    }

    function pedirEvento() {
        const desc  = prompt(\'Descripción del evento (ej: FOMC, CPI):\');
        if (!desc) return;
        const hasta = prompt(\'Bloquear hasta qué hora UTC (formato HH:MM, ej: 15:30):\');
        if (!hasta) return;
        ejecutar(\'evento_activar\', {descripcion: desc, hasta: hasta});
    }

    async function preguntar() {
        const input = document.getElementById(\'pregunta\');
        const p = input.value.trim();
        if (!p) return;
        const chat = document.getElementById(\'chat\');
        chat.innerHTML += `<div class="msg user"><div class="avatar"><img src="/static/avatar.jpg" onerror="this.parentElement.innerHTML=\'👤\'"></div><div class="bubble">${p}</div></div>`;
        input.value = \'\';
        const typingId = \'typing_\' + Date.now();
        chat.innerHTML += `<div class="msg bot" id="${typingId}"><div class="avatar">🤖</div><div class="bubble typing"><span></span><span></span><span></span></div></div>`;
        chat.scrollTop = chat.scrollHeight;
        const r = await fetch(\'/preguntar\', {method:\'POST\', headers:{\'Content-Type\':\'application/json\'}, body: JSON.stringify({pregunta: p})});
        const d = await r.json();
        document.getElementById(typingId).outerHTML = `<div class="msg bot"><div class="avatar">🤖</div><div class="bubble">${d.respuesta}</div></div>`;
        chat.scrollTop = chat.scrollHeight;
    }
</script>
</body>
</html>'''

@app.route('/')
def index():
    if 'historial' not in session:
        session['historial'] = []
    return render_template_string(HTML)

@app.route('/preguntar', methods=['POST'])
def preguntar():
    try:
        if 'historial' not in session:
            session['historial'] = []

        pregunta = request.json.get('pregunta', '')
        pregunta_lower = pregunta.lower()

        archivos_extra = []
        for moneda, archivos in ARCHIVOS_POR_MONEDA.items():
            if moneda in pregunta_lower:
                archivos_extra = archivos
                break

        necesita_codigo = bool(archivos_extra) or any(x in pregunta_lower for x in [
            'código', 'codigo', 'error', 'falla', 'bug', 'parámetro',
            'parametro', 'lógica', 'logica', 'revisar', 'auditar',
            'mejorar', 'problema', 'filtro', 'trailing', 'consejo',
            'configuración', 'configuracion', 'porqué', 'por qué',
            'audita', 'real', 'listo', 'opera'
        ])

        datos = leer_archivos()
        if necesita_codigo:
            if archivos_extra:
                datos += "\n" + leer_codigo_especifico(archivos_extra)
            else:
                datos += "\n" + leer_codigo_especifico(ARCHIVOS_GLOBALES[:6])

        historial = session['historial'][-10:]
        messages = historial + [{"role": "user", "content": pregunta}]

        respuesta = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1200,
            system=f"""Eres el asistente inteligente del bot de trading Z-Bot Padre v2, propiedad de Ariel.
Tienes dominio total del sistema: conoces el código completo, todos los filtros, los 15 francotiradores (5 monedas × alcista/bajista/lateral), la billetera, operaciones, estado en tiempo real, parámetros y estados internos.
Explica en lenguaje simple y directo. Responde SOLO con datos del reporte. Nunca inventes cifras.
Responde siempre en español. Máximo 6 oraciones claras y directas.
Si detectas algo anómalo o mejorable, menciónalo con precisión.
Recuerdas todo lo que Ariel ha preguntado en esta sesión.

ACCIONES QUE PUEDES SUGERIR (Ariel usa los botones de la pantalla para ejecutarlas):
- Activar Parada de Emergencia → detiene todas las operaciones inmediatamente
- Desactivar Parada de Emergencia → reanuda operaciones normales
- Activar Evento Macro → bloquea operaciones hasta una hora UTC especificada
- Desactivar Evento Macro → levanta el bloqueo de evento macro
Cuando Ariel te pida ejecutar alguna de estas acciones, indícale qué botón usar o qué datos ingresar.

DATOS ACTUALES DEL BOT:
{datos}""",
            messages=messages
        )

        respuesta_texto = respuesta.content[0].text

        session['historial'] = historial + [
            {"role": "user", "content": pregunta},
            {"role": "assistant", "content": respuesta_texto}
        ]
        session.modified = True

        return jsonify({"respuesta": respuesta_texto})

    except Exception as e:
        return jsonify({"respuesta": f"⚠️ El asistente tuvo un problema: {str(e)}. Revisa el screen z_asistente."})


@app.route('/ejecutar', methods=['POST'])
def ejecutar():
    """Ejecuta acciones seguras y reversibles sobre el bot."""
    try:
        data    = request.json or {}
        comando = data.get('comando', '')

        if comando == 'parada_activar':
            ruta = os.path.join(BOT_DIR, 'signals/PARADA_EMERGENCIA.txt')
            with open(ruta, 'w') as f:
                f.write('Parada activada desde el asistente web.')
            return jsonify({"ok": True, "msg": "⛔ Parada de emergencia ACTIVADA. El bot deja de operar."})

        elif comando == 'parada_desactivar':
            ruta = os.path.join(BOT_DIR, 'signals/PARADA_EMERGENCIA.txt')
            if os.path.exists(ruta):
                os.remove(ruta)
            return jsonify({"ok": True, "msg": "✅ Parada de emergencia DESACTIVADA. El bot puede operar."})

        elif comando == 'evento_activar':
            desc  = data.get('descripcion', 'Evento manual')
            hasta = data.get('hasta', '')
            if not hasta:
                return jsonify({"ok": False, "msg": "Falta la hora 'hasta' (formato HH:MM)"})
            from filtro_eventos import activar_evento_manual
            activar_evento_manual(desc, hasta)
            return jsonify({"ok": True, "msg": f"⛔ Evento macro activado: {desc} hasta {hasta} UTC"})

        elif comando == 'evento_desactivar':
            from filtro_eventos import desactivar_evento_manual
            desactivar_evento_manual()
            return jsonify({"ok": True, "msg": "✅ Evento macro desactivado. Bot puede operar."})

        else:
            return jsonify({"ok": False, "msg": f"Comando desconocido: {comando}"})

    except Exception as e:
        return jsonify({"ok": False, "msg": f"Error ejecutando comando: {e}"})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5050, debug=False)
