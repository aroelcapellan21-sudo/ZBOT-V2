# Estado actual — Z-Bot Padre v2

Índice central de estado del proyecto. Complementa a `INDICE_RESULTADOS.md` (tabla de todos los
backtests) y a `CLAUDE.md`/`INVESTIGACION.md` (contrato técnico e historial completo). Este
archivo responde "¿dónde estamos hoy?" en un vistazo — no reemplaza a los otros tres, los resume.

**Protocolo de actualización — la regla vive en `CLAUDE.md` desde 2026-09-02.** Ninguna
investigación se cierra sin actualizar este archivo (sección "CERRADO RECIENTEMENTE", y
"COLA DE INVESTIGACIÓN" si corresponde), sin su fila en `INDICE_RESULTADOS.md`, y sin cargar
sus números en `data/resultados.db`.

---

## EN PRODUCCIÓN AHORA

- **Modo:** REAL, `BOT_REAL_CONFIRMADO=true` activo (llave persistente en
  `~/.bot_real_confirmado`, sobrevive reinicios — verificado en vivo 2 veces, corte real incluido).
- **Capital nominal:** $20.00 USDT. USDT libre: $10.78 (al 2026-08-24).
- **Combo O activado en producción — 24-ago.** `director_orquesta.py` ahora llama 4
  francotiradores (antes 3): SOL pasó de LATERAL-solo a ALCISTA+LATERAL (según fase local, mismo
  patrón que BTC/ETH), y se sumó AVAX (ALCISTA+LATERAL+BAJISTA, este último inerte por el gate
  global de bajistas). Backtesteado como "Combo O" en el torneo (Sharpe 4.060 vs 2.62 de la config
  anterior). Diagnóstico completo, diff y verificación en vivo:
  `2026-08-25_diagnostico-cambio-produccion-avax-sol.md`, `2026-08-25_diff-final-combo-o.patch`.
  - **BTC ALCISTA** — RSI 50-70, SL 3.5%, TP 6.0%, EMA 20/50, `MAX_OP_TOTAL=1`, `MONTO_FIJO=$5`.
  - **ETH ALCISTA** — RSI 60-75, SL 4.5%, TP 5.0%, EMA 20/100, `MONTO_FIJO=$5` hardcodeado.
  - **SOL ALCISTA/LATERAL** — RSI 50-70/43-57. **Cambio de sizing 24-ago**: pasó de
    `CAPITAL_MAX_POR_OP=2%` a `MONTO_FIJO=$5` (mismo patrón que BTC), con chequeo previo contra
    `MONTO_MINIMO_BINANCE` antes de reservar fila — ver siguiente punto, era un bloqueador real.
  - **AVAX ALCISTA/LATERAL** — RSI 50-70/43-57. Mismo fix de sizing que SOL (idéntico código salvo
    símbolo). Primera vez conectado a producción.
  - Posiciones abiertas: BTC ALCISTA ($5, desde 2026-08-23) y ETH ALCISTA ($5, desde 2026-08-22) —
    sin cambios por este despliegue, verificado con snapshots antes/después en
    `reports/snapshots_combo_o/` (no versionados, gitignored).
- **⚠️ Bloqueador de capital corregido, no solo detectado.** SOL/AVAX ALCISTA calculaban el monto
  como 2% del capital libre — con capital real (~$10-20) eso daba ~$0.20-0.40/trade, por debajo del
  mínimo de Binance ($5) que exige `ejecutor.py` (`MONTO_MINIMO_BINANCE=5.0`), así que toda señal
  quedaba rechazada en silencio (fila `ANULADA`). El torneo no lo detectó porque backtesteó con
  capital simulado de $100,000 (`sistema_c/torneo_generico.py`), donde 2% = $2,000. Corregido a
  `MONTO_FIJO=5.0` en ambos francotiradores, mismo patrón que BTC/ETH.
- **`gestor_correlacion.py` — `MAX_TRADES_MISMA_DIR=2`, sin tocar (decisión explícita de Ariel).**
  Con los 4 francotiradores ahora ALCISTA, nunca va a haber más de 2 posiciones ALCISTA abiertas a
  la vez en todo el sistema — el 3er/4to intento se bloquea ahí, no por falta de señal. Verificado
  en vivo el primer ciclo post-activación (AVAX bloqueado por este gate con BTC+ETH ya abiertos).
- **Telegram — 2 mejoras chicas, 24-ago:** `/consejero` ahora muestra una línea inicial
  "🎯 Francotiradores activos: BTC-ALC, ETH-ALC, SOL-ALC/LAT, AVAX-ALC/LAT" (constante hardcodeada,
  actualizar a mano si cambia el wiring); `/disparos` ahora muestra "⏱️ Última operación: hace Xd Xh"
  por moneda (última fila `ABIERTA/TP/SL/TRAILING_SL/BE` en `auditoria.csv`, agrupado por symbol),
  para detectar francotiradores inactivos demasiado tiempo. Diseño y diff:
  `2026-08-25_diseno-tiempo-sin-operar.md`, `2026-08-25_diff-tiempo-sin-operar.patch`.
- **Bajistas:** los 5 desactivados por gate global (`gestor_bajistas.py`, falta de capital en
  Futuros — no por mal resultado, ver Fase 3 del torneo: el grupo BAJISTA combinado da PF 1.074,
  positivo, con AVAX BAJISTA como 2° mejor francotirador de los 15).
- **BNB:** sigue huérfano — código completo (3 fases sin pausa interna) pero
  `director_orquesta.py` no lo llama. Nota nueva: sus 11 filas históricas en `auditoria.csv` son
  todas `ANULADA` — nunca ejecutó un trade real ni siquiera cuando estuvo conectado (mismo
  bloqueador de sizing que SOL/AVAX tenían, nunca corregido para BNB porque sigue desconectado).
- **`config_cartera.py` no es fuente de verdad universal** — BTC ALCISTA lo ignora por completo
  (RSI/SL/EMA hardcodeados, distintos de lo que dice ese diccionario). ETH, SOL y AVAX ALCISTA sí
  leen RSI/EMA de ahí en vivo (el monto ya no, ver fix de sizing arriba).

## 🟢 `cerrar_huerfanas()` — la etapa 2 decidió: quitarla gana $31 en 6 años (09-sep-2026)

**Estado: PROMETEDOR con diff preparado, esperando OK de Ariel.** La etapa 2 terminó el 09-sep a
las 08:24 (ambas ramas `exit=0`). Reportes: `reports/2026-09-09_huerfanas-etapa2-6anos.md` (la
decisión), `reports/2026-09-09_impacto-realizado-cerrar-huerfanas.md` (los 31 cierres reales) y
`reports/2026-09-07_huerfanas-etapa1-2026.md` (la etapa 1, abajo).

### La etapa 2, sobre 2020-09-22 → 2026-09-08 (783.358 pasos de 4 min)

| | CON (hoy) | SIN | |
|---|---:|---:|---|
| Trades | 2.675 | 1.106 | |
| Win rate | 35,3 % | 44,1 % | 🟢 |
| PnL | +$3,77 | **+$34,79** | 🟢 **+$31,02** |
| Profit factor | 1,015 | 1,164 | 🟢 |
| Máx. drawdown | $14,91 (40,5 %) | $6,52 (17,7 %) | 🟢 −56 % |
| Sharpe | 0,084 | 1,159 | 🟢 |
| Racha perdedora | 27 | 10 | 🟢 |
| Duración mediana | 3,5 h | 16,3 h | 🔴 |
| Aperturas | 2.677 | 1.108 | 🔴 opera menos de la mitad |

