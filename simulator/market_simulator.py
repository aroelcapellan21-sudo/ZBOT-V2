import random, json, time, os
from datetime import datetime

os.makedirs("signals", exist_ok=True)
MONEDAS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "ADAUSDT", "DOTUSDT"]

def simular_quinteto():
    precios = {m: 100.0 for m in MONEDAS} # Precios base
    print("🚀 ZBot: Simulando Quinteto Skrill...")
    
    while True:
        for m in MONEDAS:
            cambio = random.uniform(-0.001, 0.001)
            precios[m] *= (1 + cambio)
            
            data = {
                "symbol": m,
                "price": round(precios[m], 2),
                "timestamp": datetime.utcnow().isoformat()
            }
            
            with open(f"signals/market_{m}.json", "w") as f:
                json.dump(data, f)
        
        print(f"📊 Actualizado: {', '.join(MONEDAS)}")
        time.sleep(5)

if __name__ == "__main__":
    simular_quinteto()
