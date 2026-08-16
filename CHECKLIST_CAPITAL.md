# Checklist — Incremento de capital real

Seguir este orden cada vez que se deposite capital adicional en Binance
y se quiera sincronizar el bot con el nuevo saldo.

Aprendido el 2026-08-15 durante la activación a REAL con $8.54 USDT.

---

## Antes de empezar

- [ ] Confirmar el saldo exacto en Binance Spot Wallet (captura o número exacto)
- [ ] Anotar el nuevo capital: `NUEVO_CAPITAL = $___`
- [ ] Verificar que no haya posiciones ABIERTA o RESERVADA en `auditoria.csv`
      ```bash
      grep -c "ABIERTA\|RESERVADA" ~/bot-padre-v2/auditoria.csv
      # Debe devolver 0 antes de continuar
      ```

---

## 1. `signals/billetera.json`

Actualizar USDT y los campos de referencia:

```json
{
  "USDT": <NUEVO_CAPITAL>,
  "capital_inicial": <NUEVO_CAPITAL>,
  "capital_real": <NUEVO_CAPITAL>,
  "ultima_actualizacion": "YYYY-MM-DD",
  "moneda_activa": "BNB",
  "BTC": 0.0,
  "AVAX": 0.0,
  "ETH": 0.0,
  "SOL": 0.0,
  "BNB": 0.0
}
```

> Si hay cripto comprada en Binance (posición abierta real), usar el saldo
> real de cada moneda en vez de 0.0.

---

## 2. `bot.db` → tabla `estado_riesgo` (fuente activa del Guardian)

Es la fuente que el Guardian realmente lee. El JSON legacy (paso 3) es
secundario pero debe mantenerse consistente.

```python
import sqlite3, json
from datetime import datetime

conn = sqlite3.connect('~/bot-padre-v2/signals/bot.db')
nuevo = {
    'capital_maximo_historico': <NUEVO_CAPITAL>,
    'capital_inicio_dia': <NUEVO_CAPITAL>,
    'fecha': 'YYYY-MM-DD',
    'bloqueado': False,
    'bloqueado_dia': False
}
conn.execute(
    'INSERT OR REPLACE INTO estado_json (tabla, data, ts) VALUES (?,?,?)',
    ('estado_riesgo', json.dumps(nuevo), datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
)
conn.commit()
conn.close()
```

Verificar:
```bash
python3 -c "
import sqlite3, json
conn = sqlite3.connect('/home/ariel/bot-padre-v2/signals/bot.db')
row = conn.execute(\"SELECT data FROM estado_json WHERE tabla='estado_riesgo'\").fetchone()
print(json.loads(row[0]))
conn.close()
"
```

---

## 3. `signals/estado_riesgo.json` (legacy, mantener consistente con bot.db)

```json
{
  "capital_maximo_historico": <NUEVO_CAPITAL>,
  "capital_inicio_dia": <NUEVO_CAPITAL>,
  "fecha": "YYYY-MM-DD",
  "bloqueado": false,
  "bloqueado_dia": false
}
```

---

## 4. `config_cartera.py` — `CAPITAL_BASE`

```python
CAPITAL_BASE = <NUEVO_CAPITAL>
```

Esto afecta al Consejero (umbral SALUDABLE/RIESGO/CRITICO) y al cálculo
de ganancia porcentual en `/resumen` y `/retiro`.

---

## 5. Francotirador activo — monto fijo

El francotirador activo usa `MONTO_FIJO`, no un porcentaje.
Decidir si el nuevo monto por operación cambia con el capital adicional.

Archivo actual: `francotirador_alcista_bnb.py`

```python
MONTO_FIJO = <MONTO_POR_OP>   # Ej: 8.0, 10.0, etc.
```

Regla orientativa: no superar el capital disponible. Si se opera con
posición única (`MAX_OP_TOTAL = 1`), `MONTO_FIJO` puede ser hasta 100%
del capital, aunque por gestión de riesgo se recomienda no más del 80%.

---

## 6. Verificación del Centinela

El Centinela lee capital desde `billetera.json` al arrancar.
Si `main.py` ya está corriendo, **reiniciar el proceso** para que tome el
nuevo capital como High Water Mark correcto:

```bash
# Verificar PID del main.py de bot-padre-v2
pgrep -af main.py
readlink /proc/<PID>/cwd   # confirmar que apunta a bot-padre-v2

# Dentro del screen v2_main:
screen -r v2_main
kill <PID>
export BOT_REAL_CONFIRMADO=true   # reexportar si es necesario
python3 main.py
```

Confirmar en el log:
```
[CENTINELA] Capital real leido desde billetera.json: $<NUEVO_CAPITAL>
```

---

## 7. Verificar Consejero

Ejecutar y confirmar que el estado es SALUDABLE:

```bash
python3 -c "
import sys; sys.path.insert(0, '/home/ariel/bot-padre-v2')
from consejero import consultar_consejero, calcular_capital_total
c = calcular_capital_total()
r = consultar_consejero(c)
print(r['estado'], r['porcentaje'], '%')
"
# Debe mostrar: SALUDABLE 100.0% (o similar)
```

---

## 8. Commit

Solo commitear archivos de código/config — NO datos runtime:

```bash
git add config_cartera.py francotirador_alcista_bnb.py
git commit -m "config: incremento capital real a $<NUEVO_CAPITAL>"
git push origin main
```

> `signals/billetera.json`, `signals/estado_riesgo.json` y `signals/bot.db`
> están en `.gitignore` — no se commitean.

---

## Resumen rápido (checklist de ejecución)

```
[ ] 1. billetera.json       → USDT = NUEVO_CAPITAL
[ ] 2. bot.db estado_riesgo → capital_maximo_historico = NUEVO_CAPITAL, bloqueado=false
[ ] 3. estado_riesgo.json   → igual que bot.db
[ ] 4. config_cartera.py    → CAPITAL_BASE = NUEVO_CAPITAL
[ ] 5. francotirador activo → MONTO_FIJO = decidir monto por op
[ ] 6. Reiniciar main.py    → Centinela confirma capital correcto en log
[ ] 7. Verificar Consejero  → estado SALUDABLE
[ ] 8. Commit + push        → solo .py modificados
```
