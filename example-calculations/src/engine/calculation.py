import threading
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import wait
from uuid import UUID

import numpy as np
import pandas as pd
from src.engine import formatters as fmt
from src.engine import sql, loaders as ld
from src.engine import aggregators as agg
from src.executors import beta as bta, fvecf as fv, utility as util
from src.executors import rates as rf
from src.executors import metrics
from src.config import parameters as param

logger = util.get_logger()


def calculate_general_metrics_with_dq(dq_id: UUID, inputs: dict):
    """
    Calculate L1 metrics for data with specific dq_id (Phase 3).
    
    This is the Phase 3 version that filters data by dq_id instead of
    calculating across all data in the system.
    
    Args:
        dq_id: Data quality ID for data filtering
        inputs: Parameters dict with country, bondIndex, etc.
    
    Returns:
        (cost_of_eq, l1_metrics): L1 calculation results
    """
    logger.info(f"Starting calculate_general_metrics_with_dq for dq_id={dq_id}")
    
    # Load data filtered by dq_id
    annual_data = sql.get_annual_wide_format_with_dq(dq_id, inputs['country'])
    monthly_data, rates, fy_dates = ld.load_dataset_for_processing()
    monthly_rf = ld.get_monthly_wide_format(bondIndex=inputs['bondIndex'])
    monthly_rf = monthly_rf.reset_index(drop=True).drop_duplicates()
    
    betas_list = []
    metrics_list = []
    risk_free_list = []
    
    jobs = [
        threading.Thread(target=lambda: metrics_list.append(
            thread_basic_metrics(annual_data, inputs)
        )),
        threading.Thread(target=lambda: betas_list.append(
            thread_beta_calculation(monthly_data, inputs)
        )),
        threading.Thread(
            target=lambda: risk_free_list.append(
                thread_rates_calculation(rates, monthly_rf, fy_dates, inputs)
            )
        )
    ]
    
    # Start threads
    with ThreadPoolExecutor() as executor:
        executor.map(lambda t: t.start(), jobs)
        executor.map(lambda t: t.join(), jobs)
    
    logger.info(f"Metrics calculation complete for dq_id={dq_id}")
    
    betas, l1_metrics, risk_free_rate = fmt.concat_metrics(
        betas_list, metrics_list, risk_free_list
    )
    cost_of_eq = calculate_cost_of_eqity(betas, inputs, risk_free_rate)
    
    return cost_of_eq, l1_metrics


def thread_basic_metrics(df, inputs):
    return metrics.generate_l1_metrics_async(df, inputs)


def thread_beta_calculation(monthly_data, inputs):
    return bta.calculate_beta_async(monthly_data, inputs)


def thread_rates_calculation(monthly_rates, monthly_rf, fy_dates, inputs):
    return rf.calculate_rates_async(fy_dates, inputs, monthly_rates, monthly_rf)


def calculate_general_metrics(inputs):
    annual_data = ld.get_annual_wide_format(inputs['country'])
    monthly_data, rates, fy_dates = ld.load_dataset_for_processing()
    monthly_rf = ld.get_monthly_wide_format(bondIndex=inputs['bondIndex'])
    monthly_rf = monthly_rf.reset_index(drop=True).drop_duplicates()
    betas_list = []
    metrics_list = []
    risk_free_list = []
    jobs = [threading.Thread(target=lambda: metrics_list.append(thread_basic_metrics(annual_data, inputs))),
            threading.Thread(target=lambda: betas_list.append(thread_beta_calculation(monthly_data, inputs))),
            threading.Thread(
                target=lambda: risk_free_list.append(thread_rates_calculation(rates, monthly_rf, fy_dates, inputs)))]
    # Start threads
    with ThreadPoolExecutor() as executor:
        executor.map(lambda t: t.start(), jobs)
        executor.map(lambda t: t.join(), jobs)
    logger.info("calculate-  Successfully Created!!")
    betas, l1_metrics, risk_free_rate = fmt.concat_metrics(betas_list, metrics_list, risk_free_list)
    cost_of_eq = calculate_cost_of_eqity(betas, inputs, risk_free_rate)
    return cost_of_eq, l1_metrics


def thread_calculate_fv_ecf(general_metrics, inputs):
    intervals = [1, 3, 5, 10]
    results = pd.concat([fv.calculate_fv_ecf_seq(general_metrics, inputs, interval)
                         for interval in intervals])

    results = pd.DataFrame(results)
    return results


def calculate_aggregated_metrics_async(all_metrics, inputs):
    intervals = [1, 3, 5, 10]
    with ThreadPoolExecutor(max_workers=4) as executor:
        # Submit each group to the executor
        pools = [executor.submit(
            agg.calculate_aggregated_metrics, all_metrics, inputs, interval)
            for interval in intervals]
        _ = wait(pools)

        # Wait for all threads to complete and get results
        results = fmt.merge_metrics(
            [pool.result() for pool in pools],
            on=['ticker', 'fy_year']
        )
        results = pd.DataFrame(results)
        return results


def thread_generate_l2_metrics(l1_metrics, inputs):
    return metrics.generate_l2_metrics(l1_metrics, inputs)


