# pylint: disable=eval-used
import pandas as pd
from sqlalchemy import create_engine, text
import boto3
import hashlib
import json
import logging
from typing import Optional, Dict, Any, Tuple
from uuid import UUID
from datetime import datetime
from contextvars import ContextVar
from src.config.parameters import DB_SCHEMA, ID_COLUMNS, USER, SERVER, PORT, DB

logger = logging.getLogger(__name__)


# Import will be done at function call time to avoid circular imports
def _get_dq_id_from_context() -> Optional[UUID]:
    """
    Get dq_id from context. Imported at call time to avoid circular imports.
    This is set by xls.py during upload_bbg_data_with_versioning or upload_with_override.
    """
    try:
        from src.engine.xls import get_dq_id
        return get_dq_id()
    except ImportError:
        return None


def execute_batch_update(dataset, table_name, temp_table="table_temp"):
    """
    Execute batch update with dq_id threading for Phase 2B.2.
    
    Adds dq_id column from context (if available) to dataset before writing to temp table.
    This allows dq_id to be included in the subsequent INSERT statement.
    
    Args:
        dataset: DataFrame to insert
        table_name: Target table name
        temp_table: Temporary table name for staging
    """
    dataset = remove_white_space(dataset)
    
    # Add dq_id from context if it's set (Phase 2B.2)
    dq_id = _get_dq_id_from_context()
    if dq_id is not None:
        dataset['dq_id'] = str(dq_id)
        print(f"Added dq_id={dq_id} to {len(dataset)} rows for table {table_name}")
    
    engine = create_updated_engine()
    dataset.to_sql(temp_table, engine, if_exists='replace')
    conn = engine.raw_connection()
    cur = conn.cursor()
    cur.execute("""Alter table  table_temp Drop Column index;""")
    conn.commit()
    print("Commit!!")
    insert_to_main_table(cur, conn, table_name)


def remove_white_space(dataset):
    for col in dataset.columns:
        if col in ID_COLUMNS:
            dataset[col] = dataset[col].astype(str)
            dataset[col] = dataset[col].apply(lambda x: x.strip())
    return dataset


def get_secret(secret_name="cissa-dev-db-password"):  # nosec
    """
    Retrieves the secret value from AWS Secrets Manager.
    Args:
        secret_name (str): The name of the secret to retrieve. Defaults to "cissa-dev-db-password".
    Returns:
        str: The secret value as a string, or None if an error occurs.
    """
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name='ap-southeast-2'
    )
    try:
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
    except Exception as e:
        print(f"Error retrieving secret: {e}")
        return None

    if 'SecretString' in get_secret_value_response:
        return get_secret_value_response['SecretString']
    return None


def create_updated_engine():
    """
    Creates a SQLAlchemy engine for connecting to the PostgreSQL database.
    Tries local development first (localhost:5432), then falls back to AWS Secrets Manager.
    """
    # Try localhost first (Docker development)
    try:
        connection_string = f"postgresql://{USER}:postgres@localhost:5432/{DB}"
        engine = create_engine(connection_string)
        # Test connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return engine
    except Exception:
        pass  # Fall back to AWS Secrets Manager
    
    # Fall back to AWS Secrets Manager for production
    secret = get_secret()
    if secret is None:
        raise ValueError("Failed to retrieve database secret. Ensure either: (1) PostgreSQL is running on localhost:5432, or (2) AWS credentials are configured.")
    
    connection_string = f"postgresql://{USER}:{secret}@{SERVER}:{PORT}/{DB}"
    engine = create_engine(connection_string)
    return engine


