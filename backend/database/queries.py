"""
Financial Data Pipeline - Common SQL Queries

This module provides ready-to-use SQL queries organized by use case.
Each query is a standalone template that can be parameterized.

Usage:
    from backend.database.etl.config import engine
    from sqlalchemy import text
    
    with engine.connect() as conn:
        result = conn.execute(text(QUERY_LATEST_DATASET))
        for row in result:
            print(row)
"""

# ============================================================================
# SECTION 1: DATASET VERSIONING
# ============================================================================

QUERY_LATEST_DATASET = """
    SELECT 
        dataset_id,
        dataset_name,
        version_number,
        status,
        created_at,
        updated_at
    FROM dataset_versions
    WHERE status = 'PROCESSED'
    ORDER BY created_at DESC
    LIMIT 1;
"""

QUERY_ALL_DATASETS = """
    SELECT 
        dataset_id,
        dataset_name,
        version_number,
        status,
        CASE 
            WHEN status = 'ERROR' THEN error_message
            ELSE ''
        END as notes,
        created_at,
        updated_at
    FROM dataset_versions
    ORDER BY created_at DESC;
"""

QUERY_DATASET_STATUS_TIMELINE = """
    SELECT 
        dataset_id,
        dataset_name,
        EXTRACT(EPOCH FROM (updated_at - created_at))::INTEGER as processing_seconds,
        status,
        created_at,
        updated_at
    FROM dataset_versions
    WHERE status = 'PROCESSED'
    ORDER BY created_at DESC
    LIMIT 20;
"""

QUERY_DATASET_QUALITY_SUMMARY = """
    SELECT 
        dataset_id,
        dataset_name,
        quality_metadata ->> 'total_raw_values' as total_raw,
        quality_metadata ->> 'valid_raw_values' as valid_raw,
        quality_metadata ->> 'imputation_attempts' as imputation_attempts,
        quality_metadata ->> 'successful_imputations' as successful_imputations,
        ROUND(100.0 * 
            (quality_metadata ->> 'valid_raw_values')::NUMERIC / 
            (quality_metadata ->> 'total_raw_values')::NUMERIC, 2) as valid_pct
    FROM dataset_versions
    WHERE status = 'PROCESSED'
    ORDER BY created_at DESC
    LIMIT 10;
"""

# ============================================================================
# SECTION 2: DATA VALIDATION & QUALITY
# ============================================================================

QUERY_VALIDATION_SUMMARY = """
    SELECT 
        validation_status,
        COUNT(*) as count,
        ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) as percentage
    FROM raw_data
    WHERE dataset_id = :dataset_id
    GROUP BY validation_status;
"""

QUERY_REJECTION_REASONS = """
    SELECT 
        rejection_reason,
        COUNT(*) as count,
        ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) as percentage
    FROM raw_data
    WHERE dataset_id = :dataset_id
        AND validation_status = 'REJECTED'
    GROUP BY rejection_reason
    ORDER BY count DESC;
"""

QUERY_PROBLEMATIC_COMPANIES = """
    SELECT 
        ticker,
        COUNT(*) as total_rows,
        COUNT(CASE WHEN validation_status = 'VALID' THEN 1 END) as valid_rows,
        COUNT(CASE WHEN validation_status = 'REJECTED' THEN 1 END) as rejected_rows,
        ROUND(100.0 * 
            COUNT(CASE WHEN validation_status = 'VALID' THEN 1 END) / COUNT(*), 2) as valid_pct
    FROM raw_data
    WHERE dataset_id = :dataset_id
    GROUP BY ticker
    HAVING COUNT(CASE WHEN validation_status = 'REJECTED' THEN 1 END) > 0
    ORDER BY rejected_rows DESC;
"""

QUERY_PROBLEMATIC_METRICS = """
    SELECT 
        metric_name,
        COUNT(*) as total_rows,
        COUNT(CASE WHEN validation_status = 'VALID' THEN 1 END) as valid_rows,
        COUNT(CASE WHEN validation_status = 'REJECTED' THEN 1 END) as rejected_rows,
        ROUND(100.0 * 
            COUNT(CASE WHEN validation_status = 'VALID' THEN 1 END) / COUNT(*), 2) as valid_pct
    FROM raw_data
    WHERE dataset_id = :dataset_id
    GROUP BY metric_name
    HAVING COUNT(CASE WHEN validation_status = 'REJECTED' THEN 1 END) > 0
    ORDER BY rejected_rows DESC;
"""

