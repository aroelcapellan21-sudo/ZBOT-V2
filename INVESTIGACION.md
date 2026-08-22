# INVESTIGACIÓN — Z-Bot Padre v2

Bitácora completa de investigación, backtests, auditorías y fixes históricos. Separado de
`CLAUDE.md` el 2026-08-22 (el archivo combinado pesaba 84.9k caracteres, por encima del límite de
40k de Claude Code). Contenido copiado íntegro desde el `CLAUDE.md` viejo — sin resumir ni perder
información — salvo las secciones que ahora viven exclusivamente en `CLAUDE.md` (Constitución,
Git, Seguridad, Código). Backup del original: `CLAUDE_BACKUP_2026-08-22.md`.

Este archivo es historial: describe qué se creyó, se probó y se decidió en cada momento, con su
fecha. **Para el estado real vigente de cualquier parámetro o francotirador, la fuente de verdad
es `CLAUDE.md` (tabla de estado real, verificada leyendo el código) — no este archivo.** Dos
notas aclaratorias se agregaron el 2026-08-22 (marcadas explícitamente) donde una sección describía
como vigente algo que ya dejó de serlo, sin alterar el texto histórico original.

---

## Camino de dinero — contrato tras la auditoría pre-REAL (ago 2026)

Auditoría completa del 2026-08-12 antes de pasar a REAL: `reports/2026-08-12_auditoria-pre-real.md`
(plan de 9 puntos; los reportes no se commitean). **Veredicto: NO pasar a REAL todavía** — ver
"Pendientes" al final de esta sección.

### `ejecutor.py` — devuelve tuplas, no strings

`ejecutar_operacion()` y `cerrar_posicion()` devuelven **`(mensaje, fill)`**, no un string suelto.
El mensaje conserva el formato `"✅ ..."` / `"❌ ..."` de siempre, así que `if "✅" in resultado`
sigue funcionando, pero **hay que desempaquetar la tupla**.

```python
resultado, fill = ejecutar_operacion(MONEDA, "COMPRA", precio, monto)
res, fill_cierre = cerrar_posicion(MONEDA, TIPO_TRADE, precio_entrada, monto_op, qty_op)
# fill = {"qty": <cripto neta de comisión>, "usdt": <USDT neto>, "precio": <fill real>}
# fill = None si la orden fue rechazada o falló
```

- **`_extraer_fill()`** normaliza la respuesta de Binance restando la comisión del array `fills`.
  `executedQty` es **bruto**: en COMPRA la comisión se cobra en el activo **base** (recibís menos
  cripto), en VENTA en el **quote** (recibís menos USDT). Persistir `executedQty` tal cual hace
  que después intentes vender ~0.1% de más.
- **`_truncar_cantidad()`** (antes `_redondear_cantidad`) trunca al `LOT_SIZE` con
  `Decimal`/`ROUND_DOWN`. Nunca `round()`: redondear hacia arriba pide más de lo que hay en cuenta
  → rechazo `-2010` → el cierre falla y la posición queda `ABIERTA` sin stop. No usar `floor()`
  sobre float: el error binario se come un tick entero (`0.29 * 100 = 28.999999999999996`).
- **`cerrar_posicion(..., qty=None)`**: si se le pasa la `qty` real persistida la usa; si es `None`
  (filas escritas antes de ago 2026) cae al cálculo teórico `monto_op / precio_entrada` y lo loguea.
- **`LOT_SIZE` está hardcodeado.** Verificado contra `/api/v3/exchangeInfo` el 2026-08-12: SOLUSDT
  decía 2 decimales y el `stepSize` real es `0.00100000` (3) — corregido. Los otros 4 estaban bien.
  Binance puede cambiarlos sin avisar; lo correcto sería leerlos al arrancar.
- **Comisiones:** `COMISION_SPOT = 0.001` (0.1% por lado, taker VIP0) se aplica **solo en
  SIMULADOR**, dentro de `_simular_fill()`, que ahora devuelve un array `fills` con la misma forma
  que Binance. En REAL la comisión se lee de la respuesta real. Antes el simulador no cobraba nada:
  el paper trading venía inflado ~0.2% por operación completa (386 ops, $7.909 de nocional, $15.82
  = 1.58 pp sobre el capital inicial).

> ⚠️ **No restaurar el simulador sobre `auditoria.csv` real.** El backup completo de esas 386
> operaciones de paper trading vive en
> `NUNCA_RESTAURAR_auditoria_simulador_386trades_2026-08-15.csv.bak` (raíz del proyecto).
> Si se sobrescribe `auditoria.csv` con ese archivo, el bot en REAL vería 386 operaciones
> históricas que nunca ocurrieron en Binance.

### `auditoria.csv` — 8 columnas, y dos estados nuevos

```
timestamp,accion,symbol,precio,rsi,estado,monto,qty
```

- El header tenía **6** columnas mientras las filas tenían 7 (faltaba `monto`). Corregido a 8.
- **`precio` ahora es el fill real de Binance**, no `cierres[-1]` (el cierre de la vela de 4h, que
  podía tener horas). SL, TP, breakeven y trailing se calculan sobre el precio al que se compró de
  verdad. Backup previo al cambio: `auditoria.csv.bak_prefix4`.
- **`qty` (8ª columna)** = `executedQty` **neto de comisión** del fill de entrada. Es la cantidad
  con la que se cierra. Filas viejas sin esa columna caen al cálculo teórico.
- Retrocompatible: los 33 módulos que leen el archivo usan `len(partes) >= N` e indexan 0..6.
  Agregar columnas al final no los rompe. **No insertar columnas en el medio.**
- **Estados nuevos: `RESERVADA` y `ANULADA`.** El flujo de apertura pasó a reservar antes de operar
  (commit `5b0e88e`):

```
reservar_operacion()  → fila RESERVADA, bajo AUDITORIA_LOCK, ANTES de mandar la orden
   ├─ falla la escritura → NO se opera (return). Nunca hay cripto sin registro.
   └─ ok → ejecutar_operacion()
             ├─ ❌ → _actualizar_fila(ANULADA)   ← se conserva como rastro de auditoría
             └─ ✅ → _actualizar_fila(ABIERTA, precio=fill["precio"], qty=fill["qty"])
```

  `contar_operaciones_abiertas()` cuenta **`RESERVADA` además de `ABIERTA`**: si el proceso muere
  entre la reserva y la orden, la fila huérfana frena compras nuevas en vez de habilitarlas.

### Reglas de oro del camino de dinero

1. **Escribir la fila ANTES de mandar la orden.** El bot decide leyendo `auditoria.csv`; si opera
   primero y anota después, un fallo al anotar hace que repita la operación.
2. **Todo append a `auditoria.csv` va bajo `AUDITORIA_LOCK`.** `revisar_cierres()` y
   `cerrar_huerfanas()` leen el archivo entero y lo reescriben con `os.replace`; una fila
   appendeada sin lock en medio de esa reescritura **se pierde**.
3. **Marcar el cierre ANTES de contabilizar, nunca al revés.** Si la contabilidad falla y la fila
   vuelve a `ABIERTA`, el ciclo siguiente re-vende una posición que ya no existe. Para eso está
   `_contabilizar()`, que envuelve `registrar_tp/sl` y nunca propaga la excepción: avisa por
   Telegram del descuadre y sigue. El `except` general tampoco devuelve la fila a `ABIERTA`
   (`nuevas_lineas.append(",".join(partes)...) if partes[5] != "ABIERTA" else linea`).
4. **Nunca salir en silencio después de haber operado.** `registrar_tp/sl` tenían un early return
   por `monto < $5` que no tocaba la billetera aunque la venta ya hubiera salido; ahora avisa.

### Polvo inmovilizado — punto abierto, no resuelto

Al cerrar hay que truncar al `stepSize` y el resto queda como cripto suelta. En BTC y BNB un tick
vale ~$0.62 y ~$0.59: sobre posiciones de $20 (`CAPITAL_MAX_POR_OP = 0.02` sobre $1.000) eso es
~3% por cierre. Medido el 2026-08-12: **$49.63 de cripto que no respalda ninguna posición abierta**
(4.6% del capital). BNB ($4.02) y AVAX ($0.33) están **debajo del `minNotional` de $5** — no se
pueden vender hasta que crezcan.

El polvo **no se pierde** (sigue en `billetera.json` y el guardián lo valoriza) pero se inmoviliza
y **distorsiona el PnL reportado por trade** hasta un 4%, que es lo que alimenta `memoria_propia`.

**No barrer el saldo completo dentro de `cerrar_posicion`**: eso realizaría el polvo viejo como
ganancia del trade en curso — reubica la distorsión en vez de eliminarla. El mecanismo correcto es
`auto_reconciliar()`, que barre **fuera** del ciclo de trades (punto 9, pendiente).

### `guardian_riesgo.py` — nunca decidir con datos incompletos (fix #7, ago 2026)

Commits `fa243ec` (C1) y `5c5c690` (C2+C3).

- **`_obtener_precio()` devuelve `None`, nunca `0.0`.** Antes, si fallaba la llamada, la moneda
  valía $0: el capital se hundía, se disparaba un drawdown inexistente y quedaba
  `bloqueado = True` en la DB — flag que **no se resetea nunca**.
  Qué tan cerca estaba: USDT libre $983.52, umbral de bloqueo $968.29, margen **$15.23**. Una
  posición normal es 2% = ~$19.67, así que con **una** posición abierta el margen desaparecía.
  Y los fallos de red no son teóricos: `memoria/telegram.log` tenía 40 errores de conexión, el
  último del 2026-08-11 (`Temporary failure in name resolution`).
- **`cargar_billetera()` levanta `DatosIncompletos`** (subclase de `RuntimeError`) si alguna
  moneda con saldo se quedó sin precio. `esta_bloqueado()` lo captura → pausa el ciclo. La
  diferencia clave: **no se persiste nada en la DB**, así que es transitorio. Cuando la red
  vuelve, el guardián autoriza solo.
- **Divisiones protegidas.** `max_hist` o `inicio_dia` en 0 levantan `DatosIncompletos` en vez de
  `ZeroDivisionError`.
- **`esta_bloqueado()` es fail-safe de verdad.** Antes capturaba solo `RuntimeError` **y** dejaba
  `verificar_riesgo()` fuera del `try`, así que el `ZeroDivisionError` mataba el ciclo entero del
  francotirador. Ahora `verificar_riesgo()` está dentro y se captura `Exception`.
- **Regla:** ante cualquier duda sobre los datos, pausar sin escribir estado. Un bloqueo
  persistido solo puede venir de un drawdown calculado con **todos** los precios disponibles.

### Camino de dinero — `reconciliar.py` (fix #9, ago 2026)

Commit `512c21c`. Barre el polvo del truncado al lot size (ver sección "Polvo inmovilizado").

- **Vende de verdad.** Antes hacía `billetera[moneda] = 0.0` y sumaba el USDT teórico **sin mandar
  ninguna orden**. En REAL: los libros decían USDT y la cripto seguía en la cuenta. Ahora usa
  `cerrar_posicion(qty=...)`; si Binance rechaza, la billetera **no se toca**.
