# pylint: disable=too-many-branches
'''
Script to generate the ranking of companies according to the Economic Equity (EE) metric
calculated using the CISSA methodology

Note: The companies that form the universe are the top 200 companies according to market capitalization
'''
import argparse

import pandas as pd
from sklearn.preprocessing import QuantileTransformer

from src.engine.sql import execute_select


def calculate_ratio(df, signal):
    """
    Calculate the ratio between the market capitalization and the EE value
    :param df: pandas dataframe
    :param signal: str
    :return: pandas dataframe
    """
    # Extract the EE and the market capitalization
    df['key'] = df['key'].apply(lambda x: x.strip())

    if signal == 'MB_ratio':
        df_ee = df[df['key'] == 'ee']
        df_mc = df[df['key'] == 'mc']
        df = df_mc.merge(df_ee, on=['ticker', 'fy_year'], how='inner')
        # Calculate the ratio
        df['value'] = df['value_x'] / df['value_y']
    elif signal == 'RMB_ratio':
        df_ee = df[df['key'] == 'ee']
        df_mc = df[df['key'] == 'mc']
        df = df_mc.merge(df_ee, on=['ticker', 'fy_year'], how='inner')
        df['value'] = (df['value_x'] - df['value_y']) / df['value_y']
    elif signal == 'MC_div_EP_1_Y':
        df_mc = df[df['key'] == 'mc']
        df_ep = df[df['key'] == 'ep_1_Y']
        df = df_mc.merge(df_ep, on=['ticker', 'fy_year'], how='inner')
        df['value'] = df['value_x'] / df['value_y']
    elif signal == 'MB_div_EP_1_Y':
        df_mc = df[df['key'] == 'mc']
        df_ee = df[df['key'] == 'ee']
        df_ep = df[df['key'] == 'ep_1_Y']
        df = df_mc.merge(df_ee, on=['ticker', 'fy_year'],
                         how='inner').merge(df_ep, on=['ticker', 'fy_year'], how='inner')
        df['value'] = (df['value_x'] - df['value_y']) / df['value']
    elif signal == 'MC_div_EP_1_Y_pred':
        df_mc = df[df['key'] == 'mc']
        df_ep = df[df['key'] == 'economic_profit']
        df = df_mc.merge(df_ep, on=['ticker', 'fy_year'], how='inner')
        df['value'] = df['value_x'] / df['value_y']
    elif signal == 'MB_div_EP_1_Y_pred':
        df_mc = df[df['key'] == 'mc']
        df_ee = df[df['key'] == 'ee']
        df_ep = df[df['key'] == 'economic_profit']
        df = df_mc.merge(df_ee, on=['ticker', 'fy_year'],
                         how='inner').merge(df_ep, on=['ticker', 'fy_year'], how='inner')
        df['value'] = (df['value_x'] - df['value_y']) / df['value']
        df.rename(columns={'fy_year_x': 'fy_year'}, inplace=True)
    # Only keep the necessary columns
    df = df[['ticker', 'fy_year', 'value']]
    return df


