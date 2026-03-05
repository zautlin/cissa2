# pylint: disable=too-many-locals,redefined-outer-name,cell-var-from-loop,too-many-arguments,too-many-statements
# pylint: disable=too-many-branches,too-many-positional-arguments
import argparse
import json
from pathlib import Path
from datetime import datetime

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import minimize
import statsmodels.api as sm


from src.backtesting.transaction_cost import ConstantTC, ParabolicTC, InverseMarketCapTC
from src.backtesting.objective_functions import sharpe_ratio_objective, mean_variance_objective
from src.backtesting.sector_analysis import calc_brinson_by_month


# Calculate the tracking error Based on returns???
def calculate_tracking_error(portfolio_returns, benchmark_returns):
    # Calculate the excess returns
    excess_returns = portfolio_returns - benchmark_returns
    # Calculate the tracking error as the standard deviation of excess returns
    tracking_error = np.sqrt(1) * np.std(excess_returns)
    return tracking_error


def transfer_coefficient_alpha_active(alpha_signals, active_weights):
    """
    Calculate the transfer coefficient using alpha signals and active weights.

    Parameters:
    alpha_signals (np.array): Alpha signals or expected returns from the model.
    active_weights (np.array): Active weights (weights relative to a benchmark).

    Returns:
    float: Transfer coefficient.
    """
    # Ensure the inputs are numpy arrays
    alpha_signals = np.array(alpha_signals)
    active_weights = np.array(active_weights)

    # Calculate the correlation coefficient between alpha signals and active weights
    correlation_matrix = np.corrcoef(alpha_signals, active_weights)

    # The transfer coefficient is the off-diagonal element of the correlation matrix
    transfer_coeff = correlation_matrix[0, 1]

    return transfer_coeff