def execute_transactional_insert(metrics, betas, config):
    metrics = remove_white_space(metrics)
    betas = remove_white_space(betas)
    config = remove_white_space(config)
    engine = create_updated_engine()
    metrics.to_sql('metrics_temp', engine, if_exists='replace')
    betas.to_sql('betas_temp', engine, if_exists='replace')
    config.to_sql('config_temp', engine, if_exists='replace')
    conn = engine.raw_connection()
    with conn.cursor() as cur:
        try:
            cur.execute("""Alter table  metrics_temp Drop Column index;""")  # nosec
            cur.execute("""Alter table  betas_temp Drop Column index;""")  # nosec
            cur.execute("""Alter table  config_temp Drop Column index;""")  # nosec
            cur.execute(
                f"""Insert into {DB_SCHEMA}.metrics select * From metrics_temp  ON CONFLICT DO NOTHING;""")  # nosec
            cur.execute(
                f"""Insert into {DB_SCHEMA}.metrics select * From betas_temp  ON CONFLICT DO NOTHING;""")  # nosec
            cur.execute(
                f"""Insert into {DB_SCHEMA}.config select * From config_temp  ON CONFLICT DO NOTHING;""")  # nosec
            cur.execute("""DROP Table metrics_temp   ;""")  # nosec
            cur.execute("""DROP Table betas_temp   ;""")  # nosec
            cur.execute("""DROP Table config_temp   ;""")  # nosec
            conn.commit()
        except TypeError as e:
            print(e)
            return None
        except ValueError as e:
            print(e)
            return None
        finally:
            conn.close()
    print("Successfully Committed")
    return True


def insert_to_main_table(cur, conn, table_name):
    table_name = f'{DB_SCHEMA}.{table_name}'
    print(table_name)
    
    # Standard insert - dq_id is already added to DataFrame in execute_batch_update if needed
    sql = f"""INSERT INTO {table_name} SELECT * FROM table_temp ON CONFLICT DO NOTHING;"""
    print(sql)
    
    cur.execute(sql)  # nosec
    conn.commit()


def create_view(sql):
    engine = create_updated_engine()
    conn = engine.raw_connection()
    cur = conn.cursor()

    cur.execute(sql)
    conn.commit()


def execute_select(sql):
    engine = create_updated_engine()
    df = pd.read_sql(sql, con=engine)
    return df


def get_goal_seek_param(inputs):
    country = inputs['country']
    start = inputs['start']
    end = inputs['end']
    guid = inputs['guid']
    parameters = f"'{country}','{guid}',{start},{end}"
    sql = f"select * from {DB_SCHEMA}.GET_PARAM_FOR_GOAL_SEEK({parameters});"  # nosec
    df = execute_select(sql)
    return df


def get_min_date():
    sql = f"select ticker, min(date) as inception from\
           (select * from  {DB_SCHEMA}.monthly_data where value is not null) as a group by ticker ;"  # nosec
    df = execute_select(sql)
    return df


def create_wide_view_for_table():
    sql = f"""CREATE VIEW {DB_SCHEMA}.FIN_ANNUAL_WIDE AS
            select b.begin_year as year_of_listing, a.* from (SELECT FY_YEAR, TICKER,FX_CURRENCY,
            MAX(value) FILTER (WHERE key = 'Share Price') AS price,
            MAX(value) FILTER (WHERE key ='REVENUE') AS revenue,
            MAX(value) FILTER (WHERE key = 'Spot Shares') AS shrouts,
            MAX(value) FILTER (WHERE key = 'Total Assets') AS assets,
            MAX(value) FILTER (WHERE key = 'FY TSR') AS fytsr,
            MAX(value) FILTER (WHERE key = 'MC') AS mc,
            MAX(value) FILTER (WHERE key = 'Cash') AS cash,
            MAX(value) FILTER (WHERE key = 'PBT') AS pbt,
            MAX(value) FILTER (WHERE key = 'MI') AS mi,
            MAX(value) FILTER (WHERE key = 'DIST') AS dist,
            MAX(value) FILTER (WHERE key = 'DIV') AS dividend,
            MAX(value) FILTER (WHERE key = 'PAT') AS pat,
            MAX(value) FILTER (WHERE key = 'FA') AS fixedassets,
            MAX(value) FILTER (WHERE key = 'Total Equity') AS eqiity,
            MAX(value) FILTER (WHERE key = 'INJ') AS cap_injection,
            MAX(value) FILTER (WHERE key = 'GW') AS goodwill,
            MAX(value) FILTER (WHERE key = 'PAT XO') AS patxo,
            MAX(value) FILTER (WHERE key = 'OP INCOME') AS opincome
            FROM {DB_SCHEMA}.ANNUAL_DATA GROUP BY FY_YEAR, TICKER,FX_CURRENCY ) as a INNER JOIN
            {DB_SCHEMA}.company as b on a.ticker=b.ticker order by TICKER, FY_YEAR, FX_CURRENCY; """  # nosec
    create_view(sql)


