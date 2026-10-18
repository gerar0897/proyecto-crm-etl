"""
Configuración de conexiones del ETL.

Los valores por defecto corresponden al contenedor local de docker-compose.yml.
Para usar otro servidor o credenciales, definir variables de entorno antes de
ejecutar los scripts (no es necesario modificar el código):

    DB_HOST       (por defecto: localhost)
    DB_PORT       (por defecto: 3306)
    DB_USER       (por defecto: root)
    DB_PASSWORD   (por defecto: root123  -> solo entorno local de desarrollo)
    DB_ORIGEN     (por defecto: crm_fuente)   base sintética con los datos del CRM
    DB_DW         (por defecto: dw_crm_2026)  Data Warehouse destino

Nota: la base "suitecrm" es de la aplicación SuiteCRM y el ETL no la usa.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "root123")
DB_ORIGEN = os.getenv("DB_ORIGEN", "crm_fuente")
DB_DW = os.getenv("DB_DW", "dw_crm_2026")


def _engine(base):
    # URL.create escapa correctamente contraseñas con caracteres especiales (@, :, /)
    url = URL.create(
        "mysql+pymysql",
        username=DB_USER, password=DB_PASSWORD,
        host=DB_HOST, port=DB_PORT, database=base,
        query={"charset": "utf8mb4"},
    )
    return create_engine(url)


ENGINE_ORIGEN = _engine(DB_ORIGEN)
ENGINE_DW = _engine(DB_DW)
