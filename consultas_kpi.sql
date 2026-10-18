-- =====================================================================
-- Consultas de validación y KPIs sobre el Data Warehouse (dw_crm_2026)
-- Proyecto: Inteligencia Comercial y CRM
--
-- Ejecutar con la base dw_crm_2026 seleccionada. Todas son de solo lectura.
-- Riesgo de doble conteo: NUNCA unir las dos fact tables solo por vendedor_sk;
-- para combinarlas se usa oportunidad_dd (clave degenerada compartida).
-- =====================================================================
USE dw_crm_2026;

-- ---------------------------------------------------------------------
-- V1. Conteo de filas por tabla (esperado con los datos sintéticos:
--     dim_vendedor 8, dim_cuenta 50, dim_lead 120, dim_contacto 80,
--     dim_sales_stage 10, dim_tipo_actividad 2, dim_tiempo 1826,
--     fact_opportunities 150, fact_actividades 350)
-- ---------------------------------------------------------------------
SELECT 'dim_vendedor' AS tabla, COUNT(*) AS filas FROM dim_vendedor
UNION ALL SELECT 'dim_cuenta',          COUNT(*) FROM dim_cuenta
UNION ALL SELECT 'dim_lead',            COUNT(*) FROM dim_lead
UNION ALL SELECT 'dim_contacto',        COUNT(*) FROM dim_contacto
UNION ALL SELECT 'dim_sales_stage',     COUNT(*) FROM dim_sales_stage
UNION ALL SELECT 'dim_tipo_actividad',  COUNT(*) FROM dim_tipo_actividad
UNION ALL SELECT 'dim_tiempo',          COUNT(*) FROM dim_tiempo
UNION ALL SELECT 'fact_opportunities',  COUNT(*) FROM fact_opportunities
UNION ALL SELECT 'fact_actividades',    COUNT(*) FROM fact_actividades;

-- ---------------------------------------------------------------------
-- V2. Integridad: actividades cuya oportunidad no existe en
--     fact_opportunities (esperado: 0). oportunidad_dd es clave degenerada,
--     no una FK declarada, por eso se valida aquí.
-- ---------------------------------------------------------------------
SELECT COUNT(*) AS actividades_sin_oportunidad
FROM fact_actividades fa
LEFT JOIN fact_opportunities fo ON fo.oportunidad_dd = fa.oportunidad_dd
WHERE fo.oportunidad_dd IS NULL;

-- ---------------------------------------------------------------------
-- V3. Oportunidades abiertas deben tener ciclo_venta_dias NULL y las
--     cerradas un valor (esperado: 0 filas inconsistentes).
-- ---------------------------------------------------------------------
SELECT COUNT(*) AS ciclo_inconsistente
FROM fact_opportunities f
JOIN dim_sales_stage s ON s.sales_stage_sk = f.sales_stage_sk
WHERE (s.es_cerrada = 0 AND f.ciclo_venta_dias IS NOT NULL)
   OR (s.es_cerrada = 1 AND f.ciclo_venta_dias IS NULL);

-- ---------------------------------------------------------------------
-- K1. Win Rate por vendedor (base declarada: total y cerradas)
--     Aditividad: ganadas y cerradas se suman; el porcentaje NO se suma, se recalcula.
-- ---------------------------------------------------------------------
SELECT v.nombre_completo                                              AS vendedor,
       COUNT(*)                                                       AS oportunidades,
       SUM(f.ganada)                                                  AS ganadas,
       SUM(s.es_cerrada)                                              AS cerradas,
       ROUND(100 * SUM(f.ganada) / COUNT(*), 1)                       AS win_rate_sobre_total_pct,
       ROUND(100 * SUM(f.ganada) / NULLIF(SUM(s.es_cerrada), 0), 1)   AS win_rate_sobre_cerradas_pct
FROM fact_opportunities f
JOIN dim_vendedor    v ON v.vendedor_sk    = f.vendedor_sk
JOIN dim_sales_stage s ON s.sales_stage_sk = f.sales_stage_sk
GROUP BY v.vendedor_sk, v.nombre_completo
ORDER BY win_rate_sobre_cerradas_pct DESC;

-- K1 global (esperado: 18 ganadas / 31 cerradas / 150 total -> 12.0 % y 58.1 %)
SELECT COUNT(*)                                                       AS oportunidades,
       SUM(f.ganada)                                                  AS ganadas,
       SUM(s.es_cerrada)                                              AS cerradas,
       ROUND(100 * SUM(f.ganada) / COUNT(*), 1)                       AS win_rate_sobre_total_pct,
       ROUND(100 * SUM(f.ganada) / NULLIF(SUM(s.es_cerrada), 0), 1)   AS win_rate_sobre_cerradas_pct
FROM fact_opportunities f
JOIN dim_sales_stage s ON s.sales_stage_sk = f.sales_stage_sk;

-- ---------------------------------------------------------------------
-- K2. Ciclo de venta promedio en días (solo oportunidades cerradas; AVG ignora NULL)
--     No aditivo: se promedia, nunca se suma.
-- ---------------------------------------------------------------------
SELECT v.nombre_completo                  AS vendedor,
       COUNT(f.ciclo_venta_dias)          AS cerradas,
       ROUND(AVG(f.ciclo_venta_dias), 1)  AS ciclo_promedio_dias
