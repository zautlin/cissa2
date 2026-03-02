""" Project parameters controlling the aesthetics, libraries, etc. """

import os

# Environment detection for local vs. production
DEPLOYMENT_MODE = os.getenv("DEPLOYMENT_MODE", "local")

DB_SCHEMA = '"USR"'
GUID = "bedd09b0-5280-4ea9-a52f-03a109b5bd74"
# ROOT_DIR = os.path.dirname(os.path.abspath("../upload_data_to_db.py"))  # project root directory

# Database configuration based on deployment mode
if DEPLOYMENT_MODE == "local":
    SERVER = os.getenv("DB_HOST", "localhost")
    DB = os.getenv("DB_NAME", "cissa")
    USER = os.getenv("DB_USER", "postgres")
    PORT = os.getenv("DB_PORT", "5432")
else:  # production
    SERVER = os.getenv("DB_HOST", "cissa-dev-postgres.cr9zt2sgd9dw.ap-southeast-2.rds.amazonaws.com")
    DB = os.getenv("DB_NAME", "cissa")
    USER = os.getenv("DB_USER", "postgres")
    PORT = os.getenv("DB_PORT", "5432")

DOWNLOADED_WORK_BOOKS = ["Base",
                         "Company TSR",
                         "Index TSR",
                         "Rf",
                         "FY Dates",
                         "FY Period",
                         "FY TSR",
                         "Spot Shares",
                         "Share Price",
                         "MC", "PAT",
                         "Total Equity", "MI",
                         "Div",
                         "Revenue",
                         "Op Income",
                         "PBT",
                         "PAT XO",
                         "Total Assets",
                         "Cash",
                         "FA",
                         "GW"

                         ]
USR_DEFINED_WORK_BOOKS = [
    "PH Equity Growth",
    "Terminal Equity Growth",
    "Franking Ratio",
    "Controls"
]
DOWNLOAD_FILE_NAME = "Bloomberg Download data"
USR_DEFINED_FILE_NAME = "user_defined"
# CONNECTION_STRING = f"postgresql://{USER}:ChangeMe123!@{SERVER}:5432/{DB}"
# CONNECTION_STRING = f"postgresql://{USER}:{PASSWORD}@{SERVER}:{PORT}/{DB}"

BASE_COLUMN_MAPPING = {"num": "id",
                       "ticker": "ticker",
                       "name": "name",
                       "fy_report_month": "fy_report_month",
                       "data_fx": "fx_currency",
                       "begin_year": "begin_year",
                       "sector": "sector",
                       "bics_name": "bics_name",
                       "bics_1": "bics_1",
                       "bics_2": "bics_2",
                       "bics_3": "bics_3",
                       "bics_4": "bics_4"
                       }
MONTHLY_DATA_COLUMNS = ['id', 'ticker', 'date', 'fx_currency', 'key', "value"]
ANNUAL_DATA_COLUMNS = ['id', 'ticker', 'FY_Year', 'fx_currency', 'key', "value"]
USR_DEFINED_DATA_COLUMNS = ['id', 'ticker', 'FY_Year', 'key', "value"]
DATES_DATA_COLUMNS = ['id', 'date', 'ticker', 'FY_Year', 'key', "value"]
BEGIN_ROW = 15
MONTHLY_END_ROW = 516
ANNUAL_END_ROW = 516
INDEX_END_ROW = 48

GOAL_SEEK_COLS = ['EP_PERCENT', 'ROE', 'GROWTH_EQ', 'BK_VAL', 'PAT', 'EQ_FCF', 'PROP_FRK_DIV', 'DIV',
                  'NET_CAP_DISTR_IMPL',
                  'FRK_CR_DISTR', 'CHANGE_IN_EQ', 'VAL_CREATED', 'PV_Ke', 'ADJ_EQ_FCF', 'MKT_VAL', 'EP_DLR',
                  'Forecast_Year']
COL_ORDER = ["ticker", "id", "fx_currency", "fy_year", "forecast_year", "ep_percent", "roe", "growth_eq", "bk_val",
             "pat", "eq_fcf",
             "prop_frk_div", "div", "net_cap_distr_impl", "frk_cr_distr", "change_in_eq", "val_created",
             "pv_ke", "adj_eq_fcf", "mkt_val", "ep_dlr", "cost_of_eq", "prop_fr_dividend", "tax_rate", "val_fr_credit",
             "ph_eq_growth",
             "th_eq_growth", "conv_horizon", "bk_eq", "obs_mkt_val", "ph_ep"]

METRICS_COL = ['ter',
               'ter_ke',
               'ter_alpha',
               'market_to_book',
               'economic_profitability',
               'roe',
               'roa',
               'eq_multiplier',
               'profit_margin',
               'operating_xcost_margin',
               'non_operating_cost_margin',
               'effective_taxrate',
               'asset_intensity',
               'fixed_asset_intensity',
               'goodwill_intensity',
               'other_asset_intensity',
               'revenue_growth',
               'equity_growth']

COL_ROLLING_PROD = ['fytsr']
COL_ROLLING_SHIFTS = ['ke', 'rf', 'c_mc', 'ke_open']
COL_ROLLING_MEANS = [
    'revenue',
    'op_cost',
    'non_op_cost',
    'tax_cost',
    'xo_cost_ex',
    'pat_ex',
    'fixedassets_open',
    'goodwill_open',
    'c_assets_open',
    'ee_open',
    'ep',
    'fixedassets',
    'goodwill',
    'oa',
    'oa_open',
    'c_assets',
    'ee',
    'c_mc_open',
    'xo_cost',
    'pat',
    'ecf',
    'fc'
]
FV_ECF_COLUMNS = ['ticker',
                  'fy_year',
                  'FV_ECF_1_Y',
                  'FV_ECF_3_Y', 'FV_ECF_5_Y', 'FV_ECF_10_Y'

                  ]
ALL_COLUMNS = COL_ROLLING_SHIFTS + COL_ROLLING_MEANS
FV_ECF_COLUMNS = ['ticker', 'fy_year', '1Y_FV_ECF', '3Y_FV_ECF', '5Y_FV_ECF', '10Y_FV_ECF']

ID_COLUMNS = ['ticker', 'fx_currency', 'key']
