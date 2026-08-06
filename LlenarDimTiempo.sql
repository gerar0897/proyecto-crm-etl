-- =====================================================================
-- Script de carga de dim_tiempo
-- Genera un registro por cada día en el rango indicado.
-- Rango por defecto: 2023-01-01 a 2027-12-31 (1826 días)
-- =====================================================================

USE dw_crm_2026;

DELIMITER //

DROP PROCEDURE IF EXISTS llenar_dim_tiempo //

CREATE PROCEDURE llenar_dim_tiempo(IN fecha_inicio DATE, IN fecha_fin DATE)
BEGIN
    DECLARE fecha_actual DATE;
    SET fecha_actual = fecha_inicio;

    WHILE fecha_actual <= fecha_fin DO
        INSERT INTO dim_tiempo (
            tiempo_sk,
            fecha,
            dia,
            mes,
            nombre_mes,
            trimestre,
            anio,
            dia_semana,
            nombre_dia,
            es_fin_semana
        ) VALUES (
            CAST(DATE_FORMAT(fecha_actual, '%Y%m%d') AS UNSIGNED),
            fecha_actual,
            DAY(fecha_actual),
            MONTH(fecha_actual),
            CASE MONTH(fecha_actual)
                WHEN 1 THEN 'Enero'    WHEN 2 THEN 'Febrero'  WHEN 3 THEN 'Marzo'
                WHEN 4 THEN 'Abril'    WHEN 5 THEN 'Mayo'     WHEN 6 THEN 'Junio'
                WHEN 7 THEN 'Julio'    WHEN 8 THEN 'Agosto'   WHEN 9 THEN 'Septiembre'
                WHEN 10 THEN 'Octubre' WHEN 11 THEN 'Noviembre' WHEN 12 THEN 'Diciembre'
            END,
            QUARTER(fecha_actual),
            YEAR(fecha_actual),
            DAYOFWEEK(fecha_actual),
            CASE DAYOFWEEK(fecha_actual)
                WHEN 1 THEN 'Domingo'   WHEN 2 THEN 'Lunes'    WHEN 3 THEN 'Martes'
                WHEN 4 THEN 'Miércoles' WHEN 5 THEN 'Jueves'   WHEN 6 THEN 'Viernes'
                WHEN 7 THEN 'Sábado'
            END,
            CASE WHEN DAYOFWEEK(fecha_actual) IN (1, 7) THEN TRUE ELSE FALSE END
        );

        SET fecha_actual = DATE_ADD(fecha_actual, INTERVAL 1 DAY);
    END WHILE;
END //

DELIMITER ;

-- Ejecutar el procedimiento con el rango deseado
CALL llenar_dim_tiempo('2023-01-01', '2027-12-31');

-- Verificación
SELECT COUNT(*) AS total_dias FROM dim_tiempo;
SELECT MIN(fecha) AS fecha_min, MAX(fecha) AS fecha_max FROM dim_tiempo;