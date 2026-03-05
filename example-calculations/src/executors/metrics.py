from concurrent.futures import ThreadPoolExecutor
import numpy as np
import pandas as pd
from src.executors import utility as util

logger = util.get_logger()


def generate_l1_metrics_async(df, inputs):
    groups = df.groupby('ticker')
    # Create ThreadPoolExecutor with 4 threads
    with ThreadPoolExecutor(max_workers=4) as executor:
        # Submit each group to the executor
        pools = [executor.submit(
            generate_l1_metrics, group, inputs)
            for name, group in groups]

        # Wait for all threads to complete and get results
        results = pd.concat([pool.result() for pool in pools])
        results = pd.DataFrame(results)[
            ['fy_year', 'ticker', 'fx_currency', 'C_MC', 'C_ASSETS',
             'OA', 'OP_COST', 'NON_OP_COST', 'TAX_COST', 'XO_COST',
             'ECF', 'NON_DIV_ECF', 'EE', 'FY_TSR', 'FY_TSR_PREL']]
        logger.info("Calculate Metrics Async: Successfully Created!!")
        return results


def generate_l1_metrics(group, inputs):
    group = group.assign(C_MC=lambda data: (data['shrouts'] * data['price']))
    group['LAG_MC'] = group.groupby('ticker')['C_MC'].shift(1)
    group = (group.assign(C_ASSETS=lambda data: (data['assets'] - data['cash']))
             .assign(OA=lambda data: (data['C_ASSETS'] - data['fixedassets'] - data['goodwill'])))
    group = group.assign(OP_COST=lambda data: (data['revenue'] - data['opincome']))
    group = group.assign(NON_OP_COST=lambda data: (data['opincome'] - data['pbt']))
    group = group.assign(TAX_COST=lambda data: (data['pbt'] - data['patxo']))
    group = group.assign(XO_COST=lambda data: (data['patxo'] - data['pat']))
    group['INCEPTION_IND'] = group.apply(is_inception_year, axis=1)
    group['ECF'] = group.apply(calculate_economic_cash_flow, axis=1)
    group = group.assign(NON_DIV_ECF=lambda data: (data['ECF'] + data['dividend']))
    group['EE'] = group.apply(calculate_economic_equity, axis=1).cumsum()
    group['FY_TSR'] = group.apply(lambda data: calculate_fy_tsr(data, inputs), axis=1)
    group['FY_TSR_PREL'] = group.apply(calculate_fy_tsr_prel, axis=1)
    logger.info("Generate Metrics From Historical Data: Successfully Created!!")
    return group


def calculate_fy_tsr(row, inputs):
    incl_franking = inputs['incl_franking']
    frank_tax_rate = inputs['frank_tax_rate']
    value_franking_cr = inputs['value_franking_cr']
    fy_tsr = np.nan
    lag_mc = row['LAG_MC']
    if lag_mc > 0:
        if row["INCEPTION_IND"] == 1:
            if incl_franking == "Yes":
                div = row['dividend'] / (1 - frank_tax_rate)
                change_in_cap = row['C_MC'] - row['LAG_MC'] + row['ECF'] - div
                adjusted_change = change_in_cap * frank_tax_rate * value_franking_cr
                fy_tsr = adjusted_change / lag_mc
            else:
                change_in_cap = row['C_MC'] - row['LAG_MC'] + row['ECF']
                fy_tsr = change_in_cap / lag_mc
    return fy_tsr


def calculate_fy_tsr_prel(row):
    fy_tsr_prel = np.nan
    if row["INCEPTION_IND"] == 1:
        fy_tsr_prel = row['FY_TSR'] + 1
    return fy_tsr_prel


def is_inception_year(row):
    inception = 0
    if row["inception"] < row["fy_year"]:
        inception = 1
    elif row["fy_year"] == row["inception"]:
        inception = 0
    else:
        inception = -1
    return inception


def calculate_economic_cash_flow(row):
    ecf = np.nan
    if row["INCEPTION_IND"] == 1:
        ecf = row['LAG_MC'] * (1 + row["fytsr"] / 100) - row['C_MC']
    return ecf