def create_view_for_metrics():
    sql = f"""  CREATE OR REPLACE  VIEW LVL1_METRICS AS
    WITH LVL1_METRICS as
        (
            select a.*,
            round(a.price * a.shrouts, 4) as  calc_mc,
            a.assets - a.cash as calc_assets,
            a.assets - a.cash - a.fixedassets as calc_oa,
            a.eqiity - a.mi as calc_ee
            from {DB_SCHEMA}.fin_annual_wide as a
        ),
        LVL2_METRICS as
        (
            select b.*,
            round(LAG(b.calc_mc,1) OVER (ORDER BY b.ticker ,b.fy_year)*(1+(b.fytsr/100)),4) - b.calc_mc as CALC_ECF
            FROM {DB_SCHEMA}.LVL1_METRICS as b
        ),
        LVL3_METRICS as
        (
            select c.ticker,
            c.fx_currency,
            c.fy_year,
            c.calc_mc,
            c.calc_ecf,
            c.calc_assets,
            c.calc_oa,
            c.calc_ee,
            c.calc_ecf -c.dividend as non_div_ecf
            FROM LVL2_METRICS as c
        )
        select * from LVL3_METRICS;  """  # nosec
    create_view(sql)


def get_TSR():
    sql = f"""
    With CTSR AS(
        SELECT *
        FROM   {DB_SCHEMA}.monthly_data
        WHERE  KEY='Company TSR'
        ),
        ITSR AS
        (
        SELECT *
        FROM   {DB_SCHEMA}.monthly_data
        WHERE  KEY='Index TSR'
        AND TICKER LIKE'%AS30%'
        )
        SELECT
        a.ticker,
        a.date,
        ROUND((CAST(a.value AS DECIMAL)/100) +1,4) AS re,
        ROUND((CAST (b.value AS DECIMAL)/100) +1,4) AS rm
        FROM CTSR a
        INNER JOIN ITSR b on   a.date=b.date
        ORDER BY TICKER,DATE; """  # nosec
    df = execute_select(sql)
    return df


def get_wide_format_data(country):
    sql = f"SELECT a.*, \
       b.begin_year AS inception \
        FROM   (SELECT * \
        FROM   {DB_SCHEMA}.fin_annual_wide \
        WHERE  ticker IN (SELECT DISTINCT ticker \
                          FROM   {DB_SCHEMA}.company \
                          WHERE   domicile_country = '{country}')) \
                          AS a   INNER JOIN company AS b  ON a.ticker = b.ticker "  # nosec
    df = execute_select(sql)
    return df


def get_annual_wide_format(country):
    sql = f"SELECT distinct a.*, \
       b.begin_year AS inception \
        FROM   (SELECT * \
        FROM   {DB_SCHEMA}.fin_annual_wide \
        WHERE  ticker IN (SELECT DISTINCT ticker \
                          FROM   {DB_SCHEMA}.company \
                          WHERE  domicile_country = '{country}')) \
                           AS a  INNER JOIN {DB_SCHEMA}.company AS b  ON a.ticker = b.ticker\
                            order by ticker, fy_year"  # nosec
    df = execute_select(sql)
    return df


def get_monthly_wide_format(bondIndex='GACGB10'):
    sql = f"SELECT \
        ticker, \
        date, \
        CAST(value AS DECIMAL) as rf,\
        ROUND((CAST(value AS DECIMAL)/100) +1,4) AS rf_prel from {DB_SCHEMA}.monthly_data \
        where key='Rf'and ticker like '%{bondIndex}%' \
        order by ticker, date desc"  # nosec
    df = execute_select(sql)
    return df