# ============================================================================
# SECTION 3: IMPUTATION ANALYSIS
# ============================================================================

QUERY_IMPUTATION_DISTRIBUTION = """
    SELECT 
        imputation_source,
        COUNT(*) as count,
        ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) as percentage
    FROM fundamentals
    WHERE dataset_id = :dataset_id
    GROUP BY imputation_source
    ORDER BY count DESC;
"""

QUERY_CONFIDENCE_DISTRIBUTION = """
    SELECT 
        CASE 
            WHEN confidence_level >= 0.95 THEN 'Very High (≥0.95)'
            WHEN confidence_level >= 0.90 THEN 'High (0.90-0.95)'
            WHEN confidence_level >= 0.75 THEN 'Medium (0.75-0.90)'
            ELSE 'Low (<0.75)'
        END as confidence_band,
        COUNT(*) as count,
        ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) as percentage,
        MIN(confidence_level)::NUMERIC(3,2) as min_conf,
        MAX(confidence_level)::NUMERIC(3,2) as max_conf,
        ROUND(AVG(confidence_level), 3)::NUMERIC(3,3) as avg_conf
    FROM fundamentals
    WHERE dataset_id = :dataset_id
    GROUP BY confidence_band
    ORDER BY min_conf DESC;
"""

QUERY_LOW_CONFIDENCE_DATA = """
    SELECT 
        ticker,
        metric_name,
        fiscal_year,
        value,
        confidence_level,
        imputation_source
    FROM fundamentals
    WHERE dataset_id = :dataset_id
        AND confidence_level < :confidence_threshold
    ORDER BY confidence_level, ticker, metric_name, fiscal_year;
"""

QUERY_IMPUTATION_BY_COMPANY = """
    SELECT 
        f.ticker,
        f.imputation_source,
        COUNT(*) as count,
        ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY f.ticker), 2) as pct_of_company
    FROM fundamentals f
    WHERE f.dataset_id = :dataset_id
    GROUP BY f.ticker, f.imputation_source
    ORDER BY f.ticker, count DESC;
"""

QUERY_IMPUTATION_BY_METRIC = """
    SELECT 
        f.metric_name,
        f.imputation_source,
        COUNT(*) as count,
        ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY f.metric_name), 2) as pct_of_metric
    FROM fundamentals f
    WHERE f.dataset_id = :dataset_id
    GROUP BY f.metric_name, f.imputation_source
    ORDER BY f.metric_name, count DESC;
"""

# ============================================================================
# SECTION 4: DATA RETRIEVAL
# ============================================================================

QUERY_COMPANY_METRICS_ALL = """
    SELECT 
        f.ticker,
        f.metric_name,
        f.fiscal_year,
        f.value,
        f.imputation_source,
        f.confidence_level
    FROM fundamentals f
    WHERE f.dataset_id = :dataset_id
        AND f.ticker = :ticker
    ORDER BY f.fiscal_year DESC, f.metric_name;
"""

QUERY_COMPANY_METRICS_SPECIFIC = """
    SELECT 
        f.ticker,
        f.metric_name,
        f.fiscal_year,
        f.value,
        f.imputation_source,
        f.confidence_level
    FROM fundamentals f
    WHERE f.dataset_id = :dataset_id
        AND f.ticker = :ticker
        AND f.metric_name = :metric_name
    ORDER BY f.fiscal_year DESC;
"""

QUERY_TIME_SERIES = """
    SELECT 
        f.fiscal_year,
        f.value,
        f.imputation_source,
        f.confidence_level,
        c.name as company_name,
        c.sector
    FROM fundamentals f
    JOIN companies c ON f.ticker = c.ticker
    WHERE f.dataset_id = :dataset_id
        AND f.ticker = :ticker
        AND f.metric_name = :metric_name
    ORDER BY f.fiscal_year;
"""