def main(args):

    # Load benchmark weights
    df_benchmark_weights = pd.read_csv(args.benchmark_weights)

    # Query to extract the market capitalization of all the companies per year
    if args.signal in ['ee', 'ep_1_Y', 'ep_3_Y']:
        sql = f"""
                SELECT * FROM "USR".metrics
                WHERE "key" = '{args.signal}';
        """  # nosec
        df_ee = execute_select(sql)
    elif args.signal in ['MB_ratio', 'RMB_ratio']:
        sql = """
                SELECT * FROM "USR".metrics
                WHERE "key" = 'ee' OR "key" = 'mc';
        """  # nosec
        df_ee = execute_select(sql)
    elif args.signal in ['MC_div_EP_1_Y', 'MB_div_EP_1_Y']:
        sql = """
                SELECT * FROM "USR".metrics
                WHERE "key" = 'ee' OR "key" = 'mc' OR "key" = 'ep_1_Y';
        """  # nosec
        df_ee = execute_select(sql)
    elif args.signal in ['MC_div_EP_1_Y_pred', 'MB_div_EP_1_Y_pred']:
        # Query to download the predicted values
        sql = """
                SELECT * FROM "USR".model_outputs
                WHERE "key" = 'economic_profit'
                AND CAST(base_year AS INTEGER) = CAST("year" AS INTEGER) - 1;
        """  # nosec
        df_ep = execute_select(sql)
        df_ep = df_ep.rename(columns={'base_year': 'fy_year'})
        sql = """
                        SELECT * FROM "USR".metrics
                        WHERE "key" = 'ee' OR "key" = 'mc';
                """  # nosec
        df_ee = execute_select(sql)
        df_ee = pd.concat([df_ee, df_ep], axis=0)
    elif args.signal == 'EP_10_Y_pred':
        # Query to download the predicted values
        sql = """
                SELECT * FROM "USR".model_outputs
                WHERE "key" = 'economic_profit'
                AND CAST(base_year AS INTEGER) = CAST("year" AS INTEGER) - 10;
        """  # nosec
        df_ep = execute_select(sql)
        df_ee = df_ep.rename(columns={'base_year': 'fy_year'})
    else:
        raise ValueError(f"Signal {args.signal} is not supported")

    # Treat value as float
    df_ee['value'] = df_ee['value'].astype(float)
    df_ee.to_csv(f'./data/cissa_ranking_{args.signal}_raw_all.csv', index=False)

    # Obtain year range
    years = df_ee['fy_year'].unique()
    years.sort()

    # Market cap
    if args.normalisation_strategy == 'market-cap':
        df_mc = pd.read_csv('./data/mc.csv')

    # Create a pandas dataframe to store the weights for each year
    df_weights = pd.DataFrame(columns=['ticker']).set_index('ticker')
    df_raw = pd.DataFrame()
    # For each year, select the top 200 companies by market capitalization
    for year in years:
        if int(year) < 2023:
            # Select year
            df_year = df_ee[df_ee['fy_year'] == year]
            if args.signal in ['MB_ratio',  'RMB_ratio', 'MC_div_EP_1_Y', 'MB_div_EP_1_Y', 'MC_div_EP_1_Y_pred',
                               'MB_div_EP_1_Y_pred']:
                # Calculate the ratio from the ee and the mc
                df_year = calculate_ratio(df_year, args.signal)
                # Convert nan values to minimum value
                df_year['value'] = df_year['value'].fillna(df_year['value'].min())
            elif args.signal in ['ee', 'ep_1_Y', 'ep_3_Y', 'EP_10_Y_pred']:
                # Convert nan values to 0
                df_year['value'] = df_year['value'].fillna(0)  # Set to undesirable value
            # Sort by market capitalization (descending)
            df_year = df_year.sort_values(by='value', ascending=False)
            # reset index
            df_year = df_year.reset_index(drop=True)
            # Sort benchmark companies in the current year
            df_benchmark_year = df_benchmark_weights[['ticker', f'weigths_{year}']].sort_values(by=f'weigths_{year}',
                                                                                                ascending=False)
            # Select top 200 companies
            list_companies = df_benchmark_year['ticker'].tolist()[:args.universe_size]
            # Filter companies
            df_year = df_year[df_year['ticker'].isin(list_companies)]
            # Normalize the market capitalization
            df_year[f'{args.signal}_{year}'] = df_year['value']
            # Only keep ticker and weights
            df_year = df_year[['ticker', f'{args.signal}_{year}']]
            df_raw_year = df_year.copy()
            # Set ticker as index
            df_raw_year = df_raw_year.set_index('ticker')
            df_raw = pd.concat([df_raw, df_raw_year], axis=1)
            if args.normalisation_strategy == 'zscore':
                # Apply z-scores
                df_year[f'norm_{args.signal}_{year}'] = (
                        (df_year[f'{args.signal}_{year}'] - df_year[f'{args.signal}_{year}'].mean()) /
                        df_year[f'{args.signal}_{year}'].std())
            elif args.normalisation_strategy == 'minmax':
                # Apply min-max normalization
                df_year[f'norm_{args.signal}_{year}'] = (
                        (df_year[f'{args.signal}_{year}'] - df_year[f'{args.signal}_{year}'].min()) /
                        (df_year[f'{args.signal}_{year}'].max() - df_year[f'{args.signal}_{year}'].min()))
            elif args.normalisation_strategy == 'quantile-normal':
                # Apply quantile normalization
                quantile_transformer = QuantileTransformer(output_distribution='normal', random_state=0)
                df_year[f'norm_{args.signal}_{year}'] = quantile_transformer.fit_transform(
                    df_year[f'{args.signal}_{year}'].values.reshape(-1, 1)).flatten()
            elif args.normalisation_strategy == 'market-cap':
                # Apply market-cap normalization
                df_mc_year = df_mc[df_mc['fy_year'] == int(year)]
                df_mc_year = df_mc_year.set_index('ticker')
                df_mc_year['value'] = df_mc_year['value'].apply(lambda x: float(x) if x != 'NULL' else 0.0)
                # Merge dataframes
                df_year = df_year.merge(df_mc_year, on='ticker', how='left')
                # Normalize by market capitalization
                df_year[f'norm_{args.signal}_{year}'] = df_year[f'{args.signal}_{year}'] / df_year['value']
                df_year[f'norm_{args.signal}_{year}'] = df_year[f'norm_{args.signal}_{year}'].fillna(0)
            else:
                df_year[f'norm_{args.signal}_{year}'] = df_year[f'{args.signal}_{year}']
            # Only keep ticker and z-scores
            df_year = df_year[['ticker', f'norm_{args.signal}_{year}']]
            # Set ticker as index
            df_year = df_year.set_index('ticker')
            # Append to the dataframe (new column)
            df_weights = pd.concat([df_weights, df_year], axis=1)

    # fill nan values with ''
    df_weights = df_weights.fillna('')
    # Save the weights to a CSV file
    out_filename = f'./data/cissa_ranking_{args.signal}_{args.normalisation_strategy}'
    out_filename = out_filename + f'_{args.suffix}' if args.suffix else out_filename
    df_weights.to_csv(f"{out_filename}.csv")

    # fill nan values with ''
    df_raw = df_raw.fillna('')
    # Save the weights to a CSV file
    out_filename = f'./data/cissa_ranking_{args.signal}_{args.normalisation_strategy}_raw'
    out_filename = out_filename + f'_{args.suffix}' if args.suffix else out_filename
    df_raw.to_csv(f"{out_filename}.csv")


# Add argument parser
parser = argparse.ArgumentParser(description='Optimize portfolio through time')
parser.add_argument('--suffix', type=str, default=None,
                    help='Suffix to add to the output file')
parser.add_argument('--benchmark-weights', type=str, required=True,
                    help='The file containing the benchmark weights')
parser.add_argument('--universe-size', type=int, default=200,
                    help='The size of the universe to be considered')
parser.add_argument('--signal', type=str, default='ee',
                    choices=['ee', 'ep_1_Y', 'ep_3_Y', 'MB_ratio', 'RMB_ratio', 'MC_div_EP_1_Y', 'MB_div_EP_1_Y',
                             'MC_div_EP_1_Y_pred', 'MB_div_EP_1_Y_pred', 'EP_10_Y_pred'],
                    help='Choose the CISSA singal to optimize the portfolio')
parser.add_argument('--normalisation-strategy', type=str, default=None,
                    choices=['zscore', 'minmax', None, 'quantile-normal', 'market-cap'],
                    help='Choose the normalisation strategy for the CISSA signal')
if __name__ == "__main__":
    my_args = parser.parse_args()
    main(my_args)
