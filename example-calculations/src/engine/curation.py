# pylint: disable=cyclic-import
from datetime import datetime
import numpy as np
import pandas as pd
from src.config import parameters as param
from src.engine import xls
from src.executors import utility as util

logger = util.get_logger()


def pre_process_dataframe(workbook, worksheet, condition):
    df = pd.read_excel(workbook, worksheet, skiprows=condition).replace('\n', '')
    df.reset_index(drop=True, inplace=True)
    columns = list(df.columns.map(lambda x: str(x).replace('\r', '')
                                  .replace('\n', '')
                                  .lower()))
    df.columns = columns
    logger.info("pre_process_dataframe-  Successfully Created!!")

    return df


def process_base(workbook, worksheet):
    base = pd.read_excel(workbook, worksheet, skiprows=param.BEGIN_ROW).replace('\n', '')
    base.reset_index(drop=True, inplace=True)
    base.columns = base.columns.map(lambda x: x.replace('\r', '')
                                    .replace('\n', '')
                                    .replace(' ', '_')
                                    .lower())
    base.rename(columns=param.BASE_COLUMN_MAPPING, errors="raise", inplace=True)
    base = base[list(param.BASE_COLUMN_MAPPING.values())]
    base.fillna(np.nan, inplace=True)
    xls.load_worksheet_to_postgres(worksheet, base)
    logger.info("process_base-  Successfully Created!!")


def process_company_tsr(workbook, worksheet):
    tsr = pre_process_dataframe(workbook, worksheet,
                                lambda x: x < param.BEGIN_ROW or x > param.MONTHLY_END_ROW)
    tsr.rename(columns={"num": "id", "data fx": "fx_currency"}, inplace=True)
    tsr.fillna(np.nan, inplace=True)
    tsr = tsr[tsr['id'] != '']
    tsr['id'] = tsr['id'].astype('int')

    tsr = tsr.melt(
        id_vars=['id', 'ticker', 'name', 'fx_currency'],
        var_name='date',
        value_name='value'
    )
    tsr['key'] = "Company TSR"
    tsr['date'] = pd.to_datetime(tsr.date, format='mixed')  # %Y-%m-%dT%H:%M:%S.%f
    tsr['value'] = pd.to_numeric(tsr['value'], errors='coerce')
    tsr = tsr[param.MONTHLY_DATA_COLUMNS]
    xls.load_worksheet_to_postgres(worksheet, tsr)
    logger.info("process_company_tsr-  Successfully Created!!")


def process_index_tsr(workbook, worksheet):
    index = pre_process_dataframe(workbook, worksheet,
                                  lambda x: x < param.BEGIN_ROW or x > param.INDEX_END_ROW)
    index.rename(columns={"num": "id", "fx": "fx_currency"}, inplace=True)
    index.fillna('', inplace=True)
    index = index[index['id'] != '']
    index['id'] = index['id'].astype('int')
    index = index.melt(
        id_vars=['id', 'ticker', 'code', 'country', 'fx_currency', 'index name'],
        var_name='date',
        value_name='value'
    )
    index['key'] = "Index TSR"
    index['date'] = pd.to_datetime(index.date)
    index['value'] = pd.to_numeric(index['value'], errors='coerce')
    index = index[param.MONTHLY_DATA_COLUMNS]
    xls.load_worksheet_to_postgres(worksheet, index)
    logger.info("process_company_tsr-  Successfully Created!!")


def process_rf(workbook, worksheet):
    rf = pre_process_dataframe(workbook, worksheet, lambda x: x < param.BEGIN_ROW or x > param.INDEX_END_ROW)
    rf.rename(columns={"num": "id", "fx": "fx_currency"}, inplace=True)
    rf.fillna('', inplace=True)
    rf = rf[rf['id'] != '']
    rf['id'] = rf['id'].astype('int')
    rf = rf.melt(
        id_vars=['id', 'ticker', 'code', 'country', 'fx_currency', 'bond name'],
        var_name='date',
        value_name='value'
    )
    rf['key'] = "Rf"
    rf['date'] = pd.to_datetime(rf.date)
    rf['value'] = pd.to_numeric(rf['value'], errors='coerce')
    rf = rf[param.MONTHLY_DATA_COLUMNS]
    xls.load_worksheet_to_postgres(worksheet, rf)
    logger.info("process_rf-  Successfully Created!!")


