# CIERRE FINAL - Bot Padre v2

Estos eran los ÚNICOS 3 puntos pendientes para considerar el código
técnicamente listo para operar en real. **Los 3 están resueltos y verificados
(2026-07-29).**

1. ✅ **Resuelto (commit `ac3dcd0`).** Corregir asimetría contable: auditoria.csv
   registra ahora el precio REAL de cierre (`precio_actual`), no el teórico
   (`sl_efectivo`), en las 3 ramas de SL (BE, trailing, SL normal) de los 15
   francotiradores.

2. ✅ **Resuelto (commit `04b4074`).** Cerrado el hueco de monitoreo nocturno:
   el sistema evalúa el SL las 24 horas (`revisar_cierres(..., evaluar_tp=False)`
   cuando el horario corta); el TP sigue exigiendo la ventana 4-21h UTC-4.

3. ✅ **Resuelto (commit `0278d48`).** Segunda confirmación técnica antes de
   operar en REAL: `ejecutor.py` exige además la variable de entorno
   `BOT_REAL_CONFIRMADO=true` en el proceso — `modo.json` diciendo `"REAL"` ya
   no alcanza por sí solo.

Detalle completo de cada cambio en `CLAUDE.md` (secciones "Modo de operación",
"Gestión de salidas vs gates de entrada" y "Asimetría TP/SL en el registro de
cierres").

REGLA: no se agregan puntos nuevos a esta lista sin que Ariel lo apruebe
explícitamente. Cualquier deuda técnica adicional que surja de acá en más se
documenta en `CLAUDE.md`, no acá.