# Function to perform optimization
def optimize_portfolio_through_time(expected_returns_series, cov_matrices_series, benchmark_weights,
                                    bics_sector_mapping, max_tracking_error, actual_returns, universe_companies,
                                    active_weight_boundary, objective_function, transaction_cost=None,
                                    apply_beta_constraint=False):
    num_time_periods = len(expected_returns_series)
    num_assets = len(expected_returns_series[0])

    results = []
    gross_cum_returns_optimal = []
    gross_cum_returns_benchmark = []
    net_cum_returns_optimal = []
    net_cum_returns_benchmark = []
    for t in range(num_time_periods):
        print(f'Time period -> {t}')
        expected_returns = expected_returns_series[t]
        # Actual returns for current period (with previous portfolio weights)
        actual_returns_t = actual_returns[t]
        if actual_returns_t:
            # Replace nan values with zeros in the list
            actual_returns_t = [0 if np.isnan(x) else x for x in actual_returns_t]
        cov_matrix = cov_matrices_series[t]

        benchmark_weights_t = benchmark_weights[t] if isinstance(benchmark_weights[t], list) else benchmark_weights

        # Initialisation weights
        if t == 0:
            # Benchmark weights for the first time period
            initial_weights = benchmark_weights_t
        else:
            # Optimized weights from the previous time period
            prev_p_weights = results[t - 1]['Optimized Weights']
            prev_p_assets = universe_companies[t - 1]
            # Re-order the weights according to the current universe
            initial_weights = [prev_p_weights[prev_p_assets.index(asset)] if asset in prev_p_assets else 0
                               for asset in universe_companies[t]]

        # Initialize sector dict
        sector_dict_p = {sector: 0 for sector in set(bics_sector_mapping.values())}
        sector_dict_b = {sector: 0 for sector in set(bics_sector_mapping.values())}

        # Define the portfolio return function
        def portfolio_return(weights):
            return np.dot(weights, expected_returns)

        def actual_portfolio_return(weights):
            return np.dot(weights, actual_returns_t)

        # Define the portfolio risk function
        def portfolio_risk(weights):
            return np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))

        # Define the tracking error function
        def tracking_error(weights):
            active_weights = weights - benchmark_weights_t
            return np.sqrt(np.dot(active_weights.T, np.dot(cov_matrix, active_weights)))

        # Define the beta constraint
        def beta_constraint(weights):
            benchmark_weights_array = np.array(benchmark_weights_t)
            market_variance = np.dot(benchmark_weights_array.T, np.dot(cov_matrix, benchmark_weights_array))
            portfolio_market_covariance = np.dot(weights.T, np.dot(cov_matrix, benchmark_weights_array))
            portfolio_beta = portfolio_market_covariance / market_variance
            return portfolio_beta - 1

        # Define the objective function (maximize return/risk ratio)
        def objective(weights):

            if transaction_cost and t > 0:
                if isinstance(transaction_cost, InverseMarketCapTC):
                    transaction_cost.set_tc(benchmark_weights_t)
                tc_fnct = transaction_cost
            else:
                tc_fnct = None

            if objective_function == 'sharpe_ratio':
                return sharpe_ratio_objective(portfolio_return(weights), portfolio_risk(weights),
                                              tc_fnct, weights - initial_weights)
            if objective_function == 'mean_variance':  # pylint: disable=no-else-return
                return mean_variance_objective(portfolio_return(weights), portfolio_risk(weights),
                                               1.0, tc_fnct, weights - initial_weights)
            else:
                raise ValueError('Objective function not recognized.')

        # Define the constraint (sum of weights equals 1)
        constraints = [
            {'type': 'eq', 'fun': lambda weights: np.sum(weights) - 1},
        ]

        if max_tracking_error:
            constraints.append({'type': 'ineq', 'fun': lambda weights: max_tracking_error - tracking_error(weights)})
        if apply_beta_constraint:
            constraints.append({'type': 'eq', 'fun': beta_constraint})

        # Define bounds per asset
        # - lower_bound -> max(0, benchmark_weight - 0.05)
        # - upper_bound -> benchmark_weight + 0.05
        bounds = tuple((max(0, benchmark_weights_t[i] - active_weight_boundary),
                        benchmark_weights_t[i] + active_weight_boundary)
                       for i in range(num_assets))

        # Perform the optimization to maximize the return/risk ratio
        result = minimize(objective, np.array(initial_weights), method='SLSQP', bounds=bounds,
                          constraints=constraints)

        # Get the optimized weights
        optimized_weights = result.x

        # Calculate the expected return and risk of the optimized portfolio
        optimized_return = portfolio_return(optimized_weights)
        gross_optimized_returns = actual_portfolio_return(initial_weights) \
            if actual_returns_t is not None else None
        gross_benchmark_returns = actual_portfolio_return(benchmark_weights[t-1]) \
            if actual_returns_t is not None else None
        optimized_risk = portfolio_risk(optimized_weights)

        # Calculate the tracking error
        optimized_tracking_error = tracking_error(optimized_weights)

        # Calculate turnover
        optimized_turnover = np.sum(np.abs(optimized_weights - initial_weights)) / 2

        # Benchmark turnover
        benchmark_turnover = np.sum(np.abs(np.array(benchmark_weights_t) - np.array(benchmark_weights[t-1]))) / 2

        # Calculate transfer coefficient
        active_weights = optimized_weights - benchmark_weights_t
        transfer_coefficient = transfer_coefficient_alpha_active(expected_returns, active_weights)

        # Calculate actual transaction cost
        if transaction_cost and t > 0:
            transaction_cost_t = transaction_cost.calculate_tc(optimized_weights - initial_weights)
        else:
            transaction_cost_t = 'N/A'

        # Calculate net returns (gross returns - transaction cost)
        net_optimized_returns = gross_optimized_returns - transaction_cost_t \
            if transaction_cost_t != 'N/A' else gross_optimized_returns
        net_benchmark_returns = gross_benchmark_returns - transaction_cost_t \
            if transaction_cost_t != 'N/A' else gross_benchmark_returns

        # Calculate cumulative returns
        if t == 0:
            # Gross cumulative returns
            gross_cum_opt = 1
            gross_cum_ben = 1
            # Net cumulative returns
            net_cum_opt = 1
            net_cum_ben = 1

        else:
            # Gross cumulative returns
            gross_cum_opt = gross_cum_returns_optimal[-1] * (1 + gross_optimized_returns)
            gross_cum_ben = gross_cum_returns_benchmark[-1] * (1 + gross_benchmark_returns)
            # Net cumulative returns
            net_cum_opt = net_cum_returns_optimal[-1] * (1 + net_optimized_returns)
            net_cum_ben = net_cum_returns_benchmark[-1] * (1 + net_benchmark_returns)

        # Append to lists
        gross_cum_returns_optimal.append(gross_cum_opt)
        gross_cum_returns_benchmark.append(gross_cum_ben)
        net_cum_returns_optimal.append(net_cum_opt)
        net_cum_returns_benchmark.append(net_cum_ben)

        # Calculate weights per sector
        for i, asset in enumerate(universe_companies[t]):
            sector = bics_sector_mapping[asset]
            sector_dict_p[sector] += optimized_weights[i]
            sector_dict_b[sector] += benchmark_weights_t[i]

        # sector_returns_t = sector_returns() if actual_returns_t else None

        # Collect the results
        results.append({
            'Time Period': t + 1,
            'Optimized Weights': optimized_weights,
            'Initial Universe': universe_companies[t-1] if actual_returns_t else None,
            # Elementwise product
            'Initial Weights Portfolio': initial_weights,
            'Stock Returns': actual_returns_t if actual_returns_t else None,
            'Initial Weights Benchmark': benchmark_weights_t,
            'Sector Weights Portfolio': sector_dict_p,
            'Sector Weights Benchmark': sector_dict_b,
            # 'Sector Returns': sector_returns_t,
            'Expected Return (signal)': optimized_return,
            'Cum. Gross Portfolio Return': gross_cum_opt,
            'Cum. Gross Benchmark Return': gross_cum_ben,
            'Gross Portfolio Return': gross_optimized_returns,
            'Gross Benchmark Return': gross_benchmark_returns,
            'Cum. Net Portfolio Return': net_cum_opt,
            'Cum. Net Benchmark Return': net_cum_ben,
            'Net Portfolio Return': net_optimized_returns,
            'Net Benchmark Return': net_benchmark_returns,
            'Standard Deviation': optimized_risk,
            'Tracking Error': optimized_tracking_error,
            'Turnover': optimized_turnover,
            'Turnover (Benchmark)': benchmark_turnover,
            'Transaction Cost': transaction_cost_t,
            'Transfer Coefficient': transfer_coefficient,
            'Alpha signal': expected_returns,
            'Active Weights': active_weights
        })

    return results


