# conector_binance.py
# Conector REST puro a Binance (SIN librerías externas)
# Solo consulta balances (seguro para DEMO)

import time
import hmac
import hashlib
import requests
from urllib.parse import urlencode

API_KEY = "gtN9RuiGEut2jX2xPRtj2KgeWDsYdPt71QB1S3hNUyw078zntxJaHAen1ZC8ACG0"
API_SECRET = "XHOrBy5wuGCK0YZzNa8M2XTMltsvl2QwANYl9hg37wdCcCWIJ1wXsCpqXrEPzHa7"

BASE_URL =  "https://testnet.binance.vision"

def firmar(params, secret):
    query = urlencode(params)
    signature = hmac.new(
        secret.encode(),
        query.encode(),
        hashlib.sha256
    ).hexdigest()
    return query + "&signature=" + signature

def obtener_balances():
    endpoint = "/api/v3/account"
    params = {
        "timestamp": int(time.time() * 1000)
    }

    query_firmada = firmar(params, API_SECRET)
    url = BASE_URL + endpoint + "?" + query_firmada

    headers = {
        "X-MBX-APIKEY": API_KEY
    }

    r = requests.get(url, headers=headers, timeout=10)
    r.raise_for_status()
    data = r.json()

    print("\nBALANCES DISPONIBLES:\n")
    for asset in data["balances"]:
        libre = float(asset["free"])
        bloqueado = float(asset["locked"])
        if libre > 0 or bloqueado > 0:
            print(f"{asset['asset']}: libre={libre} bloqueado={bloqueado}")

if __name__ == "__main__":
    obtener_balances()