**Gana en 7 de 7 años calendario y en 4 de 4 monedas** (BTC cambia de signo: −$7,03 → +$9,32).
Bootstrap por bloque mensual: **IC 95 % [+$17,06 · +$45,13], no cruza cero**, P(delta ≤ 0) = 0,0000;
test de signo **42/61 meses, p = 0,0044**; sin los 5 mejores meses sigue **+$19,94**. El "piso
mecánico" que invalidó otros IC **no aplica**: SIN empeora en 23 de 65 meses.

**De dónde salen los $31, exacto:** +$17,07 de **1.801 reaperturas que sólo existen en CON**,
+$14,31 de 307 trades con la misma entrada y salida distinta, −$0,36 de 232 que sólo existen en SIN.
Es el mecanismo ya documentado —cierra por voto global, el director reabre porque la fase local no
cambió— medido de punta a punta.

⚠️ **Cuatro asteriscos que hay que leer antes de citar esto:**
- **Las huellas de datos no son idénticas al final** (CON hasta las 04:00, SIN hasta las 20:00 del
  08-sep: 4 velas en 6 años). La próxima corrida pareada congela la huella antes de arrancar.
- **A escala actual son ~$0,43/mes.** Lo que vale no es el monto: son 1.801 operaciones inútiles
  menos y la mitad de drawdown.
- **Ambas ramas superan el límite de 10 % del guardián** (40,5 % y 17,7 %). Quitarlo aleja del
  bloqueo, no lo evita.
- **El bot operaría menos de la mitad.** Si algún día se busca frecuencia, este cambio va en contra.

### Y ya se disparó con dinero real: 31 veces, del 3 al 7 de septiembre

`CLAUDE.md` dice (31-ago) *"0 filas `FASE_CAMBIO`, el mecanismo nunca llegó a dispararse"*. **Quedó
desactualizado**: hay **31** (16 AVAX, 8 BTC, 7 SOL), exactamente lo que ese mismo archivo anticipó
al pasar `MONTO_FIJO` a $7/$10.

De las 24 que se pudieron emparejar con su cierre real: efecto sobre la caja **−$5,0973**, pero
**+$4,9754 de eso es polvo inmovilizado** (cripto sin vender por truncamiento al `stepSize`) y sólo
**−$0,1219 es pérdida efectiva por precio**. **BTC concentra el polvo:** ~$0,79 por vuelta, el
**8,2 % del ticket cada vez**.

> 🔴 **CORREGIDO EL 2026-09-09 17:40 — el polvo NO está en la cuenta.** `/api/v3/account` da
> **BTC = 0,0** real contra 6,916e-05 en `billetera.json`, y USDT **29,0076** real contra
> 23,3342 registrado: las dos diferencias se compensan, ese BTC se vendió de verdad y la
> contabilidad no lo registró. **Sigue en pie el mecanismo** (Binance confirma compras de
> 0,00012 y ventas de 0,00011) y el efecto sobre la caja de cada vuelta; **no es cierto que
> hoy haya ~$5 inmovilizados ni que sean ~13 % del capital**. Se midió desde
> `historial_billetera.csv` sin cruzarlo contra el saldo real.
> Detalle: `reports/2026-09-09_billetera-vs-binance-y-correccion-del-polvo.md`
 El mecanismo no crea el polvo —todo cierre
trunca— pero **multiplica los cierres**: 31 en 5 días, duración mediana de 20 minutos.

### El hallazgo estructural (éste sí es firme)

`cerrar_huerfanas()` (`director_orquesta.py:35`) cierra por la fuerza toda posición cuya acción no
coincide con la **fase global** nueva. Su propósito nunca se declaró en el código, y **nunca se
había medido**: los 8 escenarios del Ítem 2 no la desactivaban (el de PF 0,774 era *zona muerta*,
que recorta los cierres forzados de 210 a 91 pero deja el mecanismo en pie).

Medido ahora sobre 2026 con el simulador honesto: **de los 237 trades, 210 (88,6 %) los cierra este
mecanismo.** El TP y el SL casi no intervienen. Y esos cierres cortos son los que pierden:

| trades de la rama CON | n | PnL | WR |
|---|---:|---:|---:|
| duración < 12 h (mayormente forzados) | 170 | −$3,73 | 21,2 % |
| duración ≥ 12 h | 67 | −$1,49 | 34,3 % |

**El 71 % de la pérdida sale de los cierres que produce este mecanismo**, con 13 pp menos de win
rate que los que se dejan correr. Quien lea la documentación anterior creería que el bot sale por
TP o por SL; en los hechos sale por cambio de régimen casi siempre.

### La ventaja de quitarlo: real en agregado, no confirmada en el tiempo

| | CON (hoy) | SIN | |
|---|---:|---:|---|
| Trades | 237 | 40 | |
| Win rate | 24,9 % | 35,0 % | 🟢 |
| PnL | −$5,22 | −$2,27 | 🟢 |
| Profit factor | 0,619 | 0,738 | 🟢 |
| Máx. drawdown | $5,67 (15,4 %) | $3,32 (9,0 %) | 🟢 −41 % |
| Racha perdedora | 14 | 7 | 🟢 |
| Duración media | 14,9 h | 118,7 h | 🔴 8× |
| % del calendario expuesto | 59,1 % | 79,6 % | 🔴 |

**Las dos ramas pierden dinero.** SIN pierde menos: es *menos malo*, no rentable.

**Lo que distingue este resultado del análisis fase global vs local:** la ventaja **sobrevive a las
8 exclusiones de sensibilidad** (+$1,06 a +$3,53 quitando el mejor trade, los 3 mejores, el mejor
mes, o cualquiera de las 4 monedas). El de fase global vs local se daba vuelta ante casi cualquier
exclusión; éste no se da vuelta en ninguna.

**Lo que todavía falta:** el walk-forward mensual da **4 de 7 meses** a favor y el IC95 % bootstrap
de la diferencia mensual **cruza cero** ([−0,2645, +1,1345]). La rama SIN tiene sólo 40 trades en 8
meses. Sobre 7 períodos, 4-3 es indistinguible de una moneda al aire.

### Dos datos que conviene no perder

- **El drawdown de la rama CON llega al 15,4 %, por encima del límite de 10 % del guardián.** En la
  rama SIN queda en 9,0 %, por debajo. Quitar el mecanismo alejaría al bot del bloqueo, no lo
  acercaría.
- **La concurrencia no cambia** (máximo 2 posiciones simultáneas en ambas ramas, topadas por
  `MAX_TRADES_MISMA_DIR=2`). Lo que sube es el *tiempo* expuesto, no la cantidad de apuestas a la
  vez. Ésta era la medición que el Ítem 2 había dejado explícitamente pendiente.

### Qué NO se hizo

No se tocó producción, no se aplicó nada. El bot sigue en REAL con `cerrar_huerfanas()` activa.
**El diff está preparado y esperando OK explícito de Ariel** — una sola línea en
`director_orquesta.py:208`. Tampoco se barrió el polvo: `/reconciliar` vende dinero real y es
manual por diseño.

**Registrado en `data/resultados.db`:** pruebas **293** (rama CON), **294** (rama SIN) y **295**
(impacto realizado).

