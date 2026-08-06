
"""
Script de Carga Inicial del Data Warehouse
Proyecto: Inteligencia Comercial y CRM
Origen: SuiteCRM (MySQL)
Destino: dw_crm_2026 (MySQL)

Este script realiza la extracción, transformación y carga inicial
de las dimensiones del modelo Kimball desde SuiteCRM al DW.
"""

import pandas as pd
from sqlalchemy import create_engine, text
from datetime import datetime

# =====================================================================
# CONFIGURACIÓN DE CONEXIONES
# =====================================================================

# Origen: SuiteCRM
ENGINE_ORIGEN = create_engine(
    "mysql+pymysql://root:root123@localhost:3306/suitecrm"
)

# Destino: Data Warehouse
ENGINE_DW = create_engine(
    "mysql+pymysql://root:root123@localhost:3306/dw_crm_2026"
)


# =====================================================================
# FUNCIONES DE CARGA POR DIMENSIÓN
# =====================================================================

def cargar_dim_vendedor():
    """Carga dim_vendedor desde suitecrm.users"""
    print("→ Cargando dim_vendedor...")

    query = """
        SELECT
            id           AS vendedor_nk,
            first_name   AS nombre,
            last_name    AS apellido,
            email,
            title        AS cargo,
            department   AS departamento
        FROM users
    """
    df = pd.read_sql(query, ENGINE_ORIGEN)

    # Transformación: nombre_completo
    df["nombre_completo"] = (
        df["nombre"].fillna("") + " " + df["apellido"].fillna("")
    ).str.strip()

    # Carga al DW
    df.to_sql("dim_vendedor", ENGINE_DW, if_exists="append", index=False)
    print(f"  ✓ dim_vendedor: {len(df)} filas cargadas")


def cargar_dim_cuenta():
    """Carga dim_cuenta desde suitecrm.accounts"""
    print("→ Cargando dim_cuenta...")

    query = """
        SELECT
            id               AS cuenta_nk,
            name             AS nombre_empresa,
            industry         AS industria,
            annual_revenue   AS ingresos_anuales,
            billing_country  AS pais
        FROM accounts
    """
    df = pd.read_sql(query, ENGINE_ORIGEN)

    # Transformación: nulos en ingresos → 0
    df["ingresos_anuales"] = pd.to_numeric(
        df["ingresos_anuales"], errors="coerce"
    ).fillna(0)

    df.to_sql("dim_cuenta", ENGINE_DW, if_exists="append", index=False)
    print(f"  ✓ dim_cuenta: {len(df)} filas cargadas")


def cargar_dim_lead():
    """Carga dim_lead desde suitecrm.leads"""
    print("→ Cargando dim_lead...")

    query = """
        SELECT
            id           AS lead_nk,
            lead_source  AS fuente,
            status       AS estado,
            converted    AS convertido
        FROM leads
    """
    df = pd.read_sql(query, ENGINE_ORIGEN)

    # Transformación: convertido a booleano
    df["convertido"] = df["convertido"].fillna(0).astype(bool)

    df.to_sql("dim_lead", ENGINE_DW, if_exists="append", index=False)
    print(f"  ✓ dim_lead: {len(df)} filas cargadas")


def cargar_dim_contacto():
    """Carga dim_contacto desde suitecrm.contacts"""
    print("→ Cargando dim_contacto...")

    query = """
        SELECT
            id           AS contacto_nk,
            first_name   AS nombre,
            last_name    AS apellido,
            email,
            phone_work   AS telefono
        FROM contacts
    """
    df = pd.read_sql(query, ENGINE_ORIGEN)

    # Transformación: nombre_completo
    df["nombre_completo"] = (
        df["nombre"].fillna("") + " " + df["apellido"].fillna("")
    ).str.strip()

    df.to_sql("dim_contacto", ENGINE_DW, if_exists="append", index=False)
    print(f"  ✓ dim_contacto: {len(df)} filas cargadas")


def cargar_dim_sales_stage():
    """
    Carga dim_sales_stage con valores catálogo estándar de SuiteCRM.
    A diferencia de las demás, esta se llena con INSERTs directos
    porque es una dimensión pequeña de tipo catálogo.
    """
    print("→ Cargando dim_sales_stage...")

    etapas = [
        # (nk, descripcion, orden, es_cerrada, es_ganada)
        ("Prospecting",         "Prospección inicial",         1, False, False),
        ("Qualification",       "Calificación del prospecto",  2, False, False),
        ("Needs Analysis",      "Análisis de necesidades",     3, False, False),
        ("Value Proposition",   "Propuesta de valor",          4, False, False),
        ("Id. Decision Makers", "Identificar tomadores",       5, False, False),
        ("Perception Analysis", "Análisis de percepción",      6, False, False),
        ("Proposal/Price Quote","Propuesta / Cotización",      7, False, False),
        ("Negotiation/Review",  "Negociación / Revisión",      8, False, False),
        ("Closed Won",          "Cerrada Ganada",              9, True,  True),
        ("Closed Lost",         "Cerrada Perdida",            10, True,  False),
    ]

    df = pd.DataFrame(etapas, columns=[
        "sales_stage_nk", "descripcion", "orden_pipeline",
        "es_cerrada", "es_ganada"
    ])

    df.to_sql("dim_sales_stage", ENGINE_DW, if_exists="append", index=False)
    print(f"  ✓ dim_sales_stage: {len(df)} filas cargadas")


def cargar_dim_tipo_actividad():
    """Carga dim_tipo_actividad con valores catálogo (Call, Meeting)"""
    print("→ Cargando dim_tipo_actividad...")

    tipos = [
        ("Call",    "Llamada telefónica al cliente"),
        ("Meeting", "Reunión con el cliente"),
    ]

    df = pd.DataFrame(tipos, columns=["tipo_actividad_nk", "descripcion"])
    df.to_sql("dim_tipo_actividad", ENGINE_DW, if_exists="append", index=False)
    print(f"  ✓ dim_tipo_actividad: {len(df)} filas cargadas")


# =====================================================================
# ORQUESTADOR
# =====================================================================

def ejecutar_carga_inicial():
    """
    Orquesta la carga inicial de todas las dimensiones en el orden
    correcto. Las dimensiones no tienen dependencias entre sí, pero
    deben cargarse antes que las fact tables.
    """
    inicio = datetime.now()
    print("=" * 60)
    print("INICIO DE CARGA INICIAL - DIMENSIONES")
    print(f"Timestamp: {inicio.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # Nota: dim_tiempo se carga por separado con script SQL
    # (LlenarDimTiempo ejecutado previamente)

    cargar_dim_vendedor()
    cargar_dim_cuenta()
    cargar_dim_lead()
    cargar_dim_contacto()
    cargar_dim_sales_stage()
    cargar_dim_tipo_actividad()

    fin = datetime.now()
    duracion = (fin - inicio).total_seconds()

    print("=" * 60)
    print(f"CARGA COMPLETADA en {duracion:.2f} segundos")
    print(f"Timestamp: {fin.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)


# =====================================================================
# PUNTO DE ENTRADA
# =====================================================================

if __name__ == "__main__":
    ejecutar_carga_inicial()