def get_metrics(ticker):
    sql = f"select *, trim(type) as report_types from {DB_SCHEMA}.metrics where ticker=\'{ticker}\'"  # nosec
    df = execute_select(sql)
    return df


def get_fy_dates():
    sql = f"select distinct a.ticker,bics_1 as sector,a.value as date from {DB_SCHEMA}.fy_dates as a \
           inner join {DB_SCHEMA}.company as b on a.ticker=b.ticker  \
            order by ticker,value"  # nosec
    df = execute_select(sql)
    return df


def get_general_metrics_from_db(guid):
    sql = f"select distinct * from {DB_SCHEMA}.l1_wide_metrics where guid='{guid}'   \
               order by ticker,fy_year"  # nosec
    df = execute_select(sql)
    return df


def save_goal_seek_output(dataset):
    execute_batch_update(dataset, 'model_outputs')


def get_sector_metrics(guid):
    sql = f"select distinct a.*,b.sector from {DB_SCHEMA}.metrics_for_aggregation as a\
             inner join {DB_SCHEMA}.company as b \
             on a.ticker=b.ticker where guid='{guid}'\
             order by ticker,fy_year"  # nosec
    df = execute_select(sql)
    return df


def save_sector_metrics_to_db(dataset):
    execute_batch_update(dataset, 'sector_metrics')
    return True


# ============================================================================
# PHASE 2B: Versioning & Caching Helper Functions (11 total)
# ============================================================================

def calculate_file_hash(file_path: str) -> str:
    """
    Calculate SHA-256 hash of a file for duplicate detection.
    
    Args:
        file_path: Path to the Excel file
        
    Returns:
        str: SHA-256 hash of the file (64 hex characters)
    """
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def get_or_create_data_version(
    file_path: str,
    version_name: str,
    metadata: Optional[Dict[str, Any]] = None,
    created_by: str = "admin"
) -> UUID:
    """
    Get or create a data_versions entry for a Bloomberg download.
    If the file hash already exists, returns existing raw_id.
    Otherwise creates a new versioning entry.
    
    Args:
        file_path: Path to the Excel file
        version_name: Human-readable name (e.g., "Jan 2025 Snapshot")
        metadata: Optional JSON metadata
        created_by: Username of uploader
        
    Returns:
        UUID: The raw_id (existing or newly created)
    """
    file_hash = calculate_file_hash(file_path)
    engine = create_updated_engine()
    
    # Check if this file hash already exists
    check_sql = f"""
        SELECT raw_id FROM {DB_SCHEMA}.data_versions 
        WHERE file_hash = %s 
        LIMIT 1;
    """
    
    conn = engine.raw_connection()
    try:
        cur = conn.cursor()
        cur.execute(check_sql, (file_hash,))
        result = cur.fetchone()
        
        if result:
            cur.close()
            return result[0]
        
        # File hash is new - create versioning entry
        metadata_json = json.dumps(metadata) if metadata else None
        insert_sql = f"""
            INSERT INTO {DB_SCHEMA}.data_versions 
            (version_name, file_hash, file_path, metadata, created_by)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING raw_id;
        """
        
        cur.execute(insert_sql, (version_name, file_hash, file_path, metadata_json, created_by))
        raw_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        
        return raw_id
    finally:
        conn.close()


def create_adjusted_data(
    raw_id: UUID,
    plug_id: Optional[UUID] = None,
    created_by: str = "admin",
    metadata: Optional[Dict[str, Any]] = None
) -> UUID:
    """
    Create or return existing adjusted_data entry (merged raw + overrides).
    Uses UNIQUE constraint on (raw_id, plug_id) to prevent duplicates.
    
    Args:
        raw_id: Reference to data_versions entry
        plug_id: Optional reference to override_versions entry
        created_by: Username performing the merge
        metadata: Optional JSON metadata about the merge
        
    Returns:
        UUID: The adj_id (existing or newly created)
    """
    engine = create_updated_engine()
    metadata_json = json.dumps(metadata) if metadata else None
    
    conn = engine.raw_connection()
    try:
        cur = conn.cursor()
        # Try to fetch existing
        fetch_sql = f"""
            SELECT adj_id FROM {DB_SCHEMA}.adjusted_data 
            WHERE raw_id = %s AND plug_id IS NOT DISTINCT FROM %s
            LIMIT 1;
        """
        
        cur.execute(fetch_sql, (raw_id, plug_id))
        result = cur.fetchone()
        
        if result:
            cur.close()
            return result[0]
        
        # Create new adjusted_data entry
        insert_sql = f"""
            INSERT INTO {DB_SCHEMA}.adjusted_data 
            (raw_id, plug_id, created_by, metadata)
            VALUES (%s, %s, %s, %s)
            RETURNING adj_id;
        """
        
        cur.execute(insert_sql, (raw_id, plug_id, created_by, metadata_json))
        adj_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        
        return adj_id
    finally:
        conn.close()