def calculate_L2_metrics_async(inputs):
    fv_ecf_list = []
    open_col_for_join = ['ticker_open', 'fy_year_open', 'fx_currency_open']
    l2_metrics_list = []
    annual_data = sql.get_annual_wide_format(inputs['country'])
    annual_data['fytsr'] = (annual_data['fytsr'] / 100) + 1
    l1_metrics = sql.get_general_metrics_from_db(guid=param.GUID)
    annual_data["fy_year"] = annual_data["fy_year"].astype(int)
    annual_data['fx_currency'] = annual_data['fx_currency'].str.strip()
    annual_data['ticker'] = annual_data['ticker'].str.strip()
    l1_metrics["fy_year"] = l1_metrics["fy_year"].astype(int)
    l1_metrics = l1_metrics[l1_metrics['fy_year'] > 1999]
    l1_metrics['fx_currency'] = l1_metrics['fx_currency'].str.strip()
    l1_metrics['ticker'] = l1_metrics['ticker'].str.strip()
    general_metrics = fmt.merge_metrics([annual_data, l1_metrics], on=['ticker', 'fy_year', 'fx_currency'])
    general_metrics["fy_year"] = general_metrics["fy_year"].astype(int)
    open_general_metrics = general_metrics.copy(deep=True)
    open_general_metrics['fy_year'] = open_general_metrics['fy_year'] + 1
    open_general_metrics = open_general_metrics.add_suffix('_open')
    all_l1_metrics = pd.merge(general_metrics, open_general_metrics, how="left",
                              left_on=['ticker', 'fy_year', 'fx_currency'],
                              right_on=open_col_for_join)
    all_l1_metrics = all_l1_metrics[[col for col in all_l1_metrics.columns if col not in open_col_for_join]]

    jobs = [
        threading.Thread(target=lambda: l2_metrics_list.append(thread_generate_l2_metrics(all_l1_metrics, inputs)))]
    with ThreadPoolExecutor() as executor:
        executor.map(lambda t: t.start(), jobs)
        executor.map(lambda t: t.join(), jobs)
    l2_metrics = pd.concat(l2_metrics_list)
    jobs = [
        threading.Thread(target=lambda: fv_ecf_list.append(thread_calculate_fv_ecf(all_l1_metrics, inputs)))]
    with ThreadPoolExecutor() as executor:
        executor.map(lambda t: t.start(), jobs)
        executor.map(lambda t: t.join(), jobs)
    fv_ecf = pd.concat(fv_ecf_list)
    fv_ecf = fv_ecf.pivot_table(index=['ticker', 'fy_year', 'fx_currency'], columns='FV_ECF_TYPE',
                                values='FV_ECF_Y').reset_index()
    all_metrics = fmt.merge_metrics([l2_metrics, fv_ecf],
                                    on=['ticker', 'fy_year'])
    ratios = calculate_aggregated_metrics_async(all_metrics, inputs)
    ratios = fmt.merge_metrics([all_l1_metrics, fv_ecf, ratios, ],
                               on=['ticker', 'fy_year'])
    ratios.to_csv('ratios.csv')
    logger.info("calculate-  Successfully Created!!")
    return ratios


def calculate_cost_of_eqity(betas, inputs, risk_free_rate):
    cost_of_eq = pd.merge(betas, risk_free_rate, on=['ticker', 'fy_year'], how="inner")
    cost_of_eq['ke'] = cost_of_eq['rf'] + cost_of_eq['beta'] * inputs['risk_premium']
    return cost_of_eq


def calculate_sector_metrics(inputs):
    non_numeric_columns = ['guid', 'sector', 'fx_currency', 'fy_year', 'ticker']
    ignore_columns = ['open_rf_1_Y', 'open_rf_3_Y', 'open_rf_5_Y', 'open_rf_10_Y']
    dataset = sql.get_sector_metrics(inputs['identifier'])
    ds_pivot = dataset.pivot(index=['guid', 'ticker', 'fx_currency', 'sector', 'fy_year'],
                             columns='key', values='value')
    cols = [col.strip() for col in ds_pivot.columns]
    ds_pivot.columns = cols
    ds_pivot = pre_process(ds_pivot, inputs)
    numeric_columns = [col for col in ds_pivot.columns if col not in ignore_columns]
    ds_pivot.reset_index(inplace=True)
    others = ds_pivot.groupby(by=['guid', 'sector', 'fx_currency', 'fy_year'])[numeric_columns].sum()
    rates = (ds_pivot.groupby(['guid', 'sector', 'fx_currency', 'fy_year'])
             .agg({'open_rf_1_Y': lambda x: x.mean(skipna=False),
                   'open_rf_3_Y': lambda x: x.mean(skipna=False),
                   'open_rf_5_Y': lambda x: x.mean(skipna=False),
                   'open_rf_10_Y': lambda x: x.mean(skipna=False)}))
    df = pd.concat([others, rates]).reset_index()
    columns_to_melt = [col.strip() for col in df.columns if col not in non_numeric_columns]
    df = calculate_ratios(df, inputs)
    df_melt = pd.melt(df,
                      id_vars=['guid', 'sector', 'fx_currency', 'fy_year'],
                      value_vars=columns_to_melt,
                      var_name='key', value_name='value')
    return df_melt