QUERY_CROSS_COMPANY_COMPARISON = """
    SELECT 
        f.ticker,
        f.value,
        f.imputation_source,
        c.name as company_name,
        c.sector
    FROM fundamentals f
    JOIN companies c ON f.ticker = c.ticker
    WHERE f.dataset_id = :dataset_id
        AND f.fiscal_year = :fiscal_year
        AND f.metric_name = :metric_name
    ORDER BY f.value DESC;
"""

QUERY_SECTOR_COMPARISON = """
    SELECT 
        c.sector,
        f.ticker,
        c.name as company_name,
        f.fiscal_year,
        f.metric_name,
        f.value,
        f.imputation_source
    FROM fundamentals f
    JOIN companies c ON f.ticker = c.ticker
    WHERE f.dataset_id = :dataset_id
        AND f.fiscal_year = :fiscal_year
        AND f.metric_name = :metric_name
        AND c.sector = :sector
    ORDER BY f.value DESC;
"""

# ============================================================================
# SECTION 5: AGGREGATED VIEWS
# ============================================================================

QUERY_DATASET_OVERVIEW = """
    SELECT 
        COUNT(DISTINCT f.ticker) as companies,
        COUNT(DISTINCT f.metric_name) as metrics,
        COUNT(DISTINCT f.fiscal_year) as fiscal_years,
        COUNT(*) as total_data_points,
        ROUND(AVG(f.confidence_level), 3) as avg_confidence,
        MIN(f.fiscal_year) as earliest_fy,
        MAX(f.fiscal_year) as latest_fy
    FROM fundamentals f
    WHERE f.dataset_id = :dataset_id;
"""

QUERY_COMPANY_DATA_COMPLETENESS = """
    SELECT 
        f.ticker,
        c.name as company_name,
        c.sector,
        COUNT(DISTINCT f.metric_name) as metrics_available,
        COUNT(DISTINCT f.fiscal_year) as fiscal_years_available,
        COUNT(*) as total_data_points,
        ROUND(AVG(f.confidence_level), 3) as avg_confidence
    FROM fundamentals f
    JOIN companies c ON f.ticker = c.ticker
    WHERE f.dataset_id = :dataset_id
    GROUP BY f.ticker, c.name, c.sector
    ORDER BY total_data_points DESC;
"""

QUERY_METRIC_COVERAGE = """
    SELECT 
        f.metric_name,
        m.metric_type,
        m.unit,
        COUNT(DISTINCT f.ticker) as companies_with_data,
        COUNT(DISTINCT f.fiscal_year) as fiscal_years_available,
        COUNT(*) as total_data_points,
        ROUND(AVG(f.confidence_level), 3) as avg_confidence
    FROM fundamentals f
    JOIN metrics_catalog m ON f.metric_name = m.metric_name
    WHERE f.dataset_id = :dataset_id
    GROUP BY f.metric_name, m.metric_type, m.unit
    ORDER BY total_data_points DESC;
"""

QUERY_SECTOR_SUMMARY = """
    SELECT 
        c.sector,
        COUNT(DISTINCT f.ticker) as companies,
        COUNT(DISTINCT f.metric_name) as metrics,
        COUNT(*) as total_data_points,
        ROUND(AVG(f.confidence_level), 3) as avg_confidence,
        COUNT(CASE WHEN f.imputation_source = 'RAW' THEN 1 END)::FLOAT / COUNT(*) as raw_pct,
        COUNT(CASE WHEN f.imputation_source IN ('FORWARD_FILL', 'BACKWARD_FILL', 'INTERPOLATE') THEN 1 END)::FLOAT / COUNT(*) as imputed_pct
    FROM fundamentals f
    JOIN companies c ON f.ticker = c.ticker
    WHERE f.dataset_id = :dataset_id
    GROUP BY c.sector
    ORDER BY companies DESC;
"""

# ============================================================================
# SECTION 6: REFERENCE DATA
# ============================================================================

