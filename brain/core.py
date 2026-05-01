# =========================================
# brain/core.py - Sin librerías externas
# Constitución RESPETADA
# =========================================

class ZBotPadreV2:
    def __init__(self, symbol="BTCUSDT"):
        self.symbol = symbol
        self.config = {
            "sl_percent": 0.015,
            "tp_ratio": 2.0
        }

    def analizar_estrategia_v1(self, velas):
        if not velas or len(velas) < 200:
            return {"accion": "WAIT", "motivo": "Esperando datos (mínimo 200 velas)"}

        actual = velas[-1]
        precio = actual["close"]
        ema_200 = actual.get("ema_200")
        ema_50 = actual.get("ema_50")
        rsi = actual.get("rsi")

        if not ema_200 or not ema_50 or not rsi:
            return {"accion": "WAIT", "motivo": "Indicadores no disponibles aún"}

        alcista = precio > ema_200 and ema_50 > ema_200
        bajista = precio < ema_200 and ema_50 < ema_200

        if alcista:
            if precio <= (ema_50 * 1.002) and (40 <= rsi <= 50):
                return self._crear_orden("LONG", precio, "Pullback + RSI Alcista")

        elif bajista:
            if precio >= (ema_50 * 0.998) and (50 <= rsi <= 60):
                return self._crear_orden("SHORT", precio, "Pullback + RSI Bajista")

        return {"accion": "WAIT", "motivo": "Buscando oportunidad clara"}

    def _crear_orden(self, tipo, precio, motivo):
        if tipo == "LONG":
            sl = precio * (1 - self.config["sl_percent"])
            tp = precio + ((precio - sl) * self.config["tp_ratio"])
        else:
            sl = precio * (1 + self.config["sl_percent"])
            tp = precio - ((sl - precio) * self.config["tp_ratio"])

        return {
            "symbol": self.symbol,
            "accion": tipo,
            "entrada": round(precio, 5),
            "sl": round(sl, 5),
            "tp": round(tp, 5),
            "motivo": motivo,
            "estado": "PENDIENTE_AUDITORIA"
        }
