# laboratorio/ — chequeos permanentes del simulador

No son análisis de una vez: son verificaciones que se vuelven a correr cuando
haga falta, y que fallan ruidosamente si algo se rompió.

| Script | Qué verifica | Cuándo correrlo |
|---|---|---|
| `verificar_datos.py` | L1 · integridad de los datos históricos: huecos, duplicados, OHLC imposible, cruce entre las dos fuentes (1m agregados vs backup 4h), muestra contra la API de Binance, y si los huecos caen dentro de las ventanas de los estudios registrados | tras actualizar `data_1m/` o el backup 4h |
| `verificar_reproducibilidad.py` | L2 · que el mismo tramo dé el mismo resultado cambiando una cosa por vez: misma corrida dos veces, distinto `PYTHONHASHSEED`, distinto `--tmpdir`, y que la bandera obsoleta `--corregir-desfase` siga siendo no-op | tras tocar el simulador |
| `validar_fuera_muestra.py` | L3 · si elegir "la mejor" configuración **generaliza** o selecciona ruido: estabilidad del orden entre años, la misma prueba dentro de cada grupo, y walk-forward encadenado contra elegir al azar y contra el techo | **antes de aplicar cualquier configuración porque "ganó"** |
| `verificar_mocks.py` | L12 · **deriva entre los sandboxes y producción**: compara estáticamente cada módulo falso que un sandbox instala en `sys.modules` contra el módulo real (firma por firma, constante por constante) y marca lo que **rompe** (TypeError) aparte de lo que **acepta pero ignora** — el caso silencioso. Lista además los francotiradores pausados por código, que dan 0 trades sin avisar | **antes de correr cualquier sandbox de `sistema_c/`**, y en cada push (CI) |

Todos devuelven **exit code distinto de cero** si algo falla, así que sirven
para un hook o para CI (ver L7 en la cola).

`verificar_mocks.py` guarda en `mocks_baseline.json` las divergencias ya
conocidas y **sólo falla con las nuevas**. El baseline arranca con las **65
`SILENCIOSO`** (mocks deliberadamente permisivos: avisos de Telegram, eventos,
contabilidad — cosas que un backtest no debe modelar) y **deja afuera a
propósito las 13 `ROMPE`**, así que hoy el chequeo termina en rojo: esa es la
deuda del ítem 0b, visible en cada corrida hasta que se salde. El baseline es
deuda declarada, no permiso — vaciarlo es la meta. Para registrar una
excepción: `--actualizar`, y decir en `COLA.md` por qué se acepta.

**Contexto:** nacieron el 2026-09-07 del bloque de laboratorio, después de que
en una sola jornada aparecieran cinco artefactos de ventana corta y uno llegara
a quedar registrado como hallazgo general antes de detectarse.
Ver `reports/2026-09-07_L1-integridad-datos-historicos.md`.