## 🔴 L11 — el laboratorio mide bien y elige mal (09-sep-2026, CERRADO)

> **Cerrado con las 3 pruebas el 09-sep.** Además de los dos puntos ciegos de abajo, la
> **Prueba 2** midió que la comisión del sandbox sobreestima un 18 %, que en producción **falla
> el 92 % de los intentos de apertura sin registrar el motivo**, y que **20 de 126 estudios
> (15,9 %) cambian de signo** al quitarles un año. La **Prueba 3** cerró con el resultado más
> duro: **DSR 0 de 121** —ningún estudio del proyecto supera la corrección por prueba
> múltiple— y **PBO 48,6 %**, que coincide con el ρ +0,010 de L3 por una vía independiente.
> Quedan abiertas dos de las siete sins: *survivorship* (sin medir, ahora ítem 4b de la cola) y
> *overfitting*. Pruebas **296**, **297** y **298**.
> `reports/2026-09-09_L11-prueba2-cobertura-de-errores.md` ·
> `reports/2026-09-09_L11-prueba3-estandares-externos.md`

**Ítem 13 cerrado.** Reporte: `reports/2026-09-09_L11-evaluacion-del-laboratorio.md`. Se le dieron
de comer **600 estrategias sintéticas con ventaja conocida por diseño** (6 valores de `p` × 100
semillas, ~240 trades cada una, BTC 2020-2026) y se midió si las distingue del ruido. Criterios
**pre-registrados el 08-sep**, antes de ver un número.

| p (probabilidad de acertar el desenlace) | detectadas por **L5** (contra el azar) | por **L4-bootstrap** (contra cero) |
|---|---:|---:|
| **0,50 — ruido puro** | **0 de 100** ✅ | **100 de 100** 🔴 |
| 0,52 | 5 % | 100 % |
| 0,55 | 17 % | 100 % |
| 0,60 | **40 %** | 100 % |

**🔴 Punto ciego 1 — indulgencia.** El criterio *"IC 95 % del total no cruza cero"* —el bootstrap
citado en todo `INDICE_RESULTADOS.md`— **aprobó las 100 estrategias sin ninguna información**. La
causa: entrar al azar en BTC 2020-2026 rinde **+1,5517 % por trade** por deriva del mercado, así que
cualquier vara contra **cero** aprueba al ruido. **No invalida** su uso *comparativo* (A contra B,
que es como se usa en casi todas las filas); **sí** invalida leer "IC 95 % > 0" como "la estrategia
sirve".

**🔴 Punto ciego 2 — falta de potencia.** Con la vara correcta los falsos positivos son **0,0 %**,
pero **ninguna** ventaja inyectada se detecta en ≥ 50 % de las semillas: ni siquiera `p = 0,60`, que
son **+0,485 pp por trade** (~$0,034 en un ticket de $7). **Umbral medido: con ~240 trades el
laboratorio no distingue del azar una ventaja de ese tamaño.**

**Cómo cambia la lectura de este archivo:** la mayoría de los **NO CONCLUYENTE** registrados no
dicen *"no hay ventaja"* — dicen *"el instrumento no la ve a esta escala"*. Son cosas distintas y
hasta hoy se leían igual. Contraste del mismo día: la etapa 2 de `cerrar_huerfanas()` (+$31,02,
IC 95 % [+17,06 · +45,13] sobre 65 meses) está **muy por encima** de ese umbral, y por eso resiste.

**Pendiente:** la Prueba 2 (comisión variable, fallas de exchange, dependencia de un período) y la
Prueba 3 (Deflated Sharpe, PBO/CSCV, Minimum Backtest Length) **no se corrieron**. Medido sólo sobre
BTC 4h. La base real no se tocó: todo sobre una copia. Registrado como prueba **296**.

## 🔬 Bloque de laboratorio COMPLETO (L1–L10, 07-sep-2026)

Diez pasos cerrados en una jornada. Lo que dejó, en una tabla:

| | Qué encontró |
|---|---|
| **L1** integridad de datos | El backup 4h estaba **corrido −4 h**; corregido en la fuente (13 CSV). Los `data_1m` son exactos contra Binance. Huecos: 0,097 % |
| **L2** reproducibilidad | 4/4 tests ✅ + **huella de datos** en cada resultado (md5 de los `.npy`) |
| **L3** fuera de muestra | 🔴 **el ranking del torneo no se sostiene** (ρ +0,010); elegir el mejor **no le gana al azar** |
| **L4** Monte Carlo | El barajado ingenuo **exagera** el drawdown (41 → 14 alarmas con bloques) |
| **L5** benchmark tonto | 🟢 **la entrada SÍ le gana al azar** (P 95–100 %); la fase sola le gana a buy & hold |
| **L6** pytest | **31 tests, 31 pasan** sobre el camino del dinero y los invariantes de `auditoria.csv` |
| **L7–L10** CI, ruff, mypy | **3 bugs reales encontrados y corregidos**, uno en producción |

### El bug que encontró el linter, en el camino del dinero

**`ejecutor.py:35`** — el import defensivo de Telegram definía un `_aviso` de respaldo que
referenciaba `_e`, la variable del `except`. **Python 3 borra esa variable al salir del bloque**, así
que el respaldo **crasheaba con `NameError` la primera vez que se usaba** — justo cuando fallaba
Telegram y hacía falta avisar. Reproducido antes de corregir.

### El CI, y por qué está en dos niveles

**Bloquea** `pytest` y `ruff --select E9,F821,F811` (lo que rompe en ejecución). **Avisa sin frenar**
ruff completo (342 hallazgos, **277 son f-strings cosméticos**) y mypy (36 errores en 4 archivos).

> Un CI que nace en rojo se aprende a ignorar, y entonces no sirve para nada. Con 298 archivos y
> 65.635 líneas escritas sin linter, activar todo de golpe sería ruido desde el día uno.

Tras los 3 fixes el CI queda **verde**. `mypy` se acotó a los **16 módulos de producción**: los 298
archivos chocan con nombres de módulo duplicados, y tipar 9 años de scripts de un solo uso no aporta.

## 🟢 L5 — la entrada SÍ aporta, y la fase sola le gana a buy & hold (07-sep)

**Primera buena noticia del bloque de laboratorio.** Entradas al azar con el **mismo TP/SL** y la
**misma cantidad de trades** que el bot:

| Moneda | Bot | Azar | **P(bot > azar)** |
|---|---|---|---|
| BTC | +199,1 % | +36,6 % | **95,0 %** |
| ETH | +269,3 % | −43,2 % | **100 %** |
| SOL | +80,9 % | −108,9 % | **97,5 %** |
| AVAX | +146,5 % | −117,2 % | **100 %** |

**En 4 de 4 monedas la lógica de entrada supera al azar.** Los 12 gates, el RSI y las EMAs
seleccionan algo real.

**Y la referencia trivial que más incomoda:** estar comprado **sólo cuando la fase dice ALCISTA**,
sin un solo filtro, **le gana a buy & hold en 4 de 5 monedas con la mitad del drawdown** — BTC
+2.837 % vs +1.426 % (DD −46,5 % vs −83,9 %); AVAX **+10.826 % vs +89 %**.

⚠️ La primera versión daba **+22.900.366 %** por un look-ahead (decidía la fase con el cierre de la
vela *i* y cobraba el retorno de esa misma vela). Corregido a decidir con velas cerradas hasta *i−1*.

### El cuadro que arman L3, L4 y L5 juntos

