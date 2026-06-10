import time
from datetime import datetime

# Proceso de inteligencia pasivo — sin polling Telegram.
# El polling fue migrado a brain/telegram_engine.py para evitar
# doble respuesta al usar el mismo token.

print(f"[INTEL] Servicio de inteligencia activo — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

while True:
    time.sleep(60)
