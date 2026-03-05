# pylint: disable=too-many-locals
import numpy as np
import pandas as pd
import scipy.optimize as opt
from tqdm import tqdm

from src.executors import utility as utl
from src.executors import metrics as mt
from src.engine import stateorganizer as st

current_state = st.State()


# Call function1 to modify the state
def scale(arr):
    return arr.item()


def optimize(func):
    initial_ep = -0.0004
    optimal_value = opt.basinhopping(func, initial_ep)
    # optimal_value = goal_seek(optimize_ep, goal, initial_ep)
    return optimal_value


def run_optimizer(inputs):
    current_state.set_current_inputs(inputs)
    params = mt.get_goal_seek_parameters(inputs)
    # params  = params[params.ticker.str.contains("BHP")]
    convergence_horizon = inputs['conv_horizon']
    dataframes = []
    for _, row in tqdm(params.iterrows(), total=params.shape[0]):
        # print(row)
        # print(i)
        # YEAR OF INCEPTION TO CURRENT FINANCIAL YEAR
        year = row['fy_year']
        year = 2000 if np.isnan(year) else int(year)
        if year < 2024:
            inception_year = row['begin_year']
            inception_year = int(inception_year) if str.isnumeric(inception_year) else 2000
            if inception_year < year:
                # parallelize
                current_state.set_current_parameters(row)
                mkt_val = row['obs_mkt_val']
                if not np.isnan(mkt_val):
                    optimize(optimize_ep)
                    # optimized_ep = goal_seek(optimize_ep, goal, initial_ep)
                    optimized_data = current_state.get_optimized_dict()
                    dataframes.append(process_arrays(optimized_data, convergence_horizon))
    optimized_values = pd.concat(dataframes)
    utl.save_goal_seek_output(inputs['guid'], optimized_values)
    return optimized_values


def optimize_ep(initial_ep):
    param = current_state.get_current_parameters()
    inputs = current_state.get_current_inputs()
    convergence_horizon = inputs['conv_horizon']
    ticker = param['ticker']
    year = param['fy_year']

    cost_of_equity = param['ke']
    observed_mkt_value = param['obs_mkt_val']
    franked_dividend = param['franking_ratio']
    initial_book_equity = param['book_equity']
    initial_growth_rate = param['p_eq_growth']
    terminal_growth_rate = param['t_eq_growth']
    value_of_fr_credits = param['value_of_fr_credits']
    tax_rate = param['tax_rate']

    # Generate economic profitability
    economic_profitability = mt.generate_economic_profitability(initial_ep, convergence_horizon)

    # Generate growth in equity
    growth_in_equity = mt.generate_growth_rate(initial_growth_rate, terminal_growth_rate, convergence_horizon)

    # Generate return on equity
    return_on_equity = mt.generate_return_on_equity(economic_profitability, cost_of_equity)

    # Generate book value of equity

    book_value_equity = mt.generate_book_value_equity(initial_book_equity, growth_in_equity, convergence_horizon)

    # Generate profit after tax
    profit_after_tax = mt.generate_profit_after_tax(economic_profitability,
                                                    book_value_equity,
                                                    cost_of_equity,
                                                    convergence_horizon)

    # Generate equity free cash flow
    equity_free_cash_flow = mt.generate_equity_free_cash_flow(profit_after_tax, book_value_equity, convergence_horizon)

    # Generate proportion of franked dividend
    proportion_franked_dividend = mt.generate_proportion_of_frk_dividend(franked_dividend, convergence_horizon)

    # Generate dividend
    dividend = mt.generate_dividend(equity_free_cash_flow)

    # Generate franking credits distributed
    franking_credits_distributed = mt.generate_franking_credits(dividend, tax_rate,
                                                                proportion_franked_dividend,
                                                                value_of_fr_credits)

    # Generate implied net capital distribution
    net_capital_distribution = mt.generate_implied_net_capital_distribution(equity_free_cash_flow, dividend)

    # Generate market value of equity
    # Generate change in equity
    change_in_equity = mt.generate_change_in_equity(book_value_equity)

    # Generate equity free cash flow (FC)
    equity_free_cash_flow_fc = mt.generate_equity_free_cash_flow_fc(profit_after_tax, franking_credits_distributed,
                                                                    change_in_equity)

    # Generate present value factor
    present_value_factor = mt.generate_pvf(convergence_horizon, cost_of_equity)

    # Generate discount adjusted equity free cash flow
    discount_adjusted_equity_free_cash_flow = mt.generate_discount_adjusted_eq_fcf(equity_free_cash_flow,
                                                                                   present_value_factor)

    # Generate terminal value
    terminal_value = mt.generate_terminal_value(franking_credits_distributed, terminal_growth_rate, cost_of_equity)

    market_value_equity = mt.generate_market_value_equity(terminal_value,
                                                          book_value_equity,
                                                          equity_free_cash_flow_fc,
                                                          cost_of_equity,
                                                          convergence_horizon)
    economic_profit = mt.calculate_economic_profit(profit_after_tax, book_value_equity, cost_of_equity)

    # Calculate value created
    value_created = mt.calculate_value_created(book_value_equity, market_value_equity)
    present_state = {
        'ep': economic_profitability,
        'growth_in_equity': growth_in_equity,
        'pat': profit_after_tax,
        'return_on_equity': return_on_equity,
        'book_value_equity': book_value_equity,
        'profit_after_tax': profit_after_tax,
        'equity_free_cash_flow': equity_free_cash_flow,
        'proportion_franked_dividend': proportion_franked_dividend,
        'dividend': dividend,
        'franking_credits_distributed': franking_credits_distributed,
        'net_capital_distribution': net_capital_distribution,
        'present_value_factor': present_value_factor,
        'discount_adjusted_equity_free_cash_flow': discount_adjusted_equity_free_cash_flow,
        'market_value_equity': market_value_equity,
        'change_in_equity': change_in_equity,
        'equity_free_cash_flow_fc': equity_free_cash_flow_fc,
        'value_created': value_created,
        'economic_profit': economic_profit,
        'base_year': [year] * convergence_horizon,
        'year': generate_years(year, convergence_horizon + 2),
        'ticker': [ticker] * (convergence_horizon + 2)
    }
    current_state.store_current_state(present_state)
    diff = market_value_equity[0] - observed_mkt_value
    return np.power(diff, 2)


def generate_years(start_year, length):
    return list(range(start_year, start_year + length + 2))


def replicate_string(ticker, n):
    return [ticker for _ in range(n)]


def arrays_to_dataframe(**kwargs):
    return pd.DataFrame(kwargs)


def process_arrays(arr_dict, convergence_horizon):
    # Create an empty DataFrame
    dfs = []
    df = pd.DataFrame()
    key_columns = ['year', 'base_year', 'ticker']
    # Add identifier columns
    for key in key_columns:
        df[key] = pd.Series(arr_dict[key])
    # Process other arrays
    for key in list(arr_dict.keys()):
        if key not in key_columns:
            temp_df = pd.DataFrame()
            temp_df['key'] = pd.Series([key] * (convergence_horizon + 2))
            temp_df['value'] = pd.Series(arr_dict[key])
            dfs.append(pd.concat([df, temp_df], axis=1))
    final_df = pd.concat(dfs)
    return final_df