- **Respeta los locks:** `billetera.json` bajo `signals/billetera.json.lock` reusando
  `gestor_billetera`, y `auditoria.csv` bajo `AUDITORIA_LOCK`.
- **Umbral por `minNotional` ($5 USDT).** Antes era `CANTIDAD_MINIMA = 0.000001`, una cantidad de
  cripto sin relación con lo que Binance acepta.
- **Barre `saldo − qty comprometida`,** no saltea la moneda entera si tiene posición abierta. Antes
  el polvo de un activo que se opera seguido no se limpiaba nunca. El barrido pasó de $16.98 a
  $40.67.
- **`RESERVADA` también protege.** Es un bug que introdujo el fix #5: entre `ejecutar_operacion` y
  `_actualizar_fila(ABIERTA)` la fila dice `RESERVADA` y la cripto **ya está comprada**. Mirando
  solo `ABIERTA`, el barrido la habría vendido.
- **Solo manual.** `auto_reconciliar()` fue **eliminado** y su llamada en `supervisor_v2.py`
  reemplazada por un comentario. Vende dinero real: no corre sin supervisión.
- Backups con sello temporal (antes el nombre era fijo y cada corrida pisaba el anterior).

### Pendientes — NO pasar a REAL antes de esto

Los 9 puntos del plan están cerrados. Lo que falta **no es código**:

- **Validación en testnet (bloqueante).** Nada de lo anterior se probó contra órdenes reales: todo
  fue SIMULADOR y sandbox. Correr el stack contra `testnet.binance.vision` y verificar que un
  ciclo abrir → SL → cerrar deja `billetera.json` cuadrado contra el saldo que reporta la API.
  Ese test habría detectado los bugs #3 y #4 solo, sin auditoría de por medio.
- **$7.56 inbarribles** en SOL/BNB/AVAX, por debajo del `minNotional`. Nada que hacer hasta que
  crezcan.
- **52 sesiones de screen** contra las 29 documentadas — duplicados de julio, sin limpiar.

## Pendiente futuro — Sistema de gestión estacional por comandos Telegram
Implementar después de validar REAL con 30+ trades. Comandos propuestos:
/pausar_[moneda] — detiene una moneda en meses históricamente malos
/activar_[moneda] — reactiva cuando llega mes favorable
/estado_estacional — muestra mes actual y comportamiento histórico de cada moneda activa
Basado en análisis de estacionalidad 2021-2025 guardado en reports/2026-08-13_estacionalidad.md
Meses malos confirmados: abril, mayo, junio (todas las monedas negativas en junio)
Meses buenos confirmados: julio, octubre
NO implementar antes de tener 30+ trades reales en REAL.

## Dirección de operación — SPOT solo-LONG (desde jun 2026)
- El bot opera **solo ALCISTA y LATERAL**. Los 5 francotiradores bajistas están desactivados.
- Razón: hacer SHORT es imposible en cuenta SPOT. En SIMULADOR generaba balances de cripto negativos (causa raíz de los negativos en billetera).
- Gate central: `gestor_bajistas.py` → `bajistas_activos()`. Cada `evaluar()` bajista lo consulta y retorna temprano si está desactivado.
- **Reactivación MANUAL (desde 2026-08-12, commit `c263fbd`, fix #8).** Exige **dos** condiciones:
  `BOT_BAJISTAS_CONFIRMADO=true` en el entorno del proceso **y** `availableBalance` USDT ≥ 5.0 en
  Futuros USDT-M. Sin la variable corta antes de consultar la API (ahorra una llamada por ciclo).
  Cachea 5 min; ante error de API → desactivado. Estado en `signals/estado_bajistas.json`.
  La variable sigue el patrón de `BOT_REAL_CONFIRMADO`: no vive en ningún archivo del repo, se
  exporta a mano el día que se decida — **después** de reescribir el ejecutor para futuros.
- **Antes bastaba el saldo:** fondear futuros por cualquier motivo, incluso ajeno a los shorts,
  reactivaba solos a los 5 francotiradores. Y fondear futuros **no habilita shorts reales** — la
  ruta de ejecución sigue siendo spot. Al momento del fix el gate estaba en `false` por accidente,
  no por diseño: el motivo registrado era `error_api: HTTP Error 401: Unauthorized` (la API key no
  tiene permiso de futuros). Si algún día lo tuviera, se habría reactivado solo.
- **Pendiente:** `ejecutor.py:cerrar_posicion` cierra shorts con BUY spot. Para shorts reales en futuros hay que reescribir el ejecutor — reactivar el gate no basta.
- **Evidencia (backtest 5.4 años, 4h):** `backtest_direccional.py` → `reports_historicos/backtest_direccional.json`. Desactivar bajistas sube WR +2.1 pp (40.7%→42.8%) y cuesta ~28 pp de PnL en 5.4 años descontando fees (≈cero). El PnL bajista bruto (+342 pp) descansa casi entero en AVAX; BTC/ETH/BNB bajistas son negativos tras fees. Si se reactivan en futuros, hacerlo **selectivo por activo**, no los 5 en bloque.

## Gestión de salidas vs gates de entrada (hallazgo jun 2026 — SOLO_SL jul 2026, extendido a los 6 gates ago 2026)
- En `evaluar()` de los 15 francotiradores, `revisar_cierres()` (que evalúa SL/TP de
  posiciones abiertas) se llama **después** de los 6 gates de entrada (guardian, termómetro,
  spread, horario, límite diario, eventos). Si cualquiera hace `return`, el SL/TP **no se
  evalúa** ese ciclo. En concreto, fuera de la ventana 4-21h (UTC-4) las posiciones quedan
  **hasta 7h sin stop activo**.
- Se evaluó moverlo antes de los gates. **Backtest (`backtest_gate_salida.py`, 1h 2023→hoy,
  5 laterales, ~30k velas, → `reports_historicos/backtest_gate_salida.json`):**
  - **FIXED** (gestionar salidas siempre): **−44.3 pp** con fees en 3.4 años vs el actual.
  - **SOLO_SL** (SL siempre 24h, TP solo en horario): **−10.6 pp** con fees (≈−3 pp/año).
  - Causa: no mirar de noche deja que trades que tocan SL reboten (mercado mean-reverting);
    corregirlo realiza más pérdidas y añade fees.
- **Decisión original (Ariel, jun 2026): NO cambiar el código** — el backtest histórico no
  mostraba mejora de PnL. El matiz pendiente: el backtest 1h **no captura** la protección de
  cola que SOLO_SL daría en vivo (el bot evalúa cada 60s; ante crash nocturno cortaría en ~1
  min en vez de esperar a las 4am).
- **Reconsiderado y aplicado (2026-07-29, commit `04b4074`, punto 2 de `CIERRE_FINAL.md`):**
  Ariel priorizó cerrar el riesgo de cola por sobre los ~3 pp/año de costo del backtest.
  `revisar_cierres()` de los 15 francotiradores ahora acepta `evaluar_tp=False`; cuando
  `puede_operar_horario()` corta, se llama igual con el SL activo (`evaluar_tp=False`) antes
  del `return` — el TP sigue exigiendo ventana horaria, el SL ya se evalúa 24h. Los otros 5
  gates (guardian, termómetro, spread, límite diario, eventos) no se tocaron.
- **Extendido a los 5 gates restantes (2026-08-12, commit `37fdf5b`, punto 2 de la auditoría
  pre-REAL):** guardian, termómetro, spread, límite diario y eventos también llaman
  `revisar_cierres(precio_actual, evaluar_tp=False)` antes del `return`. 75 inserciones en los
  15 francotiradores; el TP sigue exigiendo que pasen **todos** los gates.
  **Frecuencia medida** (`reports/2026-08-12_frecuencia-gates-salida.md`): eventos macro es el
  único recurrente — 153 min/día (10.6%), en las ventanas 13:15-14:45, 17:45-18:15 y
  19:45-20:15 UTC, o sea la franja CPI/Fed, la más volátil del día. Guardian: 0 disparos en 782
  snapshots (DD máx real 0.97%) pero su bloqueo es **permanente**. Límite diario: 1 día de 19.
  Spread: 0 disparos por spread real (el book de los 5 pares está siempre a 1 tick, entre 30x y
  30.000x bajo el límite de 0.48%) — en la práctica solo dispara ante fallo de la API.
  Costo estimado ~1.1 pp/año (extrapolación del backtest de julio, **no** backtest propio).
- **El termómetro está muerto desde marzo 2026.** Nadie llama `clasificar_mercado()` fuera del
  `if __name__ == "__main__"` del propio `termometro.py`; el estado en la DB tiene timestamp
  2026-03-04 y `puede_operar_termometro()` lee ese estado congelado, así que **siempre devuelve
  True**. Si alguien reconecta el módulo, pasaría a bloquear ~29.5% del tiempo de golpe
  (`MERCADO_MUERTO`). Por eso el fix se aplicó también ahí, aunque hoy sea inerte. Decidir si se
  conecta o se elimina es un punto abierto.
- **Verificado línea por línea en los 15 francotiradores (2026-08-18):** el patrón de arriba
  (`revisar_cierres(precio_actual, evaluar_tp=False)` antes de cada `return` de horario/eventos/
  guardián/termómetro/spread/límite diario, y `evaluar_tp=True` al final) se confirma exacto en
  14 de los 15 — incluidos los 5 bajistas, que además tienen un gate extra
  (`gestor_bajistas.bajistas_activos()`) como **primer** chequeo de `evaluar()`, antes que
  cualquier otro.
- **Gap encontrado y corregido el mismo día (2026-08-18, commit `e60a547`):** con bajistas
  desactivados (estado actual), los 5 bajistas retornaban en ese primer gate **sin llamar
  `revisar_cierres()` en absoluto** — a diferencia de horario/eventos, no protegía una posición
  bajista que quedara abierta mientras el gate siguiera en `False`. En la práctica no debería
  haber ninguna (los bajistas tampoco pueden abrir con el gate apagado), pero el código no la
  protegía de todos modos si alguna vez la hubiera. Corregido en los 5 (`bajista_btc/eth/sol/
  bnb/avax.py`) moviendo `fetch_velas()`/`precio_actual` antes del gate y llamando
  `revisar_cierres(precio_actual, evaluar_tp=True)` dentro de esa misma rama, antes del
  `return` — mismo patrón que ya usan horario/eventos en estos archivos (revisar salidas antes
  de cortar), sin llamada duplicada cuando el gate esté activo (la cadena normal de gates, más
  abajo, ya tiene sus propias llamadas a `revisar_cierres`). Mismo enfoque seguro que ya usaba
  `francotirador_lateral_eth.py` para su propia desactivación (ver excepción debajo).
  - **Excepción real: `francotirador_lateral_eth.py` no sigue el patrón — está desactivado por
    código, no solo por config, desde el 2026-08-13** (commit `8153b6d`, backtest forense PF
    0.90 — ver `project_forense_eth_alcista_lateral` en memoria persistente). `evaluar()` hace
    `return` incondicional en la línea 293, **antes** de llegar a `esta_bloqueado()` (295),
    `puede_operar_horario()` (307) o `puede_operar_eventos()` (315) — todo ese bloque queda
    inalcanzable. En su lugar, la línea 291 llama `revisar_cierres(precio_actual,
    evaluar_tp=True)` **una sola vez, sin ninguna condición** — más permisivo que el resto de los
    14 (ni SL ni TP quedan sujetos a horario/eventos/guardián/etc. para este francotirador
    específico, aunque en la práctica no importa porque tampoco abre posiciones nuevas). No es un
    bug: el propio comentario del código (línea 290) explica la intención — mantener
    `revisar_cierres` activo solo para proteger una posición que ya estuviera abierta al momento
    de desactivar la fase, sin la sobrecarga de evaluar los 6 gates de entrada que ya no importan
    si nunca se va a abrir un trade nuevo.

## Asimetría TP/SL en el registro de cierres (hallazgo jun 2026 — corregido jul 2026, superado por el fill real ago 2026)
- En `revisar_cierres()` de los **15 francotiradores** (alcista/bajista/lateral × 5 activos), el
  cierre por **SL se registra al precio teórico `sl_efectivo`, NO al `precio_actual` real**:
  `registrar_sl(precio_entrada, sl_efectivo, ...)` en las 3 ramas (BE, trailing, SL normal) y el
  aviso siempre reporta `-STOP_LOSS%` nominal. En cambio el **TP sí usa `precio_actual`**:
  `registrar_tp(precio_entrada, precio_actual, ...)`.
- **Consecuencia:** el PnL contable está sesgado **al alza** por ambos lados — ganancias reales
  (o mayores) en TP, pérdidas **topadas** al nominal en SL. En **SIMULADOR** es inocuo: el peor
  caso de un SL queda topado en `-STOP_LOSS%` aunque el precio real haya caído mucho más (ej. un
  gap nocturno con el monitoreo congelado fuera de la ventana 4-21h se contabiliza como -3.5% en
  BTC, no como la caída real). En **REAL** el registro a `sl_efectivo` es contabilidad ficticia:
  `cerrar_posicion` ejecutaría orden de mercado al precio real del gap (sin tope) pero los libros
  anotarían -SL% → riesgo de cola sin tope **y** PnL sobreestimado.
- **Corregido (2026-07-29, commit `ac3dcd0`, punto 1 de `CIERRE_FINAL.md`):** las 3 ramas de
  `revisar_cierres()` (BE, trailing, SL normal) en los 15 francotiradores ahora llaman
  `registrar_sl(precio_entrada, precio_actual, ...)` — igual que ya hacía `registrar_tp`. El
  aviso y el registro contable reflejan el precio real de cierre, no el nominal `sl_efectivo`.
  Aplicado junto con SOLO_SL (ver sección anterior), como estaba planeado.
- **Superado por el fix #4 (2026-08-12, commit `49b1e55`):** ya no se usa `precio_actual` (el
  cierre de la última vela) sino el **fill real que devuelve Binance**. Ver la sección
  "Camino de dinero" abajo — `registrar_tp/sl` reciben `qty` y `usdt` del fill.

