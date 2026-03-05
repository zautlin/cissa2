import numpy as np
from src.executors import utility as util
from src.config import parameters as param
from src.engine import formatters as fmt

logger = util.get_logger()


def thread_calculate_mean(metrics, interval):
    window = interval
    columns = param.COL_ROLLING_MEANS

    metrics = metrics[['ticker', 'fy_year'] + columns]
    groups = metrics.groupby('ticker', as_index=False)
    kwargs = {
        f'{col}_{window}_Y': groups[col].rolling(window, min_periods=interval).mean().reset_index(drop=True)[col]
        for col in columns
    }
    metrics = metrics.assign(**kwargs)
    return metrics


def thread_shift(metrics, interval):
    columns = param.COL_ROLLING_SHIFTS
    metrics = metrics[['ticker', 'fy_year'] + columns]
    groups = metrics.groupby('ticker')
    lags = interval
    kwargs = {
        f'{col}_{lags}_Y': groups[col].shift(lags)
        for col in columns
    }
    metrics = metrics.assign(**kwargs)
    return metrics


def thread_prod(metrics, interval):
    columns = param.COL_ROLLING_PROD
    metrics = metrics[['ticker', 'fy_year'] + columns]
    groups = metrics.groupby('ticker')
    lags = interval
    kwargs = {
        f'{col}_{lags}_Y': groups[col].rolling(window=interval).apply(
            lambda x: np.power(x.prod(), 1 / interval) - 1, raw=True).reset_index(drop=True)
        for col in columns
    }
    metrics = metrics.assign(**kwargs)
    return metrics


def aggregate_metrics(all_metrics, interval):
    metrics = all_metrics.copy(deep=True)
    fv_ecf = all_metrics[param.FV_ECF_COLUMNS]
    shift = thread_shift(metrics, interval)
    mean = thread_calculate_mean(metrics, interval)
    prod = thread_prod(metrics, interval)
    aggregated_metrics = fmt.merge_metrics([fv_ecf, mean, shift, prod],
                                           on=['ticker', 'fy_year'])
    logger.info("calculate-  Successfully Created!!")
    return aggregated_metrics


def shift_columns(metrics, interval):
    lags = interval
    columns = param.ALL_COLUMNS
    groups = metrics.groupby('ticker')
    metrics = metrics.assign(**{
        f'{col}_{lags}_Y': groups[col].shift(lags)  # fixing issue xls not consistent by adding lags-1
        for col in columns
    })
    return metrics


def calculate_aggregated_metrics(metrics, inputs, interval):
    metrics = aggregate_metrics(metrics, interval)
    metrics = initialize_temp_columns(interval, metrics)
    metrics = calculate_intermediary_metrics(interval, metrics, inputs)
    ratios = calculate_ratios(interval, metrics)
    ratios = ratios.filter(regex='1|3|5|10|ticker|fy_year')
    include_list = [col for col in ratios.columns if 'FV_ECF' not in col]
    ratios = ratios[include_list]
    return ratios


def calculate_intermediary_metrics(interval, int_metrics, inputs):
    risk_premium = inputs['risk_premium']

    int_metrics[f"TER_{interval}_Y"] = np.power(
        1 + int_metrics[f"TRTE_{interval}_Y"] / int_metrics[f"c_mc_open_{interval}_Y"], 1 / interval) - 1
    int_metrics[f"TER_KE_{interval}_Y"] = int_metrics[f"TER_{interval}_Y"] - int_metrics[
        f'ke_{interval}_Y']
    int_metrics[f"rm_{interval}_Y"] = np.power(
        1 + int_metrics[f"rm_{interval}_Y_S1"] / int_metrics[f"rm_{interval}_Y_S2"], 1 / interval) - 1
    int_metrics[f"RA_MM_{interval}_Y"] = (
            (int_metrics[f"rm_{interval}_Y"] - (int_metrics[f"rf_{interval}_Y"] + risk_premium))
            * (int_metrics[f'ke_{interval}_Y'] - int_metrics[f"rf_{interval}_Y"]) / risk_premium)
    int_metrics[f"WP_{interval}_Y"] = int_metrics[f"c_mc_open_{interval}_Y"] * np.power(
        1 + int_metrics[f'ke_{interval}_Y'], interval)
    int_metrics[f"WC_TERA_{interval}_Y"] = int_metrics[f"c_mc_open_{interval}_Y"] * np.power(
        1 + int_metrics[f"TER_{interval}_Y"], interval) - int_metrics[
                                               f"c_mc_open_{interval}_Y"] * np.power(
        1 + int_metrics[f'ke_{interval}_Y'] + int_metrics[f'RA_MM_{interval}_Y'], interval)
    int_metrics[f"WC_{interval}_Y"] = int_metrics[f"c_mc_open_{interval}_Y"] * np.power(
        1 + int_metrics[f"TER_{interval}_Y"], interval) - int_metrics[
                                          f"c_mc_open_{interval}_Y"] * np.power(
        1 + int_metrics[f'ke_{interval}_Y'], interval)
    int_metrics[f"TERA_{interval}_Y"] = int_metrics[f"TER_KE_{interval}_Y"] - int_metrics[
        f"RA_MM_{interval}_Y"]
    int_metrics[f'x_revenue_{interval}_Y'] = (int_metrics[f'revenue_{interval}_Y'] *
                                              (int_metrics[f'revenue_{interval}_Y'] -
                                               int_metrics.groupby('ticker')[f'revenue_{interval}_Y'].shift(
                                                   1)) / abs(int_metrics[f'revenue_{interval}_Y']))
    int_metrics[f'x_ee_{interval}_Y'] = int_metrics[f'ee_{interval}_Y'] * (
            int_metrics[f'ee_{interval}_Y'] - int_metrics.groupby('ticker')[f'ee_{interval}_Y'].shift(1)
    ) / abs(int_metrics[f'ee_{interval}_Y'])
    int_metrics[f'x_open_beta_{interval}_Y'] = np.power(
        (int_metrics[f"WP_{interval}_Y"] / int_metrics[
            f"c_mc_open_{interval}_Y"]), (1 / interval)) - 1 - int_metrics[f"rf_{interval}_Y"]
    int_metrics[f'rev_delta_{interval}_Y'] = (int_metrics[f'revenue_{interval}_Y'] *
                                              (int_metrics[f'revenue_{interval}_Y']
                                               - int_metrics[f'revenue_{interval}_Y'].shift(
                                                          1))
                                              / abs(int_metrics[f'revenue_{interval}_Y']))
    int_metrics[f'ee_delta_{interval}_Y'] = (int_metrics[f'ee_{interval}_Y'] *
                                             (int_metrics[f'ee_{interval}_Y'] - int_metrics[f'ee_{interval}_Y'].shift(
                                                 1))
                                             / abs(int_metrics[f'ee_{interval}_Y']))

    int_metrics[f'rev_growth_{interval}_Y'] = int_metrics[f'rev_delta_{interval}_Y'] / int_metrics[
        f'rev_delta_{interval}_Y'].shift(1)
    int_metrics[f'rev_growth_{interval}_Y'] = int_metrics[f'ee_delta_{interval}_Y'] / int_metrics[
        f'ee_delta_{interval}_Y'].shift(1)

    return int_metrics