| Pregunta | Respuesta | De dónde |
|---|---|---|
| ¿La entrada aporta sobre el azar? | **Sí** (P 95–100 %) | L5 |
| ¿Está bien medida su magnitud? | **Sí** (bootstrap robusto) | L4 |
| ¿Se puede saber cuál variante es la mejor? | **No** (el ranking es ruido) | L3 |
| ¿Cuánto del año puede operar? | **15–41 %** | Ítem 2b/2c |
| ¿Le gana a lo trivial? | **La fase sola ya le gana a buy & hold** | L5 |

**Lectura sugerida —no veredicto medido—:** el valor parece estar más en **estar dentro en el
régimen correcto** que en afinar qué combinación de gates se usa. Confirmarlo es trabajo de la
revisión posterior a los 10 pasos.

## 🟡 L4 — Monte Carlo: el barajado ingenuo miente (07-sep)

**El hallazgo es metodológico, y casi queda registrada una falsa alarma.**

Barajando **trade a trade**, 41 de 108 estudios daban el drawdown observado por debajo del percentil
5 — o sea "el riesgo real es 1,70× mayor de lo medido". **Barajando por bloques de 20 trades quedan
14.**

| Barajado | DD obs < pct 5 | Típicos |
|---|---|---|
| trade a trade | **41** | 66 |
| **bloques de 20** | **14** | **92** |

El barajado libre **destruye la estructura temporal** y genera secuencias de pérdidas que la
estrategia real nunca produjo. **Dos tercios de la alarma eran artefacto del método.**
`laboratorio/monte_carlo.py` quedó con bloques de 20 por defecto.

**Lo que sí queda:** 14 de 108 (13 %) conservan el DD bajo el percentil 5 — más del 5 % esperable,
pero acotado y con estimación gruesa.

**Y la buena noticia del bootstrap:** en los estudios grandes el **signo del resultado es robusto**
(P(>0) ≈ 100 %, IC 95 % enteramente positivos).

> **Contraste con L3, y es el punto: cuánto rinde una configuración está bien medido. Cuál es la
> mejor, no.** L4 confirma la primera mitad; L3 había demolido la segunda.

⚠️ **Unidades:** los drawdowns están en **puntos porcentuales sumados por trade**, no en % de la
cuenta. 30 puntos con $7 por trade son **$2,10 ≈ 5,7 %** de un capital de $36,86.

## 🔴 L3 — el ranking del torneo NO se sostiene entre años (07-sep)

**Elegir "la mejor combinación" mirando todo el histórico selecciona ruido.** Partiendo los **2.790
trades** del torneo ya guardados en `resultados.db` por año:

| | |
|---|---|
| ρ medio del orden entre años | **+0,010** (21 pares) — indistinguible del azar |
| El mejor global (`avax_alcista`) | gana **1 de 7 años**; 8º, 8º y 9º en tres de ellos |
| Controlando por moneda (sólo fases entre sí) | **ρ −0,058** (103 pares) |

**La objeción obvia no lo salva.** Comparar `avax_alcista` contra `bnb_lateral` mezcla "qué
estrategia es mejor" con "qué moneda se movió ese año" — por eso se repitió dentro de cada moneda, y
sigue dando azar. **El desorden viene de la elección misma.** Sólo AVAX muestra algo de señal
(ρ +0,233, gana 4/6).

**Qué sigue valiendo:** cada PF, WR y n del torneo está bien medido y se puede citar.
**Qué NO:** que alguna combinación sea "la mejor".

### Y el walk-forward lo confirma: elegir el mejor no le gana al azar

Diseño: elegir la mejor combinación **con los datos hasta el mes N**, medir el mes **N+1**, correr la
ventana y repetir. Contra elegir **al azar** y contra el **techo** (elegir con el futuro a la vista).

| Historia mínima | Meses sin operar | Ventaja sobre el azar | P(>0) |
|---|---|---|---|
| 12 m | incluidos | +67,41 % | 76,7 % |
| 24 m | incluidos | +64,64 % | 76,5 % |
| 36 m | **excluidos** | +4,00 % | 50,8 % |
| 48 m | **excluidos** | **−24,78 %** | **36,4 %** |

**Se desarma en dos direcciones:** cuanta **más** historia se exige para elegir, **menos** ventaja hay
(al revés de lo esperable si funcionara); y **excluyendo los meses en que la elegida no operó** —la
comparación justa, porque su resultado cuenta 0 mientras el azar incluye combos que sí operaron, y en
meses malos *no operar parece una virtud*— la ventaja se evapora y termina invirtiéndose.

**Techo:** elegir con el futuro daría **+1.334,77 %**. El método captura **10,7 %**.

> 🔴 **Tercera vía independiente con la misma conclusión.** Bootstrap del Ítem 2 (7 IC 95 % cruzando
> el cero) · estabilidad del ranking entre años (ρ +0,010) · walk-forward (P = 77,4 % con el corte
> más favorable, 36,4 % con el más exigente). **Ya es un patrón sobre el método de selección, no una
> coincidencia.**

**Regla que queda:** cualquier configuración que se proponga aplicar tiene que mostrar que **gana
fuera de la ventana donde se la eligió** y que **le gana al azar**. Se verifica con
`laboratorio/validar_fuera_muestra.py`.

Coincide con el bootstrap del Ítem 2 (los 7 IC 95 % cruzaban el cero). **Dos métodos independientes,
la misma conclusión: no hay señal suficiente para elegir un ganador.**

⚠️ **El torneo dejó de estar etiquetado como "REFERENCIA PRINCIPAL"** en `INDICE_RESULTADOS.md`.
Antes de usarlo para decidir una configuración, exigirle que gane **fuera** de la ventana donde se la
eligió — un filtro que **ninguna comparación registrada hasta hoy pasó, porque nunca se aplicó**.

Detalle: `reports/2026-09-07_L3-validacion-fuera-de-muestra.md`.

## 🔬 laboratorio/ — los chequeos permanentes del simulador (desde 07-sep)

Dos scripts que **se vuelven a correr cuando haga falta** y **fallan con exit code** si algo se
rompió, así que sirven para CI:

- **`laboratorio/verificar_datos.py`** (L1) — huecos, duplicados, OHLC imposible, cruce entre las dos
  fuentes, muestra contra Binance, e impacto de los huecos sobre las ventanas ya registradas.
  Correrlo tras actualizar `data_1m/` o el backup 4h.
- **`laboratorio/verificar_reproducibilidad.py`** (L2) — el mismo tramo cambiando una cosa por vez.
  Correrlo tras tocar el simulador.

**L2 · Reproducibilidad: los 4 tests pasan** (misma corrida ×2 · distinto `PYTHONHASHSEED` ·
distinto `--tmpdir` · bandera obsoleta no-op). El test B era el que valía: el orden de `SYMS` **sí**
cambia con la semilla de hash, pero **el resultado no depende de eso** — medido, no razonado.

⚠️ **El asterisco, y no es menor:** eso prueba reproducibilidad *el mismo día, en la misma máquina,
con los mismos datos*. **No a lo largo del tiempo.** `FECHA_FIN = datetime.now()` y las velas de 4 h
se bajan frescas en cada arranque: la Tarea 1A y `CONTROL4H` corrieron con **19.823 vs 19.826 velas**
por unas horas de diferencia.

