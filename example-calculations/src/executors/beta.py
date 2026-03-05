import threading

import pandas as pd
import numpy as np
from statsmodels.regression.rolling import RollingOLS

from src.engine import sql as si


def run_regressions(df):
    x = df['re']
    y = df['rm']
    window = 60 if len(x) > 60 else len(x)
    model = RollingOLS(y, x, window=window)
    result = model.fit()
    params = pd.DataFrame(result.params).rename(columns={'re': 'slope'})
    bse = pd.DataFrame(result.bse).rename(columns={'re': 'std_err'})
    df = pd.merge(params, bse, on=['date', 'ticker'], how="inner")
    return df


def rolling_ols_threaded(group, results):
    thread = threading.Thread(target=lambda: results.append(run_regressions(group)))
    thread.start()
    thread.join()


def calculate_slope(df, error_tolerance, beta_rounding):
    df = df.set_index(['date', 'ticker'])
    results = []
    for _, group in df.groupby('ticker'):
        rolling_ols_threaded(group, results)
    result = pd.concat(results)
    result['rel_std_err'] = abs(result['std_err']) / ((abs(result['slope']) * 2 / 3) + 1 / 3)
    result['slope_wo_rounding'] = round((result['slope'] * 2 / 3) + 1 / 3, 4)
    result['adjusted_slope'] = result.apply(
        lambda x: round((((x['slope'] * 2 / 3) + 1 / 3) / beta_rounding), 4) * beta_rounding
        if error_tolerance >= x['rel_std_err'] else np.nan, axis=1)

    result = result.reset_index()
    return result


def generate_annual_slope(beta_df):
    fy_dates = si.get_fy_dates()
    columns = ['yr_mth', 'year', 'ticker', 'sector', 'slope', 'adjusted_slope', 'std_err', 'rel_std_err']
    beta_df['yr_mth'] = pd.to_datetime(beta_df['date']).dt.strftime('%m%Y')
    beta_df['year'] = pd.to_datetime(beta_df['date']).dt.strftime('%Y')
    beta_df.drop_duplicates(inplace=True, ignore_index=True)
    fy_dates['yr_mth'] = pd.to_datetime(fy_dates['date']).dt.strftime('%m%Y')
    annual_beta = pd.merge(fy_dates, beta_df, how="inner", on=['yr_mth', 'ticker'])[columns]
    return annual_beta


def generate_sector_slope(annual_beta):
    beta_by_sector = (annual_beta
                      .groupby(['sector', 'year'])
                      .agg(sector_slope=('adjusted_slope', lambda x: x.mean(skipna=True))))
    return beta_by_sector


def generate_spot_slope(sector_beta, annual_beta):
    spot_betas = pd.merge(annual_beta, sector_beta, on=['year', 'sector'], how='inner')
    spot_betas['spot_slope'] = spot_betas['adjusted_slope'].fillna(spot_betas['sector_slope'])
    return spot_betas


def generate_avg_slope_by_ticker(spot_beta):
    beta_by_ticker = (spot_beta
                      .groupby(['ticker'])
                      .agg(avg_spot_slope_by_ticker=('spot_slope',
                                                     lambda x: x.mean(skipna=False))))
    return beta_by_ticker


def generate_beta(spot_slope, avg_spot_slope_by_ticker, inputs):
    spot_betas = pd.merge(spot_slope, avg_spot_slope_by_ticker, on=['ticker'], how='inner')
    spot_betas['beta'] = spot_betas.apply(
        lambda x: calculate_beta(x, inputs['approach_to_ke'], inputs['beta_rounding']), axis=1)
    spot_betas['fy_year'] = spot_betas['year']
    return spot_betas


def calculate_beta(x, approach_to_ke, beta_rounding):
    if approach_to_ke == 'FIXED':
        value = np.round(x['avg_spot_slope_by_ticker'] / beta_rounding, 4) * beta_rounding
    else:
        value = np.round(x['spot_slope'] / beta_rounding, 4) * beta_rounding
    return value


def calculate_beta_async(monthly_dataset, inputs):
    annual_slope = (monthly_dataset
                    .pipe(calculate_slope, inputs["error_tolerance"], inputs["beta_rounding"])
                    .pipe(generate_annual_slope))
    spot_slope = (annual_slope.pipe(generate_sector_slope)
                  .pipe(generate_spot_slope, annual_slope))
    avg_spot_slope_by_ticker = spot_slope.pipe(generate_avg_slope_by_ticker)
    betas = generate_beta(spot_slope, avg_spot_slope_by_ticker, inputs).round(
        {"slope": 4, "adjusted_slope": 4, "std_err": 4, "rel_std_err": 4, "sector_slope": 4, "beta": 4,
         "avg_spot_slope_by_ticker": 4})
    betas = betas[['fy_year', 'ticker', 'sector_slope', 'beta']]
    betas['fx_currency'] = inputs['currency']
    return betas