QUERY_ALL_COMPANIES = """
    SELECT 
        ticker,
        name,
        sector,
        currency
    FROM companies
    ORDER BY ticker;
"""

QUERY_COMPANIES_BY_SECTOR = """
    SELECT 
        sector,
        COUNT(*) as company_count,
        STRING_AGG(ticker, ', ' ORDER BY ticker) as tickers
    FROM companies
    GROUP BY sector
    ORDER BY company_count DESC;
"""

QUERY_ALL_METRICS = """
    SELECT 
        metric_id,
        metric_name,
        metric_type,
        unit,
        description
    FROM metrics_catalog
    ORDER BY metric_name;
"""

QUERY_FISCAL_YEAR_DATES = """
    SELECT 
        ticker,
        fiscal_year,
        fy_period_date
    FROM fiscal_year_mapping
    WHERE ticker = :ticker
    ORDER BY fiscal_year DESC;
"""

# ============================================================================
# SECTION 7: DOWNSTREAM ANALYSIS (Optional)
# ============================================================================

QUERY_METRICS_OUTPUTS = """
    SELECT 
        m.ticker,
        m.fiscal_year,
        m.metric_name,
        m.metric_value,
        ps.parameter_set_name,
        m.created_at
    FROM metrics_outputs m
    JOIN parameter_sets ps ON m.parameter_set_id = ps.parameter_set_id
    WHERE m.dataset_id = :dataset_id
        AND m.ticker = :ticker
    ORDER BY m.fiscal_year DESC, m.metric_name;
"""

QUERY_OPTIMIZATION_OUTPUTS = """
    SELECT 
        o.ticker,
        o.allocation_weight,
        o.expected_return,
        o.volatility,
        o.valuation_multiple,
        o.optimization_scenario,
        ps.parameter_set_name
    FROM optimization_outputs o
    JOIN parameter_sets ps ON o.parameter_set_id = ps.parameter_set_id
    WHERE o.dataset_id = :dataset_id
        AND o.optimization_scenario = :scenario
    ORDER BY o.allocation_weight DESC;
"""

# ============================================================================
# SECTION 8: AUDIT & TRACKING
# ============================================================================

QUERY_RECENT_PIPELINES = """
    SELECT 
        dataset_id,
        dataset_name,
        version_number,
        status,
        EXTRACT(EPOCH FROM (updated_at - created_at))::INTEGER as processing_seconds,
        created_at,
        updated_at
    FROM dataset_versions
    ORDER BY created_at DESC
    LIMIT 20;
"""

QUERY_PIPELINE_ERRORS = """
    SELECT 
        dataset_id,
        dataset_name,
        status,
        error_message,
        created_at,
        updated_at
    FROM dataset_versions
    WHERE status = 'ERROR'
    ORDER BY created_at DESC
    LIMIT 20;
"""

QUERY_PROCESSING_TIME_ANALYSIS = """
    SELECT 
        dataset_name,
        EXTRACT(EPOCH FROM (updated_at - created_at))::INTEGER as processing_seconds,
        EXTRACT(EPOCH FROM (updated_at - created_at))::INTEGER / 60.0 as processing_minutes,
        quality_metadata ->> 'total_raw_values' as raw_rows_processed,
        status
    FROM dataset_versions
    WHERE status IN ('PROCESSED', 'ERROR')
    ORDER BY updated_at DESC
    LIMIT 20;
"""

# ============================================================================
# HELPER: Execute Query Template
# ============================================================================

def execute_query(engine, query_template: str, params: dict = None):
    """
    Execute a query template with optional parameters.
    
    Args:
        engine: SQLAlchemy engine
        query_template: SQL query string with :param placeholders
        params: Dictionary of parameters to bind
    
    Returns:
        List of result rows
    
    Example:
        results = execute_query(
            engine, 
            QUERY_IMPUTATION_DISTRIBUTION,
            {"dataset_id": "550e8400-e29b-41d4-a716-446655440000"}
        )
        for row in results:
            print(row)
    """
    from sqlalchemy import text
    
    params = params or {}
    with engine.connect() as conn:
        result = conn.execute(text(query_template), params)
        return result.fetchall()