**Resuelto con una huella de datos** en cada resultado (`_huella_datos`): velas y rango por moneda +
**md5 de los 5 `.npy`**, calculada una vez al arranque (~2,7 s para 1,45 GB). Ahora dos corridas que
difieren se pueden distinguir entre **"cambió el simulador"** y **"cambiaron los datos"** — que hasta
hoy era indistinguible.

## 🔧 L1 · Integridad de datos — el backup 4h estaba corrido 4 h, ya está corregido (07-sep)

**Los datos siempre estuvieron bien; las etiquetas de tiempo del backup, no.** Cada fila de los CSV
de `~/bot-padre-v3-backup/data/historico_4h/` decía ser **4 horas más temprano** de lo que era.

Detectado cruzando dos fuentes independientes: los `data_1m` agregados a 4 h contra el backup.
Diferían en el 98,5–99,2 % de las velas. Probando desplazamientos, `backup[t] == 1m[t+4h]` con
**mediana 0,000000 % y 100,0 % de velas iguales**.

**Corregido en la fuente el 07-sep** (los 13 CSV, +4 h por fila, precios intactos). Verificado
después: las dos fuentes coinciden al **100 %**. Respaldo en `historico_4h_pre_correccion_desfase/`
y una marca que impide aplicarlo dos veces — **una segunda pasada dejaría los datos +8 h**.

**Por qué se corrigió en la fuente y no con una bandera:** de los **58 `.py` que leen ese backup**,
**35 no corregían nada** y **9 sólo ajustaban el índice de inicio** (la ventana quedaba bien, las
horas seguían mal por dentro). **Ninguno de los 58 tenía los timestamps correctos.** Una bandera
opcional deja el error a un olvido de distancia.

- Se quitó la compensación de los **9** de `sistema_c/` (Uso A).
- **No se tocaron los 6** que usan `hours=4 * velas` para calcular duración (Uso B) — no tienen relación.
- La bandera `--corregir-desfase` del sandbox quedó como **no-op**, no eliminada: 4 lanzadores la
  pasan y los checkpoints reanudables la llevan en su firma. Verificado: con y sin ella, resultado idéntico.

⚠️ **Esto NO altera ningún resultado ya registrado** — los estudios viejos corrieron con los datos
como estaban. Lo que cambia es que **de acá en adelante todos leen la hora correcta**. Si se rehace
un estudio viejo dará distinto en lo que dependa de la hora, y eso es lo correcto.

### Lo demás que midió L1

**Los `data_1m` son exactos**: 48/48 velas de muestra idénticas a la API de Binance, y las **15,8 M
de velas** con OHLC coherente (cero duplicados, cero timestamps hacia atrás, ninguna con `high<low`).

**Huecos: 20.153 minutos = 0,097 %** del total. Caen dentro del torneo (0,43 % de la ventana), los 12
gates (0,43 %) y el ensanchado de TP/SL (0,41 %); **cero en los 8 escenarios del Ítem 2**. Decisión:
**no rellenarlos** — un precio interpolado puede disparar un TP que nunca existió.

## 🔴 El bot opera en la fase MÁS QUIETA del mercado y está ciego 73–85% del año (07-sep-2026)

Medido sobre 2026 completo: 89.516 ciclos de 4 min, 248,7 días, fase **LOCAL** de cada moneda —que
es la que despacha `director_orquesta.py:248`, no el voto global.

### Cobertura real: sólo hay francotiradores ALCISTA activos

| Moneda | ALCISTA | LATERAL | BAJISTA | Días operables (de 248,7) |
|---|---|---|---|---|
| ETH | **27,0 %** | 48,7 % | 24,3 % | 67,1 |
| BNB | 25,3 % | 51,3 % | 23,4 % | 62,8 · *no opera, huérfano* |
| BTC | 22,6 % | 56,3 % | 21,1 % | 56,2 |
| SOL | 17,9 % | 64,6 % | 17,5 % | 44,4 |
| AVAX | **14,9 %** | 60,1 % | 24,9 % | **37,2** |

**El bot no puede operar entre el 73 % y el 85 % del año.** AVAX, con dinero real, tiene fase
ALCISTA sólo 37 de 249 días.

### ✅ Confirmado con 2021–2025: la cobertura NUNCA supera el 41 %

| Año | ALCISTA promedio de las 4 que operan |
|---|---|
| 2021 | **41,0 %** ← el mejor |
| 2022 | **14,5 %** ← el peor |
| 2023 | 33,9 % |
| 2024 | 30,1 % |
| 2025 | 20,4 % |
| 2026 | 20,6 % |

**En seis años el bot nunca pudo operar más del 41 % del tiempo.** Incluso en el mejor año estuvo
ciego el 59 %; en el peor, el 85,5 %. Promedio de los seis: 26,8 %.

⚠️ 2026 (20,6 %) está **por debajo** del promedio: el rango real es **14,5 %–41,0 %**, no el
"15 %–27 %" que sugería medir sólo 2026.

### ⚠️ CORREGIDO — lo de BAJISTA era un dato de 2026, no un patrón

Se registró el 07-sep que *"BAJISTA tiene 40 % más rango y 46 % más volumen que ALCISTA"*. **Con
2021–2025 eso no se sostiene:**

| Año | rango BAJISTA / ALCISTA | |
|---|---|---|
| 2021 | 0,94× | ← se invierte |
| 2022 | 1,27× | |
| 2023 | **0,65×** | ← se invierte fuerte |
| 2024 | 1,10× | |
| 2025 | 1,22× | |
| 2026 | 1,40× | ← el año que se había medido |

**Sólo 4 de 6 años.** En volumen es peor: 0,52× en 2021 y 0,44× en 2023. **No usar ese dato como
argumento para investigar BAJISTA.**

### ✅ Lo que SÍ se sostiene: LATERAL es la mayor parte del año

**5 de 6 años** LATERAL tiene más velas que ALCISTA (hasta **2,93×** en 2022), con rango entre
**0,62× y 0,93×** (mediana 0,89×). La mayor parte del año, con movimiento apenas menor. **Éste es
el hallazgo robusto de los tres**, y es el que sostiene el Ítem 2c.

### ⚠️ ALCANCE de todo el trabajo anterior sobre francotiradores ALCISTA

**El torneo de francotiradores, la auditoría de los 12 gates y el ensanchado de TP/SL midieron una
estrategia que sólo puede actuar ~1/5 del año.**

**No quedan invalidados** —las comparaciones entre configuraciones ALCISTA siguen valiendo entre
sí— pero **su alcance está acotado a esa ventana**. Cualquier proyección de rendimiento anual a
partir de ellos hereda ese techo.

### Qué dispara los cambios de fase (para saber dónde aplicar histéresis)

`cambio_7d` **55,1 %** de los cruces que cambian la fase · `cambio_30d` **31,6 %** ·
`precio vs EMA200` **13,3 %**. Una histéresis sobre 7 días cubre la mitad del problema; para llegar
al 87 % hay que aplicarla también al de 30 días.

Detalle: `reports/2026-09-07_item2bc-condiciones-y-cobertura.md`.

**Nota de negocio, NO tarea de código:** activar BAJISTA en real exige reescribir `ejecutor.py` para
Futuros (hoy `cerrar_posicion` cierra shorts con BUY spot) **y** abrir esa cuenta. Es decisión de
Ariel, independiente de investigar el valor potencial. **LATERAL, en cambio, es operable en SPOT hoy
mismo** y es el 48–65 % del año.