def calculate_economic_equity(row):
    ee = np.nan
    if row["INCEPTION_IND"] == 0:
        ee = row['eqiity'] - row['mi']
    elif row["INCEPTION_IND"] == 1:
        ee = row['pat'] - row['ECF']
    return ee


def generate_l2_metrics_async(general_metrics, inputs):
    groups = general_metrics.groupby('ticker')
    # Create ThreadPoolExecutor with 4 threads
    with ThreadPoolExecutor(max_workers=4) as executor:
        # Submit each group to the executor
        pools = [executor.submit(
            generate_l2_metrics, group, inputs)
            for name, group in groups]

        # Wait for all threads to complete and get results
        results = pd.concat([pool.result() for pool in pools])
        results = pd.DataFrame(results)
        logger.info("Calculate Metrics Async: Successfully Created!!")
        return results


def generate_l2_metrics(general_metrics, inputs):
    # Need to Add calc_fy_tsr
    incl_franking = inputs['incl_franking']
    frank_tax_rate = inputs['frank_tax_rate']
    value_franking_cr = inputs['value_franking_cr']
    # risk_premium = inputs['risk_premium']
    general_metrics['franking'] = inputs['franking']
    general_metrics = (((general_metrics.assign(ep=lambda data: (data['pat'] - data['ke_open'] * data['ee_open']))
                         .assign(pat_ex=lambda data: (data['ep'] / (abs(data['ee_open'] +
                                                                        data['ke_open'])) * data['ee_open'])))
                        .assign(xo_cost_ex=lambda data: (data['patxo'] - data['pat_ex'])))
                       .assign(fc=lambda data: calculate_fc(data, incl_franking, frank_tax_rate,
                                                            value_franking_cr)))

    return general_metrics


def calculate_pat_ex(row):
    ep = row['ep']
    ee_open = row['ee_open']
    ke_open = row["ke_open"]
    return (ep / abs(ee_open) + ke_open) * abs(ee_open)


def calculate_fc(row, incl_franking, frank_tax_rate, value_franking_cr):
    if incl_franking == "Yes":
        return (-1 * row['dividend'] / (1 - frank_tax_rate)) * frank_tax_rate * value_franking_cr * row['franking']
    return 0


def generate_lags(metrics, cols):
    for col in cols:
        for i in range(11):
            lag = i
            metrics[f"{col}_{lag}"] = metrics.groupby('ticker')[col].shift(lag * 1)
    return metrics


def generate_growth_rate(initial_growth_rate, terminal_growth_rate, convergence_horizon):
    # Initialize the growth rate list with the initial growth rate for the first 10 years
    growth_rate = np.zeros(convergence_horizon + 2)
    growth_rate[1:11] = initial_growth_rate
    growth_rate[0] = np.nan

    # Calculate the growth rate for the next 50 years
    for t in range(11, len(growth_rate)):

        # Calculate the new growth rate
        if t < convergence_horizon:
            growth_rate[t] = growth_rate[t - 1] - (terminal_growth_rate / (convergence_horizon - 10))
        # Append the new growth rate to the list
        else:
            growth_rate[t] = terminal_growth_rate
    return growth_rate


def generate_economic_profitability(initial_ep, convergence_horizon):
    # Initialize an array for the results
    economic_profitability_t = np.zeros(convergence_horizon + 2)
    economic_profitability_t[1:11] = initial_ep
    economic_profitability_t[0] = np.nan

    # Calculate Economic Profitability for each time step
    for t in range(11, convergence_horizon + 2):
        if t < convergence_horizon:
            economic_profitability_t[t] = economic_profitability_t[t - 1] - (initial_ep / (convergence_horizon - 10))

        else:
            economic_profitability_t[t] = 0
    return economic_profitability_t


def generate_return_on_equity(ep, ke):
    return [a + ke for a in ep]


def generate_book_value_equity(initial_book_equity, growth_in_equity, convergence_horizon):
    # Initialize bv series with the same length as input lists
    bv_series = np.zeros(convergence_horizon + 2)
    # Calculate bv for each year
    for i in range(convergence_horizon + 2):
        if i == 0:
            bv_series[i] = initial_book_equity
        else:
            bv_series[i] = abs(bv_series[i - 1]) * growth_in_equity[i] + bv_series[i - 1]
    return bv_series


