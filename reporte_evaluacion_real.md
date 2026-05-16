# REPORTE EJECUTIVO — Z-Bot V2
## Evaluación de aptitud para trading real
**Fecha:** 2026-05-16  
**Evaluador:** Claude Sonnet 4.6  
**Estado actual:** Paper trading / Binance real recién conectado

---

## 1. ARQUITECTURA DEL SISTEMA

### Capa de señal — 15 Francotiradores
Cinco activos × tres fases de mercado. Cada archivo es autónomo.

| Activo | Alcista | Bajista | Lateral |
|--------|---------|---------|---------|
| BTC | francotirador_alcista_btc.py | francotirador_bajista_btc.py | francotirador_lateral_btc.py |
| ETH | francotirador_alcista_eth.py | francotirador_bajista_eth.py | francotirador_lateral_eth.py |
| SOL | francotirador_alcista_sol.py | francotirador_bajista_sol.py | francotirador_lateral_sol.py |
| BNB | francotirador_alcista_bnb.py | francotirador_bajista_bnb.py | francotirador_lateral_bnb.py |
| AVAX | francotirador_alcista_avax.py | francotirador_bajista_avax.py | francotirador_lateral_avax.py |

### Capa de orquestación
- `director_orquesta.py` → coordina los 5 directores por activo
- `director_{btc/eth/sol/bnb/avax}.py` → selecciona francotirador activo según fase
- `consejero.py` → análisis macro antes de operar
- `supervisor_v2.py` → watchdog de procesos + auto-reconciliación de posiciones huérfanas

### Capa de filtros (8 filtros en serie)
| Filtro | Función |
|--------|---------|
| `guardian_riesgo.py` | Bloquea si pérdida diaria supera umbral |
| `termometro.py` | Pausa en volatilidad extrema (ventana 50 velas) |
| `detector_multitimeframe.py` | Confirma tendencia en 1H, 4H y 1D |
| `filtro_calidad.py` | ATR mínimo, volumen, RSI aceleración, EMA alineación |
| `filtro_horario.py` | Opera solo en horario de alta liquidez |
| `filtro_eventos.py` | Pausa ante eventos macro (CPI, Fed, etc.) |
| `limitador_diario.py` | Cap de operaciones por día |
| `gestor_correlacion.py` | Evita operar activos correlacionados simultáneamente |

### Capa de ejecución
- `ejecutor.py` → órdenes MARKET reales en api.binance.com (desde 2026-05-16)
- `trailing_stop.py` → trailing dinámico con breakeven automático
- `gestor_billetera.py` → registro atómico con lock de archivo
- `memoria_propia.py` → ajusta tamaño de posición según historial por símbolo

### Capa de infraestructura
- `asistente.py` → interfaz web con Claude API para control del bot
- `tunnel_asistente.py` → túnel Cloudflare para acceso remoto
- `historial_precios.py` → SQLite con precios por hora
- `z_webserver_v2.py` → dashboard web en tiempo real
- `servidor_intel.py` → datos de mercado (volumen, liquidez, fuerza de sector)

---

## 2. PARÁMETROS ACTUALES

### Parámetros por fase (hardcodeados en francotiradores)

| Fase | RSI | SL | TP | EMA | Trail Act | Trail Dist |
|------|-----|----|----|-----|-----------|------------|
| **Alcista** | 50-70 | 3.5% | 6.0% | 20/50 | 0.5% | 1.0% |
| **Bajista** | 30-50 | 3.5% | 6.0% | 20/50 | 0.5% | 1.0% |
| **Lateral** | 43-57 | 3.5% | 4.0% | 10/30 | 0.5% | 1.0% |

### Gestión de capital
- **Capital máximo por operación:** 2% del capital disponible
- **Operaciones simultáneas por símbolo:** máximo 3
- **Monto mínimo Binance:** $5 USDT
- **Breakeven automático:** 2 velas (8h) + precio ≥ entrada + 0.8%

### Distribución de cartera (pesos óptimos)
| Activo | Peso |
|--------|------|
| SOLUSDT | 23.85% |
| BTCUSDT | 21.68% |
| ETHUSDT | 18.97% |
| BNBUSDT | 18.97% |
| AVAXUSDT | 16.53% |

---

## 3. RENDIMIENTO REAL EN PAPER TRADING