def create_data_quality(
    adj_id: UUID,
    status: str = "passed",
    created_by: str = "admin",
    metadata: Optional[Dict[str, Any]] = None
) -> UUID:
    """
    Create a data_quality check entry for an adjusted dataset.
    Allows multiple dq_ids per adj_id (same data checked with different rules).
    
    Args:
        adj_id: Reference to adjusted_data entry
        status: Quality status ('passed', 'failed', 'warnings')
        created_by: Username performing the check
        metadata: DQ check details (rules, issues, interpolation method, etc.)
        
    Returns:
        UUID: The dq_id
    """
    engine = create_updated_engine()
    metadata_json = json.dumps(metadata) if metadata else None
    
    insert_sql = f"""
        INSERT INTO {DB_SCHEMA}.data_quality 
        (adj_id, status, created_by, metadata)
        VALUES (%s, %s, %s, %s)
        RETURNING dq_id;
    """
    
    conn = engine.raw_connection()
    try:
        cur = conn.cursor()
        cur.execute(insert_sql, (adj_id, status, created_by, metadata_json))
        dq_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        
        return dq_id
    finally:
        conn.close()


def create_override_version(
    raw_id: UUID,
    file_path: str,
    version_name: str,
    metadata: Optional[Dict[str, Any]] = None,
    created_by: str = "admin"
) -> UUID:
    """
    Create or return existing override_versions entry (plug file).
    Similar to get_or_create_data_version but targets a specific raw_id.
    
    Args:
        raw_id: Reference to the Bloomberg data version being overridden
        file_path: Path to the override Excel file
        version_name: Human-readable name (e.g., "Override v1 for Jan 2025")
        metadata: Optional JSON metadata
        created_by: Username of uploader
        
    Returns:
        UUID: The plug_id (existing or newly created)
    """
    file_hash = calculate_file_hash(file_path)
    engine = create_updated_engine()
    
    # Check if this file hash already exists
    check_sql = f"""
        SELECT plug_id FROM {DB_SCHEMA}.override_versions 
        WHERE file_hash = %s 
        LIMIT 1;
    """
    
    conn = engine.raw_connection()
    try:
        cur = conn.cursor()
        cur.execute(check_sql, (file_hash,))
        result = cur.fetchone()
        
        if result:
            cur.close()
            return result[0]
        
        # File hash is new - create override entry
        metadata_json = json.dumps(metadata) if metadata else None
        insert_sql = f"""
            INSERT INTO {DB_SCHEMA}.override_versions 
            (raw_id, version_name, file_hash, file_path, metadata, created_by)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING plug_id;
        """
        
        cur.execute(insert_sql, (raw_id, version_name, file_hash, file_path, metadata_json, created_by))
        plug_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        
        return plug_id
    finally:
        conn.close()