def generate_profit_after_tax(economic_profitability, book_equity, cost_of_equity, convergence_horizon):
    # Initialize Profit After Tax series with the same length as input lists
    profit_after_tax_series = np.zeros(convergence_horizon + 2)
    # Calculate Profit After Tax for each year
    for i in range(convergence_horizon + 2):
        if i > 0:
            profit_after_tax_series[i] = abs(book_equity[i - 1]) * economic_profitability[i] + book_equity[
                i - 1] * cost_of_equity
        else:
            profit_after_tax_series[i] = np.nan

    return profit_after_tax_series


def generate_equity_free_cash_flow(profit_after_tax, book_equity, convergence_horizon):
    # Initialize Equity Free Cash Flow series with the same length as input lists
    equity_free_cash_flow_series = np.zeros(convergence_horizon + 2)
    # Calculate Equity Free Cash Flow for each year
    for i in range(convergence_horizon + 2):
        if i > 0:
            equity_free_cash_flow_series[i] = profit_after_tax[i] - (book_equity[i] - book_equity[i - 1])
        else:
            equity_free_cash_flow_series[i] = np.nan
    return equity_free_cash_flow_series


def generate_proportion_of_frk_dividend(franked_dividend, convergence_horizon):
    frk_dividend_series = np.zeros(convergence_horizon + 2)
    frk_dividend_series = frk_dividend_series + franked_dividend
    frk_dividend_series[0] = np.nan
    return frk_dividend_series


def generate_dividend(equity_free_cash_flow):
    dividend = np.where(equity_free_cash_flow > 0, equity_free_cash_flow, 0)
    dividend[0] = np.nan
    return dividend


def generate_implied_net_capital_distribution(equity_free_cash_flow, dividend):
    return [a - b for a, b in
            zip(equity_free_cash_flow, dividend)]


def generate_franking_credits(dividends, tax_rate, proportion_franked, value_of_fr_credits):
    return [(dividend / (1 - tax_rate)) * tax_rate * prop_franked * value_of_fr_credits
            for dividend, prop_franked in zip(dividends, proportion_franked)]


def generate_pvf(convergence_horizon, ke):
    pvf = np.zeros(convergence_horizon + 2)
    for i in range(convergence_horizon + 2):
        if i > 0:
            pvf[i] = 1 / np.power(1 + ke, i)
        else:
            pvf[i] = np.nan
    return pvf


def generate_terminal_value(frk_credits_distributed, terminal_growth_rate, ke):
    last_item = frk_credits_distributed[-1]
    value = (last_item * (1 + terminal_growth_rate)) / (ke - terminal_growth_rate)
    return value


def generate_market_value_equity(terminal_value, book_values, fcf, ke, convergence_horizon):
    # Set the last value of MVE array
    mve = [0] * (convergence_horizon + 2)
    mve[-1] = terminal_value + book_values[-1]
    # Calculate prior year values
    for y in range(len(mve) - 2, -1, -1):
        mve[y] = (fcf[y + 1] + mve[y + 1]) / (1 + ke)
    return mve


def generate_change_in_equity(book_value):
    return [np.nan if i == 0 else book_value[i - 1] - book_value[i] for i in range(len(book_value))]


def generate_equity_free_cash_flow_fc(profit_after_tax, value_of_franking_credits_distributed, change_in_equity):
    return [a + b + c for a, b, c in
            zip(profit_after_tax, value_of_franking_credits_distributed, change_in_equity)]


def generate_discount_adjusted_eq_fcf(equity_free_cash_flow, pvf):
    return [a * b for a, b in zip(equity_free_cash_flow, pvf)]


def calculate_value_created(book_value, mkt_value):
    return [b - a for a, b in zip(mkt_value, book_value)]


def calculate_economic_profit(profit_after_tax, book_value_of_equity, cost_of_equity):
    # Shift the book_value_of_equity array to represent the previous year's values
    previous_year_equity = [0] + book_value_of_equity[:-1]
    economic_profit = [pat - bve * cost_of_equity for pat, bve in zip(profit_after_tax, previous_year_equity)]
    return economic_profit


def get_goal_seek_parameters(inputs):
    return util.get_goal_seek_parameters(inputs)