def main(args):

    # Create './output' directory
    now_datetime = datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
    dirname = f"p-opt-{args.test_name}-{now_datetime}"
    # Create the directory if it does not exist
    Path(f'./output/{dirname}').mkdir(parents=True, exist_ok=True)

    # Save args hyperparameters to a json file
    with open(f'output/{dirname}/hyperparameters.json', 'w', encoding='utf-8') as f:
        arg_dict = vars(args)
        f.write(json.dumps(arg_dict, indent=4))

    # Read benchmark weights
    df_benchmark_weights = pd.read_csv(args.benchmark_weights, index_col='ticker')
    # Read company BICS sector mapping
    df_company_bics = pd.read_csv(args.company_bics, index_col='ticker')
    # Convert to dictionary
    company_bics_dict = df_company_bics['bics_1'].to_dict()
    # Read the alpha signal
    df_cissa = pd.read_csv(args.alpha_signal_data,
                           index_col='ticker')
    # Read the actual returns data
    df_actual_returns = pd.read_csv(args.company_tsr_data, index_col='ticker')

    # we don't seme to have ep_1_Y values for 2002, so start from 2003
    if args.signal in ['ep_1_Y', 'MC_div_EP_1_Y', 'MB_div_EP_1_Y', 'MC_div_EP_1_Y_pred', 'MB_div_EP_1_Y_pred',
                       'EP_10_Y_pred']:
        df_cissa = df_cissa.iloc[:, 1:]
        df_actual_returns = df_actual_returns.iloc[:, 1:]
        df_benchmark_weights = df_benchmark_weights.iloc[:, 1:]
    elif args.signal == 'ep_3_Y':
        df_cissa = df_cissa.iloc[:, 3:]
        df_actual_returns = df_actual_returns.iloc[:, 3:]
        df_benchmark_weights = df_benchmark_weights.iloc[:, 3:]

    time_periods = len(df_cissa.columns)

    # First year
    first_year = int(df_cissa.columns[0].split('_')[-1])
    # Last year
    last_year = int(df_cissa.columns[-1].split('_')[-1])

    print(f'Optimisation window -> {first_year} to {last_year}')

    # max_tracking_error = 0.02

    benchmark_weights = []
    universe_companies = []
    ee_values_series = []
    actual_returns_series = []
    cov_matrices_series = []
    year_time_periods = []
    # Build data structures
    for colname in df_benchmark_weights.columns:
        # Sort rows according to benchmark weights in that column
        df_bnchmrk_srtd = df_benchmark_weights.sort_values(by=colname, ascending=False)[[colname]]
        # Select top 200 companies and weights
        list_companies = df_bnchmrk_srtd.index.tolist()[:args.universe_size]
        list_weights = df_bnchmrk_srtd[colname].tolist()[:args.universe_size]
        # Append to the universe
        universe_companies.append(list_companies)
        # Append to the benchmark weights
        benchmark_weights.append(list_weights)

        # Select the economic equity values for the selected companies
        # Add missing companies to dataframe
        missing_companies = list(set(list_companies) - set(df_cissa.index))
        if missing_companies:
            for company in missing_companies:
                df_cissa.loc[company] = [None] * time_periods
        df_ee_srtd = df_cissa.loc[list_companies]
        ee_colname = f'norm_{args.signal}_{colname.split("_")[-1]}'
        list_ee_values = df_ee_srtd[ee_colname].tolist()
        # Append to the economic equity values
        ee_values_series.append(list_ee_values)

        # Actual returns
        df_actual_returns_srtd = df_actual_returns.loc[list_companies]
        # We are considering the actual returns at the end of the time period
        year_t = int(colname.split('_')[1])
        year_time_periods.append(year_t)
        year_t1 = int(colname.split('_')[1]) + 1
        tsr_colname = f'tsr_{year_t}'
        tsr_1_colname = f'tsr_{year_t1}'
        # Note -> The list actual_returns_series will have the actual returns for the next time period, and will be
        # one time period shorter than the rest of the list, as we do not have an actual return for time period 0.
        if tsr_colname == f'tsr_{first_year}':
            actual_returns_series.append(None)
            actual_returns_series.append(df_actual_returns_srtd[tsr_1_colname].tolist())
        elif tsr_colname != f'tsr_{last_year}':
            actual_returns_series.append(df_actual_returns_srtd[tsr_1_colname].tolist())

        # Load covariance matrices
        colname_year = colname.split('_')[1]
        df_cov_matrix = pd.read_csv(f'{args.cov_matrices_data}/cov_matrix_{colname_year}.csv',
                                    index_col=0)
        # Re-shuffle the rows and columns according to the benchmark weights index (list_companies)
        df_cov_matrix = df_cov_matrix.loc[list_companies, list_companies]
        # Extract the covariance matrix
        cov_matrices_series.append(df_cov_matrix.values)

    # Initialize the transaction cost object
    if args.apply_transaction_cost == 'constant':
        transaction_cost = ConstantTC(cost=args.transaction_cost)
    elif args.apply_transaction_cost == 'parabolic':
        transaction_cost = ParabolicTC(active_weight_boundary=args.active_weight_boundary)
    elif args.apply_transaction_cost == 'inverse_market_cap':
        transaction_cost = InverseMarketCapTC()
    else:
        transaction_cost = None

    # Perform optimization through time
    print('Optimizing portfolio through time...')
    results = optimize_portfolio_through_time(ee_values_series, cov_matrices_series, benchmark_weights,
                                              company_bics_dict, args.max_tracking_error, actual_returns_series,
                                              universe_companies, args.active_weight_boundary, args.objective_function,
                                              transaction_cost, args.apply_beta_constraint)

    # Prepare the results for export
    weights_df = pd.DataFrame()
    for t in range(time_periods):
        t_df = pd.DataFrame()
        t_df['Asset'] = universe_companies[t]
        t_df[f'year - {year_time_periods[t]}'] = [f"{w * 100:.2f}%" for w in np.array(results[t]['Optimized Weights'])]
        t_df.set_index('Asset', inplace=True)
        weights_df = pd.concat([weights_df, t_df], axis=1)

    # Add the portfolio statistics to the export data
    columns = ['Asset'] + [f'year - {year_time_periods[t]}' for t in range(time_periods)]
    weights_data = []
    stats = ['Expected Return (signal)', 'Standard Deviation', 'Tracking Error',
             'Turnover', 'Transaction Cost', 'Transfer Coefficient', 'Cum. Gross Portfolio Return',
             'Cum. Gross Benchmark Return', 'Gross Portfolio Return', 'Gross Benchmark Return',
             'Cum. Net Portfolio Return', 'Cum. Net Benchmark Return', 'Net Portfolio Return', 'Net Benchmark Return']
    for stat in stats:
        row = {'Asset': stat}
        for t in range(time_periods):
            if results[t][stat] == 'N/A':
                row[f'year - {year_time_periods[t]}'] = 'N/A'
            else:
                row[f'year - {year_time_periods[t]}'] = f"{results[t][stat] * 100:.2f}%" \
                    if isinstance(results[t][stat], float) else results[t][stat]

        weights_data.append(row)

    # Create a DataFrame for the results
    stats_df = pd.DataFrame(weights_data, columns=columns)
    stats_df.set_index('Asset', inplace=True)
    weights_df = pd.concat([weights_df, stats_df], axis=0)

    # Save the results to a CSV file
    weights_df.to_csv(f'output/{dirname}/portfolio_optimization_results.csv')

    # Display the table
    print(weights_df)

    # Calculate summary statistics
    # Extract the gross cumulative returns benchmark

    cum_gross_return_optimal = [result['Cum. Gross Portfolio Return'] for result in results]
    cum_gross_return_benchmark = [result['Cum. Gross Benchmark Return'] for result in results]
    # Gross cumulative returns
    cum_gross_return_optimal_last = cum_gross_return_optimal[-1] - 1
    cum_gross_return_benchmark_last = cum_gross_return_benchmark[-1] - 1
    cum_gross_active_return = cum_gross_return_optimal_last - cum_gross_return_benchmark_last
    # Net cumulative returns
    cum_net_return_optimal = [result['Cum. Net Portfolio Return'] for result in results]
    cum_net_return_benchmark = [result['Cum. Net Benchmark Return'] for result in results]
    cum_net_return_optimal_last = cum_net_return_optimal[-1] - 1
    cum_net_return_benchmark_last = cum_net_return_benchmark[-1] - 1
    cum_net_active_return = cum_net_return_optimal_last - cum_net_return_benchmark_last

    # Pop None values from list
    returns_optimal_gross = [result['Gross Portfolio Return'] for result in results][1:]
    returns_benchmark_gross = [result['Gross Benchmark Return'] for result in results][1:]
    total_risk = np.std(np.array(returns_optimal_gross) - 1)
    total_risk_benchmark = np.std(np.array(returns_benchmark_gross) - 1)
    tracking_error_gross = calculate_tracking_error(np.array(returns_optimal_gross), np.array(returns_benchmark_gross))

    # Calculate tracking error for net returns
    returns_optimal_net = [result['Net Portfolio Return'] for result in results][1:]
    returns_benchmark_net = [result['Net Benchmark Return'] for result in results][1:]
    tracking_error_net = calculate_tracking_error(np.array(returns_optimal_net), np.array(returns_benchmark_net))

    # Convert cumulative returns to annualized cumulative returns
    # Gross
    annualized_return_optimal_gross = (cum_gross_return_optimal_last + 1) ** (1 / time_periods) - 1
    annualized_return_benchmark_gross = (cum_gross_return_benchmark_last + 1) ** (1 / time_periods) - 1
    annualized_active_return_gross = annualized_return_optimal_gross - annualized_return_benchmark_gross
    # Net
    annualized_return_optimal_net = (cum_net_return_optimal_last + 1) ** (1 / time_periods) - 1
    annualized_return_benchmark_net = (cum_net_return_benchmark_last + 1) ** (1 / time_periods) - 1
    annualized_active_return_net = annualized_return_optimal_net - annualized_return_benchmark_net

    # Calculate Sharpe ratio and information ratio (assuming risk-free rate = 0)
    sharpe_ratio = annualized_return_optimal_gross / total_risk
    sharpe_ratio_benchmark = annualized_return_benchmark_gross / total_risk_benchmark
    information_ratio_gross = annualized_active_return_gross / tracking_error_gross
    information_ratio_net = annualized_active_return_net / tracking_error_net
    # Calculate average turnover
    average_turnover = np.mean([result['Turnover'] for result in results])
    average_b_turnover = np.mean([result['Turnover (Benchmark)'] for result in results])

    # Calculate average transfer coefficient
    average_transfer_coefficient = np.mean([result['Transfer Coefficient'] for result in results])

    # Calculate average transaction cost
    if transaction_cost:
        average_transaction_cost = np.mean([result['Transaction Cost'] for result in results][1:])
    else:
        average_transaction_cost = 0

    # Alpha and Beta - Capital Asset Pricing Model (CAPM)
    df_risk_free_rates = pd.read_csv('./data/rba_cash_rate_hist.csv')
    if args.signal in ['ep_1_Y', 'MC_div_EP_1_Y', 'MB_div_EP_1_Y', 'MC_div_EP_1_Y_pred', 'MB_div_EP_1_Y_pred',
                       'EP_10_Y_pred']:
        risk_free_rates = [x/100 for x in df_risk_free_rates['cash_rate_pct'].tolist()][2:]
    elif args.signal == 'ep_3_Y':
        risk_free_rates = [x/100 for x in df_risk_free_rates['cash_rate_pct'].tolist()][4:]
    else:
        risk_free_rates = [x/100 for x in df_risk_free_rates['cash_rate_pct'].tolist()][1:]
    # excess returns
    excess_p_returns = np.array(returns_optimal_gross) - np.array(risk_free_rates)
    excess_b_returns = np.array(returns_benchmark_gross) - np.array(risk_free_rates)
    # Add a constant to the benchmark returns for the intercept
    x = sm.add_constant(excess_b_returns)
    y = excess_p_returns
    model = sm.OLS(y, x).fit()
    alpha, beta = model.params

    # max drawdown
    df_tmp = pd.DataFrame()
    df_tmp['fund_returns'] = returns_optimal_gross
    df_tmp['benchmark_returns'] = returns_benchmark_gross
    drawdown_series_p = 100 * ((1 + df_tmp['fund_returns']).cumprod() -
                               (1 + df_tmp['fund_returns']).cumprod().cummax())
    max_drawdown_p = drawdown_series_p.min()
    drawdown_series_b = 100 * ((1 + df_tmp['benchmark_returns']).cumprod() -
                               (1 + df_tmp['benchmark_returns']).cumprod().cummax())
    max_drawdown_b = drawdown_series_b.min()

    summary_stats = {
        # Gross returns
        'Cum. Optimal Return (Gross)': f"{cum_gross_return_optimal_last * 100:.2f}%",
        'Cum. Benchmark Return (Gross)': f"{cum_gross_return_benchmark_last * 100:.2f}%",
        'Annu. Optimal Return (Gross)': f"{annualized_return_optimal_gross * 100:.2f}%",
        'Annu. Benchmark Return (Gross)': f"{annualized_return_benchmark_gross * 100:.2f}%",
        'Cum. Active Return (Gross)': f"{cum_gross_active_return * 100:.2f}%",
        'Annu. Active Return (Gross)': f"{annualized_active_return_gross * 100:.2f}%",
        # Net Returns
        'Cum. Optimal Return (Net)': f"{cum_net_return_optimal_last * 100:.2f}%",
        'Cum. Benchmark Return (Net)': f"{cum_net_return_benchmark_last * 100:.2f}%",
        'Annu. Optimal Return (Net)': f"{annualized_return_optimal_net * 100:.2f}%",
        'Annu. Benchmark Return (Net)': f"{annualized_return_benchmark_net * 100:.2f}%",
        'Cum. Active Return (Net)': f"{cum_net_active_return * 100:.2f}%",
        'Annu. Active Return (Net)': f"{annualized_active_return_net * 100:.2f}%",
        # Only with Gross Returns
        'Total Risk': f"{total_risk * 100:.2f}%",
        'Total Risk (Benchmark)': f"{total_risk_benchmark * 100:.2f}%",
        'Tracking Error (Gross)': f"{tracking_error_gross * 100:.2f}%",
        'Tracking Error (Net)': f"{tracking_error_net * 100:.2f}%",
        'Sharpe Ratio': f"{sharpe_ratio:.2f}",
        'Sharpe Ratio (Benchmark)': f"{sharpe_ratio_benchmark:.2f}",
        'Information Ratio (Gross)': f"{information_ratio_gross:.2f}",
        'Information Ratio (Net)': f"{information_ratio_net:.2f}",
        'Avg. Turnover': f"{average_turnover * 100:.2f}%",
        'Avg. Turnover (Benchmark)': f"{average_b_turnover * 100:.2f}%",
        'Avg. Transaction Cost': f"{average_transaction_cost * 100:.2f}%",
        'Alpha': f"{alpha*100:.4f}",
        'Beta': f"{beta:.4f}",
        'Max Drawdown (Optimal)': f"{max_drawdown_p:.2f}%",
        'Max Drawdown (Benchmark)': f"{max_drawdown_b:.2f}%",
        'Avg. Transfer Coefficient': f"{average_transfer_coefficient:.4f}"
    }

    summary_stats_df = pd.DataFrame([summary_stats])

    # Save the summary statistics to a CSV file
    summary_stats_df.to_csv(f'output/{dirname}/summary_statistics.csv', index=False)

    # Display summary statistics
    print(summary_stats_df)

    # Plot the cumulative returns
    plt.figure(figsize=(10, 6))
    year_range = list(range(first_year+1, last_year + 2))
    # Convert years with date at the end of the year (i.e., 31st of Decemeber) in datetime format
    # year_range = [datetime.strptime(f'{year}-12-31', '%Y-%m-%d') for year in year_range]
    plt.plot(year_range, np.array(cum_gross_return_optimal) * 100,
             label='Optimal (Gross)', color='b')
    plt.plot(year_range, np.array(cum_gross_return_benchmark) * 100,
             label='Benchmark (Gross)', color='b', linestyle='--')
    plt.plot(year_range, np.array(cum_net_return_optimal) * 100,
             label='Optimal (Net)', color='g')
    plt.plot(year_range, np.array(cum_net_return_benchmark) * 100,
             label='Benchmark (Net)', color='g', linestyle='--')
    plt.xlabel('Time Period')
    plt.ylabel('Cumulative Return (%)')
    plt.title('Cumulative Return of Optimal Portfolio vs Benchmark')
    plt.xticks(year_range[::2])
    plt.legend()
    plt.grid(True)
    plt.savefig(f'output/{dirname}/cumulative_returns.png')
    # plt.show()

    # Load s&p_asx_200 official data
    df_sp_asx_200 = pd.read_csv('./data/s&p_asx_200_official_returns.csv')
    # Date to datetime
    df_sp_asx_200['dates'] = pd.to_datetime(df_sp_asx_200['dates'], format='%d/%m/%Y')
    df_sp_asx_200.sort_values(by='dates', inplace=True)
    # Extract year
    df_sp_asx_200['year'] = df_sp_asx_200['dates'].dt.year
    # Filter to years of interest
    df_sp_asx_200 = df_sp_asx_200[(df_sp_asx_200['year'] > first_year) & (df_sp_asx_200['year'] <= last_year)]
    # Calculate cummulative returns grouped by year
    df_sp_asx_200_year = df_sp_asx_200.groupby('year')['s&p_asx_200'].agg(lambda x: (x + 1).prod() - 1).reset_index()
    asx_200_returns = df_sp_asx_200_year['s&p_asx_200'].tolist()

    # Prepare returns file for notebook analysis
    df_returns_output = pd.DataFrame(columns=['dates', 'fund_returns', 'benchmark_returns', 's&p_asx_200'])
    year_range = list(range(first_year + 1, last_year + 1))
    for i, year in enumerate(year_range):
        df_returns_output.loc[i] = [f'{year}-12-31', returns_optimal_gross[i],
                                    returns_benchmark_gross[i], asx_200_returns[i]]
    # Output the returns to a CSV file
    df_returns_output.to_csv(f'./output/{dirname}/op_vs_benchmark_returns.csv', index=False)

    # Plot the yearly returns
    plt.figure(figsize=(10, 6))
    plt.plot(year_range, np.array(returns_optimal_gross) * 100, label='Optimal (Gross)')
    plt.plot(year_range, np.array(returns_benchmark_gross) * 100, label='Benchmark (Gross)', linestyle='--')
    plt.plot(year_range, np.array(asx_200_returns) * 100, label='S&P ASX 200', linestyle='-.')
    plt.xlabel('Year')
    plt.ylabel('Returns (%)')
    plt.title('Yearly Returns of Optimal Portfolio vs Benchmark vs S&P ASX 200')
    plt.legend()
    plt.grid(True)
    plt.savefig(f'output/{dirname}/yearly_returns.png')
    # plt.show()

    # Plot scatterplot with active weights and alpha signal
    plt.figure(figsize=(10, 6))
    for t in range(time_periods):
        plt.scatter(results[t]['Alpha signal'], results[t]['Active Weights'], label=f'Year {year_time_periods[t]}')
    plt.xlabel('Alpha Signal')
    plt.ylabel('Active Weights')
    plt.title('Alpha Signal vs Active Weights')
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(f'output/{dirname}/alpha_signal_vs_active_weights.png')

    # Benchmark analysis
    # Calculate the sector exposures for the benchmark and portfolio
    exposures_ts_df_p = pd.DataFrame()
    exposures_ts_df_b = pd.DataFrame()
    for i, result in enumerate(results):
        sector_weights_benchmark = result['Sector Weights Benchmark']
        sector_weights_portfolio = result['Sector Weights Portfolio']
        # Convert to DataFrame
        sector_weights_benchmark_df = pd.DataFrame(sector_weights_benchmark.items(), columns=['Sector', 'Weight'])
        exposures_b = sector_weights_benchmark_df.groupby('Sector').sum()['Weight']
        sector_weights_portfolio_df = pd.DataFrame(sector_weights_portfolio.items(), columns=['Sector', 'Weight'])
        exposures_p = sector_weights_portfolio_df.groupby('Sector').sum()['Weight']
        exposures_df = pd.DataFrame({
            'Portfolio': exposures_p,
            'Benchmark': exposures_b
        }).fillna(0)
        # Separated
        exposures_df_p = pd.DataFrame({
            'weight': exposures_p
        }).fillna(0)
        exposures_ts_df_p = pd.concat([exposures_ts_df_p, exposures_df_p], axis=1)
        exposures_df_b = pd.DataFrame({
            'weight': exposures_b
        }).fillna(0)
        exposures_ts_df_b = pd.concat([exposures_ts_df_b, exposures_df_b], axis=1)
        # Plot the sector exposures
        exposures_df.plot(kind='bar', figsize=(12, 6))
        plt.title('Sector Exposures: Portfolio vs. Benchmark')
        plt.xlabel('Sector')
        plt.ylabel('Exposure')
        plt.xticks(rotation=45)
        plt.legend(loc='upper right')
        plt.grid(axis='y')
        plt.tight_layout()
        Path(f'./output/{dirname}/sector_exposures').mkdir(parents=True, exist_ok=True)
        plt.savefig(f'output/{dirname}/sector_exposures/barchart_sector_exposures_iter_{result["Time Period"]}.png')

    # Plot exposures overtime in each sector
    for i, sector in enumerate(exposures_ts_df_p.index.tolist()):
        _, ax = plt.subplots(2, 1, figsize=(15, 7))
        # Plot the sector exposures
        ax[0].plot(year_time_periods, exposures_ts_df_p.loc[sector], label='Portfolio')
        ax[0].plot(year_time_periods, exposures_ts_df_b.loc[sector], label='Benchmark')
        ax[0].set_title(sector)
        ax[0].set_ylabel('Weight')
        ax[0].legend()
        ax[0].grid(True)
        # Plot active differences
        ax[1].plot(year_time_periods, exposures_ts_df_p.loc[sector] - exposures_ts_df_b.loc[sector],
                   color='green', label='Active')
        # Add horizontal line at 0
        ax[1].axhline(0, color='black', linestyle='--')
        ax[1].set_xlabel('Year')
        ax[1].set_ylabel('Weight')
        ax[1].legend()
        ax[1].grid(True)
        plt.tight_layout()
        plt.savefig(f'output/{dirname}/sector_exposures/ts_{sector}.png')

    # Attribution analysis
    df_exposures = pd.DataFrame()
    list_years = list(range(first_year, last_year + 1))
    for i, result in enumerate(results):
        universe = result['Initial Universe']
        if universe is None:
            continue
        port_weights = result['Initial Weights Portfolio']
        bm_weights = result['Initial Weights Benchmark']
        port_returns = result['Stock Returns']
        year = list_years[i]
        for j, asset in enumerate(universe):
            new_row = {'Date': year, 'bm_weights': bm_weights[j], 'por_weights': port_weights[j],
                       'Returns': port_returns[j], 'Asset': asset,
                       'Sector': company_bics_dict[asset]}
            tmp_df = pd.DataFrame(new_row, index=[0])
            df_exposures = pd.concat([df_exposures, tmp_df], axis=0)

    # Add Date column with year
    brinson_df = df_exposures.groupby('Date').apply(calc_brinson_by_month).reset_index()
    brinson_df.to_csv(f'output/{dirname}/brinson_analysis.csv', index=False)