## 🔴 El bot casi no está operando su estrategia (medido 07-sep-2026)

**En 2026, el 89% de los cierres del bot son por cambio de fase global, no por TP ni por SL.**
Simulación de 2026 completo a 4 minutos, con el simulador ya corregido: **210 de 237 cierres** son
`FASE_CAMBIO`. Sólo 27 llegan a TP o SL.

El voto de `detectar_fase_global()` —5 monedas, y basta que 2 dejen de estar ALCISTA para que caiga
a LATERAL— barre las posiciones antes de que la lógica de TP/SL tenga ocasión de actuar. Causa
mecánica: el umbral duro sin histéresis de `detectar_fase()` (`utils.py:92`, `cambio > 1.0`),
evaluado cada 240 s.

> **Los 8 escenarios probados dan EXACTAMENTE 12 TP.** Apagar el churn de 210 cierres a 24 (−89%)
> no hace que **ni una sola** operación más llegue al take profit. Los trades que el mecanismo
> cierra no son trades que iban a ganar.

### Estado: 🟡 NO CONCLUYENTE — decisión abierta, NO archivada

Las 3 soluciones se midieron juntas (8 combinaciones) y **ninguna es significativa**: los 7 IC 95%
cruzan el cero. La mejor (zona muerta 0,25) da +$2,83 con P(mejor)=80,1%. Los 8 pierden plata
(PF 0,603–0,774): la mejor reduce la pérdida de −$12,22 a −$9,38.

**Esto NO se archiva como "no sirve".** No es una apuesta de rendimiento que falló: es un **defecto
de diseño real** — hoy el bot cierra posiciones que su propia lógica de entrada considera válidas.
Lo que falta no es voluntad, es evidencia.

**⚠️ QUÉ FALTA PARA DECIDIR DE VERDAD:**

> **Medir el impacto del cambio de duración por trade sobre el perfil de riesgo.** Las soluciones
> alargan mucho el trade medio: **14,9 h** en el baseline → **32,3 h** con la zona muerta →
> **83,0 h** con las tres. Eso cambia el drawdown máximo y la exposición simultánea, y **este
> estudio no lo midió**. Sin ese número no se puede aprobar ni rechazar: se estaría cambiando el
> perfil de riesgo del bot a ciegas.

Detalle: `reports/2026-09-07_item2-paso2-ocho-escenarios.md`.

**Y más grande que el ítem:** con PF 0,774 en el mejor caso, el problema no es sólo el director.
Antes de seguir parcheando `cerrar_huerfanas()` corresponde preguntarse por qué la fase global
cambia 200+ veces en 8 meses.

## 🛑 LEER ANTES DE CITAR CUALQUIER BACKTEST DE ESTE ARCHIVO (06-sep-2026)

**El simulador tenía tres fallos de fidelidad. Todo resultado anterior al 06-sep-2026 los arrastra.**
Esto no invalida el historial, pero cambia cómo hay que leerlo. Si venís de otra sesión o de otra
herramienta y no tenés el contexto: esto es lo que necesitás saber, no hace falta reconstruir nada.

**La causa raíz es una sola, y ya estaba documentada el 03-sep para el RSI:** el bot real evalúa cada
240 s y ve la **vela de 4h EN CURSO**; el simulador miraba **velas cerradas**. Apareció en tres
lugares distintos:

| # | Fallo | Efecto medido | Estado |
|---|---|---|---|
| 1 | La fase de despacho (`_pop_gate` → `_fase_actual`) usaba velas cerradas | El simulador abría **5 veces** donde producción intentó **190** en la misma ventana | ✅ corregido 06-sep |
| 2 | `_f_urlopen` **ignoraba el parámetro `interval`**: servía velas de 4h aunque le pidieran 1h o 1d | `detector_multitimeframe` comparaba **tres veces la misma serie**. Era el bloqueo dominante: **2.380 → 644** tras el fix | ✅ corregido 06-sep |
| 3 | `data_1m/` desactualizado (terminaba el 04-sep) y **sin BNB**, que entra en el voto de fase global | Recortaba la ventana de simulación **en silencio**; el voto se calculaba sobre 4 monedas en vez de 5 | ✅ corregido 06-sep |

**Qué significa en la práctica:**

- **Las comparaciones RELATIVAS entre estrategias siguen valiendo**: todas se midieron con el mismo
  simulador y el mismo sesgo.
- **Los niveles ABSOLUTOS están sesgados a la baja en frecuencia.** El simulador subestimaba cuántas
  veces se opera. Cualquier cifra de "trades por semana" o "operaciones al mes" anterior al 06-sep
  es un piso, no una medición.
- **Los fallos 1 y 2 sólo afectan al modo `--paso 4m`.** A 4 horas cada paso ES una vela cerrada, así
  que no hay "vela en curso" que perder. Los backtests a 4h no los sufren — pero sí sufren lo del
  hallazgo de abajo (sobreestiman el resultado).
- **Correcciones aplicadas en `~/tarea1a_4m/sandbox_director.py`.** `sandbox_multi_fix.py`, el que
  midió la Tarea 1A, **todavía las tiene**: rehacer esa prueba con el simulador corregido.

Detalle completo: `reports/2026-09-06_item2-paso1-fidelidad.md` y la auditoría que ya había
señalado la causa raíz, `reports/2026-09-03_tarea1-auditoria-confiabilidad-simulador.md`.

**Fidelidad tras corregir**, contra las 2.316 líneas `ORQUESTA` que el bot dejó en `eventos.log`:
fase global coincide en el **87,3%** de los ciclos (510/584) y produce **31 transiciones contra 33
reales**. El modelo sirve para comparar soluciones entre sí; **sobreestima los cierres forzados un
14%**, así que no se le pueden pedir números absolutos.

## ⚠️ Hallazgo transversal 06-sep — los backtests a 4h sobreestiman

**Tarea 1A cerrada.** El bot real evalúa cada 240 s (`sleep_segundos`), o sea cada 4 minutos; todos
los backtests de este índice se corrieron a 4 horas. Simular a la resolución real da **PF 1.202
contra 1.384**, y WR **45.7% contra 49.7%**, con 81.5% más trades. Consistente en las 4 monedas, sin
una sola excepción.

Mecanismo medido: los 1.204 trades que **sólo** aparecen a 4m rinden PF 1.142, contra PF 1.606 de los
215 que ambas resoluciones ven. Mirar más seguido no encuentra mejores oportunidades: encuentra más
oportunidades mediocres.

**Cómo leer el resto de este archivo a partir de ahora:** las comparaciones *relativas* entre
estrategias siguen valiendo (todas se midieron igual), pero el **nivel absoluto está inflado**. Antes
de aplicar cualquier cambio que dependa de cruzar el umbral PF ≥ 1.6, revalidarlo a 4 minutos.

Detalle: `reports/2026-09-06_tarea1a-4m-vs-4h-comparacion.md`.

## COLA DE INVESTIGACIÓN → se mudó a `COLA.md` (09-sep-2026)

> **La cola ya no vive acá.** Hasta el 09-sep había **dos** colas con numeraciones distintas y sin
> un solo ítem en común —esta sección (ítems 1-10) y `~/zbot-drive/cola/zbot-cola.md` (ítems 2-14)—,
> que juntas sumaban 20 pendientes que nadie veía a la vez, con el trabajo de "revisar los hallazgos
> anteriores" escrito **dos veces**.
>
> **Fuente de verdad única: `COLA.md`**, en la raíz del repo. Se versiona en git y se sincroniza
> sola a Drive junto con `reports/`. Los 10 ítems que estaban acá se migraron completos al bloque
> **"Mantenimiento y deuda técnica" (M1-M10)** de ese archivo; ninguno se perdió.
>
> El orden de trabajo confirmado por Ariel el 09-sep está al tope de `COLA.md`.

