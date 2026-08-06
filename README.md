# Proyecto CRM ETL — Inteligencia Comercial y CRM

Data Warehouse dimensional para análisis de ventas y actividades comerciales.
Especialización en Ingeniería de Datos — Universidad de El Salvador, Julio 2026.

## Equipo

- Gerardo Figueroa
- Roberto Ángel Aragón
- Edwin Barrera

## Arquitectura

- **Origen**: SuiteCRM (MySQL) — sistema OLTP con datos ficticios de prueba.
- **ETL**: Python 3 + pandas + SQLAlchemy.
- **Destino**: Data Warehouse dimensional `dw_crm_2026` (MySQL).
- **Modelo**: Star Schema Kimball con 2 fact tables y 7 dimensiones.

## Estructura del proyecto

```
proyecto-crm-etl/
├── CreacionDW.sql         # Script de creación del modelo dimensional
├── LlenarDimTiempo.sql    # Genera dim_tiempo (2023-2027)
├── carga_inicial.py       # ETL de las 6 dimensiones desde SuiteCRM
├── carga_facts.py         # ETL de fact_opportunities y fact_actividades
├── requirements.txt       # Dependencias Python
└── README.md
```

## Requisitos previos

- Python 3.10 o superior
- Docker con MySQL 8 corriendo (base `suitecrm` con datos de prueba)
- DBeaver (opcional, para explorar el DW visualmente)

## Setup

### 1. Clonar el repositorio

```bash
git clone <url-del-repo>
cd proyecto-crm-etl
```

### 2. Crear entorno virtual e instalar dependencias

```bash
python3 -m venv venv
source venv/bin/activate      # macOS/Linux
venv\Scripts\activate         # Windows
pip install -r requirements.txt
```

### 3. Ejecutar scripts SQL en DBeaver

Conectado al MySQL de Docker, ejecutar en orden:

1. `CreacionDW.sql` — crea la base `dw_crm_2026` y todas las tablas.
2. `LlenarDimTiempo.sql` — llena `dim_tiempo` con el rango 2023-2027.

### 4. Ejecutar los scripts Python

```bash
python3 carga_inicial.py    # Carga las 6 dimensiones desde SuiteCRM
python3 carga_facts.py      # Carga fact_opportunities y fact_actividades
```

## Modelo dimensional

### Fact tables

- **`fact_opportunities`** — grano: una oportunidad de venta.
  Métricas: monto, probabilidad, ciclo_venta_dias, ganada.
- **`fact_actividades`** — grano: una actividad (call o meeting).
  Métricas: duracion_horas, contador_actividad.

### Dimensiones

- `dim_tiempo` (generada)
- `dim_vendedor`, `dim_cuenta`, `dim_lead`, `dim_contacto` (desde SuiteCRM)
- `dim_sales_stage`, `dim_tipo_actividad` (catálogos definidos en el ETL)

### Dimensiones conformadas

`dim_vendedor` y `dim_tiempo` son compartidas por ambas fact tables,
permitiendo análisis cruzados de oportunidades vs actividades.

## Estado actual del proyecto

- [x] Modelo dimensional diseñado y creado
- [x] Dimensión de tiempo generada (2023-2027)
- [x] Carga inicial de dimensiones desde SuiteCRM
- [x] Carga inicial de fact tables con lookups a dimensiones
- [ ] Carga incremental (SCD Tipo 1 y 2)
- [ ] Dashboards en Metabase
