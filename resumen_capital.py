# resumen_capital.py
# Modulo de capital por bot y por par
import os, json, csv

BOTS = {
    "V4": {"path": "~/bot-padre-v4", "sl": 0.035, "tp": 0.10, "cap_op": 0.03,
           "pares": ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","AVAXUSDT"]},
    "V5": {"path": "~/bot-padre-v5", "sl": 0.035, "tp": 0.06, "cap_op": 0.05,
           "pares": ["BTCUSDT","ETHUSDT"]},
    "V6": {"path": "~/bot-padre-v6", "sl": 0.035, "tp": 0.10, "cap_op": 0.03,
           "pares": ["BTCUSDT","ETHUSDT","AVAXUSDT"]},
}
CAPITAL_INI = 1000.0

def leer_capital(path):
    try:
        ruta = os.path.expanduser(f"{path}/signals/billetera.json")
        with open(ruta, "r") as f:
            return round(json.load(f).get("USDT", CAPITAL_INI), 4)
    except:
        return CAPITAL_INI

def leer_trades_por_par(path):
    """Retorna dict con {symbol: {"tp": n, "sl": n}} """
    resultado = {}
    try:
        ruta = os.path.expanduser(f"{path}/auditoria.csv")
        with open(ruta, "r") as f:
            reader = csv.reader(f)
            next(reader)
            for row in reader:
                if len(row) < 6: continue
                symbol = row[2]
                estado = row[5].strip().upper()
                if symbol not in resultado:
                    resultado[symbol] = {"tp": 0, "sl": 0}
                if estado == "TP":
                    resultado[symbol]["tp"] += 1
                elif estado == "SL":
                    resultado[symbol]["sl"] += 1
    except:
        pass
    return resultado

def generar_bloque_capital():
    caps = {}
    trades = {}
    for nombre, cfg in BOTS.items():
        caps[nombre] = leer_capital(cfg["path"])
        trades[nombre] = leer_trades_por_par(cfg["path"])

    total = round(sum(caps.values()), 4)
    msg = f"💰 Capital total: ${total}\n"
    for nombre, cap in caps.items():
        gan = round(cap - CAPITAL_INI, 4)
        emoji = "✅" if gan > 0 else "🔴" if gan < 0 else "⚪"
        msg += f"  {nombre} → {emoji} ha ganado: ${gan}\n"

    msg += "━━━━━━━━━━━━━━━━━━━\n"
    msg += "💰 CAPITAL POR PAR\n"

    todos_pares = ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","AVAXUSDT"]
    for symbol in todos_pares:
        gan_total = 0
        linea_bots = []
        for nombre, cfg in BOTS.items():
            if symbol not in cfg["pares"]:
                linea_bots.append(f"{nombre}:—")
                continue
            t = trades[nombre].get(symbol, {"tp":0,"sl":0})
            # Calcular proporcion de ganancia real por par
            total_ops = sum(
                trades[nombre].get(s, {"tp":0,"sl":0})["tp"] +
                trades[nombre].get(s, {"tp":0,"sl":0})["sl"]
                for s in cfg["pares"]
            )
            ops_par = t["tp"] + t["sl"]
            gan_bot = round(caps[nombre] - CAPITAL_INI, 4)
            gan_par = round(gan_bot * (ops_par / total_ops), 4) if total_ops > 0 else 0.0
            gan_total += gan_par
            linea_bots.append(f"{nombre}:${gan_par}")

        gan_total = round(gan_total, 4)
        emoji = "✅" if gan_total > 0 else "🔴" if gan_total < 0 else "⚪"
        msg += f"\n{emoji} {symbol} → ${gan_total} ganado\n"
        msg += f"  {' | '.join(linea_bots)}\n"

    return msg

if __name__ == "__main__":
    print(generar_bloque_capital())