## CERRADO RECIENTEMENTE

Más reciente primero. Ver `INDICE_RESULTADOS.md` para el detalle de métricas de cada uno.

| Fecha | Investigación | Veredicto |
|---|---|---|
| 02-sep | Ensanchar TP/SL de los 4 francotiradores activos (1.5× y 2×, más variantes asimétricas) | 🟡 Prometedor, **no aplicar todavía** — mejora en las 4 monedas y en las 3 ventanas del walk-forward, pero el bootstrap cruza cero (P(mejor) 83%) y el máximo PF es 1.444, bajo el umbral 1.6. Falta repetirlo con los 12 gates. Ver `2026-09-02_backtest-sl-tp-ensanchado-y-montos.md` |
| 02-sep | Combinaciones de monto por moneda con $36.86 de capital | 🔴 Dejar 10/7/7/7 — desbalancear por ratio ganancia/pérdida es el peor de 5 combos (el ratio no predice: ETH con 1.02 rinde el doble por dólar que BTC con 1.57), y usar ~$36 deja una zona muerta silenciosa entre $33.79 y $36 donde la 4ª moneda no abre |
| 02-sep | **[INFRAESTRUCTURA]** Base de datos consultable de resultados (`data/resultados.db`) + regla permanente de indexado en `CLAUDE.md` | Aplicado. 94 pruebas cargadas: 74 del índice histórico + 20 del backfill 25-ago→02-sep. Consultas con `python3 consultar.py`. Ver `2026-09-02_diseno-db-resultados-y-regla-indice.md` |
| 01-sep | Riesgo real por operación y margen para subir el monto | Informativo — arriesga **0.79% del capital** por operación ($0.29 de un ticket de $7). El límite para subir el monto es el capital, no el riesgo. Ratio ganancia/pérdida: BTC 1.57, **ETH 1.02**, SOL 1.62, AVAX 1.62 |
| 31-ago | **[PRODUCCIÓN]** Puntos ciegos del camino del dinero | Aplicado: BTC `MONTO_FIJO` $7→$10 y validación de `status` en `ejecutor.py` (rechazo definitivo vs `OrdenIncierta`), 14/14 escenarios simulados correctos |
| 31-ago | Auditoría económica del trailing — conectar `trailing_stop.py` | 🔴 Descartado — PF 0.583 vs 0.919 actual, mata 152 de 168 TP, WR 42.1%→29.4% |
| 31-ago | Fix B — breakeven y trailing anclados al máximo (12 combinaciones) | 🔴 Descartado — la mejor da PF 1.00 vs 0.98 actual; ninguna llega al umbral 1.6 |
| 31-ago | Termómetro — impacto económico de reconectarlo | 🔴 Descartado — bloquearía 31.9% del tiempo (66.2% en agosto) y habría cortado 4 de las 8 operaciones reales (costo $0.34) |
| 31-ago | `cerrar_huerfanas()` — fase GLOBAL vs LOCAL (222 divergencias + las 8 ops reales) | 🔴 No se corrige (decisión de Ariel, 31-ago) — impacto realizado $0.00, IC95% cruza cero, drawdown 5.8× mayor |
| 31-ago | Auditoría de arquitectura y conexiones — 4 conexiones rotas | Documentadas, **no reparadas**: efecto económico cero o negativo en las 4 (termómetro, centinela, trailing huérfano, fase global/local) |
| 30-ago | Aporte individual del combo O (5 escenarios) + walk-forward de 3 ventanas | Las 4 monedas aportan: sacar cualquiera baja el PnL total. "Sin BTC" gana en las 3 ventanas pero no se aplicó |
| 30-ago | **[PRODUCCIÓN]** Subir `MONTO_FIJO` $5 → $7 | Aplicado — con $5 el `minNotional` de Binance bloqueaba los cierres; 0 bloqueos del guardián de entrada en 1,648 señales reales |
| 24-ago | **[PRODUCCIÓN]** Activación Combo O — SOL ALCISTA+LATERAL, AVAX conectado por primera vez | Aplicado y verificado en vivo. Diagnóstico previo detectó bloqueador crítico (sizing SOL/AVAX por debajo del mínimo Binance) antes de tocar nada; corregido a `MONTO_FIJO=$5` en ambos. Posiciones BTC/ETH abiertas intactas (snapshots antes/después). Ver `2026-08-25_diagnostico-cambio-produccion-avax-sol.md`, `2026-08-25_diff-final-combo-o.patch` |
| 24-ago | **[PRODUCCIÓN]** Telegram — línea de francotiradores activos (`/consejero`) y tiempo sin operar (`/disparos`) | 2 cambios chicos aplicados y verificados. `/disparos` reusa infraestructura existente (no comando nuevo) — extiende el loop por moneda ya presente. Ver `2026-08-25_diseno-tiempo-sin-operar.md`, `2026-08-25_diff-tiempo-sin-operar.patch`, `2026-08-25_diff-linea-francotiradores-telegram.patch` |
| 25-ago | *(proyecto separado, `~/experimento_director_adaptativo/`)* BNB — ¿caída de BTC como señal de ENTRADA? (3 variantes: inmediata, 1 vela después, gate adicional) | 🔴 Descartado, las 3 variantes. Entrada inmediata peor que la real (WR 42.3% vs 45.3%, PF 0.982); con 1 vela de espera queda empatada (no significativo, Δ−0.06% IC95%[−1.13,0.99]); como gate adicional mejora en el punto central (+0.98% vs −0.03%/trade) pero no significativo (IC95%[−1.30,3.25]) y sin consistencia año a año (n=1-3 en varios años). El rebote de 24h es real pero chico (mediana +0.88%) frente al TP real (6.5%) — no sobrevive a un trade completo. Ver `experimento_director_adaptativo/reports/2026-08-25_bnb-entrada-tras-caida-btc.md` |
| 25-ago | *(proyecto separado, `~/experimento_director_adaptativo/`)* Profundización BTC→BNB (par más consistente del ranking de correlación) | Hallazgo contrario a la hipótesis: BTC cae ≥3%/24h → BNB tiende a **rebotar** (mediana +0.88%, bootstrap significativo IC95% [0.21,1.33], consistente 9/10 años), no a caer con él. BTC sube fuerte no muestra reacción significativa. No sirve como señal de aviso para cerrar BNB — sugiere lo opuesto. Profundizado en la fila de arriba (como señal de entrada, también descartado). Ver `experimento_director_adaptativo/reports/2026-08-25_btc-lidera-bnb.md` |
| 25-ago | *(proyecto separado, `~/experimento_director_adaptativo/`)* Director adaptativo Fase 1+1B — cambiar dinámicamente entre A y O según fase global de mercado, 9 combinaciones de ventana/líder/frecuencia | Descartado en 8 de 9 combinaciones — pero **ventana 150 + voto 5 monedas + revisión diaria SÍ supera a O fijo** (Sharpe 4.336 vs 4.060, PnL $50.40 vs $47.84, mejor racha), con el trade-off de peor drawdown (−14.62% vs −12.92%). No es una tendencia general de "detectar más rápido = mejor" — es una combinación específica frágil. Ver `experimento_director_adaptativo/reports/2026-08-25_fase1-viabilidad.md` y `-fase1b-deteccion-rapida.md` |
| 25-ago | Perfil de perdedoras + circuit breaker (A y O, $20 real) | Sin señal de aviso previo clara (RSI/volumen/ATR de entrada casi iguales ganadoras/perdedoras); circuit breaker (3 pérdidas→pausa 7 días) mejora DD en ambas pero es mixto (cuesta $ en A, empeora la racha máxima en O); mayor parte del costo viene de rachas cortas (1-3), no largas |
| 25-ago | Recálculo A vs. O con capital real ($20) | Ganancia en $ idéntica en cualquier capital base ($24.03/$47.84, `MONTO_FIJO` fijo); WR/PF/Sharpe/racha invariantes; DD%/retorno%/peor30d% sí cambian (DD de O sube a −12.92% con $20); O requiere hasta $20 simultáneos (4 francotiradores × $5), sin margen libre hoy |
| 25-ago | Torneo de francotiradores — Fase 2 (10 combinaciones nuevas, 3 y 4 francotiradores) | O (4 francotiradores, 100% SPOT) supera a B en Sharpe y retorno; N (con AVAX bajista) sigue siendo el mejor de 3 pero requiere Futuros; ninguna significativa vs A/B (ver cola #1) |
| 25-ago | Correlación 5 monedas — Fase A (entradas) y Fase B (posiciones abiertas) | Fase A: ninguna de 40 combinaciones significativa (IC cruza cero en las 22 que pasan el filtro); Fase B: no evaluable, 0/40 combos llegan a n≥30 (máx. observado 7) — limitación estructural, no resultado nulo (ver cola #10) |
| 24-ago | Torneo de francotiradores (15 combinaciones, Fase 1) | ALCISTA significativamente mejor que LATERAL; config actual no es la óptima (ver cola #1) |
| 24-ago | Volatilidad como filtro de entrada (BTC/ETH/SOL) | BTC/ETH empeoran, SOL prometedor no confirmado (ver cola #2) |
| 24-ago | Volatilidad como aviso de salida (postergación) | 🔴 Descartado — mediana 0.00pp pese a n≥30 |
| 24-ago | Antecedentes de movimientos grandes (Fase 1 exploratoria, múltiples umbrales) | Umbral 5% da n≥30 en las 3 monedas; ATR elevado previo es la única variable con patrón consistente |
| 24-ago | Ajuste por mecha en el TP | 🔴 Descartado — máx. 17 eventos de calendario independientes |
| 24-ago | Análisis de outliers del trailing k×ATR | Exploratorio — origina la hipótesis de "ajuste por mecha" (descartada arriba) |
| 23-ago | TP postergado con trailing k×ATR | 🔴 Descartado — 94-100% del efecto en 1-2 trades por moneda |
| 24-ago | Combinación RSI 55-75 + MAX_OP_TOTAL=2 (BTC) | 🔴 Descartado — no significativo, trade-off desproporcionado |
| 24-ago | Fase 2-B — gates restantes (Parte 1: 6 gates × umbral; Parte 2: EMA50-BASE20, compresión, Sistema C) | Ninguno significativo; Sistema C BTC pasa de 🟡 a 🔴 |
| 24-ago | Auditoría de gates inertes (remoción completa) | Sin efecto medible en ninguno de los 3 |
| 23-ago | Fase 2 — aporte individual de gates (RSI/EMA/MAX_OP_TOTAL/multitimeframe) | Ninguno significativo; MAX_OP_TOTAL=2 no implementado (decisión Ariel) |
| 23-ago | Bug de offset de timestamps (UTC-4) en backups de 4h | Corregido en disco (sin commit, `.gitignore`d) en v2 y v3-backup |
| 23-ago | Experimento Dennis/Turtle + Prueba D/E (gestión de riesgo y salida alternativa) | 🔴 Archivado en ambas monedas tras estrés-test completo (granularidad real 4min) |
| 22-ago | Reorganización `CLAUDE.md`/`INVESTIGACION.md` (82.9k → 21.2k + 76.9k chars) | Commit `51d46c4` |
| 22-ago | Fix `gestor_billetera.py` — `ultima_actualizacion` no se actualizaba | Commit `3825d50` |
| 22-ago | Fix `reconciliar.py` — polvo bajo 1 tick descartado en silencio | Commit `3760b6b` |
| 24-ago | Reorganización de archivos sueltos del home (fuera de `bot-padre-v2/`) | 46 ítems movidos, nada borrado — ver cola #3, #4 |

## REGLAS PERMANENTES

Metodología acumulada de toda la serie de investigaciones — aplicar sin que haga falta repetirla.

1. **Evaluar mecanismos de salida con precisión de 1h (o más fina), nunca solo con el cierre de
   4h.** La evaluación gruesa infla sistemáticamente los resultados — visto en detector de vela
   fuerte (+67pp a 4h → ~0 a 1h), Prueba D (PF 2.1 a 4h → 1.5 o negativo a 4min real), TP
   postergado.
2. **No concluir de una ventana con n<30** (n<10 para descartar de plano). Muestras chicas generan
   "hallazgos" que se revierten con más datos — pasó 4 veces esta sesión (mtf SOL LATERAL, eventos
   SOL LATERAL, horario×calidad, fix memoria por símbolo).
3. **Un mecanismo con "piso"** (nunca puede cerrar peor que el baseline) **hace que el bootstrap
   "no cruce cero" de forma mecánica, no como evidencia real** — el criterio que decide en esos
   casos es la dependencia de outliers (top-3/top-5 como % del efecto total), no el IC.
4. **Contar eventos de calendario únicos, no solo trades**, cuando varias monedas pueden compartir
   la misma vela/fecha de disparo (ej. 2026-08-19 en BTC/ETH/SOL a la vez) — son el mismo evento de
   mercado, no observaciones independientes.
5. **Verificar el bug de offset de timestamps (UTC-4)** antes de confiar en cualquier hallazgo
   basado en la hora del día — ya invalidó 1 hallazgo (horario×calidad) y afectó la confianza en
   otros 2.
6. **Antes de asumir el valor de un parámetro de producción, comprobar con grep si el francotirador
   importa `config_cartera.py` o lo tiene hardcodeado** — confirmado que difieren para BTC.
7. **Mirar siempre mediana y % del top-5, no solo media/PF** — una media/PF positivos empujados por
   una cola de outliers no son un candidato.
8. **Walk-forward de mínimo 3 ventanas, y out-of-sample real (forward) cuando exista** — el
   candidato BNB mostró que un backtest 🟡 prometedor puede volverse negativo en forward real 2026.
9. **Reusar datasets `evaluar()`/`revisar_cierres()` literal ya validados en vez de recalcular** —
   criterio aplicado en toda la serie de gates de esta sesión.
10. **Bootstrap no pareado cuando los conjuntos de entrada difieren entre variantes; pareado cuando
    comparten timestamps exactos** — usar el que corresponda según el solapamiento real, no asumir
    uno fijo.
11. **α ajustado por Bonferroni cuando se prueban múltiples variantes/comparaciones a la vez**, no
    un α fijo para toda la sesión.
12. **Cerrar todo reporte con "qué no se hizo"** (no se tocó producción, no se activó nada, no se
    hizo commit).