## Oscilación de detectar_fase() — causa raíz y fix (jul 2026)
- **Síntoma:** en julio 2026, 96.7% de los trades LATERAL y 100% de los ALCISTA cerraban por FASE_CAMBIO,
  nunca por TP/SL — mediana de vida de una posición LATERAL: 5.2 minutos. Detalle en
  `reports/2026-07-12_analisis-cierres-fase-cambio-julio.md`.
- **Causa raíz:** `detectar_fase()` (`utils.py`) tiene hardcodeado `velas_7d=42` y `velas_30d=180`, válido
  solo si las velas son de **4h** (42×4h=7d, 180×4h=30d). `signals/modo.json` tenía `intervalo_velas:"1h"`,
  así que "7d" era en realidad 1.75 días y "30d" 7.5 días — un detector calibrado para tendencias de
  semanas reaccionaba a swings de 1-8 días. Confirmado empírico corriendo `detectar_fase()` real sobre
  velas reales: con 1h la fase global cambia 1.49/día (dura 16h); con 4h, 0.40/día (dura 60.5h) — ~4x menos
  oscilación. Detalle en `reports/2026-07-12_causa-oscilacion-detectar_fase.md`.
- **Fix aplicado (2026-07-12):** `modo.json` → `intervalo_velas:"4h"`, `sleep_segundos:240`. No se tocó
  `utils.py` ni las constantes — el desajuste era de configuración, no del algoritmo.
- **Hallazgo colateral resuelto el mismo día:** se encontraron **todos** los screens del stack duplicados
  (una tanda desde las 13:43, otra desde las 20:22 del 2026-07-12). Solo se depuró `v2_main` (pedido
  explícito) — el resto de los duplicados (`z_diagnostico`, `z_executor`, `z_webserver`, etc., tanda 13:43)
  **sigue sin limpiar**, a la espera de instrucción explícita ítem por ítem (no asumir "limpiar duplicados"
  como autorización en bloque). Detalle en `reports/2026-07-12_fix-duplicado-y-modo-4h.md`.

## TRAILING_DISTANCIA y SL — backtests jul 2026 (NO cambiar sin re-decidir)
- **Por qué ningún trade llega a TP limpio:** con `TRAILING_ACTIVACION=0.5%` y `TRAILING_DISTANCIA=1.0%`,
  el trailing exige que el precio nunca retroceda >1% desde su máximo mientras recorre 4-7 pp hasta el TP —
  casi imposible en cripto. Backtest de 13 posiciones reales dejadas correr sin límite: ninguna superó 77%
  del camino al TP. Detalle en `reports/2026-07-13_por-que-nunca-llega-a-tp.md`.
- **Backtest largo (2021-2026, ~10k trades, entrada simplificada = fase 4h + RSI, sin replicar spread/
  horario/eventos/calidad/multitf/memoria — ver metodología completa en el reporte):**
  `TRAILING_DISTANCIA` 1% (actual) vs 1.5% vs 2% vs 3%, SL/TP sin cambiar:
  - WR y % de TP limpio **suben** con trailing más ancho: WR 55.3%→62.9%, TP limpio 5.5%→19.0% (1%→3%).
  - PnL total y drawdown **empeoran** con trailing más ancho: retorno +186.2%→+91.3%, DD máx 1.12%→1.94%
    (capital compuesto $1,000, 2%/trade). Causa: trailing angosto genera ~1.7x más trades/año (recicla el
    slot de `MAX_OP_TOTAL=1` más rápido), y ese volumen pesa más que la calidad por trade.
  - **No hay un óptimo único** sin definir qué se prioriza (throughput total vs. WR/menos whipsaw).
  - DD medido es una cota optimista: hereda el sesgo de "Asimetría TP/SL" (SL registra precio teórico, no
    real) — un gap real (LUNA, FTX) daría más drawdown del que este backtest puede ver.
  - Detalle: `reports/2026-07-13_backtest_trailing_2021-2026.md` y
    `reports/2026-07-13_drawdown_maximo_por_escenario.md`.
- **SL uniforme 3.0% vs SL actual (3.5-5.0% según símbolo), mismo backtest, trailing 1%:** SL 3% **empeora**
  los tres ejes — WR 55.3%→53.6%, retorno +186.2%→+167.2%, DD máx casi sin cambio (1.12%→1.00%, $0.29 de
  diferencia). **No se justifica bajar el SL a 3%.** Detalle: `reports/2026-07-13_backtest_sl_actual_vs_sl3.md`.
- **Decisión: documentado, sin implementar ningún cambio de TRAILING_DISTANCIA ni SL.** Antes de tocar
  código: correr con capital compuesto real (no suma simple de %) y con los filtros de producción que este
  backtest no replicó, y decidir explícitamente qué se optimiza (PnL total vs. calidad/WR).

## memoria_propia.json no se actualiza — causa raíz ligada a FASE_CAMBIO (hallazgo jul 2026, NO corregido)
- **Síntoma:** `data/memoria_propia.json` dejó de actualizarse el 2026-07-17 08:35:05.
- **Causa raíz:** `actualizar_memoria()` (`memoria_propia.py`) solo se llama desde
  `revisar_cierres()` de los 15 francotiradores, tras un cierre TP/SL/BE/TRAILING_SL. El último
  cierre de ese tipo fue el 2026-07-14. Desde entonces, ~91% de los cierres pasan por
  `cerrar_huerfanas()` en `director_orquesta.py` (cierre por cambio de fase, estado
  `FASE_CAMBIO`), que nunca importa ni llama a `actualizar_memoria()`.
- **Segunda capa, más de fondo:** aunque se agregara esa llamada, `analizar_historial()` filtra
  solo `estado in ("TP","SL","TRAILING_SL","BE")` — ignora `FASE_CAMBIO` por completo. Además,
  `auditoria.csv` no guarda si un `FASE_CAMBIO` fue ganador o perdedor: `cerrar_huerfanas()`
  sobreescribe el campo `estado` de la fila pero nunca actualiza `precio` ni `timestamp` (quedan
  con los valores de apertura), así que el resultado de cada cierre por fase no está persistido
  en ningún lado en forma directa.
- **Backtest de impacto (2026-07-23, reconstrucción cruzando `auditoria.csv` con
  `historial_billetera.csv` por huella de cantidad — `reports/2026-07-23_backtest_fase_cambio_en_memoria.md`):**
  - Hoy el filtro `puede_operar_memoria()` está **completamente inerte**: con solo 32 trades
    TP/SL reales repartidos en 5 símbolos, ninguno alcanza `MIN_TRADES=15` — todas las entradas
    pasan con factor 1.0.
  - Si se incluyera `FASE_CAMBIO` en el aprendizaje, los 5 símbolos cruzarían el umbral de
    golpe: BTC/ETH/SOL quedarían al factor 0.6 (WR reconstruido ~44-48%), BNB al factor 0.8 (WR
    ~58%), y **AVAX quedaría bloqueado por completo** (WR reconstruido 33.3%, debajo del piso de
    40%).
  - Confianza del backtest: moderada, no alta — el WR de cada `FASE_CAMBIO` se reconstruyó
    cruzando datos (no hay ground truth directo), validado 7/7 contra los pocos casos con dato
    conocido, pero es muestra chica. El período coincide con los screens duplicados encontrados
    el mismo día (dos instancias de `v2_main` corriendo en paralelo), posible fuente de ruido
    adicional. La dirección del hallazgo (inerte hoy → bloquearía AVAX si se incluye) es
    confiable; el número exacto de WR no debería tratarse como definitivo.
- **Fix mínimo aplicado (2026-07-23):** `director_orquesta.py:cerrar_huerfanas()` ahora importa y
  llama `actualizar_memoria(symbol, cambio)` tras cada cierre por `FASE_CAMBIO`, igual que ya
  hacían los francotiradores tras un TP/SL/BE/TRAILING_SL. Esto solo restaura el refresco de
  `data/memoria_propia.json` (vuelve a actualizarse en cada cierre) — **no** cambia qué cuenta
  `analizar_historial()` como trade válido, sigue filtrando solo
  `estado in ("TP","SL","TRAILING_SL","BE")`. Con los 32 trades reales actuales ningún símbolo
  llega a `MIN_TRADES=15`, así que hoy este fix no cambia ningún factor de `puede_operar_memoria()`
  — solo mantiene el archivo fresco.