def execute_batch_update_with_dq(
    dataset: pd.DataFrame,
    table_name: str,
    dq_id: UUID,
    temp_table: str = "table_temp"
) -> bool:
    """
    Execute batch update with data_quality_id foreign key reference.
    Threads dq_id through the pipeline into input tables.
    
    Args:
        dataset: DataFrame to insert
        table_name: Target table name (e.g., 'annual_data', 'monthly_data')
        dq_id: Reference to data_quality entry
        temp_table: Temporary table name for staging
        
    Returns:
        bool: True if successful
    """
    dataset = remove_white_space(dataset)
    engine = create_updated_engine()
    
    # Add dq_id column to dataset
    dataset['dq_id'] = str(dq_id)
    
    dataset.to_sql(temp_table, engine, if_exists='replace')
    
    conn = engine.raw_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"ALTER TABLE {temp_table} DROP COLUMN index;")
        
        # Insert with dq_id FK
        full_table_name = f'{DB_SCHEMA}.{table_name}'
        insert_sql = f"""
            INSERT INTO {full_table_name} SELECT * FROM {temp_table} 
            ON CONFLICT DO NOTHING;
        """
        
        cur.execute(insert_sql)
        cur.execute(f"DROP TABLE {temp_table};")
        conn.commit()
        cur.close()
    finally:
        conn.close()
    
    return True


def get_or_create_parameter_scenario(
    params_dict: Dict[str, Any],
    is_default: bool = False,
    created_by: str = "admin"
) -> UUID:
    """
    Get or create a parameter_scenarios entry with canonical JSON.
    Ensures deduplication via UNIQUE constraint on parameters JSONB.
    
    Args:
        params_dict: Parameter dictionary (e.g., risk_premium, beta_rounding, etc.)
        is_default: Whether to mark this as the default parameter set
        created_by: Username creating this parameter set
        
    Returns:
        UUID: The param_id (existing or newly created)
    """
    # Canonicalize: sort keys for consistent JSON representation
    canonical_params_json = json.dumps(params_dict, sort_keys=True, separators=(',', ':'))
    engine = create_updated_engine()
    
    conn = engine.raw_connection()
    try:
        cur = conn.cursor()
        # Try to fetch existing with canonical JSON
        fetch_sql = f"""
            SELECT param_id FROM {DB_SCHEMA}.parameter_scenarios 
            WHERE parameters = %s::jsonb
            LIMIT 1;
        """
        
        cur.execute(fetch_sql, (canonical_params_json,))
        result = cur.fetchone()
        
        if result:
            cur.close()
            param_id = result[0]
            return param_id if isinstance(param_id, UUID) else UUID(param_id)
        
        # Create new parameter set
        insert_sql = f"""
            INSERT INTO {DB_SCHEMA}.parameter_scenarios 
            (parameters, is_default, created_by)
            VALUES (%s::jsonb, %s, %s)
            RETURNING param_id;
        """
        
        cur.execute(insert_sql, (canonical_params_json, is_default, created_by))
        param_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        
        return param_id if isinstance(param_id, UUID) else UUID(param_id)
    finally:
        conn.close()


def find_completed_metric_run(dq_id: UUID, param_id: UUID) -> Optional[UUID]:
    """
    Check if a completed metric calculation exists for (dq_id, param_id) pair.
    Returns cached calc_id if found, otherwise None.
    This enables cache detection before executing generate_l1_metrics.py.
    
    Args:
        dq_id: Reference to data_quality entry
        param_id: Reference to parameter_scenarios entry
        
    Returns:
        UUID: calc_id of completed metric run, or None if no cache hit
    """
    engine = create_updated_engine()
    
    sql = f"""
        SELECT calc_id FROM {DB_SCHEMA}.metric_runs 
        WHERE dq_id = %s AND param_id = %s AND status = 'completed'
        ORDER BY completed_at DESC
        LIMIT 1;
    """
    
    conn = engine.raw_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, (dq_id, param_id))
        result = cur.fetchone()
        cur.close()
        
        return result[0] if result else None
    finally:
        conn.close()


def get_cached_metric_results(calc_id: UUID) -> pd.DataFrame:
    """
    Retrieve cached metric results from a previous calculation.
    Returns DataFrame with columns: ticker, fx_currency, fy_year, key, value, param_id
    
    Args:
        calc_id: Reference to metric_runs entry
        
    Returns:
        pd.DataFrame: Cached metric results
    """
    sql = f"""
        SELECT ticker, fx_currency, fy_year, key, value, param_id
        FROM {DB_SCHEMA}.metric_results
        WHERE calc_id = %s
        ORDER BY ticker, key, fy_year;
    """
    
    engine = create_updated_engine()
    df = pd.read_sql(sql, con=engine, params=(calc_id,))
    return df


