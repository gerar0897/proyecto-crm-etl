"""
Script de Carga Inicial de Fact Tables
Proyecto: Inteligencia Comercial y CRM
Origen: SuiteCRM (MySQL)
Destino: dw_crm_2026 (MySQL)

Este script carga las tablas de hechos aplicando lookups a las
dimensiones ya pobladas, para reemplazar las llaves naturales
(UUIDs del CRM) por surrogate keys del DW.
"""

import pandas as pd
from sqlalchemy import create_engine
from datetime import datetime

# =====================================================================
# CONEXIONES
# =====================================================================

ENGINE_ORIGEN = create_engine(
    "mysql+pymysql://root:root123@localhost:3306/suitecrm"
)

ENGINE_DW = create_engine(
    "mysql+pymysql://root:root123@localhost:3306/dw_crm_2026"
)


# =====================================================================
# FUNCIONES AUXILIARES DE LOOKUP
# =====================================================================

def cargar_lookups():
    """
    Carga las dimensiones en memoria como diccionarios de lookup:
    { natural_key : surrogate_key }.
    Esto acelera las traducciones NK→SK durante la carga de facts.
    """
    print("→ Cargando lookups de dimensiones en memoria...")

    lookups = {}

    lookups["vendedor"] = pd.read_sql(
        "SELECT vendedor_nk, vendedor_sk FROM dim_vendedor",
        ENGINE_DW
    ).set_index("vendedor_nk")["vendedor_sk"].to_dict()

    lookups["cuenta"] = pd.read_sql(
        "SELECT cuenta_nk, cuenta_sk FROM dim_cuenta",
        ENGINE_DW
    ).set_index("cuenta_nk")["cuenta_sk"].to_dict()

    lookups["lead"] = pd.read_sql(
        "SELECT lead_nk, lead_sk FROM dim_lead",
        ENGINE_DW
    ).set_index("lead_nk")["lead_sk"].to_dict()

    lookups["contacto"] = pd.read_sql(
        "SELECT contacto_nk, contacto_sk FROM dim_contacto",
        ENGINE_DW
    ).set_index("contacto_nk")["contacto_sk"].to_dict()

    lookups["sales_stage"] = pd.read_sql(
        "SELECT sales_stage_nk, sales_stage_sk FROM dim_sales_stage",
        ENGINE_DW
    ).set_index("sales_stage_nk")["sales_stage_sk"].to_dict()

    lookups["tipo_actividad"] = pd.read_sql(
        "SELECT tipo_actividad_nk, tipo_actividad_sk FROM dim_tipo_actividad",
        ENGINE_DW
    ).set_index("tipo_actividad_nk")["tipo_actividad_sk"].to_dict()

    print(f"  ✓ Lookups cargados:")
    for nombre, dic in lookups.items():
        print(f"     {nombre}: {len(dic)} entradas")

    return lookups


def fecha_a_sk(fecha):
    """
    Convierte una fecha (datetime o date) al formato YYYYMMDD
    que usamos como surrogate key en dim_tiempo.
    Retorna None si la fecha es nula.
    """
    if pd.isna(fecha):
        return None
    return int(pd.to_datetime(fecha).strftime("%Y%m%d"))


# =====================================================================
# CARGA DE FACT TABLES
# =====================================================================

def cargar_fact_opportunities(lookups):
    """Carga fact_opportunities desde suitecrm.opportunities"""
    print("→ Cargando fact_opportunities...")

    query = """
        SELECT
            id                 AS oportunidad_dd,
            assigned_user_id   AS vendedor_nk,
            account_id         AS cuenta_nk,
            sales_stage        AS sales_stage_nk,
            date_entered       AS fecha_creacion,
            close_date         AS fecha_cierre,
            amount             AS monto,
            probability        AS probabilidad
        FROM opportunities
    """
    df = pd.read_sql(query, ENGINE_ORIGEN)
    filas_originales = len(df)

    # --- LOOKUPS: traducir NK → SK ---
    df["vendedor_sk"]    = df["vendedor_nk"].map(lookups["vendedor"])
    df["cuenta_sk"]      = df["cuenta_nk"].map(lookups["cuenta"])
    df["sales_stage_sk"] = df["sales_stage_nk"].map(lookups["sales_stage"])

    # --- FECHAS: convertir a formato SK YYYYMMDD ---
    df["fecha_creacion_sk"] = df["fecha_creacion"].apply(fecha_a_sk)
    df["fecha_cierre_sk"]   = df["fecha_cierre"].apply(fecha_a_sk)

    # --- MÉTRICAS DERIVADAS ---
    # Ciclo de venta: días entre creación y cierre
    df["ciclo_venta_dias"] = (
        pd.to_datetime(df["fecha_cierre"]) - pd.to_datetime(df["fecha_creacion"])
    ).dt.days

    # Ganada: True si la etapa es "Closed Won"
    df["ganada"] = df["sales_stage_nk"] == "Closed Won"

    # --- LIMPIEZA DE NULOS EN MÉTRICAS ---
    df["monto"] = pd.to_numeric(df["monto"], errors="coerce").fillna(0)
    df["probabilidad"] = pd.to_numeric(df["probabilidad"], errors="coerce").fillna(0)

    # --- FILTRO: solo filas con FKs válidas (integridad referencial) ---
    df_valido = df.dropna(subset=[
        "vendedor_sk", "cuenta_sk", "sales_stage_sk", "fecha_creacion_sk"
    ]).copy()

    filas_descartadas = filas_originales - len(df_valido)
    if filas_descartadas > 0:
        print(f"  ⚠ {filas_descartadas} filas descartadas por FKs nulas")

    # --- SELECCIONAR SOLO COLUMNAS QUE VAN A LA FACT ---
    columnas_fact = [
        "vendedor_sk", "cuenta_sk", "sales_stage_sk",
        "fecha_creacion_sk", "fecha_cierre_sk",
        "oportunidad_dd", "monto", "probabilidad",
        "ciclo_venta_dias", "ganada"
    ]
    df_final = df_valido[columnas_fact]

    # --- CARGA AL DW ---
    df_final.to_sql(
        "fact_opportunities", ENGINE_DW,
        if_exists="append", index=False
    )
    print(f"  ✓ fact_opportunities: {len(df_final)} filas cargadas")