- **Pendiente, NO aplicado:** incluir `FASE_CAMBIO` en `analizar_historial()`. Se retoma cuando se
  ataque la causa raíz de por qué el 91% de los cierres son `FASE_CAMBIO` en vez de TP/SL real
  (ver sección "TRAILING_DISTANCIA y SL" y "Oscilación de detectar_fase()" arriba). Si en ese
  momento se decide sumarlo, persistir el precio de salida real en `auditoria.csv` al momento del
  cierre en vez de reconstruirlo después (hoy `cerrar_huerfanas()` no actualiza `precio` ni
  `timestamp` al cerrar, por eso hubo que reconstruir vía `historial_billetera.csv` para el
  backtest).

## Auditoría de gates de entrada — serie completa (ago 2026)

Serie de 20 auditorías de solo lectura sobre los gates de entrada de los 3 francotiradores
activos hoy (**BTC ALCISTA**, **ETH ALCISTA**, **SOL LATERAL**), en dos tandas: ventana corta
(2026-01-01→08-17) y, para los gates reconstruibles con solo precio, ventana extendida (BTC/ETH
2017-2026 ~9 años, SOL 2020-2026 ~5.9 años — la misma historia usada para calibrar los
parámetros de cada francotirador, así que **no es validación out-of-sample**, es caracterización
histórica completa). Ningún archivo de producción tocado, ningún commit de los scripts (quedan en
scratchpad de sesión) ni de los reportes (`reports/` no se commitea). Metodología base: recalcular
`raw_signal` de forma independiente (mismas fórmulas reales de `utils.py`, sin reimplementar) para
aislar qué llamadas a un gate correspondían a una señal que de verdad habría abierto trade, y
simular cada señal bloqueada con `revisar_cierres()` literal.

**Hallazgo transversal más importante de toda la serie: los resultados con muestra chica (n<30)
tienden a diluirse o revertirse con más datos.** No tratar ningún hallazgo de esta serie con n<30
como concluyente sin revisar si ya se hizo (o se puede hacer) la versión con ventana extendida.

### Por gate

| Gate | Impacto real medido | Reporte |
|---|---|---|
| `gestor_correlacion` (componente `trades_misma_dir`) | Matemáticamente inalcanzable con solo 3 francotiradores activos (máximo teórico 1, umbral de bloqueo 2) | `2026-08-18_auditoria-correlacion.md` |
| `gestor_correlacion` (componente fase-BTC-macro) | 0/61 bloqueos reales en la ventana corta — BTC/ETH nunca tuvieron señal propia coincidiendo con BTC macro bajista | `2026-08-18_auditoria-correlacion.md` |
| `filtro_horario` | Determinista (bloquea la vela de 00:00 hora local, 1/6 del tiempo). Confirmado neutro con muestra grande (502-1078 señales/moneda, 9 años): diferencias de solo −2.5pp a +0.4pp vs. WR real | `2026-08-18_auditoria-horario-limitador.md`, extendido en `2026-08-18_auditoria-horario-limitador-extendido.md` |
| `limitador_diario` (límite diario) | **0 bloqueos en 11,536 señales evaluadas, hasta 9 años y 909 trades reales combinados.** Máximo real de cierres el mismo día: 4 (vs umbral 8); racha máx. de SL seguidos: 3 (vs umbral 4). El gate más inerte de la serie | `2026-08-18_auditoria-horario-limitador-extendido.md` |
| `medidor_spread` | **NO reconstruible con datos históricos** (Binance no da bid/ask histórico, sin logs propios). Hallazgo aparte: `SPREAD_MAXIMO` es una constante fija 0.48% para las 5 monedas — el nombre `TP_PCT` sugiere que debería ser dinámico por francotirador, pero no lo es | `2026-08-18_auditoria-spread.md` |
| `termometro` | Congelado desde marzo 2026 (verificado en vivo) → 0 impacto real. Si se reconectara: bloquearía ~32% del tiempo con efecto **mixto** (protegería a BTC, sería contraproducente en ETH) | `2026-08-18_auditoria-termometro-guardian.md` |
| `guardian_riesgo` | No reconstruible para el 66% de la ventana pedida (sin datos ene-may 2026). Tramo con datos: margen 10x-17x de los límites, nunca bloqueó | `2026-08-18_auditoria-termometro-guardian.md` |
| `filtro_eventos` | Solo detecta bloqueo en la vela 20:00-00:00 UTC por un problema de granularidad (evalúa 1 vez por vela 4h, producción sondea cada 4 min) — es, paradójicamente, la vela con *menor* overlap real (6.2%) de las 3 afectadas | `2026-08-18_auditoria-eventos.md` |
| `filtro_calidad` | **Hallazgo más citado de la serie, revertido con más datos**: SOL LATERAL "protegía" con WR 16.7% (n=36, solo 2026) — con 9x más datos (n=959, 2020-2026) da WR 47.9%, prácticamente neutro. BTC también converge a neutro (47.4% vs 48.3%). Solo ETH invierte de signo, moderado (52.2% vs 57.2%) | `2026-08-18_auditoria-filtro-calidad.md`, revertido en `2026-08-18_auditoria-filtro-calidad-extendido.md` |
| `filtro_estadístico` | Único motivo real de bloqueo: `racha==5` (incondicional). **Techo estructural de muestra** — ni con 9 años de historia ninguna moneda individual cruza n=30 (BTC=19, ETH=15, SOL=7) | `2026-08-18_auditoria-filtro-estadistico.md`, extendido en `2026-08-18_auditoria-estadistico-memoria-extendido.md` |
| `memoria_propia` | Único motivo real: `racha_mala` (`perdidas_ultimos_5>=3`, cross-symbol). Puede quedar congelado en el peor valor semanas si escasean cierres reales (episodio de 60 días abr-jun 2026 ya documentado abajo). **No extendible**: backup de trades reales arranca 2026-03-01, no hay dato anterior. BTC (n=57) y SOL (n=84) ya tenían muestra suficiente; ETH (n=9) no, y no hay forma de subirlo hoy | `2026-08-18_auditoria-memoria-propia.md`, extensión evaluada en `2026-08-18_auditoria-estadistico-memoria-extendido.md` |
| `multitimeframe` (ETH específicamente) | Hallazgo repetido 3 veces con WR 100% (n=10-12) **no se sostuvo** con 9 años de datos: n=104, WR real 63.5% vs. 57.2% de producción — misma dirección, magnitud mucho menor | `2026-08-18_auditoria-multitimeframe.md`, revertido en `2026-08-18_auditoria-eth-multitimeframe-extendido.md` |

### Matriz de solapamiento entre gates (10 de 10 pares posibles)

Se evaluaron los 5 gates que pueden bloquear una señal antes del chequeo RSI+EMA final
(`horario`, `multitimeframe`, `calidad`, `estadístico`, `memoria`) de forma **independiente**
entre sí (bypaseando el orden real de producción) para medir si tienden a bloquear las mismas
señales. Ninguno de los 10 pares mostró redundancia sistemática — todas las razones
observado/esperado (bajo independencia estadística simple) quedaron entre 0.76 y 1.43.

| Par | Razón obs/esp | Reporte |
|---|---|---|
| horario × multitimeframe | 1.04 | `2026-08-18_auditoria-horario-multitimeframe-solapamiento.md` |
| calidad × estadístico | 0.70 (corta) / 0.91 (9 años) | `2026-08-18_auditoria-calidad-estadistico-solapamiento.md` |
| multitimeframe × memoria | 0.76 | `2026-08-18_auditoria-multitimeframe-memoria-solapamiento.md` |
| horario × calidad | 1.08 | `2026-08-18_auditoria-pares-solapamiento-restantes.md` |
| horario × estadístico | 1.20 (n chico) | ídem |
| **multitimeframe × calidad** | **1.23 agregado, 2.23 en BTC** | ídem — causa raíz abajo |
| multitimeframe × estadístico | 0.77 (n chico) | ídem |
| horario × memoria | 1.08 | ídem |
| calidad × memoria | 1.10 | ídem |
| estadístico × memoria | 1.43 (n=11, no concluyente) | ídem |