def pre_process(int_metrics, inputs):
    intervals = [1, 3, 5, 10]
    risk_premium = inputs['risk_premium']
    for interval in intervals:
        int_metrics[f'open_rf_delta_{interval}_Y'] = int_metrics[f'open_rf_{interval}_Y']
        int_metrics[f'open_beta_delta_{interval}_Y'] = (np.power(
            int_metrics[f'WP_{interval}_Y'] / int_metrics[f'c_mc_open_{interval}_Y'], 1 / interval) - 1
                                                        - int_metrics[f'open_rf_delta_{interval}_Y']) / risk_premium
    return int_metrics


def calculate_ratios(sector_metrics, inputs):
    indexes = [1, 3, 5, 10]
    risk_premium = inputs['risk_premium']
    for index in indexes:
        sector_metrics[f'OPEN_BETA_{index}_Y'] = (np.power(
            sector_metrics[f'WP_{index}_Y'] / sector_metrics[f'c_mc_open_{index}_Y'], 1 / index) - 1
                                                  - sector_metrics[f'open_rf_{index}_Y']) / risk_premium
        sector_metrics[f'TER_{index}_Y'] = np.power(((sector_metrics[f'WC_{index}_Y'] + sector_metrics[f'WP_{index}_Y'])
                                                     / sector_metrics[f'c_mc_open_{index}_Y']), 1 / index)
        sector_metrics[f'TERA_{index}_Y'] = (sector_metrics[f'TER_KE_{index}_Y'] -
                                             np.power((
                                                     np.power((1 + sector_metrics[f'TER_{index}_Y']), index)
                                                     - sector_metrics[f'WC_TERA_{index}_Y'] / sector_metrics[
                                                         f'c_mc_open_{index}_Y']
                                             ), 1 / index))
        sector_metrics[f'MB_RATIO_{index}_Y'] = sector_metrics[f'c_mc_{index}_Y'] / sector_metrics[f'ee_{index}_Y']
        sector_metrics[f'EP_PCT_{index}_Y'] = sector_metrics[f'ep_{index}_Y'] / sector_metrics[f'ee_open_{index}_Y']
        sector_metrics[f'ROEE_{index}_Y'] = sector_metrics[f'pat_ex_{index}_Y'] / sector_metrics[f'ee_open_{index}_Y']
        sector_metrics[f'ROA_{index}_Y'] = sector_metrics[f'pat_ex_{index}_Y'] / sector_metrics[f'c_assets_{index}_Y']
        sector_metrics[f'PROFIT_MARGIN_{index}_Y'] = sector_metrics[f'pat_ex_{index}_Y'] / sector_metrics[
            f'revenue_{index}_Y']
        sector_metrics[f'OP_COST_MARGIN_{index}_Y'] = sector_metrics[f'op_cost_{index}_Y'] / sector_metrics[
            f'revenue_{index}_Y']
        sector_metrics[f'OP_COST_MARGIN_{index}_Y'] = sector_metrics[f'non_op_cost_{index}_Y'] / sector_metrics[
            f'revenue_{index}_Y']
        sector_metrics[f'EFF_TAX_RATE_{index}_Y'] = sector_metrics[f'tax_cost_{index}_Y'] / abs(
            sector_metrics[f'pat_{index}_Y'])
        sector_metrics[f'XO_COST_{index}_Y'] = sector_metrics[f'xo_cost_{index}_Y'] / sector_metrics[
            f'revenue_{index}_Y']
        sector_metrics[f'FA_INTENSITY_{index}_Y'] = sector_metrics[f'fixedassets_open_{index}_Y'] / sector_metrics[
            f'revenue_{index}_Y']
        sector_metrics[f'GW_INTENSITY_{index}_Y'] = sector_metrics[f'goodwill_open_{index}_Y'] / sector_metrics[
            f'revenue_{index}_Y']
        sector_metrics[f'OA_INTENSITY_{index}_Y'] = sector_metrics[f'oa_open_{index}_Y'] / sector_metrics[
            f'revenue_{index}_Y']
        sector_metrics[f'ASSET_INTENSITY_{index}_Y'] = sector_metrics[f'c_assets_open_{index}_Y'] / sector_metrics[
            f'revenue_{index}_Y']
        sector_metrics[f'ECON_EQ_MULT_{index}_Y'] = sector_metrics[f'c_assets_open_{index}_Y'] / sector_metrics[
            f'ee_open_{index}_Y']
        sector_metrics[f'REV_GROWTH_{index}_Y'] = sector_metrics[f'rev_delta_{index}_Y'] / sector_metrics[
            f'rev_delta_{index}_Y'].shift(1)
        sector_metrics[f'EE_GROWTH_{index}_Y'] = sector_metrics[f'ee_delta_{index}_Y'] / sector_metrics[
            f'ee_delta_{index}_Y'].shift(1)
        return sector_metrics
