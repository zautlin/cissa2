from concurrent.futures import ThreadPoolExecutor
import numpy as np
import pandas as pd
from src.executors import utility as util

logger = util.get_logger()


def get_return_rates(risk_free_rates, tsr):
    tsr['yr_mth'] = pd.to_datetime(tsr['date']).dt.strftime('%m%Y')
    risk_free_rates['yr_mth'] = pd.to_datetime(risk_free_rates['date']).dt.strftime('%m%Y')
    rates = pd.merge(tsr, risk_free_rates[['yr_mth', 'rf']], how="inner", on=['yr_mth'])
    rates = rates[['ticker', 'yr_mth', 'rf', 'rm', 're']]
    rates['re_rf'] = rates['re'] - rates['rf']
    logger.info("get_return_rates: Successfully Created!!")
    return rates


def calculate_annual_rf(monthly_rates, inputs):
    monthly_rates['rf_1y_raw'] = np.power(monthly_rates['rf_prel'].rolling(12).apply(lambda x: x.prod()), 1 / 12) - 1
    monthly_rates['rf_1y'] = np.round(np.round((monthly_rates['rf_1y_raw'] / inputs["beta_rounding"]), 0) * inputs[
        "beta_rounding"], 4)  # rf_1y
    monthly_rates['rf'] = inputs["benchmark"] - inputs["risk_premium"] if inputs["approach_to_ke"] == 'FIXED' else \
        monthly_rates['rf_1y']
    logger.info("calculate_PREL: Successfully Created!!")
    return monthly_rates


def calculate_annual_rates(monthly_rates, fy_dates):
    fy_dates['yr_mth'] = pd.to_datetime(fy_dates['date']).dt.strftime('%m%Y')
    annual_rates = pd.merge(fy_dates[["ticker", "yr_mth", 'date']], monthly_rates, how="inner", on=['yr_mth', 'ticker'])
    annual_rates['fy_year'] = pd.to_datetime(fy_dates['date']).dt.strftime('%Y')
    annual_rates = annual_rates[['ticker', 'fy_year', 'rf', 'rm']]
    annual_rates = annual_rates[annual_rates['rf'].notnull()]
    logger.info("calculate_annual_rates: Successfully Created!!")
    return annual_rates


def generate_annual_rates(group, monthly_rf, fy_dates, inputs):
    tsr = group
    # print(monthly_rf)
    monthly_rates_pct = calculate_annual_rf(monthly_rf, inputs)
    # print(fy_dates)
    monthly_prel = get_return_rates(monthly_rates_pct, tsr)
    annual_rates = calculate_annual_rates(monthly_prel, fy_dates)
    logger.info("annual_rates: Successfully Created!!")
    return annual_rates


def calculate_ke_async_1(fy_dates, inputs, monthly_rates, monthly_rf):
    groups = monthly_rates.groupby('ticker')
    # Create ThreadPoolExecutor with 4 threads
    with ThreadPoolExecutor(max_workers=4) as executor:
        # Submit each group to the executor
        pools = [executor.submit(
            generate_annual_rates, group, monthly_rf, fy_dates, inputs)
            for name, group in groups]
        # Wait for all threads to complete and get results
        results = pd.concat([pool.result() for pool in pools])
        logger.info("calculate_ke_async: Successfully Created!!")
        return results


def calculate_rates_async(fy_dates, inputs, monthly_rates, monthly_rf):
    groups = monthly_rates.groupby('ticker')
    df = groups.apply(lambda x: generate_annual_rates(x, monthly_rf, fy_dates, inputs))
    # Create ThreadPoolExecutor with 4 threads
    return df
