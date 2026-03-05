"""
Phase 3: Metrics calculation with dq_id (data quality ID) threading.

This module provides the entry point for L1 and L2 metrics calculation
tied to specific data versions via dq_id.
"""

import logging
from uuid import UUID
from src.engine.calculation import calculate_general_metrics_with_dq
from src.engine.loaders import store_metrics_with_calc_id
from src.engine import sql

logger = logging.getLogger(__name__)


def calculate_metrics_with_dq(
    dq_id: UUID,
    calc_id: UUID,
    parameters: dict,
    db_connection=None
) -> tuple[dict, list[dict]]:
    """
    Calculate L1 and L2 metrics for data with specific dq_id.
    
    This is the primary entry point for Phase 3 metrics calculation.
    Metrics are calculated ONLY from data with the specified dq_id,
    ensuring data isolation and proper version tracking.
    
    Args:
        dq_id: Data quality ID linking to source data version
        calc_id: Calculation run ID for result tracking and audit trail
        parameters: Dict with metric calculation parameters
            Example:
            {
                "identifier": "some_guid",
                "error_tolerance": 0.8,
                "approach_to_ke": "Floating",
                "beta_rounding": 0.1,
                "risk_premium": 0.05,
                "userid": "system",
                "country": "AUS",
                "currency": "AUD",
                "benchmark_return": 0.03,
                "incl_franking": "Yes",
                "frank_tax_rate": 0.3,
                "value_franking_cr": 0.7,
                "exchange": "ASX",
                "franking": 1,
                "bondIndex": "GACGB10"
            }
        db_connection: Optional DB connection (for testing/transaction management)
    
    Returns:
        Tuple of:
        - results_dict: {ticker: {fy_year: {metric_key: value}}} (for processing)
        - results_list: [{ticker, fx_currency, fy_year, key, value}] (for DB insert)
    
    Raises:
        ValueError: If dq_id not found or has no data with dq_id
        Exception: Any error during L1/L2 calculation (caller handles)
    """
    
    logger.info(f"Starting metrics calculation for dq_id={dq_id}, calc_id={calc_id}")
    
    try:
        # Step 1: Verify dq_id exists and has data
        logger.debug(f"Verifying dq_id {dq_id} exists and has data")
        if not sql.verify_dq_id_has_data(dq_id):
            raise ValueError(
                f"dq_id {dq_id} not found or has no data with dq_id populated"
            )
        
        # Step 2: Calculate L1 and L2 metrics with dq_id filtering
        logger.info(f"Calling calculate_general_metrics_with_dq for dq_id={dq_id}")
        cost_of_eq, l1_metrics = calculate_general_metrics_with_dq(
            dq_id=dq_id,
            parameters=parameters
        )
        
        # Step 3: Calculate L2 metrics (depends on L1)
        logger.info(f"Calculating L2 metrics for dq_id={dq_id}")
        l2_metrics = calculate_l2_metrics_with_dq(
            dq_id=dq_id,
            l1_metrics=l1_metrics,
            parameters=parameters
        )
        
        # Step 4: Format results for storage
        logger.debug("Formatting results for database storage")
        results_list = format_results_for_storage(
            l1_metrics, l2_metrics
        )
        
        logger.info(
            f"Metrics calculation successful: "
            f"dq_id={dq_id}, calc_id={calc_id}, "
            f"results_count={len(results_list)}"
        )
        
        return {}, results_list
    
    except Exception as e:
        logger.error(
            f"Metrics calculation failed for dq_id={dq_id}, calc_id={calc_id}: {e}",
            exc_info=True
        )
        raise


def calculate_l2_metrics_with_dq(
    dq_id: UUID,
    l1_metrics,
    parameters: dict
):
    """
    Calculate L2 metrics using L1 results and annual data with dq_id filtering.
    
    L2 metrics depend on L1 results, so this function requires L1 to be
    calculated first.
    
    Args:
        dq_id: Data quality ID for data filtering
        l1_metrics: L1 metrics DataFrame from L1 calculation
        parameters: Calculation parameters
    
    Returns:
        L2 metrics DataFrame
    """
    from src.engine import calculation as calc
    from src.engine import sql as sql_module
    from src.engine import formatters as fmt
    import pandas as pd
    
    logger.debug(f"Starting L2 metrics calculation for dq_id={dq_id}")
    
    # Load annual data filtered by dq_id
    annual_data = sql_module.get_annual_wide_format_with_dq(dq_id)
    
    if annual_data is None or annual_data.empty:
        logger.warning(f"No annual data found for dq_id={dq_id}")
        return pd.DataFrame()
    
    # Prepare data
    annual_data['fytsr'] = (annual_data['fytsr'] / 100) + 1
    annual_data["fy_year"] = annual_data["fy_year"].astype(int)
    annual_data['fx_currency'] = annual_data['fx_currency'].str.strip()
    annual_data['ticker'] = annual_data['ticker'].str.strip()
    
    # Prepare L1 metrics
    l1_metrics["fy_year"] = l1_metrics["fy_year"].astype(int)
    l1_metrics = l1_metrics[l1_metrics['fy_year'] > 1999]
    l1_metrics['fx_currency'] = l1_metrics['fx_currency'].str.strip()
    l1_metrics['ticker'] = l1_metrics['ticker'].str.strip()
    
    # Merge L1 metrics with annual data
    general_metrics = fmt.merge_metrics(
        [annual_data, l1_metrics], 
        on=['ticker', 'fy_year', 'fx_currency']
    )
    
    general_metrics["fy_year"] = general_metrics["fy_year"].astype(int)
    
    # Calculate L2 metrics
    l2_metrics = calc.calculate_aggregated_metrics_async(general_metrics, parameters)
    
    logger.debug(f"L2 metrics calculation complete for dq_id={dq_id}")
    
    return l2_metrics


def format_results_for_storage(l1_metrics, l2_metrics) -> list[dict]:
    """
    Format L1 and L2 metrics into storage format.
    
    Converts metrics DataFrames into list of dicts with structure:
    {
        'ticker': str,
        'fx_currency': str,
        'fy_year': int,
        'key': str (metric name),
        'value': numeric
    }
    
    Args:
        l1_metrics: L1 metrics DataFrame
        l2_metrics: L2 metrics DataFrame
    
    Returns:
        List of formatted result dictionaries
    """
    import pandas as pd
    
    results_list = []
    
    # Format L1 metrics
    if l1_metrics is not None and not l1_metrics.empty:
        # L1 metrics are already in wide format with columns like C_MC, C_ASSETS, etc.
        # Convert to long format
        id_vars = ['ticker', 'fx_currency', 'fy_year']
        l1_long = pd.melt(
            l1_metrics,
            id_vars=id_vars,
            value_vars=[col for col in l1_metrics.columns if col not in id_vars],
            var_name='key',
            value_name='value'
        )
        
        # Convert to list of dicts
        results_list.extend(l1_long.to_dict('records'))
    
    # Format L2 metrics
    if l2_metrics is not None and not l2_metrics.empty:
        # L2 metrics are already in long format
        # Ensure proper column names
        l2_long = pd.melt(
            l2_metrics,
            id_vars=['ticker', 'fy_year'] if 'fy_year' in l2_metrics.columns else ['ticker'],
            var_name='key',
            value_name='value'
        )
        
        # Add fx_currency if not present
        if 'fx_currency' not in l2_long.columns:
            l2_long['fx_currency'] = None
        
        results_list.extend(l2_long.to_dict('records'))
    
    logger.debug(f"Formatted {len(results_list)} metric results for storage")
    
    return results_list
