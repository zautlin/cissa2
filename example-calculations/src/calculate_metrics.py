import timeit
# import os
import functools as ft
import math
import pandas as pd


PRIMARY_COLS_STMT = ['instrument', 'sector', 'CompanyName', 'CompanyId', 'Source',
                     'Year', 'Period', 'FiscalYearEnd', 'CurrencyId']
METRICS_COLS = ['ReportType', 'ROA', 'EM', 'PM', 'EPS', 'AI', 'OCM', 'NOCM', 'FAI', 'GI', 'ROE', 'EP']
EXTRA_COLS = ['ReportType', 'fiscal_year', 'N_PeriodEndingDate']
AVG_COLS = ['AvgTotalAssets', 'AvgTotalEquity', 'AvgNetPPE', 'AvgGoodWill',
            'AvgGoodwillAndOtherIntangibleAssets', 'AvgOrdinarySharesNumber']
BETA_COLS = ['CompanyId', 'year', 'SecID']

FILE_PATH = "./consl"


def main():
    started = timeit.default_timer()
    generate_metrics()
    get_cost_of_eq()
    print("The time difference is :", timeit.default_timer() - started)


def generate_metrics():
    financial_statements = pre_process()
    return calculate_metric(financial_statements)


def pre_process():
    bs_stmt = get_bs_stmt()
    inc_stmt = get_inc_stmt()
    cost_of_eq = get_cost_of_eq()

    merge_bs_inc = pd.merge(bs_stmt, inc_stmt, how="inner", on=PRIMARY_COLS_STMT + EXTRA_COLS)
    final = pd.merge(merge_bs_inc, cost_of_eq, how="inner", on=['CompanyId', 'Year'])

    print("***********************SUMMARY*********************************")
    print(f"Number of rows in bs_stmt---{len(bs_stmt)}")
    print(f"Number of rows in inc_stmt---{len(inc_stmt)}")
    print(f"Number of rows in merged---{len(merge_bs_inc)}")
    print(f"Number of rows in merged---{len(final)}")
    print("***********************END SUMMARY*****************************")
    return final


def get_bs_stmt():
    bs_stmt = load_bs_stmt()
    bs_stmt = generate_avg_n_lags(bs_stmt)
    return bs_stmt


def load_bs_stmt():
    bs_stmt = pd.read_csv(f"{FILE_PATH}\\bs_consolidated.csv")
    bs_stmt = filter_by_report_type(bs_stmt)

    return bs_stmt


def generate_avg_n_lags(bs_stmt):
    bs_stmt.drop("IsCalculated", axis=1, inplace=True)
    bs_stmt.sort_values(by=['CompanyId', 'AsOfDate'], inplace=True)
    bs_stmt['BS_TotalAssets_L'] = bs_stmt.groupby('CompanyId')['BS_TotalAssets'].shift()
    bs_stmt['BS_TotalEquity_L'] = bs_stmt.groupby('CompanyId')['BS_TotalEquity'].shift()
    bs_stmt['BS_NetPPE_L'] = bs_stmt.groupby('CompanyId')['BS_NetPPE'].shift()
    bs_stmt['BS_Goodwill_L'] = bs_stmt.groupby('CompanyId')['BS_Goodwill'].shift()
    bs_stmt['BS_OrdinarySharesNumber_L'] = bs_stmt.groupby('CompanyId')['BS_OrdinarySharesNumber'].shift()
    bs_stmt['BS_GoodwillAndOtherIntangibleAssets_L'] = bs_stmt.groupby('CompanyId')[
        'BS_GoodwillAndOtherIntangibleAssets'].shift()
    bs_stmt = bs_stmt[bs_stmt['Year'] > 2001]  # after shifting the first row will be empty
    bs_stmt = bs_stmt.assign(AvgTotalAssets=lambda row: (row['BS_TotalAssets_L'] + row['BS_TotalAssets']) / 2)
    bs_stmt = bs_stmt.assign(AvgTotalEquity=lambda row: (row['BS_TotalEquity_L'] + row['BS_TotalEquity']) / 2)
    bs_stmt = bs_stmt.assign(AvgNetPPE=lambda row: (row['BS_NetPPE_L'] + row['BS_NetPPE']) / 2)
    bs_stmt = bs_stmt.assign(AvgGoodWill=lambda row: (row['BS_Goodwill_L'] + row['BS_Goodwill']) / 2)
    bs_stmt = bs_stmt.assign(
        AvgGoodwillAndOtherIntangibleAssets=lambda row: (
                                            row['BS_GoodwillAndOtherIntangibleAssets_L'] +
                                            row['BS_GoodwillAndOtherIntangibleAssets']) / 2)
    bs_stmt = bs_stmt.assign(
        AvgOrdinarySharesNumber=lambda row: (row['BS_OrdinarySharesNumber_L'] + row['BS_OrdinarySharesNumber']) / 2)
    # bs_stmt.to_csv(f"{FILE_PATH}\\bs_shifted.csv")
    return bs_stmt[PRIMARY_COLS_STMT + EXTRA_COLS + AVG_COLS]


def get_inc_stmt():
    inc_stmt = pd.read_csv(f"{FILE_PATH}\\is_consolidated.csv")
    inc_stmt = filter_by_report_type(inc_stmt)
    return inc_stmt


