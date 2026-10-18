"""
Script de Carga Inicial del Data Warehouse (dimensiones)
Proyecto: Inteligencia Comercial y CRM
Origen: crm_fuente (MySQL, datos sintéticos con estructura simplificada de SuiteCRM)
Destino: dw_crm_2026 (MySQL)

Este script realiza la extracción, transformación y carga de las dimensiones
del modelo Kimball desde la base fuente (crm_fuente) al DW.

Orden de ejecución del proyecto:
    1) LlenarDimTiempo.sql   (una sola vez)
    2) carga_inicial.py      (este script: dimensiones)
    3) carga_facts.py        (hechos)

Diseño de la carga (repetible):
    - Primero se EXTRAE y TRANSFORMA todo en memoria. Si la fuente falla,
      el DW no se toca.
    - Solo después se vacían las tablas del DW y se insertan las dimensiones.
"""

import pandas as pd
from sqlalchemy import text
from datetime import datetime

# Conexiones: ver config.py (variables de entorno DB_*; por defecto, el docker-compose local)
from config import ENGINE_ORIGEN, ENGINE_DW


# =====================================================================
# EXTRACCIÓN + TRANSFORMACIÓN POR DIMENSIÓN (devuelven un DataFrame)
# =====================================================================

def preparar_dim_vendedor():
    """dim_vendedor desde crm_fuente.users"""
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
    return df


def preparar_dim_cuenta():
    """dim_cuenta desde crm_fuente.accounts"""
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
    return df


def preparar_dim_lead():
    """dim_lead desde crm_fuente.leads"""
    query = """
        SELECT
            id           AS lead_nk,
            lead_source  AS fuente,
            status       AS estado,
            converted    AS convertido
        FROM leads
    """
    df = pd.read_sql(query, ENGINE_ORIGEN)

    # Transformación: convertido a booleano (regla RN-05: se usa el campo
    # converted, no el texto de status; ver README sobre la inconsistencia)
    df["convertido"] = df["convertido"].fillna(0).astype(bool)
    return df


def preparar_dim_contacto():
    """dim_contacto desde crm_fuente.contacts"""
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
    return df


def preparar_dim_sales_stage():
    """
    dim_sales_stage con valores catálogo estándar del CRM.
    A diferencia de las demás, se define aquí (no se lee de la fuente)
    porque es una dimensión pequeña de tipo catálogo.
    """
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
    return pd.DataFrame(etapas, columns=[
        "sales_stage_nk", "descripcion", "orden_pipeline",
        "es_cerrada", "es_ganada"
    ])


def preparar_dim_tipo_actividad():
    """dim_tipo_actividad con valores catálogo (Call, Meeting)"""
    tipos = [
        ("Call",    "Llamada telefónica al cliente"),
        ("Meeting", "Reunión con el cliente"),
    ]
    return pd.DataFrame(tipos, columns=["tipo_actividad_nk", "descripcion"])


# =====================================================================
# REINICIO (carga repetible / idempotente)
# =====================================================================

# Tablas que se recargan completas. dim_tiempo NO se toca: la genera
# LlenarDimTiempo.sql y no depende del CRM.
TABLAS_A_REINICIAR = [
    "fact_actividades", "fact_opportunities",      # hechos primero
    "dim_vendedor", "dim_cuenta", "dim_lead", "dim_contacto",
    "dim_sales_stage", "dim_tipo_actividad",
]


def reiniciar_dw():
    """
    Vacía dimensiones y hechos (excepto dim_tiempo) para que una segunda
    ejecución produzca el mismo resultado que la primera, en lugar de
    duplicar filas con surrogate keys nuevas. TRUNCATE además reinicia el
    AUTO_INCREMENT, así que las SKs vuelven a ser 1, 2, 3...

    Como las dimensiones cambian de SK, los hechos quedarían apuntando a
    llaves obsoletas: por eso también se vacían. Después de este script
    hay que volver a ejecutar carga_facts.py.
    """
    print("→ Reiniciando dimensiones y hechos (dim_tiempo se conserva)...")
    with ENGINE_DW.begin() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        for tabla in TABLAS_A_REINICIAR:
            conn.execute(text(f"TRUNCATE TABLE {tabla}"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
    print("  ✓ Tablas vaciadas. Recuerda ejecutar carga_facts.py al terminar.")


# =====================================================================
# ORQUESTADOR
# =====================================================================

def ejecutar_carga_inicial():
    """
    Orquesta la carga de todas las dimensiones. Las dimensiones no tienen
    dependencias entre sí, pero deben cargarse antes que las fact tables.
    """
    inicio = datetime.now()
    print("=" * 60)
    print("INICIO DE CARGA INICIAL - DIMENSIONES")
    print(f"Timestamp: {inicio.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # Nota: dim_tiempo se carga por separado con script SQL
    # (LlenarDimTiempo.sql ejecutado previamente)

    # 1) EXTRAER + TRANSFORMAR todo antes de tocar el DW
    print("→ Extrayendo y transformando desde la fuente...")
    dimensiones = {
        "dim_vendedor":       preparar_dim_vendedor(),
        "dim_cuenta":         preparar_dim_cuenta(),
        "dim_lead":           preparar_dim_lead(),
        "dim_contacto":       preparar_dim_contacto(),
        "dim_sales_stage":    preparar_dim_sales_stage(),
        "dim_tipo_actividad": preparar_dim_tipo_actividad(),
    }

    # 2) CARGAR: vaciar e insertar
    reiniciar_dw()
    for nombre, df in dimensiones.items():
        df.to_sql(nombre, ENGINE_DW, if_exists="append", index=False)
        print(f"  ✓ {nombre}: {len(df)} filas cargadas")

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