# Add argument parser
parser = argparse.ArgumentParser(description='Optimize portfolio through time')
parser.add_argument('--test-name', type=str, default='test',
                    help='The name of the test to be performed')
# Input files
parser.add_argument('--benchmark-weights', type=str, required=True,
                    help='The file containing the benchmark weights')
parser.add_argument('--alpha-signal-data', type=str, required=True,
                    help='The file containing the alpha signal')
parser.add_argument('--cov-matrices-data', type=str, required=True,
                    help='The directory containing the covariance matrices')
parser.add_argument('--company-tsr-data', type=str, required=True,
                    help='The file containing the company TSR data')
parser.add_argument('--company-bics', type=str, required=True,
                    help='The file containing the company BICS sector mapping')
# Other parameters
parser.add_argument('--universe-size', type=int, default=200,
                    help='The size of the universe to be considered')
parser.add_argument('--apply-transaction-cost', type=str, default=None,
                    choices=[None, 'constant', 'parabolic', 'inverse_market_cap'],
                    help='Whether to include transaction costs in the optimization')
parser.add_argument('--transaction-cost', type=float, default=0.002,
                    help='The transaction cost to be applied to the optimization')
parser.add_argument('--objective-function', type=str, default='mean_variance',
                    choices=['sharpe_ratio', 'mean_variance'],
                    help='The objective function to be used in the optimization.')
parser.add_argument('--signal', type=str, default='ee',
                    choices=['ee', 'ep_1_Y', 'ep_3_Y', 'MB_ratio', 'RMB_ratio', 'MC_div_EP_1_Y', 'MB_div_EP_1_Y',
                             'MC_div_EP_1_Y_pred', 'MB_div_EP_1_Y_pred', 'EP_10_Y_pred'],
                    help='Choose the CISSA singal to optimize the portfolio')
# Constraint arguments
parser.add_argument('--max-tracking-error', type=float, default=None,
                    help='The maximum tracking error allowed for the portfolio')
parser.add_argument('--active-weight-boundary', type=float, default=0.05,
                    help='The difference in allocation of an individual secutiry between'
                         'the optimal portfolio and the benchmark.')
parser.add_argument('--apply-beta-constraint', action='store_true',
                    help='Whether to apply a beta constraint to the optimization')
if __name__ == "__main__":
    script_args = parser.parse_args()
    main(script_args)