def calculate_metric(financial_statements):
    financial_statements = financial_statements.assign(ROA=lambda row: (row['IS_NetIncome'] / row['AvgTotalAssets']))
    financial_statements = financial_statements.assign(ROE=lambda row: (row['IS_NetIncome'] / row['AvgTotalEquity']))
    financial_statements = financial_statements.assign(EM=lambda row: (row['AvgTotalAssets'] / row['AvgTotalEquity']))
    financial_statements = financial_statements.assign(PM=lambda row: ((row['IS_NetIncome']) / row['IS_TotalRevenue']))
    financial_statements: object = financial_statements.assign(EPS=lambda row:  (
            row['IS_NetIncomeCommonStockholders'] / row['AvgOrdinarySharesNumber']))
    financial_statements = financial_statements.assign(AI=lambda row: (row['AvgTotalAssets'] / row['IS_TotalRevenue']))
    financial_statements = financial_statements.assign(OCM=lambda row: (
                                                        row['IS_OperatingExpense'] / row['IS_TotalRevenue']))
    financial_statements = financial_statements.assign(NOCM=lambda row: (
            row['IS_OtherNonOperatingIncomeExpenses'] / row['IS_TotalRevenue']))
    financial_statements = financial_statements.assign(FAI=lambda row: (row['AvgNetPPE'] / row['IS_TotalRevenue']))
    financial_statements = financial_statements.assign(GI=lambda row: (row['AvgGoodWill'] / row['IS_TotalRevenue']))
    financial_statements = financial_statements.assign(EP=lambda row: (row['ROE'] - row['COE']))
    metrics = financial_statements[PRIMARY_COLS_STMT + METRICS_COLS]

    metrics.to_csv(f"{FILE_PATH}\\metrics.csv")
    return metrics


def filter_by_report_type(df):
    df['date'] = pd.to_datetime(df['AsOfDate']).dt.date
    df['Year'] = pd.to_datetime(df['AsOfDate']).dt.year
    df['order'] = df.apply(calculate_order, axis=1)
    df = df[df.groupby(PRIMARY_COLS_STMT).order.transform('max') == df['order']]
    return df


def calculate_order(row):
    x = row
    order = x['Year'] * 10 + 4 if x['ReportType'] == 'A' \
        else (x['Year'] * 10 + 3 if x['ReportType'] == 'P'
              else (x['Year'] * 10 + 2 if x['ReportType'] == 'R'
                    else (x['Year'] * 10 + 1 if x['ReportType'] == 'I' else x['Year'] * 10 + 0)))

    return order


def get_cost_of_eq():
    dfs = [calc_annual_asx_return(),
           calc_annual_rf_rate(),
           extract_annual_beta()]
    return calculate_cost_of_equity(dfs)


def calculate_cost_of_equity(dfs):
    df_final = ft.reduce(lambda left, right: pd.merge(left, right, on='Year', how="inner"), dfs)
    df_final = df_final.assign(RP=lambda row: row['mkt_retn'] - row['rf'])
    df_final = df_final.assign(COE=lambda row: row['rf'] + row['Beta'] * (row['RP']))
    df_final.reset_index(drop=True, inplace=True)

    df_final.to_csv(f"{FILE_PATH}\\COE.csv")
    return df_final


def calc_annual_asx_return():
    asx_return = pd.read_csv(f"{FILE_PATH}\\asx_return.csv")
    asx_return['index'] = asx_return['index'].str.replace(',', '').astype(float)
    asx_return.date = pd.to_numeric(asx_return.date, errors='coerce')
    asx_return.sort_values(by=['date'], inplace=True)
    asx_return['index_l'] = asx_return['index'].shift()
    asx_return['Year'] = asx_return.date.map(lambda x: int(x / 10000))
    asx_return['mkt_return'] = asx_return.apply(calc_return, axis=1)
    asx_return = asx_return.groupby('Year')['mkt_return'].agg("sum").to_frame()
    asx_return.reset_index(inplace=True)
    asx_return.to_csv(f"{FILE_PATH}\\asx_return_1.csv")
    print(asx_return.columns)
    return asx_return[['Year', 'mkt_return']]


def calc_return(row):
    x = pd.to_numeric(row['index'], errors='coerce')
    y = pd.to_numeric(row['index_l'], errors='coerce')
    return math.log(x / y)


def calc_annual_rf_rate():
    risk_free_rate = pd.read_csv(f"{FILE_PATH}\\risk_free_rates.csv")
    risk_free_rate['Year'] = pd.to_datetime(risk_free_rate['Date']).dt.year
    risk_free_rate = risk_free_rate.assign(rf=lambda row: row['Close'] / 100)
    risk_free_rate = risk_free_rate.groupby('Year')['rf'].agg("mean").to_frame()
    risk_free_rate.reset_index(inplace=True)
    risk_free_rate.to_csv(f"{FILE_PATH}\\risk_free_rate_1.csv")
    return risk_free_rate[['Year', 'rf']]


def extract_annual_beta():
    betas_all = pd.read_csv(f"{FILE_PATH}\\betas.csv")
    betas_all['date'] = pd.to_datetime(betas_all['asofdate']).dt.date
    betas_all['Year'] = pd.to_datetime(betas_all['asofdate']).dt.year
    betas_all = betas_all.reset_index(drop=True)

    betas_all['order'] = betas_all.Period.map(lambda x: 4 if x == '48M' else (
        3 if x == '36M' else (
            2 if x == '60M' else (
                1 if x == '120M' else 0))))

    betas_all = betas_all[betas_all.groupby(
        ['CompanyId', 'Year', 'SecID', 'Period']).date.transform('max') == betas_all['date']]

    betas_all = betas_all[betas_all.groupby(
        ['CompanyId', 'Year', 'SecID']).order.transform('max') == betas_all['order']]
    betas_all.to_csv(f"{FILE_PATH}\\betas_all.csv")

    return betas_all[['CompanyId', 'Year', 'SecID', 'Beta']]


if __name__ == '__main__':
    main()
