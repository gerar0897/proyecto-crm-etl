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

## Setup completo (primera vez)

### 1. Clonar el repositorio

```bash
git clone https://github.com/gerar0897/proyecto-crm-etl.git
cd proyecto-crm-etl
```

### 2. Levantar los servicios Docker (MySQL + Metabase)

```bash
docker-compose up -d
```

Esto arranca:
- MySQL 8 en `localhost:3306` (usuario `root`, password `root123`)
- Metabase en `localhost:3000`

### 3. Importar los datos de SuiteCRM

Con el contenedor MySQL corriendo, importar el dump con los datos de prueba:

```bash
# Primero crear la base
docker exec -i proyecto-crm-mysql-1 mysql -uroot -proot123 -e "CREATE DATABASE IF NOT EXISTS suitecrm;"

# Luego importar el dump
docker exec -i proyecto-crm-mysql-1 mysql -uroot -proot123 suitecrm < suitecrm_dump.sql
```

En Windows, el nombre del contenedor puede variar. Verificar con:
```bash
docker ps
```

### 4. Crear entorno virtual Python e instalar dependencias

```bash
python3 -m venv venv
source venv/bin/activate      # macOS/Linux
venv\Scripts\activate         # Windows
pip install -r requirements.txt
```

### 5. Crear el Data Warehouse

Conectarse al MySQL con DBeaver (u otro cliente) y ejecutar en orden:

1. `CreacionDW.sql` — crea la base `dw_crm_2026` y todas las tablas.
2. `LlenarDimTiempo.sql` — llena `dim_tiempo` con el rango 2023-2027.

### 6. Ejecutar los scripts Python de carga

```bash
python3 carga_inicial.py    # Carga las 6 dimensiones desde SuiteCRM
python3 carga_facts.py      # Carga fact_opportunities y fact_actividades
```

### 7. Verificar en DBeaver

Con las 8 dimensiones y 2 fact tables cargadas, el DW está listo para consultas analíticas.