def initialize_temp_columns(interval, metrics):
    metrics[f"TRTE_{interval}_Y"] = metrics[f"{interval}Y_FV_ECF"] + (
            metrics['c_mc'] - metrics[f"c_mc_{interval}_Y"])
    metrics[f"rm_{interval}_Y_S1"] = metrics['fy_year'].map(
        metrics.groupby('fy_year')[f"TRTE_{interval}_Y"].sum())
    metrics[f"rm_{interval}_Y_S2"] = metrics['fy_year'].map(
        metrics.groupby('fy_year')[f"c_mc_open_{interval}_Y"].sum())
    return metrics


# ke_{interval}_Y in xls is ke_open_{interval}_Y
# c_mc_{interval}_Y in xls is c_mc_open_{interval}_Y

def calculate_ratios(interval, metrics):
    metrics[f'mb_ratio_{interval}_Y'] = (metrics[f"c_mc_{interval}_Y"] / metrics[
        f"ee_{interval}_Y"])
    metrics[f'ep_pct_{interval}_Y'] = (metrics[f"ep_{interval}_Y"] / metrics[
        f"ee_open_{interval}_Y"])
    metrics[f'roee_{interval}_Y'] = (metrics[f"pat_ex_{interval}_Y"] / metrics[
        f"ee_open_{interval}_Y"])
    metrics[f'roa_{interval}_Y'] = (metrics[f"pat_ex_{interval}_Y"] / metrics[
        f"c_assets_{interval}_Y"])
    metrics[f'profit_margin_{interval}_Y'] = (
            metrics[f"pat_ex_{interval}_Y"] / metrics[f"revenue_{interval}_Y"])
    metrics[f'op_cost_margin_{interval}_Y'] = (
            metrics[f"op_cost_{interval}_Y"] / metrics[f"revenue_{interval}_Y"])
    metrics[f'non_op_cost_margin_{interval}_Y'] = (
            metrics[f"op_cost_{interval}_Y"] / metrics[f"non_op_cost_{interval}_Y"])
    metrics[f'ef_tax_rate_{interval}_Y'] = metrics[f"tax_cost_{interval}_Y"] / (
        abs(metrics[
                f"pat_{interval}_Y"] + metrics[f"xo_cost_{interval}_Y"]))
    metrics[f'xo_cost_margin_{interval}_Y'] = (
            metrics[f"xo_cost_{interval}_Y"] / metrics[f"revenue_{interval}_Y"])
    metrics[f'fa_intensity_{interval}_Y'] = (
            metrics[f"xo_cost_{interval}_Y"] / metrics[f"fixedassets_open_{interval}_Y"])
    metrics[f'gw_intensity_{interval}_Y'] = (
            metrics[f"goodwill_open_{interval}_Y"] / metrics[f"revenue_{interval}_Y"])
    metrics[f'oa_intensity_{interval}_Y'] = (
            metrics[f"oa_open_{interval}_Y"] / metrics[f"revenue_{interval}_Y"])
    metrics[f'assets_intensity_{interval}_Y'] = (
            metrics[f"c_assets_open_{interval}_Y"] / metrics[f"revenue_{interval}_Y"])
    metrics[f'econ_eq_mult_{interval}_Y'] = (
            metrics[f"c_assets_open_{interval}_Y"] / abs(metrics[f"ee_open_{interval}_Y"]))
    metrics[f'revenue_growth_{interval}_Y'] = metrics[f'x_revenue_{interval}_Y'] / metrics.groupby('ticker')[
        f'revenue_{interval}_Y'].shift(1)
    metrics[f'ee_growth_{interval}_Y'] = metrics[f'x_ee_{interval}_Y'] / metrics.groupby('ticker')[
        f'ee_{interval}_Y'].shift(1)
    return metrics