def create_metric_run(
    dq_id: UUID,
    param_id: UUID,
    status: str = "pending",
    created_by: str = "admin",
    metadata: Optional[Dict[str, Any]] = None
) -> UUID:
    """
    Create a metric_runs entry to track calculation execution.
    Status starts as 'pending', transitions to 'running' → 'completed'/'failed'.
    
    Args:
        dq_id: Reference to data_quality entry
        param_id: Reference to parameter_scenarios entry
        status: Initial status ('pending', 'running', 'completed', 'failed')
        created_by: Username triggering the calculation
        metadata: Optional execution metadata (error messages, logs, etc.)
        
    Returns:
        UUID: The calc_id (newly created)
    """
    engine = create_updated_engine()
    metadata_json = json.dumps(metadata) if metadata else None
    
    insert_sql = f"""
        INSERT INTO {DB_SCHEMA}.metric_runs 
        (dq_id, param_id, status, created_by, metadata)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING calc_id;
    """
    
    conn = engine.raw_connection()
    try:
        cur = conn.cursor()
        cur.execute(insert_sql, (dq_id, param_id, status, created_by, metadata_json))
        calc_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        
        return calc_id
    finally:
        conn.close()


def write_metric_results(
    calc_id: UUID,
    param_id: UUID,
    metrics_df: pd.DataFrame
) -> int:
    """
    Write metric calculation results to metric_results table.
    Expected columns: ticker, fx_currency, fy_year, key, value
    
    Args:
        calc_id: Reference to metric_runs entry (which calculation produced this)
        param_id: Reference to parameter_scenarios entry (which parameters were used)
        metrics_df: DataFrame with columns [ticker, fx_currency, fy_year, key, value]
        
    Returns:
        int: Number of rows inserted
    """
    engine = create_updated_engine()
    
    # Add FK columns
    df = metrics_df.copy()
    df['calc_id'] = str(calc_id)
    df['param_id'] = str(param_id)
    
    # Temporary table for bulk insert
    temp_table = "metric_results_temp"
    df.to_sql(temp_table, engine, if_exists='replace')
    
    row_count = 0
    conn = engine.raw_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"ALTER TABLE {temp_table} DROP COLUMN index;")
        
        # Insert into metric_results
        insert_sql = f"""
            INSERT INTO {DB_SCHEMA}.metric_results 
            (calc_id, param_id, ticker, fx_currency, fy_year, key, value)
            SELECT calc_id, param_id, ticker, fx_currency, fy_year, key, value
            FROM {temp_table};
        """
        
        cur.execute(insert_sql)
        row_count = cur.rowcount
        cur.execute(f"DROP TABLE {temp_table};")
        conn.commit()
        cur.close()
    finally:
        conn.close()
    
    return row_count


# ============================================================================
# PHASE 3: Data Quality ID (dq_id) Threading Helper Functions
# ============================================================================

def verify_dq_id_has_data(dq_id: UUID) -> bool:
    """
    Verify that a dq_id exists and has associated data in versioning tables.
    
    Args:
        dq_id: Data quality ID to verify
    
    Returns:
        bool: True if dq_id exists and has data, False otherwise
    """
    try:
        query = f"""
            SELECT COUNT(*) as cnt FROM {DB_SCHEMA}.data_quality 
            WHERE dq_id = '{dq_id}'
        """
        result = execute_select(query)
        return len(result) > 0 and result.iloc[0]['cnt'] > 0
    except Exception as e:
        logger.error(f"Error verifying dq_id {dq_id}: {e}")
        return False


