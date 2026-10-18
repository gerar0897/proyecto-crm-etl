"""
Script de Carga Inicial de Fact Tables
Proyecto: Inteligencia Comercial y CRM
Origen: crm_fuente (MySQL, datos sintéticos con estructura simplificada de SuiteCRM)
Destino: dw_crm_2026 (MySQL)

Este script carga las tablas de hechos aplicando lookups a las
dimensiones ya pobladas, para reemplazar las llaves naturales
(UUIDs del CRM) por surrogate keys del DW.
"""

import pandas as pd
from sqlalchemy import text
from datetime import datetime

# Conexiones: ver config.py (variables de entorno DB_*; por defecto, el docker-compose local)
from config import ENGINE_ORIGEN, ENGINE_DW


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
# REINICIO DE HECHOS (cambio H-12: carga repetible)
# =====================================================================

def vaciar_hechos():
    """
    Vacía las fact tables justo antes de insertarlas, de modo que ejecutar
    este script varias veces deje siempre el mismo resultado (sin duplicados).
    Se llama DESPUÉS de extraer y transformar: si la fuente falla, los hechos
    existentes no se pierden. Las dimensiones no se tocan.
    """
    print("→ Vaciando fact tables antes de recargar...")
    with ENGINE_DW.begin() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        conn.execute(text("TRUNCATE TABLE fact_actividades"))
        conn.execute(text("TRUNCATE TABLE fact_opportunities"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))


# =====================================================================
# CARGA DE FACT TABLES
# =====================================================================

ETAPAS_CERRADAS = ["Closed Won", "Closed Lost"]


def preparar_fact_opportunities(lookups):
    """Extrae y transforma fact_opportunities desde crm_fuente.opportunities"""
    print("→ Preparando fact_opportunities...")

    query = """
        SELECT
            id                 AS oportunidad_dd,
            assigned_user_id   AS vendedor_nk,
            account_id         AS cuenta_nk,
            sales_stage        AS sales_stage_nk,
            date_entered       AS fecha_creacion,
            close_date         AS fecha_cierre,
            amount             AS monto,
            probability        AS probabilidad,
            lead_source        AS fuente
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
    # Ciclo de venta: días entre creación y cierre.
    # Cambio H-08: solo tiene sentido en oportunidades CERRADAS. En las
    # abiertas, close_date es una fecha estimada, no un cierre real; se deja
    # en NULL para que AVG() la ignore. (RN-04: nunca negativo.)
    ciclo = (
        pd.to_datetime(df["fecha_cierre"]) - pd.to_datetime(df["fecha_creacion"])
    ).dt.days.clip(lower=0).astype("Int64")
    df["ciclo_venta_dias"] = ciclo.where(df["sales_stage_nk"].isin(ETAPAS_CERRADAS))

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
        "oportunidad_dd", "fuente", "monto", "probabilidad",
        "ciclo_venta_dias", "ganada"
    ]
    return df_valido[columnas_fact]


def preparar_fact_actividades(lookups, oportunidades_validas):
    """
    Extrae y transforma fact_actividades desde crm_fuente.calls y
    crm_fuente.meetings unidas (UNION) porque son dos tipos del mismo hecho:
    una interacción.
    """
    print("→ Preparando fact_actividades...")

    query = """
        SELECT
            id                 AS actividad_dd,
            opportunity_id     AS oportunidad_dd,
            assigned_user_id   AS vendedor_nk,
            'Call'             AS tipo_actividad_nk,
            date_entered       AS fecha_actividad,
            status             AS estado,
            duration_hours     AS duracion_horas
        FROM calls
        UNION ALL
        SELECT
            id                 AS actividad_dd,
            opportunity_id     AS oportunidad_dd,
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

    # --- OPORTUNIDAD: validar que la oportunidad referenciada se cargará en el DW ---
    # (cambio H-03) oportunidad_dd es una dimensión degenerada, no una FK
    # declarada, así que se valida aquí y se reporta; no se oculta.
    sin_oportunidad = (~df["oportunidad_dd"].isin(oportunidades_validas)).sum()
    if sin_oportunidad > 0:
        print(f"  ⚠ {sin_oportunidad} actividades apuntan a una oportunidad "
              f"que no existe en fact_opportunities")

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
        "actividad_dd", "oportunidad_dd", "estado",
        "duracion_horas", "contador_actividad"
    ]
    return df_valido[columnas_fact]


def insertar_hecho(nombre_tabla, df):
    """Inserta un DataFrame ya preparado en la fact table indicada."""
    df.to_sql(nombre_tabla, ENGINE_DW, if_exists="append", index=False)
    print(f"  ✓ {nombre_tabla}: {len(df)} filas cargadas")


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

    # 1) EXTRAER + TRANSFORMAR todo antes de tocar las fact tables
    df_opp = preparar_fact_opportunities(lookups)
    df_act = preparar_fact_actividades(lookups, set(df_opp["oportunidad_dd"]))

    # Protección: si no hay oportunidades válidas, casi seguro faltan las
    # dimensiones. Se aborta SIN vaciar los hechos existentes.
    if df_opp.empty:
        raise SystemExit(
            "✗ No hay oportunidades válidas para cargar. "
            "¿Se ejecutó carga_inicial.py antes que carga_facts.py? "
            "No se modificó ninguna fact table."
        )

    # 2) CARGAR: vaciar e insertar (oportunidades primero)
    vaciar_hechos()
    insertar_hecho("fact_opportunities", df_opp)
    insertar_hecho("fact_actividades", df_act)

    fin = datetime.now()
    duracion = (fin - inicio).total_seconds()

    print("=" * 60)
    print(f"CARGA COMPLETADA en {duracion:.2f} segundos")
    print(f"Timestamp: {fin.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)


if __name__ == "__main__":
    ejecutar_carga_facts()