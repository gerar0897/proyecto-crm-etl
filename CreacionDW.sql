-- =====================================================================
-- Script de creación del Data Warehouse dimensional
-- Proyecto: Inteligencia Comercial y CRM
-- Modelo: Kimball (Star Schema)
-- =====================================================================

CREATE DATABASE IF NOT EXISTS dw_crm_2026
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE dw_crm_2026;

-- =====================================================================
-- DIMENSIONES
-- =====================================================================

CREATE TABLE dim_tiempo (
    tiempo_sk INT PRIMARY KEY,
    fecha DATE NOT NULL,
    dia TINYINT NOT NULL,
    mes TINYINT NOT NULL,
    nombre_mes VARCHAR(20) NOT NULL,
    trimestre TINYINT NOT NULL,
    anio SMALLINT NOT NULL,
    dia_semana TINYINT NOT NULL,
    nombre_dia VARCHAR(20) NOT NULL,
    es_fin_semana BOOLEAN NOT NULL
);

CREATE TABLE dim_vendedor (
    vendedor_sk INT AUTO_INCREMENT PRIMARY KEY,
    vendedor_nk VARCHAR(36) NOT NULL,
    nombre VARCHAR(100),
    apellido VARCHAR(100),
    nombre_completo VARCHAR(200),
    email VARCHAR(150),
    cargo VARCHAR(100),
    departamento VARCHAR(100)
);

CREATE TABLE dim_cuenta (
    cuenta_sk INT AUTO_INCREMENT PRIMARY KEY,
    cuenta_nk VARCHAR(36) NOT NULL,
    nombre_empresa VARCHAR(200),
    industria VARCHAR(100),
    ingresos_anuales DECIMAL(15,2),
    pais VARCHAR(100)
);

CREATE TABLE dim_lead (
    lead_sk INT AUTO_INCREMENT PRIMARY KEY,
    lead_nk VARCHAR(36) NOT NULL,
    fuente VARCHAR(100),
    estado VARCHAR(100),
    convertido BOOLEAN
);

CREATE TABLE dim_contacto (
    contacto_sk INT AUTO_INCREMENT PRIMARY KEY,
    contacto_nk VARCHAR(36) NOT NULL,
    nombre VARCHAR(100),
    apellido VARCHAR(100),
    nombre_completo VARCHAR(200),
    email VARCHAR(150),
    telefono VARCHAR(50)
);

CREATE TABLE dim_sales_stage (
    sales_stage_sk INT AUTO_INCREMENT PRIMARY KEY,
    sales_stage_nk VARCHAR(50) NOT NULL,
    descripcion VARCHAR(200),
    orden_pipeline TINYINT,
    es_cerrada BOOLEAN,
    es_ganada BOOLEAN
);

CREATE TABLE dim_tipo_actividad (
    tipo_actividad_sk INT AUTO_INCREMENT PRIMARY KEY,
    tipo_actividad_nk VARCHAR(20) NOT NULL,
    descripcion VARCHAR(100)
);

-- =====================================================================
-- FACT TABLES
-- =====================================================================

CREATE TABLE fact_opportunities (
    vendedor_sk INT NOT NULL,
    cuenta_sk INT NOT NULL,
    sales_stage_sk INT NOT NULL,
    fecha_creacion_sk INT NOT NULL,
    fecha_cierre_sk INT,
    oportunidad_dd VARCHAR(36) NOT NULL,
    monto DECIMAL(15,2),
    probabilidad DECIMAL(5,2),
    ciclo_venta_dias INT,
    ganada BOOLEAN,
    FOREIGN KEY (vendedor_sk) REFERENCES dim_vendedor(vendedor_sk),
    FOREIGN KEY (cuenta_sk) REFERENCES dim_cuenta(cuenta_sk),
    FOREIGN KEY (sales_stage_sk) REFERENCES dim_sales_stage(sales_stage_sk),
    FOREIGN KEY (fecha_creacion_sk) REFERENCES dim_tiempo(tiempo_sk),
    FOREIGN KEY (fecha_cierre_sk) REFERENCES dim_tiempo(tiempo_sk)
);

CREATE TABLE fact_actividades (
    vendedor_sk INT NOT NULL,
    tipo_actividad_sk INT NOT NULL,
    fecha_actividad_sk INT NOT NULL,
    contacto_sk INT,
    lead_sk INT,
    actividad_dd VARCHAR(36) NOT NULL,
    estado VARCHAR(50),
    duracion_horas DECIMAL(6,2),
    contador_actividad INT DEFAULT 1,
    FOREIGN KEY (vendedor_sk) REFERENCES dim_vendedor(vendedor_sk),
    FOREIGN KEY (tipo_actividad_sk) REFERENCES dim_tipo_actividad(tipo_actividad_sk),
    FOREIGN KEY (fecha_actividad_sk) REFERENCES dim_tiempo(tiempo_sk),
    FOREIGN KEY (contacto_sk) REFERENCES dim_contacto(contacto_sk),
    FOREIGN KEY (lead_sk) REFERENCES dim_lead(lead_sk)
);

-- =====================================================================
-- TABLA AUXILIAR DE PARÁMETROS (para futura carga incremental)
-- =====================================================================

CREATE TABLE parametros (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    valor VARCHAR(500) NOT NULL
);

INSERT INTO parametros (nombre, valor) VALUES ('ultima_fecha_ejecucion', '2026-07-28');