FROM fact_opportunities f
JOIN dim_vendedor v ON v.vendedor_sk = f.vendedor_sk
GROUP BY v.vendedor_sk, v.nombre_completo
ORDER BY ciclo_promedio_dias;

-- ---------------------------------------------------------------------
-- K3. Pipeline ponderado (abiertas) frente a ingresos ganados
--     Forecast = monto * probabilidad / 100. En las ganadas la probabilidad es 100,
--     así que forecast = real; lo informativo es el pipeline abierto ponderado.
-- ---------------------------------------------------------------------
SELECT ROUND(SUM(CASE WHEN s.es_cerrada = 0 THEN f.monto * f.probabilidad / 100 ELSE 0 END), 2) AS pipeline_abierto_ponderado,
       ROUND(SUM(CASE WHEN s.es_cerrada = 0 THEN f.monto ELSE 0 END), 2)                        AS pipeline_abierto_sin_ponderar,
       ROUND(SUM(CASE WHEN f.ganada = 1 THEN f.monto ELSE 0 END), 2)                            AS ingresos_ganados
FROM fact_opportunities f
JOIN dim_sales_stage s ON s.sales_stage_sk = f.sales_stage_sk;

-- ---------------------------------------------------------------------
-- K4. Actividades por oportunidad, por responsable de la oportunidad.
--     Unión 1:N por oportunidad_dd (cada actividad pertenece a una sola oportunidad):
--     no infla el conteo. Global esperado: 350 / 150 = 2.33
-- ---------------------------------------------------------------------
SELECT v.nombre_completo                                                   AS vendedor,
       COUNT(DISTINCT fo.oportunidad_dd)                                   AS oportunidades,
       COUNT(fa.actividad_dd)                                              AS actividades,
       ROUND(COUNT(fa.actividad_dd) / COUNT(DISTINCT fo.oportunidad_dd), 2) AS actividades_por_oportunidad
FROM fact_opportunities fo
JOIN dim_vendedor v           ON v.vendedor_sk = fo.vendedor_sk
LEFT JOIN fact_actividades fa ON fa.oportunidad_dd = fo.oportunidad_dd
GROUP BY v.vendedor_sk, v.nombre_completo
ORDER BY actividades_por_oportunidad DESC;

-- ---------------------------------------------------------------------
-- K5. Lead-to-Opportunity rate (proxy): leads convertidos / total de leads.
--     Se calcula solo desde dim_lead porque la fuente no relaciona leads con
--     oportunidades. Esperado global: 53 / 120 = 44.2 %
--     (Con el campo estado = 'Converted' serían 71 / 120 = 59.2 %; ver README, RN-05.)
-- ---------------------------------------------------------------------
SELECT fuente,
       COUNT(*)                                    AS leads,
       SUM(convertido)                             AS convertidos,
       ROUND(100 * SUM(convertido) / COUNT(*), 1)  AS tasa_conversion_pct
FROM dim_lead
GROUP BY fuente
ORDER BY tasa_conversion_pct DESC;

-- ---------------------------------------------------------------------
-- K6. Oportunidades y monto ganado por fuente de prospecto
-- ---------------------------------------------------------------------
SELECT f.fuente,
       COUNT(*)                                                     AS oportunidades,
       SUM(f.ganada)                                                AS ganadas,
       ROUND(SUM(CASE WHEN f.ganada = 1 THEN f.monto ELSE 0 END), 2) AS monto_ganado
FROM fact_opportunities f
GROUP BY f.fuente
ORDER BY oportunidades DESC;

-- ---------------------------------------------------------------------
-- K7. Oportunidades y monto ganado por industria del cliente
-- ---------------------------------------------------------------------
SELECT c.industria,
       COUNT(*)                                                     AS oportunidades,
       SUM(f.ganada)                                                AS ganadas,
       ROUND(SUM(CASE WHEN f.ganada = 1 THEN f.monto ELSE 0 END), 2) AS monto_ganado
FROM fact_opportunities f
JOIN dim_cuenta c ON c.cuenta_sk = f.cuenta_sk
GROUP BY c.industria
ORDER BY oportunidades DESC;

-- ---------------------------------------------------------------------
-- K8. Pipeline por etapa (embudo)
-- ---------------------------------------------------------------------
SELECT s.orden_pipeline, s.sales_stage_nk AS etapa,
       COUNT(*)                  AS oportunidades,
       ROUND(SUM(f.monto), 2)    AS monto_total
FROM fact_opportunities f
JOIN dim_sales_stage s ON s.sales_stage_sk = f.sales_stage_sk
GROUP BY s.sales_stage_sk, s.orden_pipeline, s.sales_stage_nk
ORDER BY s.orden_pipeline;

-- ---------------------------------------------------------------------
-- K9. Oportunidades creadas por mes (dim_tiempo, rol "fecha de creación")
-- ---------------------------------------------------------------------
SELECT t.anio, t.mes, t.nombre_mes,
       COUNT(*)                AS oportunidades_creadas,
       ROUND(SUM(f.monto), 2)  AS monto_creado
FROM fact_opportunities f
JOIN dim_tiempo t ON t.tiempo_sk = f.fecha_creacion_sk
GROUP BY t.anio, t.mes, t.nombre_mes
ORDER BY t.anio, t.mes;