def process_annual(workbook, worksheet, key):
    df = pre_process_dataframe(workbook, worksheet, lambda x: x < param.BEGIN_ROW or x > param.ANNUAL_END_ROW)
    print(df.columns)
    df.rename(columns={"num": "id", "data fx": "fx_currency"}, inplace=True)
    df.fillna('', inplace=True)
    df = df[df['id'] != '']
    df['id'] = df['id'].astype('int')
    df = df.melt(
        id_vars=['id', 'ticker', 'fx_currency', 'name'],
        var_name='FY_Year',
        value_name='value'
    )
    df['key'] = key
    df['FY_Year'] = df['FY_Year'].str.split(' ').str[1]
    df['FY_Year'] = df['FY_Year'].astype('int')
    if key == 'FY Dates':
        df['value'] = pd.to_datetime(df['value'], errors='coerce').dt.date
    else:
        df['value'] = pd.to_numeric(df['value'], errors='coerce')
    df = df[param.ANNUAL_DATA_COLUMNS]
    xls.load_worksheet_to_postgres(worksheet, df)
    logger.info("process_annual-  Successfully Created!!")


def process_user_defined_data(workbook, worksheet, key):
    df = pre_process_dataframe(workbook, worksheet, lambda x: x < param.BEGIN_ROW or x > param.ANNUAL_END_ROW)
    df.rename(columns={"num": "id"}, inplace=True)
    df.fillna('', inplace=True)
    df = df[df['id'] != '']
    df['id'] = df['id'].astype('int')
    df = df.melt(
        id_vars=['id', 'ticker', 'name'],
        var_name='FY_Year',
        value_name='value'
    )
    df['key'] = key
    df['FY_Year'] = df['FY_Year'].astype('int')
    df['value'] = pd.to_numeric(df['value'], errors='coerce')
    df['date'] = datetime.today().strftime('%Y-%m-%d')
    df = df[param.DATES_DATA_COLUMNS]
    xls.load_worksheet_to_postgres(worksheet, df)
    logger.info("process_user_defined_data-  Successfully Created!!")


def process_config(inputs):
    config = pd.DataFrame(inputs, index=[0])
    config.rename(columns={'identifier': 'guid', 'currency': 'fx_currency'}, inplace=True)
    config = config.melt(
        id_vars=['guid', 'userid', 'country', 'fx_currency'],
        var_name='key',
        value_name='value'
    )
    config['date'] = datetime.today().strftime('%Y-%m-%d')
    config = config[['guid', 'userid', 'country', 'fx_currency', 'date', 'key', 'value']]
    logger.info("load_config-  Successfully Created!!")
    return config


def process_metrics(metrics, identifier):
    metrics = metrics.melt(
        id_vars=['fy_year', 'ticker', 'fx_currency'],
        var_name='key',
        value_name='value'
    )
    metrics['guid'] = identifier
    metrics = metrics[['guid', 'ticker', 'fx_currency', 'fy_year', 'key', 'value']]
    logger.info("load_metrics-  Successfully Created!!")

    return metrics


def process_fy_tsr(workbook, worksheet):
    process_annual(workbook, worksheet, "FY TSR")


def process_spot_shares(workbook, worksheet):
    process_annual(workbook, worksheet, "Spot Shares")


def process_share_price(workbook, worksheet):
    process_annual(workbook, worksheet, "Share Price")


def process_mc(workbook, worksheet):
    process_annual(workbook, worksheet, "MC")


def process_pat(workbook, worksheet):
    process_annual(workbook, worksheet, "PAT")


def process_mi(workbook, worksheet):
    process_annual(workbook, worksheet, "MI")


def process_div(workbook, worksheet):
    process_annual(workbook, worksheet, "DIV")


def process_dist(workbook, worksheet):
    process_annual(workbook, worksheet, "DIST")


def process_inj(workbook, worksheet):
    process_annual(workbook, worksheet, "INJ")


def process_revenue(workbook, worksheet):
    process_annual(workbook, worksheet, "REVENUE")


def process_op_income(workbook, worksheet):
    process_annual(workbook, worksheet, "OP INCOME")


def process_pbt(workbook, worksheet):
    process_annual(workbook, worksheet, "PBT")


def process_pat_xo(workbook, worksheet):
    process_annual(workbook, worksheet, "PAT XO")


def process_total_assets(workbook, worksheet):
    process_annual(workbook, worksheet, "Total Assets")


def initialize(ws):
    return ws


def process_total_equity(workbook, worksheet):
    process_annual(workbook, worksheet, "Total Equity")


def process_cash(workbook, worksheet):
    process_annual(workbook, worksheet, "Cash")


def process_fa(workbook, worksheet):
    process_annual(workbook, worksheet, "FA")


def process_gw(workbook, worksheet):
    process_annual(workbook, worksheet, "GW")


def process_fy_dates(workbook, worksheet):
    process_annual(workbook, worksheet, "FY Dates")


def process_fy_period(workbook, worksheet):
    process_annual(workbook, worksheet, "FY Period")


def process_ph_equity_growth(workbook, worksheet):
    process_user_defined_data(workbook, worksheet, "PH Equity Growth")


def process_terminal_equity_growth(workbook, worksheet):
    process_user_defined_data(workbook, worksheet, "Terminal Equity Growth")


def process_franking_ratio(workbook, worksheet):
    process_user_defined_data(workbook, worksheet, "Franking Ratio")
