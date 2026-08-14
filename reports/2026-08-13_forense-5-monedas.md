# Forense 5 monedas — BTCUSDT / SOLUSDT / BNBUSDT / AVAXUSDT

**Metodología:** misma que el forense ETH del 2026-08-13.  
**Datos:** ETHUSDT/BTCUSDT/SOLUSDT/BNBUSDT/AVAXUSDT 4H | 2021-01-01 en adelante  
**Capital inicial:** $20 | **Monto/trade:** $5 | **Comisión:** 0.1% por lado ($0.01/trade)  
**Fases:** solo ALCISTA y LATERAL (bajistas excluidos, igual que en producción)  
**Bajistas excluidos:** el bot opera solo LONG en SPOT.

---

## Tabla comparativa — combinado (alcista + lateral)

| Moneda | Trades | WR | Expect/trade | PF | Capital final | Racha SL | Prom. mes | Mejor/Peor mes |
|--------|--------|----|--------------|----|---------------|----------|-----------|----------------|
| ETHUSDT *(ref)* | 630 (TP:291/SL:339) | 46.2% | $-0.0030 | 0.977 | $17.95 ❌ | 11 | $-0.0302 | 2022-07 $+1.73 / 2021-05 $-1.76 |
| BTCUSDT | 493 (TP:228/SL:265) | 46.2% | $-0.0080 | 0.931 | $16.07 ❌ | 10 | $-0.0634 | 2021-02 $+1.29 / 2021-05 $-1.86 |
| SOLUSDT | 1183 (TP:568/SL:615) | 48.0% | $-0.0008 | 0.993 | $18.99 ❌ | 8 | $-0.0162 | 2021-02 $+2.84 / 2024-04 $-2.30 |
| BNBUSDT | 649 (TP:319/SL:330) | 49.2% | $-0.0015 | 0.987 | $19.01 ❌ | 8 | $-0.0160 | 2021-02 $+1.76 / 2022-11 $-1.64 |
| AVAXUSDT | 1150 (TP:548/SL:602) | 47.7% | $-0.0027 | 0.980 | $16.92 ❌ | 9 | $-0.0496 | 2023-11 $+2.81 / 2022-04 $-2.26 |

---

## Desglose por fase — cada moneda

| Moneda / Fase | Trades | WR | Expect/trade | PF | Capital final | Racha SL | Prom. mes | Mejor/Peor mes |
|---------------|--------|----|--------------|----|---------------|----------|-----------|----------------|
| ETH *(ref)* — ALCISTA | 254 (TP:132/SL:122) | 52.0% | $+0.0118 | 1.105 | $23.01 ✅ | 8 | $+0.0519 | 2024-02 $+1.68 / 2025-03 $-0.70 |
| ETH *(ref)* — LATERAL | 376 (TP:159/SL:217) | 42.3% | $-0.0130 | 0.904 | $15.12 ❌ | 10 | $-0.0801 | 2021-01 $+1.13 / 2021-05 $-2.02 |
| | | | | | | | | |
| BTCUSDT — ALCISTA | 205 (TP:98/SL:107) | 47.8% | $+0.0029 | 1.022 | $20.60 ✅ | 7 | $+0.0100 | 2021-02 $+1.83 / 2021-05 $-0.78 |
| BTCUSDT — LATERAL | 288 (TP:130/SL:158) | 45.1% | $-0.0157 | 0.845 | $15.47 ❌ | 8 | $-0.0809 | 2022-06 $+0.77 / 2022-04 $-1.11 |
| | | | | | | | | |
| SOLUSDT — ALCISTA | 696 (TP:326/SL:370) | 46.8% | $-0.0024 | 0.983 | $18.34 ❌ | 9 | $-0.0268 | 2022-03 $+2.12 / 2021-09 $-1.90 |
| SOLUSDT — LATERAL | 487 (TP:242/SL:245) | 49.7% | $+0.0013 | 1.014 | $20.66 ✅ | 7 | $+0.0106 | 2021-01 $+1.53 / 2024-04 $-1.29 |
| | | | | | | | | |
| BNBUSDT — ALCISTA | 259 (TP:137/SL:122) | 52.9% | $+0.0163 | 1.147 | $24.21 ✅ | 5 | $+0.0739 | 2021-02 $+1.24 / 2021-05 $-0.94 |
| BNBUSDT — LATERAL | 390 (TP:182/SL:208) | 46.7% | $-0.0133 | 0.894 | $14.80 ❌ | 7 | $-0.0839 | 2021-07 $+1.46 / 2025-10 $-1.63 |
| | | | | | | | | |
| AVAXUSDT — ALCISTA | 453 (TP:224/SL:229) | 49.4% | $-0.0001 | 0.999 | $19.95 ❌ | 8 | $-0.0009 | 2021-02 $+2.19 / 2023-02 $-0.94 |
| AVAXUSDT — LATERAL | 697 (TP:324/SL:373) | 46.5% | $-0.0043 | 0.969 | $16.98 ❌ | 9 | $-0.0487 | 2023-11 $+3.25 / 2022-04 $-1.79 |
| | | | | | | | | |

---

## Parámetros usados en el forense

| Moneda | Fase | RSI entrada | SL | TP |
|--------|------|------------|----|----|
| BTCUSDT | alcista | 55–75 | 5.0% | 6.0% |
| BTCUSDT | lateral | 43–57 | 3.5% | 4.0% |
| SOLUSDT | alcista | 50–70 | 5.0% | 6.0% |
| SOLUSDT | lateral | 43–57 | 3.5% | 4.0% |
| BNBUSDT | alcista | 60–75 | 4.5% | 5.0% |
| BNBUSDT | lateral | 43–57 | 4.5% | 5.0% |
| AVAXUSDT | alcista | 60–75 | 4.5% | 5.0% |
| AVAXUSDT | lateral | 43–57 | 5.0% | 6.0% |
| ETHUSDT | alcista | 60–75 | 4.5% | 5.0% |
| ETHUSDT | lateral | 43–57 | 4.5% | 6.0% |

---

## Conclusiones

### Fase ALCISTA
- **Rentable (expectancy > 0):** BTCUSDT (PF 1.022, expect $+0.0029), BNBUSDT (PF 1.147, expect $+0.0163)
- **Pierde con comisiones:** SOLUSDT (PF 0.983), AVAXUSDT (PF 0.999)

### Fase LATERAL
- **Rentable (expectancy > 0):** SOLUSDT (PF 1.014)
- **Pierde con comisiones:** BTCUSDT (PF 0.845), BNBUSDT (PF 0.894), AVAXUSDT (PF 0.969)

### Nota metodológica
- Capital final calculado aplicando cada trade en orden cronológico desde $20. Si el capital cae por debajo de $5 el loop se detiene.
- TIMEOUT (sin resultado en 100 velas) no modifica el capital — igual que el script original.
- Los parámetros son los del bot en producción actuales (`PARAMS` del script `backtest_perfil_comparativo.py`).