**Único hallazgo con sustancia: `multitimeframe×calidad` en BTC específicamente (razón 2.23,
no replica en ETH ni con la misma fuerza en SOL).** Causa raíz encontrada y verificada
(`2026-08-18_investigacion-mtf-calidad-btc.md`): `filtro_calidad.señal_tiene_calidad()` y
`detector_multitimeframe.detectar_tendencia(..., "4h")` comparten, **sin coordinarse**, el mismo
chequeo de alineación EMA20/EMA50 **hardcodeado** en fase ALCISTA (ninguno de los dos lee el
`EMA_CORTA`/`EMA_LARGA` real del francotirador que los llama). BTC ALCISTA usa EMA20/EMA50 como su
propia condición de entrada — coincide exacto con el hardcode. ETH ALCISTA usa EMA20/**EMA100** —
no coincide. Verificado con datos: de las 246 señales BTC bloqueadas por ambos gates, **59.8%**
son por "EMAs no alineadas" (vs. 9.8% cuando calidad bloquea sola — 6x más frecuente); en ETH ese
motivo aparece en **0%** de las 6 señales compartidas. El régimen de mercado que dispara
multitimeframe (1h/4h/1d en LATERAL, MACD negativo 4h y 1d) es idéntico en ambas monedas — lo que
cambia es si ese régimen también hace fallar el chequeo EMA hardcodeado de calidad, y eso depende
solo de qué EMA larga usa la entrada propia de cada francotirador. **No es un bug** (ambos gates
funcionan como están diseñados) pero es una nota para el futuro: si algún día se cambia el
`EMA_LARGA` de un francotirador ALCISTA, el grado de solapamiento entre estos dos gates cambia con
él, sin que nadie lo haya pedido — y el mismo patrón (dos gates que comparten un parámetro
hardcodeado en vez de leer el del francotirador que los llama) podría repetirse en otros pares no
auditados con este nivel de detalle.

**Segunda causa raíz encontrada — `horario×calidad` (razón 1.06-1.13, consistente en las 3
monedas)**, esta vez sin código compartido: `filtro_horario` es función pura de reloj, no toca
precio (`2026-08-18_investigacion-horario-calidad-estadistico.md`). La correlación viene de un
**artefacto de indexación**: `filtro_calidad.señal_tiene_calidad()` mide volumen con
`vol_actual = velas[-2]` (la vela **cerrada anterior**, a propósito, "para evitar falsos bajos en
vela en curso"). Cuando la señal cae en la vela de las 04:00 UTC (la que bloquea `filtro_horario`,
distinta de la de eventos), esa vela es `velas[-1]` y `velas[-2]` termina siendo la de las
**00:00 UTC** — verificado con datos reales de mercado (no solo señales) que es, consistentemente
en BTC/ETH/SOL, una de las dos horas de menor volumen relativo del día (~0.88 vs. promedio diario
~1.0-1.4, junto con 16:00 UTC — la propia vela de 04:00 tiene volumen prácticamente promedio, no
es floja ella misma). Confirmado numéricamente: en las 3 monedas, calidad bloquea más seguido
cuando la señal cae en la vela horario-bloqueada (+3.4 a +4.1pp) y, dentro de esas, "volumen bajo"
es proporcionalmente mucho más frecuente (51.6%-56.4%) que en el resto (34.8%-43.6%). El par
`horario×estadístico` (racha==5) muestra la misma dirección en BTC/ETH pero **no en SOL** — no se
encontró un mecanismo tan sólido como el del volumen, queda parcialmente explicado. **Tampoco es
un bug** — `velas[-2]` es una decisión de diseño razonable; el efecto secundario de heredar
ocasionalmente el volumen de una hora floja es una curiosidad, no un error, y la magnitud es
demasiado chica para tocar nada. **Patrón a tener en cuenta hacia adelante**: van dos veces en
esta serie que dos gates aparentemente sin relación correlacionan por un motivo de implementación
no obvio (hardcode compartido en un caso, indexación de vela adyacente en el otro) — al investigar
cualquier correlación nueva entre gates, buscar primero un mecanismo de código antes de asumir que
es una relación de mercado genuina.

**No se recomienda ningún cambio de producción como consecuencia de esta serie.**

## Telegram
- Admins: ADMIN_YAYO (6578945006), ADMIN_SOCIA (6533031969)
- Token en `keys.env` como `TELEGRAM_BOT_TOKEN` — **ese es el nombre exacto de la clave, todos los módulos deben leerlo así**.
- El bot responde comandos vía polling en `brain/telegram_engine.py`.
- **Dos rutas de salida a Telegram, no confundir:**
  - `brain/telegram_engine.py` → polling de comandos y respuestas (`/status`, etc.).
  - `engine.py:enviar_aviso()` → **avisos de trades** (entradas, TP, SL, errores de cierre). Lo usan los 15 francotiradores y `director_orquesta`.
- **Bug histórico (jun 2026):** `engine.cargar_token()` buscaba `TELEGRAM_TOKEN=` (clave inexistente) en vez de `TELEGRAM_BOT_TOKEN=`, así que los avisos de trades nunca salían — se abrían posiciones sin notificación. El polling sí funcionaba porque leía la clave correcta. Corregido.
- **Log de fallos:** `engine.enviar_aviso()` registra cualquier fallo de envío en `memoria/telegram.log` (token ausente, rechazo de la API con `ok:false`, o excepción de red). Antes solo se imprimían al stdout del screen y se perdían. Si no llega un aviso, revisar **primero** ese archivo. Si está vacío, el envío salió bien y el problema es del lado de Telegram/cliente.
- **Comandos que mueven dinero o estado, patrón de dos pasos** (ago 2026): sin argumento muestran
  un previo que **no toca nada**; solo con `confirmar` como segunda palabra ejecutan. Ambos están
  admin-gateados por el chequeo al tope de `procesar_comando`.
  - `/reconciliar` → previo del polvo vendible · `/reconciliar confirmar` → vende en Binance.
  - `/desbloquear` → estado del guardián · `/desbloquear confirmar` → levanta el bloqueo.
    **Ojo:** desbloquear **rebasea `capital_maximo_historico` al capital actual**. Es a propósito:
    si solo se apagara el flag, `verificar_riesgo()` compararía contra el mismo pico y bloquearía
    de nuevo en el ciclo siguiente. La contrapartida es que se pierde la referencia del pico
    anterior y el drawdown se cuenta desde el capital del momento. Queda huella en
    `estado_riesgo.desbloqueo` con timestamp, motivo y estado previo.
- **`/cerrar` no cerraba nada (bug encontrado y corregido el 2026-08-12, commit `49b1e55`):**
  `cerrar_operacion_manual()` marcaba la fila como `MANUAL_WIN`/`MANUAL_LOSS`, calculaba una
  ganancia y la reportaba — pero **nunca llamaba a `cerrar_posicion` ni tocaba
  `billetera.json`**. En SIMULADOR era cosmético; en REAL apretabas "🚪 Salir", el bot
  contestaba que cerró con +$X y la cripto seguía en la cuenta, ya fuera del estado `ABIERTA`
  que vigila `revisar_cierres` — posición sin stop y sin registro. Ahora manda la orden real,
  deja la posición `ABIERTA` si Binance la rechaza, y contabiliza con el fill.

## Investigación de estrategia de entrada — ago 2026

Sesión exhaustiva de backtesting sobre datos históricos reales (2017-2026, 18,677 velas 4H por activo).
Reportes completos en `reports/backtest_*.json`. Resumen de evidencia acumulada:

### Lo que se probó y descartó (con evidencia)
- RSI solo (cualquier rango) → PF máx 1.60, insuficiente
- RSI + EMA20 → idéntico a RSI solo, EMA no filtra nada adicional
- RSI + RSI semanal → PF 2.61 pero solo 7 trades/año, inviable
- RSI + BTC semanal EMA200 → PF 1.58, empeora el resultado
- FASE_CAMBIO eliminado → WR cae a 41.4%, PnL -$25 vs +$45 real. FASE_CAMBIO protege capital.

### Hallazgo crítico — FASE_CAMBIO
FASE_CAMBIO no es el enemigo. Con 376 cierres generó +$45 real vs -$25 simulado sin él.
El problema no está en las salidas sino en las entradas.

### Mejor combinación encontrada con evidencia
**BTC: RSI 65-80 + momentum 3de4 + cuerpo vela <40%**
- PF: 2.12 | WR: 29.7% | T/mes: 1.5

**ETH: RSI 70-80 + momentum 3de5**
- PF: 1.93 | WR: 19.5% | T/mes: 1.9

### Anatomía TP vs SL (evidencia de 9 años)
Las entradas ganadoras tienen consistentemente:
- Cuerpo de vela de entrada < 50% (consolidación, no euforia)
- Volumen relativo menor (1.59-1.88 vs 1.78-1.91 en perdedoras)
- Precio no sobreextendido en últimas 20 velas

### Limitación real con $20 de capital
Con 1% de riesgo por trade y mejor configuración BTC:
- Ganancia: $0.48-$0.66/mes
- Para generar $2-3/mes se necesita capital de $200-300
- El bot es rentable — el límite es el capital inicial, no la estrategia

### Fondeo.xyz — criterios reales (verificados ago 2026)
- One-Step: WR ≥50%, profit target 10%, drawdown diario 5%, max loss 10%, **mínimo 3 trades/DÍA**
- Subscription $49/mes: sin WR mínimo, sin profit target, sin mínimo trades/día — solo no violar drawdown 10%
- Opera en Bybit (no Binance) — requeriría adaptar el bot
- El bot actual hace ~3 trades/MES, incompatible con One-Step (3/día)
- Modelo Subscription es el único compatible con la frecuencia actual

### Plan acordado
1. Depositar $20 en Binance y activar REAL pasado mañana (ago 2026)
2. Operar con configuración actual del bot — no implementar nuevos filtros sin backtest aprobado
3. Reinvertir ganancias para crecer el capital gradualmente
4. Escalar cuando se confirme rentabilidad real

### Comandos para activar REAL
```bash
screen -r v2_main
export BOT_REAL_CONFIRMADO=true
echo '{"modo":"REAL","intervalo_velas":"4h","sleep_segundos":240}' > ~/bot-padre-v2/signals/modo.json
```

## Investigación de parámetros BNB ALCISTA — ago 2026

> **Estado actualizado (2026-08-15, commit `349b53c`):** el candidato `RSI 60–68 / SL 4.5% /
> TP 6.5%` descrito en esta sección como "🟡 PROMETEDOR" pasó a ser la configuración de
> **producción real** en `config_cartera.py` y `francotirador_alcista_bnb.py` al activar el
> modo REAL con $8.54 USDT. Los veredictos "🟡 PROMETEDOR" y "no autoriza cambio a producción"
> de esta sección describen el estado de la investigación **antes** de esa activación — se
> conservan como registro histórico. Los 30+ trades reales que las pruebas piden como umbral
> se cuentan **desde el 2026-08-15**.

### Hallazgo de robustez (2026-08-13)

Análisis de sensibilidad sobre 10 combinaciones vecinas al candidato `RSI 60–68 / SL 4.5% / TP 6.5%`.
9 de 10 combinaciones validan positivo en 2024–2026 → **zona robusta confirmada**.
Reporte: `reports/2026-08-13_robustez-bnb-alcista.md`.

| Config | PF val 2024–2026 | Capital | Nota |
|--------|-----------------|---------|------|
| **ACTUAL producción** (60–75/4.5/5.0) | 1.057 | $20.77 | ✅ |
| **Candidato** (60–68/4.5/6.5) | 1.078 | $20.93 | ✅ |
| Mejor vecino (65–68/4.5/6.5) | 1.385 | $22.72 | ✅ destacado |
| RSI-min 55 | 0.973 | $19.61 | ❌ único negativo |

~~**Hallazgo BTC macro (2026-08-13, INVALIDADO por backtest aislado 2026-08-14):**~~
~~señales BNB cuando BTC está *bajo* su EMA200 semanal tienen WR 58.1% y PF 1.856.~~
Ver sección siguiente.

**Estado:** solo investigación. No se modificó config_cartera.py ni ningún francotirador.
Cualquier cambio de parámetros requiere OK explícito de Ariel.

### Backtest aislado filtro BTC/EMA200w (2026-08-14) — resultado invalidado

Reporte: `reports/2026-08-14_filtro-btc-ema200w-bnb.md`. Commit: `8dcd302`.

| Escenario | Trades val 2024 | Trades val 2025 | Veredicto |
|-----------|-----------------|-----------------|-----------|
| SIN FILTRO | 51 | 37 | — (base) |
| BTC SOBRE EMA200w | 51 (= SIN FILTRO) | 37 (= SIN FILTRO) | ⚪ C) No aporta mejora |
| BTC BAJO EMA200w | **0** | **0** | ⚠️ Evidencia insuficiente |

**Causa:** BTC estuvo sobre su EMA200w el **100% del tiempo** en 2024 y 2025.
- El filtro SOBRE no descarta ninguna señal en validación → idéntico a SIN FILTRO.
- El filtro BAJO no genera ningún trade en validación → no evaluable out-of-sample.
- Los 31 trades "bajo EMA" con WR 58.1% eran **100% in-sample** del bear market 2021–2023.

**Conclusión:** filtro BTC/EMA200w descartado como mejora. Para reevaluar se necesita
que BTC vuelva a operar bajo su EMA200w durante suficiente tiempo (≥10 trades).

### Estabilidad anual y rolling walk-forward (2026-08-14) — resumen acumulado

Reportes: `reports/2026-08-14_estabilidad-anual-bnb.md`, `reports/2026-08-14_rolling-bnb-alcista.md`.
Commits: `b4a8f6e`, pendiente.

**Estabilidad anual 2021–2025 (5 años, todos válidos ≥10 trades):**

| Métrica | Producción | Candidato |
|---------|-----------|-----------|
| Años ganados | 2/5 | **3/5** |
| PF promedio | 1.106 | **1.240** |
| Expectancy promedio | +$0.0115 | **+$0.0284** |
| Capital promedio | $20.78 | **$21.25** |
| DD promedio | 8.7% | **7.1%** |

- PF candidato > 1.0 en 4/5 años (80%)
- PF candidato > PF producción en 4/5 años (80%)
- Expectancy candidato > 0 en 4/5 años (80%)
- DD candidato ≤ DD producción en 4/5 años (80%)
- **Veredicto: 🟡 B) PROMETEDOR PERO INSUFICIENTEMENTE CONSISTENTE**
  Hay un año negativo (candidato PF < 1.0) que impide declarar robustez plena.

**Rolling walk-forward 24m/12m (ventanas 2023/2024/2025):**
- Candidato gana 2/3 ventanas · PF prom 1.297 vs 1.133 · Expect +$0.0343 vs +$0.0143
- **Veredicto: 🟡 B) PROMETEDOR PERO INSUFICIENTE** (solo 3 ventanas disponibles)

**Cuadro acumulado de evidencia BNB candidato (RSI 60–68 / SL 4.5% / TP 6.5%):**

| Estudio | Veredicto | Detalle |
|---------|-----------|---------|
| Robustez vecindad (10 combinaciones) | Zona amplia | 9/10 positivos en val 2024–2026 |
| Walk-forward 3yr/1yr (2 ventanas) | **A) ROBUSTO** | 2/2 ventanas positivas, PF 1.185 vs 1.137 |
| Walk-forward 24m/12m (3 ventanas) | **B) PROMETEDOR** | 2/3 ventanas ganadas, PF 1.297 vs 1.133 |
| Estabilidad anual 2021–2025 | **B) PROMETEDOR** | 3/5 años, 4/5 (80%) con PF>1 y exp>0 |
| Filtro BTC/EMA200w | Descartado | In-sample; 0 trades en validación 2024–2025 |

### Análisis de significancia y robustez (2026-08-14)

Reporte: `reports/2026-08-14_bnb-alcista-significancia-robustez.md`. Commit: `f11290e`.

**Consistencia anual (5 años válidos, 2021–2025):**
- PF > 1.0: **5/5 años (100%)**
- Expectancy > 0: **5/5 años (100%)**
- DD ≤ producción: 4/5 años (80%)
- Supera en expectancy: 4/5 años (80%)
- Gana en capital: 3/5 años (60%)

**Bootstrap 10,000 muestras:**
- P(diff > 0): 72.0% — no es concluyente (umbral orientativo ~85%)
- IC 95%: [−$0.029, +$0.056] — **cruza cero** → varianza aleatoria no descartable
- Limitación: trades serialmente dependientes → bootstrap subestima varianza real.
  No interpretar como prueba estadística formal.

**Sensibilidad de vecindad (6 vecinos, 2021–2025):**
- **6/6 vecinos** con PF > 1.0 → zona robusta total, candidato no es pico aislado

**Veredicto: 🟡 B) PROMETEDOR** (igual en los 6 estudios independientes)
El IC95 del bootstrap cruza cero y solo gana 3/5 años en capital — evidencia
insuficiente para A sin trades reales.

### Prueba controlada en SIMULADOR — ene–ago 2026 (2026-08-14)

Reporte: `reports/2026-08-14_bnb-alcista-prueba-simulador.md`. Commit: `a6d366f`.
Datos reales Binance API · Script aislado · **0 archivos de producción tocados.**

| Métrica | Producción | Candidato | Δ |
|---------|-----------|-----------|---|
| Trades | 20 | 19 | −1 |
| WR | 40.0% | 31.6% | −8.4 pp |
| Expectancy | −$0.0450 | −$0.0613 | −$0.016 |
| PF | 0.681 | 0.619 | −0.062 |
| Capital | $19.10 | $18.84 | −$0.26 |
| DD máx | 8.0% | 8.8% | +0.8 pp |

**Resultado:** ambos sistemas negativos en 2026 ene–ago. Producción gana levemente.
Consistente con los backtests: 2026 tiene muestra insuficiente y ambos pierden en ese período.
No invalida el cuadro histórico 2021–2025 (candidato PF>1 en 5/5 años).

**Conclusión consolidada:** evidencia múltiple e independiente apunta a una mejora real
del candidato sobre producción en el período 2021–2025. En 2026 ambos sistemas son negativos.
El freno al veredicto A es un año negativo en el histórico, IC95 bootstrap cruzando cero
y que 2026 no favorece a ninguno de los dos.
**Siguiente paso: activar REAL y acumular 30+ trades reales.**
No autoriza ningún cambio a producción.

### Análisis acumulativo ampliado — trades compartidos/exclusivos y desglose mensual (2026-08-14)

Reporte: `reports/2026-08-14_bnb-alcista-acumulativo.md`. Commit: `fb63738`.
Script: `forward_bnb_analisis.py` — analiza los 20/19 trades del simulador previo sin re-simular.
**0 archivos de producción tocados.**

**Trades compartidos vs exclusivos:**

| Categoría | Trades | TP | SL | P/L acum |
|-----------|--------|----|----|----------|
| Compartidos — Producción | 15 | 6 | 9 | −$0.675 |
| Compartidos — Candidato  | 15 | 6 | 9 | −$0.225 |
| Exclusivos Producción    |  5 | 2 | 3 | −$0.225 |
| Exclusivos Candidato     |  4 | 0 | 4 | −$0.940 |

**Hallazgo clave:** en los 15 trades compartidos (misma señal RSI 60–68) ambos sistemas
tienen idéntico ratio TP/SL (6/9). El candidato supera a producción por cobrar más en cada TP
($0.315 vs $0.240). La desventaja del candidato viene de sus 4 exclusivos: 0 TP / 4 SL (−$0.94).
Esos 4 aparecen porque el TP más alto (6.5%) mantiene la posición abierta más tiempo; cuando
cierra por SL, la siguiente señal también resulta SL (mercado ya en tendencia bajista).

**Desglose mensual (meses con ambos sistemas activos: 7):**

| Mes | Ganador | Nota |
|-----|---------|------|
| Enero 2026 | Producción | PF 1.02 vs 0.67 |
| Febrero 2026 | Empate | 3 SL cada uno |
| Marzo 2026 | Candidato | PF 0.45 vs 0.34 |
| Abril 2026 | Producción | 1 trade (TP) vs 2 trades (1 TP) — muestra mínima |
| Mayo 2026 | Producción | PF 1.02 vs 0.89 |
| Junio 2026 | Empate | 1 SL cada uno |
| Julio 2026 | Empate | 1 TP cada uno; candidato cobra más |

Producción gana 3/7 meses · Candidato gana 1/7 · Empate 3/7.

**Veredicto: INSUFICIENTE PARA CONCLUIR** — 19 trades vs umbral mínimo de 30.
No se implementa ningún cambio. Re-evaluar cuando Producción tenga ≥30 trades reales.

> Nota (2026-08-15): esta prueba comparaba Producción vieja (60–75/4.5/5.0) contra el
> Candidato. Desde el commit `349b53c` el Candidato **es** Producción — el punto de
> comparación de esta prueba ya no existe tal como se describe arriba.

> **Nota aclaratoria (2026-08-22):** toda esta sección describe BNB como si estuviera en
> producción real ("el candidato... pasó a ser la configuración de producción real", nota del
> 2026-08-15 al inicio de la sección). **Verificado el 2026-08-22 que esto ya no es así:**
> `director_orquesta.py` solo importa y llama a `dirigir_btc`, `dirigir_eth`, `dirigir_sol` —
> `director_bnb.py` está desconectado del ciclo de producción desde el commit `bf414c0`
> (2026-08-17) y no se ejecuta nunca, independientemente de qué parámetros tenga configurados
> internamente. Ver la tabla de estado real de francotiradores en `CLAUDE.md` para el estado
> vigente. Esta sección se conserva intacta como historial de la investigación tal como se hizo
> en su momento — no se reescribe retroactivamente.

## Estado técnico verificado — 2026-08-13

### Cadena ETH verificada en esta sesión

- `director_orquesta.py` → `director_eth.py` → `francotirador_alcista_eth.py` / `francotirador_lateral_eth.py`:
  cadena completa compilada y ejecutada sin errores.
- Un ciclo completo de la orquesta fue ejecutado correctamente en SIMULADOR.
- La fase global fue probada: `detectar_fase()` puede detectar LATERAL con velas 4H actuales.
- Ambas fases ETH están conectadas a `config_cartera.py` y leen parámetros desde ahí.

### Parámetros efectivos ETH (leídos de config_cartera.py, verificados 2026-08-13)

| Fase | RSI entrada | SL | TP | EMA | Trailing activación / distancia |
|------|------------|----|----|-----|--------------------------------|
| ALCISTA | 60–75 | 4.5% | 5.0% | 20/100 | 0.5% / 1.0% |
| LATERAL | 43–57 | 4.5% | 6.0% | 20/100 | 0.5% / 1.0% |

### Hallazgos de backtest forense — 2026-08-13 (ETHUSDT 4H, 2021–2026, $5/trade, com. 0.1%)

Reportes completos en `reports/2026-08-13_auditoria-forense-expectancy.md`,
`reports/2026-08-13_expectancy-real.md` y `reports/2026-08-13_alcista-vs-lateral.md`.

**Resultado global (alcista + lateral combinados):**

| Métrica | Valor |
|---------|-------|
| Total trades (TP+SL) | 630 (TP:291 / SL:339) |
| Win rate real | 46.19% |
| Expectancy/trade | −$0.003 |
| Profit factor real | 0.9765 |
| Capital final desde $20 | $17.95 |
| Racha máx SL | 11 |

**Por fase — diferencia crítica:**

| Fase | Trades | WR | Expect/trade | PF | Capital final |
|------|--------|----|--------------|----|---------------|
| ALCISTA | 254 | 51.97% | **+$0.012** | **1.105** | **$23.01** ✅ |
| LATERAL | 376 | 42.29% | **−$0.013** | **0.904** | **$15.12** ❌ |

- El script original (`backtest_perfil_comparativo.py`) reportaba capital $118.33 usando un modelo
  de riesgo-fijo (`ganancia = $5 × tp/sl`) que no es equivalente a operar $5 de posición real.
  Con $5 de valor de posición y comisiones reales el resultado es −10.2%.
- **Fase alcista es rentable en aislamiento.** Fase lateral destruye capital con las comisiones actuales.
- Sistema sigue en **SIMULADOR**. No se modificó ningún parámetro de producción.

## Investigación BTC ALCISTA — ago 2026

### Sistema C — definición

- **Sistema C:** RSI 55–60 + gate SOBRE EMA200d (diaria, anti-lookahead: se usa EMA del día D−1 para señales del día D)
- **Parámetros:** RSI 55–60, SL 5.0%, TP 6.0%, sin trailing (igual que Producción en SL/TP)
- **Producción BTC:** RSI 55–75, SL 5.0%, TP 6.0%, sin gate EMA

### Resumen de evidencia acumulada (2026-08-14)

Reportes: `reports/2026-08-14_btc-alcista-*.md`, `reports/2026-08-14_btc-*.md`

| Estudio | Prod PF | SistC PF | Trades SistC | Veredicto |
|---------|---------|---------|-------------|-----------|
| Train 2021–2023 | 1.101 | 1.177 | 74 | ✅ |
| OOS 2024–2025 | 1.201 | 1.322 | 59 | ✅ PROMETEDOR |
| Robustez EMA100–250 (OOS) | — | 1.264–1.322 | 52–64 | ✅ 4/4 EMAs positivas |
| Bootstrap ΔExp OOS | — | P(Δ>0)=61.6% | — | ⚠️ IC95% cruza 0 |
| ETH Sistema C (mismo gate) | — | PF OOS 0.960 | 67 | 🔴 DESCARTADO (0/4 EMAs) |
| Forward ene–ago 2026 | PF 0.637 | 0 trades | 0 | ⚠️ NO OPERA |

### Hallazgo crítico del forward 2026

En ene–ago 2026, BTC estuvo **por debajo de su EMA200d** durante todos los momentos en que RSI tocó 55–60. Sistema C quedó inactivo — diseñado correctamente para no operar en régimen bajista macro. Producción generó 22 trades (PF 0.637, negativo), todos en RSI 60–75 o RSI 55–60 con macro bajista.

Esto puede ser **fortaleza** (evita pérdidas en corrección) o **limitación** (períodos sin actividad). Cuando BTC recupere EMA200d, Sistema C volverá a activarse.

### Veredicto BTC Sistema C: 🟡 PROMETEDOR — NO ACTIVAR hasta 30+ trades reales

- Producción BTC: preservada sin cambios
- Sistema C: no activado, pendiente de acumular datos en régimen alcista macro

> **Nota aclaratoria (2026-08-22):** esta sección describe "Producción BTC: RSI 55–75, SL 5.0%,
> TP 6.0%, sin gate EMA" — esos valores coinciden con el diccionario `BTCUSDT.alcista` de
> `config_cartera.py`, pero **verificado el 2026-08-22 que `francotirador_alcista_btc.py` no
> importa `config_cartera.py` en absoluto** y usa constantes hardcodeadas propias: RSI 50–70,
> SL 3.5%, TP 6.0%, EMA 20/50 (`MAX_OP_TOTAL=1`). El diccionario citado aquí siempre fue código
> muerto para BTC — no es que el valor haya cambiado con el tiempo, es que esta sección nunca
> reflejó lo que corre en vivo. Ver `reports/2026-08-22_config_cartera-codigo-muerto-3-francotiradores-activos.md`
> y la tabla de estado real en `CLAUDE.md`. Cualquier decisión sobre Sistema C que compare contra
> "Producción BTC" debería re-verificarse contra los parámetros reales antes de usarse.

---

## Plan Maestro — Investigación y selección de 5 monedas / francotiradores

### Objetivo general

No reemplazar los 15 francotiradores existentes. Investigar, uno por uno y de manera ordenada,
las 5 monedas seleccionadas para determinar qué configuración funciona mejor y bajo qué
condiciones conviene activar o desactivar cada una. Meta: construir una segunda lista de 5
monedas/configuraciones respaldadas por evidencia. Los 15 francotiradores originales se
preservan sin modificar durante toda la investigación.

### Regla fundamental

NO hacer pruebas al azar. Cada moneda tiene un expediente propio. Cada prueba queda
identificada y numerada (ej. BNB ALCISTA Prueba #1, Prueba #2…). No saltar a otra
modificación sin documentar qué se aprendió de la anterior. Antes de comenzar una nueva prueba
indicar: qué prueba anterior se continúa, qué se aprendió, qué hipótesis se prueba, qué
parámetros cambian, qué permanecen, qué datos se usan y qué criterio determinará el resultado.

### Aislamiento permanente durante la investigación

- NO modificar `config_cartera.py`, francotiradores de producción, `auditoria.csv` ni
  `billetera.json`.
- Los scripts experimentales son independientes y no activan candidatos en producción.
- Todo resultado queda en reporte propio en `reports/`.
- Toda prueba indica explícitamente que está en SIMULADOR.
- La producción permanece intacta hasta decisión explícita de activación.

### Metodología por moneda

**Fase A — Baseline:** ejecutar/revisar config actual de producción, obtener datos históricos
comparables, registrar resultados base.

**Fase B — Candidatos:** probar modificaciones razonables de RSI, TP y SL de a una variable
por vez; comparar siempre contra Producción.

**Fase C — Análisis profundo** (para candidatos prometedores): trades compartidos/exclusivos,
efecto del TP/SL, comportamiento mensual y por régimen, estabilidad, DD, sensibilidad a
parámetros, robustez frente a variaciones pequeñas.

**Fase D — Validación:** un candidato no se aprueba con una sola prueba. Umbral mínimo de
referencia: 30 trades antes de declarar veredicto. El umbral se define antes de cada evaluación.

### Campos mínimos por prueba documentada

Config producción · candidatos probados · parámetros · período · fuente de datos · N velas ·
N trades · TP count · SL count · WR · Expectancy · PF · DD máx · capital inicial/final ·
trades compartidos · trades exclusivos · comportamiento mensual · comportamiento por régimen ·
limitaciones · conclusión · siguiente prueba recomendada.

### Objetivo final: matriz de activación

Al terminar las 5 monedas, construir una matriz histórica (moneda × mes × régimen) que permita
reglas del estilo "BNB bajo estas condiciones históricamente tiene mejor comportamiento".
Las reglas deben surgir de los datos, no de intuición. Posteriormente se diseñará un sistema
externo de inteligencia separado del bot principal (base de datos de evidencia: backtests,
forwards, reales, métricas mensuales, régimen, estado de candidatos) y, en fase futura, comandos
Telegram (/activar, /desactivar, /estado, /recomendaciones) — sin implementar todavía.

### Principio de conservación

Ninguna prueba experimental destruye información anterior. Cada prueba deja script, reporte,
parámetros, fecha, datos, resultado, conclusión y siguiente paso. No sobrescribir reportes
importantes.

### 13. Estado actual de la investigación (2026-08-14)

| Moneda | Estado | Pruebas completadas | Nota |
|--------|--------|---------------------|------|
| BNB ALCISTA | 🟡 PROMETEDOR | Prueba #1 (forward ene–ago 2026) + Prueba #2 (Sistema C bootstrap exhaustivo) | Sistema C RSI 55–60 + EMA200d: PF OOS 1.318, 4/4 EMAs positivas, pero EMA200 NO la mejor (EMA250 mejor). IC95% cruza cero. Forward 2026: 3 trades (89% bajo EMA200d). Producción intacta. Sistema C NO activado. |
| ETH ALCISTA | 🔴 SISTEMA C DESCARTADO | Baseline forward 2026 + Sistema C | ETH Sistema C descartado (PF OOS 0.960, 0/4 EMAs). Producción sigue activa (PF 1.105 histórico). |
| BTC ALCISTA | 🟡 EN INVESTIGACIÓN | Prueba #1 completada (múltiples fases) | Sistema C PROMETEDOR OOS (PF 1.322, 4/4 EMAs). Forward 2026: NO OPERA (BTC < EMA200d en régimen bajista). |
| SOL ALCISTA | 🔴 SISTEMA C DESCARTADO | Prueba #1 completada (bootstrap + vecindad EMA) | PF OOS 0.984, 0/4 EMAs positivas. Patrón RSI 55–60 + gate EMA no funciona en SOL. Producción intacta. |
| AVAX ALCISTA | 🔴 SISTEMA C DESCARTADO | Prueba #1 completada (bootstrap + vecindad EMA) | PF OOS 0.707, 0/4 EMAs positivas. EMA200 la peor de las cuatro. Delta bootstrap −$0.0352 (P(D>0)=16.9%). Producción intacta. |

Los 15 francotiradores originales: 🟢 PRESERVADOS — no modificar durante esta investigación.

Segunda lista de 5: ✅ DEFINIDA (2026-08-15) — ver sección "Segunda lista — Candidatas Sistema C".
Matriz calendario/régimen: 🟡 BORRADOR CON EVIDENCIA REAL 2026 (2026-08-16) — ver
`reports/2026-08-16_matriz-calendario-regimen-5monedas.md`. Régimen dominante (`detectar_fase()`
real) cruzado con señales de entrada RSI+EMA+fase, ene–ago 2026, 5 monedas. Hallazgo: febrero
5/5 monedas en BAJISTA dominante (0 señales en las 5); junio 4/5 BAJISTA (0 señales en las 5) —
confirma el mes malo universal de [[project_estacionalidad_5monedas]]. Febrero **contradice** el
prior histórico 2021-2025 (que lo marcaba "bueno unánime"). Falta ampliar a más años de régimen
real antes de proponer reglas de activación por Telegram. Ningún cambio de producción.
Sistema externo de inteligencia: 🔒 DISEÑO FUTURO.
Integración Telegram: 🔒 FASE FUTURA.

**Orden de investigación (lista original — completa):**
1. BNB ALCISTA — 🟡 PROMETEDOR (Prueba #2 Sistema C cerrada — PF OOS 1.318, 4/4 EMAs, IC95% cruza cero)
2. ETH ALCISTA — 🔴 Sistema C descartado · Producción preservada
3. BTC ALCISTA — 🟡 EN INVESTIGACIÓN (Sistema C prometedor OOS · no opera en régimen bajista 2026)
4. SOL ALCISTA — 🔴 Sistema C descartado (PF OOS 0.984, 0/4 EMAs) · Producción preservada
5. AVAX ALCISTA — 🔴 Sistema C descartado (PF OOS 0.707, 0/4 EMAs) · Producción preservada

**Conclusión del experimento Sistema C (2026-08-14):**
El patrón RSI 55–60 + gate EMA diaria NO es generalizable entre altcoins.
BTC y BNB muestran evidencia OOS positiva (4/4 EMAs cada uno), pero IC95% cruza cero en ambos.
ETH, SOL y AVAX: 0/4 EMAs positivas en los tres casos.

| Activo | PF OOS | Exp OOS | EMAs>1 | EMA200 mejor | Trades OOS | Forward 2026 | Veredicto |
|--------|--------|---------|--------|-------------|-----------|-------------|-----------|
| BTC | 1.322 | +$0.0383 | 4/4 | ✅ | 59 | 0 trades (100% bajo EMA200d) | 🟡 PROMETEDOR |
| BNB | 1.318 | +$0.0379 | 4/4 | ❌ (mejor EMA250) | 72 | 3 trades (89% bajo EMA200d) | 🟡 PROMETEDOR |
| ETH | 0.960 | −$0.0055 | 0/4 | — | 67 | N/A | 🔴 DESCARTADO |
| SOL | 0.984 | −$0.0022 | 0/4 | — | 96 | 0 trades | 🔴 DESCARTADO |
| AVAX | 0.707 | −$0.0466 | 0/4 | — | 67 | 0 trades | 🔴 DESCARTADO |

No avanzar a la siguiente moneda de forma aleatoria. Completar y documentar cada etapa de
la moneda actual antes de pasar a la siguiente, salvo decisión explícita de cambiar el orden.

### Regla para retomar el proyecto

Consultar primero este documento y los reportes existentes antes de crear una nueva prueba.
No asumir que una moneda está descartada o aprobada sin revisar su historial completo.

---

## Estado de investigación de francotiradores — actualizado 2026-08-14

### Punto 13 — Estado actual de investigación

BNB ALCISTA: 🟡 PROMETEDOR — Prueba #2 (Sistema C bootstrap exhaustivo) completada (2026-08-14). Sistema C RSI 55–60 + gate EMA200d diaria: PF OOS 1.318 (72 trades), WR 54.2%, Exp +$0.0379. Vecindad 4/4 EMAs positivas pero EMA200 NO la mejor (EMA250 mejor → PARCIALMENTE_ROBUSTA). IC95% bootstrap cruza cero [−$0.0644, +$0.0933], P(D>0) = 63.9%. Forward 2026: 3 trades, BNB 89% bajo EMA200d (gate activo, comportamiento esperado). Producción intacta. Sistema C NO activado.

ETH ALCISTA: 🔴 SISTEMA C DESCARTADO — Baseline forward 2026 completado (PF 0.721, 29 trades). Sistema C (RSI 55–60 + EMA200d) descartado: PF OOS 0.960, 0/4 EMAs positivas en OOS. Producción ETH preservada sin cambios.

BTC ALCISTA: 🟡 EN INVESTIGACIÓN — Prueba #1 completada (múltiples fases: forense, RSI, EMA200d, robustez, walkforward, bootstrap, forward 2026). Sistema C PROMETEDOR en OOS (PF 1.322, 4/4 EMAs). Forward 2026: 0 trades — BTC estuvo bajo EMA200d todo el período de señales RSI 55–60. Producción intacta. Sistema C no activado.

SOL ALCISTA: 🔴 SISTEMA C DESCARTADO — Bootstrap + vecindad EMA completados (2026-08-14). PF OOS 0.984, 0/4 EMAs positivas. Delta bootstrap −$0.0023 (P(D>0) = 47.9% — prácticamente aleatorio). Forward 2026: 0 trades (SOL bajo EMA200d). Producción intacta (RSI 50–70, SL 5%, TP 6%).

AVAX ALCISTA: 🔴 SISTEMA C DESCARTADO — Bootstrap + vecindad EMA completados (2026-08-14). PF OOS 0.707, 0/4 EMAs positivas, EMA200 la peor de las cuatro. Delta bootstrap −$0.0352 (P(D>0) = 16.9% — diferencia sistemáticamente desfavorable). Forward 2026: 0 trades (AVAX 100% del tiempo bajo EMA200d). Producción intacta (RSI 60–75, SL 4.5%, TP 5%).

### Estado de los francotiradores

Los 15 francotiradores originales: 🟢 PRESERVADOS
Segunda lista de 5: ✅ DEFINIDA (2026-08-15) — XRP, LINK, UNI, NEAR, ADA — ver sección siguiente.

### Investigación futura y sistemas complementarios

Calendario inteligente: 🟡 BORRADOR (2026-08-16) — matriz calendario/régimen con evidencia real
2026, ver punto 13 arriba y `reports/2026-08-16_matriz-calendario-regimen-5monedas.md`.
Sistema externo de inteligencia: 🔒 DISEÑO FUTURO
Integración Telegram: 🔒 FASE FUTURA

### Regla derivada de la Prueba #1 de BNB

La Prueba #1 de BNB ALCISTA fue una prueba controlada acumulativa en SIMULADOR
(2026-01-01 → 2026-08-14).

Resultado:
- Producción: PF 0.681, 20 trades, P/L -$0.9000
- Candidato RSI 60–68/TP 6.5%: PF 0.619, 19 trades, P/L -$1.1650
- Veredicto: INSUFICIENTE PARA CONCLUIR
- Umbral interno establecido: mínimo 30 trades para emitir un veredicto formal.
- Producción permanece intacta. Candidato permanece desactivado.
- No se modifican parámetros de producción como consecuencia de esta prueba.

### Regla derivada de la Prueba #2 de BNB (Sistema C)

La Prueba #2 de BNB ALCISTA fue un bootstrap exhaustivo del Sistema C
(RSI 55–60 + gate EMA200 diaria anti-lookahead) sobre datos Binance reales.
Train: 2021–2023 | OOS: 2024–2025 | Forward: 2026-01-01 → 2026-08-14.

Resultado:
- Producción OOS: PF 1.230, 108 trades, WR 54.6%, Exp +$0.0245
- Sistema C OOS:  PF 1.318, 72 trades,  WR 54.2%, Exp +$0.0379
- Vecindad EMA: 4/4 positivas (EMA100 1.308 · EMA150 1.376 · EMA200 1.318 · EMA250 1.420)
- EMA200 NO es la mejor → PARCIALMENTE_ROBUSTA
- Bootstrap Delta Exp: +$0.0134 | IC95% [−$0.0644, +$0.0933] cruza cero | P(D>0) = 63.9%
- Forward 2026: 3 trades (89% del tiempo BNB bajo EMA200d — gate bloqueado)
- Veredicto: 🟡 PROMETEDOR

- Producción permanece intacta. Sistema C NO activado.
- No se modifican parámetros de producción como consecuencia de esta prueba.
- La prueba no constituye evidencia suficiente para activar Sistema C en BNB.
- Diferencia clave con BTC: en BTC la EMA200 sí es la mejor vecina (ROBUSTA_POSITIVA);
  en BNB la mejor es EMA250 → menor robustez de diseño.

Siguiente paso: acumular 30+ trades reales en REAL antes de re-evaluar cualquier candidato.

## Segunda lista — Candidatas Sistema C (2026-08-15)

### Metodología de selección

Universo inicial: 39 pares USDT en Binance con historia disponible.
Filtros de eliminación: historia anterior a 2021-01-01 en 4H, completeness ≥ 80%.
MATICUSDT eliminado: 73.8% completeness (migración POL creó un hueco de datos).
Resultado: 26 pares válidos. 5 seleccionados por scoring objetivo con datos reales Binance API.

**Criterios de scoring (máx 100 pts):**
- Volumen diario promedio USDT (0–30 pts): liquidez real para órdenes spot
- Completeness de velas 4H (0–25 pts): calidad del historial para backtest
- Correlación con BTC en retornos diarios 2021–2025 (0–15 pts): rango objetivo 0.55–0.75
- Volatilidad anual (0–20 pts): rango objetivo 70–120% para frecuencia de señales
- Trades por día en 24h (0–10 pts): proxy de actividad retail

Criterio de exclusión adicional (no numérico): riesgo regulatorio/centralización.
ZECUSDT (score 96): excluido por riesgo de delisting en múltiples jurisdicciones (privacidad).
TRXUSDT (score 91): excluido por centralización (Justin Sun) y calidad de volumen cuestionable.

Reporte completo: `reports/2026-08-15_segunda_lista_sistema_c.md`

### Segunda lista — 5 candidatas aprobadas

| # | Par | Score | Vol $M/día | Corr BTC | Vol Anual | Historia desde |
|---|-----|-------|------------|----------|-----------|----------------|
| 1 | XRPUSDT | 100 | $68.3M | 0.600 | 82% | 2018 |
| 2 | LINKUSDT | 96 | $31.3M | 0.697 | 85% | 2019 |
| 3 | UNIUSDT | 96 | $24.9M | 0.622 | 92% | 2020 |
| 4 | NEARUSDT | 90 | $13.3M | 0.610 | 100% | 2020 |
| 5 | ADAUSDT | 90 | $10.3M | 0.675 | 81% | 2018 |

**Lista de espera (descartadas por factores no numéricos):**
- ZECUSDT (96⚠️ — privacidad, riesgo delisting)
- TRXUSDT (91⚠️ — centralización, calidad de volumen)
- LTCUSDT (90 — en reserva)
- AAVEUSDT (85 — en reserva)

### Reglas para investigar estas candidatas

- NO activar en producción ni en LIVE hasta acumular evidencia (umbral: 30 trades OOS ≥ 1.0 PF)
- Cada candidata sigue la misma metodología Sistema C: RSI 55–60 + gate EMA200d anti-lookahead
- Backtest en período 2021–2023 (train), 2024–2025 (OOS), forward desde disponibilidad
- Antes de correr backtest: verificar en vivo si la moneda pasa el filtro EMA200d/EMA250d
- Orden de investigación: XRP → LINK → UNI → NEAR → ADA (puede reordenarse con OK de Ariel)
- Estado inicial de cada una: 🔒 SIN BACKTEST (no han sido investigadas con Sistema C)

### Estado de las candidatas de la segunda lista

| Par | Estado | Prueba | Nota |
|-----|--------|--------|------|
| XRPUSDT | 🔒 SIN BACKTEST | — | Primera en la lista |
| LINKUSDT | 🔒 SIN BACKTEST | — | — |
| UNIUSDT | 🔒 SIN BACKTEST | — | — |
| NEARUSDT | 🔒 SIN BACKTEST | — | — |
| ADAUSDT | 🔒 SIN BACKTEST | — | — |

## Checklist — Incremento de capital real (2026-08-15)

Seguir este orden cada vez que se deposite capital adicional en Binance.
Aprendido durante la activación a REAL con $8.54 USDT.
Archivo completo con comandos: `CHECKLIST_CAPITAL.md` en la raíz del proyecto.

### Antes de empezar
- Confirmar saldo exacto en Binance Spot Wallet
- Verificar que `auditoria.csv` no tenga filas ABIERTA o RESERVADA (`grep -c "ABIERTA\|RESERVADA" auditoria.csv` debe devolver 0)

### Pasos en orden

1. **`signals/billetera.json`** → `USDT = NUEVO_CAPITAL`, `capital_inicial = NUEVO_CAPITAL`, `capital_real = NUEVO_CAPITAL`

2. **`bot.db` → `estado_riesgo`** (fuente activa del Guardian — la más importante):
   `capital_maximo_historico = NUEVO_CAPITAL`, `capital_inicio_dia = NUEVO_CAPITAL`, `bloqueado = false`

3. **`signals/estado_riesgo.json`** (legacy, mantener consistente con bot.db):
   mismos campos que el paso 2

4. **`config_cartera.py`** → `CAPITAL_BASE = NUEVO_CAPITAL`
   Afecta al Consejero y a los cálculos de `/resumen` y `/retiro`

5. **Francotirador activo** → `MONTO_FIJO = <monto_por_op_decidido>`
   Actualmente: `francotirador_alcista_bnb.py`, línea `MONTO_FIJO = 8.0`

6. **Reiniciar `main.py`** dentro del screen `v2_main` con `BOT_REAL_CONFIRMADO=true` exportado.
   Confirmar en log: `[CENTINELA] Capital real leido desde billetera.json: $NUEVO_CAPITAL`

7. **Verificar Consejero**: `python3 consejero.py` debe mostrar estado SALUDABLE

8. **Commit + push**: solo `config_cartera.py` y el francotirador modificado (no commitear CSVs ni JSONs de signals)

### Errores conocidos que pueden ocurrir si se omite algún paso

- **Guardian se bloquea**: `bot.db → estado_riesgo` no actualizado → drawdown calculado sobre pico antiguo (~$1075) vs capital real ($8) → 99% DD → bloqueo inmediato
- **Centinela muestra $1000**: `estado_global.py` cae al fallback si la ruta de billetera.json es incorrecta (bug histórico: typo `bot-padre-v8`, corregido 2026-08-15, commit `349b53c`)
- **Consejero en CRITICO**: `CAPITAL_BASE` viejo → porcentaje calculado incorrecto (ej. $8.54/$20 = 42.7% → CRITICO)
- **Lateral genera ANULADA**: `francotirador_lateral_bnb.py` usa `capital × 2%` = $0.17 < mínimo Binance. Corregido 2026-08-15 desactivando el lateral en `director_bnb.py` (commit `c16683c`)