def cargar_fact_actividades(lookups):
    """
    Carga fact_actividades desde suitecrm.calls y suitecrm.meetings
    unidas (UNION) porque son dos tipos del mismo hecho: una interacción.
    """
    print("→ Cargando fact_actividades...")

    query = """
        SELECT
            id                 AS actividad_dd,
            assigned_user_id   AS vendedor_nk,
            'Call'             AS tipo_actividad_nk,
            date_entered       AS fecha_actividad,
            status             AS estado,
            duration_hours     AS duracion_horas
        FROM calls
        UNION ALL
        SELECT
            id                 AS actividad_dd,
            assigned_user_id   AS vendedor_nk,
            'Meeting'          AS tipo_actividad_nk,
            date_entered       AS fecha_actividad,
            status             AS estado,
            duration_hours     AS duracion_horas
        FROM meetings
    """
    df = pd.read_sql(query, ENGINE_ORIGEN)
    filas_originales = len(df)

    # --- LOOKUPS ---
    df["vendedor_sk"]       = df["vendedor_nk"].map(lookups["vendedor"])
    df["tipo_actividad_sk"] = df["tipo_actividad_nk"].map(lookups["tipo_actividad"])

    # --- FECHA ---
    df["fecha_actividad_sk"] = df["fecha_actividad"].apply(fecha_a_sk)

    # --- CONTACTO Y LEAD: nulos (no todas las actividades los tienen) ---
    # En el modelo simplificado, estos quedan nulos.
    df["contacto_sk"] = None
    df["lead_sk"]     = None

    # --- MÉTRICAS ---
    df["duracion_horas"] = pd.to_numeric(df["duracion_horas"], errors="coerce").fillna(0)
    df["contador_actividad"] = 1

    # --- FILTRO POR INTEGRIDAD ---
    df_valido = df.dropna(subset=[
        "vendedor_sk", "tipo_actividad_sk", "fecha_actividad_sk"
    ]).copy()

    filas_descartadas = filas_originales - len(df_valido)
    if filas_descartadas > 0:
        print(f"  ⚠ {filas_descartadas} filas descartadas por FKs nulas")

    # --- COLUMNAS FINALES ---
    columnas_fact = [
        "vendedor_sk", "tipo_actividad_sk", "fecha_actividad_sk",
        "contacto_sk", "lead_sk",
        "actividad_dd", "estado",
        "duracion_horas", "contador_actividad"
    ]
    df_final = df_valido[columnas_fact]

    df_final.to_sql(
        "fact_actividades", ENGINE_DW,
        if_exists="append", index=False
    )
    print(f"  ✓ fact_actividades: {len(df_final)} filas cargadas")


# =====================================================================
# ORQUESTADOR
# =====================================================================

def ejecutar_carga_facts():
    inicio = datetime.now()
    print("=" * 60)
    print("INICIO DE CARGA INICIAL - FACT TABLES")
    print(f"Timestamp: {inicio.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    lookups = cargar_lookups()

    cargar_fact_opportunities(lookups)
    cargar_fact_actividades(lookups)

    fin = datetime.now()
    duracion = (fin - inicio).total_seconds()

    print("=" * 60)
    print(f"CARGA COMPLETADA en {duracion:.2f} segundos")
    print(f"Timestamp: {fin.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)


if __name__ == "__main__":
    ejecutar_carga_facts()