**Período:** 2026-03-01 → 2026-05-09 (~2.3 meses)  
**Capital inicial:** $1,000.00  
**Capital final:** $1,024.84  
**PnL absoluto:** +$24.84 (+2.48%)

### Métricas globales
| Métrica | Valor |
|---------|-------|
| Total trades cerrados | 25 |
| TP / BE / Trailing SL | 15 |
| SL puros | 10 |
| **Win Rate real** | **60.0%** |
| Posiciones abiertas | 0 |

### WR por símbolo y fase

| Símbolo + Fase | TP | SL | WR |
|----------------|----|----|----|
| BNBUSDT LATERAL | 2 | 0 | **100.0%** |
| ETHUSDT LATERAL | 4 | 1 | **80.0%** |
| AVAXUSDT LATERAL | 3 | 1 | **75.0%** |
| BTCUSDT LATERAL | 3 | 1 | **75.0%** |
| SOLUSDT LATERAL | 3 | 3 | 50.0% |
| AVAXUSDT ALCISTA | 0 | 1 | 0.0% (n=1) |
| ETHUSDT ALCISTA | 0 | 2 | 0.0% (n=2) |
| SOLUSDT ALCISTA | 0 | 1 | 0.0% (n=1) |

**Observación:** Los francotiradores laterales dominan en rendimiento. Los alcistas muestran 0 WR pero con muestras de 1-2 trades — estadísticamente no concluyente.

### Backtest histórico BTCUSDT (referencia, 11,769 velas 2021-2026)
| Configuración | WR | PF | MaxDD |
|--------------|----|----|-------|
| Alcista baseline | 42.1% | 1.24 | 0.81% |
| Bajista baseline | 36.4% | 0.98 | 1.21% |

El PF real en backtest no supera el umbral de aprobación (1.6). El WR real de paper trading (60%) supera ampliamente el backtest simple — evidencia de que los 8 filtros en serie agregan valor significativo sobre la señal pura.

---

## 4. BUGS CORREGIDOS

| # | Commit | Bug | Impacto |
|---|--------|-----|---------|
| 1 | `3db1bbb` | 6 bugs: conteo duplicados, lock billetera, historial capital, log rechazos | Crítico |
| 2 | `bb15c2a` | MIN_TRADES en memoria_propia: 3→15 (error estadístico 28%→4%) | Alto |
| 3 | `a69c5e0` | Auto-reconciliación posiciones huérfanas en supervisor | Alto |
| 4 | `245c8da` | Corrección 4 bugs adicionales en billetera y capital | Alto |
| 5 | `439d0e5` | Filtro volumen usaba vela abierta → bloqueaba todas las entradas | **Crítico** |
| 6 | `154ea92` | tunnel_asistente: spam de Telegram en cada reinicio | Medio |
| 7 | `f67da59` | Trailing dist 1.5%→1.0% (backtest: +$934 PnL) | Medio |
| 8 | `d55800e` | Termómetro: ventana ampliada 50 velas + pausa VOLATILIDAD_EXTREMA | Medio |
| 9 | `b1ccda3` | MTF lateral: requiere confirmación 4H (backtest: +$1,078 PnL) | Medio |

---

## 5. MEJORAS APLICADAS

| Mejora | Descripción |
|--------|-------------|
| Persistencia SQLite atómica | Historial de precios por hora en base de datos local |
| Dashboard web | `z_webserver_v2.py` con estado en tiempo real |
| Asistente Claude | Interfaz web para consultar y controlar el bot vía LLM |
| Túnel Cloudflare | Acceso remoto con URL fija sin exponer puertos |
| Notificaciones Telegram | Cobertura completa: entradas, salidas, filtros, errores |
| `config_cartera.py` | Fuente única de verdad para pesos y parámetros |
| `changelog.txt` | Trazabilidad de todos los cambios con fecha y motivo |
| Reconciliación de billetera | Detector y corrector de posiciones huérfanas |
| Breakeven automático | Protege capital tras 8h con ganancia ≥ 0.8% |
| **ejecutor.py → Binance real** | Órdenes MARKET reales firmadas con HMAC-SHA256 |

---

## 6. RIESGOS IDENTIFICADOS

