# pylint: disable=too-many-arguments,too-many-locals,too-many-positional-arguments
import numpy as np
import pandas as pd
import xlwings as xw
from src.config.parameters import GOAL_SEEK_COLS
from src.executors import metrics as mt


def execute_goal_seek(inputs):
    params = mt.get_goal_seek_parameters(inputs)
    params = params[params.ticker.str.contains("1712")]
    identifier = inputs['guid']
    dfs = []
    wb = xw.Book('./data/return_model.xlsm')
    goal_seek = wb.macro('gs')
    sheet: object = wb.sheets[0]
    for _, row in params.iterrows():
        year = row['fy_year']
        if year < 2024:
            # YEAR OF INCEPTION TO CURRENT FINANCIAL YEAR
            inception_year = row['begin_year']
            inception_year = int(inception_year) if str.isnumeric(inception_year) else 2000
            year = 2000 if np.isnan(year) else int(year)
            if inception_year < 2024:
                ticker = row['ticker']
                fx_currency = 'A$m'
                ke = row['ke']
                franking_ratio = row['franking_ratio']
                bk_eq = row['book_equity']
                mkt_val = row['obs_mkt_val']
                ph_growth = row['p_eq_growth']
                th_growth = row['t_eq_growth']
                value_of_fr_credits = row["value_of_fr_credits"]
                if not np.isnan(mkt_val):
                    fill_xls(sheet, bk_eq, franking_ratio,
                             fx_currency, ke, mkt_val, ph_growth,
                             th_growth, year, value_of_fr_credits)
                    goal_seek()
                    df = sheet['A34:BL68'].options(pd.DataFrame, transpose=True).value
                    df = df[GOAL_SEEK_COLS].round(5)
                    df = fill_df(df, bk_eq, franking_ratio, fx_currency, ke, mkt_val, ph_growth, th_growth, year,
                                 ticker)
                    dfs.append(df)
    goal_seek_output = pd.concat(dfs)
    goal_seek_output['id'] = identifier
    goal_seek_output.to_csv("return_model_xls.csv")
    wb.close()


def fill_xls(sheet, bk_eq, franking_ratio, fx_currency, ke, mkt_val, ph_growth, th_growth, year, value_of_fr_credits):
    sheet['FY_YEAR'].value = year
    sheet['VAL_FR_CREDIT'].value = value_of_fr_credits
    # FX CURRENCY  USER INPUT
    sheet['FX_CURRENCY'].value = fx_currency
    # COST OF EQUITY FROM EP PERFORMANCE DATABASE
    sheet['COST_OF_EQ'].value = ke
    # PROPORTION OF FRANKING DIVIDEND/FRANKING RATIO  IS USER INPUT (EACH YEAR EACH TICKER)
    sheet['PROP_FR_DIVIDEND'].value = franking_ratio
    # TAX RATE IS USER INPUT
    sheet['TAX_RATE'].value = 0.30
    # VALUE OF FRANKING CREDIT IS USER INPUT
    sheet['VAL_FR_CREDIT'].value = 0.75
    # PLANNING HORIZON EQUITY GROWTH USER INPUT (EACH YEAR EACH TICKER)
    sheet['PH_EQ_GROWTH'].value = ph_growth
    # TERMINAL HORIZON EQUITY GROWTH USER INPUT (EACH YEAR EACH TICKER)
    sheet['TH_EQ_GROWTH'].value = th_growth
    # CONVERGENCE HORIZON USER INPUT (EACH YEAR EACH TICKER)
    sheet['CONV_HORIZON'].value = 50
    # ECONOMIC EQUITY (EE)) FROM EP PERFORMANCE DATABASE
    sheet['BK_EQ'].value = bk_eq
    # MARKET CAPITAL FROM EP PERFORMANCE DATABASE
    sheet['OBS_MKT_VAL'].value = mkt_val
    sheet['PH_EP'].value = 0.05


def fill_df(df, bk_eq, franking_ratio, fx_currency, ke, mkt_val, ph_growth, th_growth, year, ticker):
    df['FY_YEAR'] = year
    df['ticker'] = ticker
    # FX CURRENCY  USER INPUT
    df['FX_CURRENCY'] = fx_currency
    # COST OF EQUITY FROM EP PERFORMANCE DATABASE
    df['COST_OF_EQ'] = ke
    # PROPORTION OF FRANKING DIVIDEND/FRANKING RATIO  IS USER INPUT (EACH YEAR EACH TICKER)
    df['PROP_FR_DIVIDEND'] = franking_ratio
    # TAX RATE IS USER INPUT
    df['TAX_RATE'] = 0.30
    # VALUE OF FRANKING CREDIT IS USER INPUT
    df['VAL_FR_CREDIT'] = 0.75
    # PLANNING HORIZON EQUITY GROWTH USER INPUT (EACH YEAR EACH TICKER)
    df['PH_EQ_GROWTH'] = ph_growth
    # TERMINAL HORIZON EQUITY GROWTH USER INPUT (EACH YEAR EACH TICKER)
    df['TH_EQ_GROWTH'] = th_growth
    # CONVERGENCE HORIZON USER INPUT (EACH YEAR EACH TICKER)
    df['CONV_HORIZON'] = 50
    # ECONOMIC EQUITY (EE)) FROM EP PERFORMANCE DATABASE
    df['BK_EQ'] = bk_eq
    # MARKET CAPITAL FROM EP PERFORMANCE DATABASE
    df['OBS_MKT_VAL'] = mkt_val
    df['PH_EP'] = 0.05
    return df
