import pandas as pd
from uuid import UUID
from src.engine import sql, curation as cd


def load_df_to_postgres(metrics, betas, config):
    return sql.execute_transactional_insert(metrics, betas, config)


def load_beta(dataset):
    table_name = "config"
    sql.execute_batch_update(dataset, table_name)


def load_config(dataset):
    table_name = "config"
    sql.execute_batch_update(dataset, table_name)


def load_metrics(dataset):
    table_name = "metrics"
    sql.execute_batch_update(dataset, table_name)


def load_base(dataset):
    table_name = "company"
    sql.execute_batch_update(dataset, table_name)


def load_user_defined_data(dataset):
    table_name = "user_defined_data"
    sql.execute_batch_update(dataset, table_name)


def load_dates(dataset):
    table_name = "fy_dates"
    sql.execute_batch_update(dataset, table_name)


def load_monthly(dataset):
    table_name = "monthly_data"
    sql.execute_batch_update(dataset, table_name)


def load_annual(dataset):
    table_name = "annual_data"
    sql.execute_batch_update(dataset, table_name)


def load_company_tsr(dataset):
    load_monthly(dataset)


def load_index_tsr(dataset):
    load_monthly(dataset)


def load_rf(dataset):
    load_monthly(dataset)


def load_fy_tsr(dataset):
    load_annual(dataset)


def load_spot_shares(dataset):
    load_annual(dataset)


def load_share_price(dataset):
    load_annual(dataset)


def load_mc(dataset):
    load_annual(dataset)


def load_pat(dataset):
    load_annual(dataset)


def load_mi(dataset):
    load_annual(dataset)


def load_div(dataset):
    load_annual(dataset)


def load_dist(dataset):
    load_annual(dataset)


def load_inj(dataset):
    load_annual(dataset)


def load_revenue(dataset):
    load_annual(dataset)


def load_op_income(dataset):
    load_annual(dataset)


def load_pbt(dataset):
    load_annual(dataset)


def load_pat_xo(dataset):
    load_annual(dataset)


def load_total_assets(dataset):
    load_annual(dataset)


def load_total_equity(dataset):
    load_annual(dataset)


def load_cash(dataset):
    load_annual(dataset)


def load_fa(dataset):
    load_annual(dataset)


def load_gw(dataset):
    load_annual(dataset)


def load_fy_dates(dataset):
    load_dates(dataset)


def load_fy_period(dataset):
    load_dates(dataset)


def load_ph_equity_growth(dataset):
    load_user_defined_data(dataset)


def load_terminal_equity_growth(dataset):
    load_user_defined_data(dataset)


def load_franking_ratio(dataset):
    load_user_defined_data(dataset)


def load_controls(dataset):
    table_name = "config"
    sql.execute_batch_update(dataset, table_name)


def get_all_metrics(dataset):
    return sql.get_metrics(dataset)


def load_dataset_for_processing():
    dates = sql.get_min_date()
    rates = sql.get_TSR()
    fy_dates = sql.get_fy_dates()
    rates.drop_duplicates(inplace=True)
    dates['inception'] = pd.to_datetime(dates['inception'])
    rates['date'] = pd.to_datetime(rates['date'])
    df = rates.merge(dates, how='left', on='ticker')
    df = df[(df.date >= df.inception) & (df.date.notnull())]
    return df, rates, fy_dates


def load_to_postgres_as_transaction(betas, metrics, config):
    betas = cd.process_metrics(betas, config['identifier'])
    metrics = cd.process_metrics(metrics, config['identifier'])
    config = cd.process_config(config)
    return load_df_to_postgres(metrics, betas, config)


def upload_metrics_to_db(cost_of_eq, inputs, l1_metrics):
    load_to_postgres_as_transaction(l1_metrics, cost_of_eq, inputs)


def initialize():
    return True


def load_L2_metrics_to_db(identifier, fx_currency, aggregated_metrics):
    dataset = pd.melt(aggregated_metrics, id_vars=['fy_year', 'ticker'], value_name='value')
    dataset['guid'] = identifier
    dataset['fx_curency'] = fx_currency
    dataset.rename(columns={'variable': 'key'}, inplace=True)
    dataset = dataset[['guid', 'ticker', 'fx_curency', 'fy_year', 'key', 'value']]
    dataset = dataset[dataset.fy_year > 1980]
    table_name = "metrics"
    sql.execute_batch_update(dataset, table_name)
    return True


def get_annual_wide_format(param):
    return sql.get_annual_wide_format(param)


def get_monthly_wide_format(bondIndex):
    return sql.get_monthly_wide_format(bondIndex=bondIndex)


def save_sector_metrics(sector_metrics):
    sql.save_sector_metrics_to_db(sector_metrics)
    return True


# ============================================================================
# PHASE 3: Result Storage Functions
# ============================================================================

def store_metrics_with_calc_id(
    results_list: list[dict],
    calc_id: UUID,
    param_id: UUID,
    dq_id: UUID
) -> None:
    """
    Store calculated metrics in metric_results table (Phase 3).
    
    Converts list of metric results into DataFrame and inserts into
    metric_results table with calc_id and param_id for traceability.
    
    Args:
        results_list: List of dicts with keys:
                     {ticker, fx_currency, fy_year, key, value}
        calc_id: Calculation run ID (from metric_runs)
        param_id: Parameter scenario ID
        dq_id: Data quality ID (for audit trail)
    
    Raises:
        Exception: If insertion fails
    """
    if not results_list:
        return
    
    # Convert list of dicts to DataFrame
    results_df = pd.DataFrame(results_list)
    
    # Add calc_id and param_id columns
    results_df['calc_id'] = str(calc_id)
    results_df['param_id'] = str(param_id)
    
    # Ensure required columns exist
    required_cols = ['calc_id', 'param_id', 'ticker', 'fx_currency', 'fy_year', 'key', 'value']
    for col in required_cols:
        if col not in results_df.columns:
            if col in ['fx_currency']:
                results_df[col] = None
            elif col in ['fy_year']:
                results_df[col] = 0
            else:
                raise ValueError(f"Missing required column: {col}")
    
    # Reorder columns
    results_df = results_df[required_cols]
    
    # Insert into database using batch update
    sql.write_metric_results(results_df, calc_id, param_id)