def get_annual_wide_format_with_dq(dq_id: UUID, country: str) -> pd.DataFrame:
    """
    Get annual data filtered by dq_id (Phase 3 version).
    
    Only returns data rows where dq_id FK matches the specified value.
    
    Args:
        dq_id: Data quality ID for filtering
        country: Country code for domicile filtering
    
    Returns:
        DataFrame with annual data for specified dq_id and country
    """
    query = f"""
        SELECT DISTINCT a.* 
        FROM {DB_SCHEMA}.annual_data a
        INNER JOIN {DB_SCHEMA}.company b ON a.ticker = b.ticker
        WHERE a.dq_id = '{dq_id}'
        AND b.domicile_country = '{country}'
        ORDER BY a.ticker, a.fy_year
    """
    try:
        df = execute_select(query)
        logger.info(f"Loaded {len(df)} rows of annual data for dq_id={dq_id}")
        return df
    except Exception as e:
        logger.error(f"Error loading annual data for dq_id {dq_id}: {e}")
        return pd.DataFrame()


def get_monthly_wide_format_with_dq(dq_id: UUID, bondIndex: str = 'GACGB10') -> pd.DataFrame:
    """
    Get monthly data filtered by dq_id (Phase 3 version).
    
    Args:
        dq_id: Data quality ID for filtering
        bondIndex: Bond index identifier (default: GACGB10)
    
    Returns:
        DataFrame with monthly data for specified dq_id
    """
    query = f"""
        SELECT 
            ticker, date,
            CAST(value AS DECIMAL) as rf,
            ROUND((CAST(value AS DECIMAL)/100) + 1, 4) AS rf_prel
        FROM {DB_SCHEMA}.monthly_data
        WHERE dq_id = '{dq_id}'
        AND key = 'Rf'
        AND ticker LIKE '%{bondIndex}%'
        ORDER BY ticker, date DESC
    """
    try:
        df = execute_select(query)
        logger.info(f"Loaded {len(df)} rows of monthly data for dq_id={dq_id}")
        return df
    except Exception as e:
        logger.error(f"Error loading monthly data for dq_id {dq_id}: {e}")
        return pd.DataFrame()


def get_pending_metric_runs(connection) -> list[dict]:
    """
    Get all metric_runs with status='pending' for worker processing.
    
    Args:
        connection: SQLAlchemy database connection
    
    Returns:
        List of dicts with keys: {calc_id, dq_id, param_id, parameters}
    """
    from sqlalchemy import text
    
    query = """
        SELECT 
            mr.calc_id,
            mr.dq_id,
            mr.param_id,
            ps.parameters
        FROM "USR"."metric_runs" mr
        JOIN "USR"."parameter_scenarios" ps ON mr.param_id = ps.param_id
        WHERE mr.status = 'pending'
        ORDER BY mr.created_at ASC
    """
    try:
        result = connection.execute(text(query))
        rows = result.fetchall()
        
        # Convert Row objects to dicts
        return [dict(row._mapping) for row in rows]
    except Exception as e:
        logger.error(f"Error getting pending metric runs: {e}")
        return []


def update_metric_run_status(
    connection,
    calc_id: UUID,
    status: str,
    started_at=None,
    completed_at=None,
    error_message: str = None
) -> None:
    """
    Update metric_runs status with timestamps and optional error message.
    
    Args:
        connection: SQLAlchemy database connection
        calc_id: Calculation run ID
        status: New status ('pending' | 'running' | 'completed' | 'failed')
        started_at: When calculation started
        completed_at: When calculation completed
        error_message: Error details if status is 'failed'
    """
    from sqlalchemy import text
    import json
    from datetime import datetime
    
    metadata = {}
    if error_message:
        metadata['error'] = error_message
    
    update_query = """
        UPDATE "USR"."metric_runs"
        SET 
            status = :status,
            started_at = COALESCE(:started_at, started_at),
            completed_at = COALESCE(:completed_at, completed_at),
            metadata = :metadata
        WHERE calc_id = :calc_id
    """
    
    try:
        connection.execute(
            text(update_query),
            {
                'calc_id': str(calc_id),
                'status': status,
                'started_at': started_at or datetime.utcnow(),
                'completed_at': completed_at,
                'metadata': json.dumps(metadata) if metadata else None
            }
        )
        connection.commit()
        logger.debug(f"Updated metric_runs {calc_id} status to {status}")
    except Exception as e:
        logger.error(f"Error updating metric_run status: {e}")
        raise