### Riesgo CRÍTICO
| ID | Riesgo | Detalle |
|----|--------|---------|
| R1 | **Muestra estadística insuficiente** | 25 trades en 2.3 meses no son suficientes para validar el sistema. Se necesitan mínimo 100 trades para WR estable (IC 95%). |
| R2 | **ejecutor.py sin prueba en producción** | Recién conectado a Binance real. Nunca ejecutó una orden real. El primer trade real es también el primer test de integración. |
| R3 | **Keys sin cifrado** | `keys.env` almacena API keys en texto plano. Si el servidor es comprometido, las keys son accesibles. |

### Riesgo ALTO
| ID | Riesgo | Detalle |
|----|--------|---------|
| R4 | **PF backtest < 1.6** | El Profit Factor en backtest puro (1.24) no supera el umbral mínimo definido. Los filtros mejoran el WR real pero no hay evidencia cuantitativa suficiente. |
| R5 | **Alcistas con WR 0%** | Las 3 fases alcistas registradas terminaron en SL. Muestras pequeñas pero es señal de atención. |
| R6 | **Sin stop global diario configurado** | `guardian_riesgo.py` existe pero no hay validación de que el umbral de pérdida diaria esté correctamente parametrizado. |

### Riesgo MEDIO
| ID | Riesgo | Detalle |
|----|--------|---------|
| R7 | **keys hardcodeadas en conector_binance.py** | Archivo auxiliar con credenciales testnet en el código fuente. Mal hábito aunque no afecte producción. |
| R8 | **Slippage no modelado** | Las órdenes MARKET pueden ejecutarse a precios distintos al de señal, especialmente en AVAX y activos de menor liquidez. |
| R9 | **Lot size sin validar por símbolo** | `ejecutor.py` usa 6 decimales fijos para VENTA. Binance tiene precisiones distintas por símbolo (SOL: 2 dec, BTC: 5 dec). |
| R10 | **Túnel Cloudflare inestable** | Quick tunnel cambia URL al reiniciar. Sin credenciales de named tunnel, el asistente puede quedar inaccesible. |

---

## 7. RECOMENDACIÓN FINAL

### Veredicto: ❌ NO APTO para trading real en este momento

El bot tiene una arquitectura sólida, código limpio y un WR de paper trading del 60% que es prometedor. Sin embargo, existen blockers objetivos que deben resolverse antes de operar con dinero real:

### Blockers obligatorios (en orden)

1. **Prueba de fuego del ejecutor** — Ejecutar manualmente una orden real pequeña (~$10 USDT) para verificar que la integración con Binance funciona end-to-end antes de soltar el bot. Verificar permisos de la API key en el panel de Binance (`Enable Spot & Margin Trading`).

2. **Volumen de trades** — Alcanzar mínimo 100 trades cerrados en paper trading para validar el WR con significancia estadística. Con el ritmo actual (~11 trades/mes) faltan aproximadamente 7 meses.

3. **Cifrado de keys** — Mover `keys.env` fuera del directorio del repositorio o cifrarlo. Nunca debe quedar en texto plano en un servidor conectado a internet.

4. **Validar guardian_riesgo** — Confirmar que el umbral de pérdida diaria máxima está activo y calibrado (ej: máximo -5% del capital por día).

5. **Fix lot size por símbolo** — Implementar un mapa de precisión por símbolo en `ejecutor.py` para evitar errores -1111 de Binance en VENTA.

### Ruta sugerida para ir a real

```
Ahora         → Prueba de fuego ejecutor ($10 real)
+1 mes        → 35+ trades paper con WR ≥ 58%
+3 meses      → 65+ trades paper con WR ≥ 60%
+7 meses      → 100+ trades, cifrado keys, fix lot size → GO LIVE con 10% del capital
+9 meses      → Escalar al 100% si WR real ≥ 58% y PF ≥ 1.4
```

### Lo que está bien y no necesita cambios
- Lógica de filtros en serie (efectiva, WR paper 60% vs backtest puro 42%)
- Breakeven automático (protege capital en operaciones largas)
- Trailing stop dinámico
- Gestión de posición al 2% por operación (riesgo conservador)
- Infraestructura de monitoreo (Telegram, dashboard, asistente)
- Persistencia atómica con SQLite y locks

---

*Reporte generado automáticamente el 2026-05-16. Datos de rendimiento extraídos de `auditoria.csv`. Backtest sobre 11,769 velas BTCUSDT 4H (2021-2026). Ver `backtest_resultados.txt` para detalle completo.*
