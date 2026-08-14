# Qué va a cambiar y por qué — ETH alcista vs lateral
Fecha: 2026-08-13

---

## El problema en una línea

El bot ETH opera en dos modos: ALCISTA y LATERAL.
El modo ALCISTA gana dinero. El modo LATERAL lo pierde.
Hoy lo medimos con datos reales de 5 años y comisiones incluidas.

---

## Qué encontramos

Corrimos 635 operaciones reales simuladas sobre ETH 4H desde 2021 hasta hoy.
Cada operación usa $5 de capital y paga $0.005 de comisión por lado (0.1%).

Los resultados separados por fase fueron:

**ALCISTA (254 operaciones):**
- Gana el 51.97% de las veces.
- Por cada trade ganador el bot suma $0.25 neto.
- Por cada trade perdedor el bot pierde $0.225 neto.
- Ganancia promedio por trade: +$0.012.
- Capital final partiendo de $20: **$23.01** — ganó $3.01 en 5 años.

**LATERAL (376 operaciones):**
- Gana el 42.29% de las veces.
- Por cada trade ganador el bot suma $0.29 neto.
- Por cada trade perdedor el bot pierde $0.235 neto.
- Pérdida promedio por trade: -$0.013.
- Capital final partiendo de $20: **$15.12** — perdió $4.89 en 5 años.

**Combinados:** el capital pasa de $20 a $17.95. El sistema en conjunto pierde dinero.

---

## Por qué la fase LATERAL pierde

No es que el TP sea malo o el SL sea muy ajustado.
El problema es la tasa de acierto: 42.3% es demasiado baja para el ratio riesgo/recompensa actual.

Con SL de 4.5% y TP de 6%, para que un sistema sea rentable necesita ganar al menos el 43% de las veces
sin contar comisiones. Con comisiones el umbral sube un poco más.
La fase LATERAL está justo por debajo de ese umbral: 42.3%.

El RSI entre 43 y 57 (zona "neutra") captura movimientos que no tienen dirección clara.
El precio entra en esa zona, el bot compra esperando una suba, pero el mercado lateral
no tiene suficiente fuerza para empujar el precio hasta el TP antes de que rebote hacia abajo.
El resultado: más SL que TP, y el sistema pierde aunque el TP sea más grande que el SL.

---

## Qué cambiaría

**Una sola cosa: desactivar la fase LATERAL en ETH.**

El francotirador lateral sigue existiendo en el código, no se borra nada.
El director de ETH simplemente dejaría de activarlo cuando detecta mercado lateral.
Solo operaría cuando el mercado esté en fase ALCISTA.

---

## Qué pasaría si se hace ese cambio

El bot haría menos operaciones: en vez de ~13 trades por mes haría ~5 trades por mes.

Pero los que haría serían rentables:
- En 5 años, solo con ALCISTA: capital pasa de $20 a $23.01.
- En 5 años, combinado como está hoy: capital pasa de $20 a $17.95.
- Diferencia: $5.06 a favor de operar solo ALCISTA.

El drawdown máximo también baja:
- Combinado: 27.96% de caída máxima desde el pico.
- Solo ALCISTA: 10.02% de caída máxima desde el pico.

La racha máxima de pérdidas consecutivas baja de 11 a 8.

---

## Por qué no se hizo todavía

Porque ningún cambio en los francotiradores se aplica sin backtest previo aprobado por Ariel.
Esa es la regla del proyecto desde junio 2026.

El backtest de hoy es la evidencia. La decisión de si se aplica o no es de Ariel.

---

## Una advertencia sobre los números anteriores

El script que usábamos antes (backtest_perfil_comparativo.py) mostraba que el capital final
de solo_ETH era $118.33. Ese número está mal.

No es que el script tenga un bug de programación — funciona como fue diseñado.
El problema es que usa un modelo matemático que no representa cómo opera el bot realmente.

El script calculaba la ganancia de cada TP como:
  ganancia = $5 × (porcentaje_TP / porcentaje_SL)

Con TP de 5% y SL de 4.5%, eso da $5.56 de ganancia por TP.

Pero en la realidad, operar $5 con un TP de 5% da:
  ganancia = $5 × 5% = $0.25 de ganancia por TP.

La diferencia es de 22 veces. Por eso el capital ficticio llegaba a $118 y el real llega a $18.
El script sirve para comparar perfiles entre sí (cuál es mejor relativo al otro),
pero los dólares que muestra no son dólares reales.

---

## Resumen en tres líneas

1. La fase LATERAL hace que el sistema pierda dinero porque acierta solo el 42% de las veces.
2. Si se desactiva la fase LATERAL, el sistema pasa a ser rentable (aunque gana poco con $20).
3. El cambio es pequeño en código, grande en impacto, y requiere OK de Ariel para aplicarse.
