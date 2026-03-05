'''
Script to generate benchmark weights for the ASX200 index

Note: We are selecting the top 200 companies according to market capitalization
from a subset of 500 companies, which are the highest valued companies in the ASX
on 2023.
'''
import argparse

import pandas as pd

from src.engine.sql import execute_select


def main(args):

    # Query to extract the market capitalization of all the companies per year
    sql = """
            SELECT * FROM "USR".metrics
            WHERE "key" = 'mc';
    """
    df_metrics = execute_select(sql)

    # Download company data too
    sql = """
            SELECT DISTINCT ticker, bics_1 FROM "USR".company;
    """
    df_company = execute_select(sql)
    df_company['bics_1'] = df_company['bics_1'].apply(lambda x: x.strip())
    df_company.to_csv('./data/company_bics_1.csv', index=False)

    # Treat value as float
    df_metrics['value'] = df_metrics['value'].astype(float)

    # Obtain year range
    years = df_metrics['fy_year'].unique()
    years.sort()

    # Create a pandas dataframe to store the weights for each year
    if args.partition_by_mc:
        df_weights_small = pd.DataFrame(columns=['ticker']).set_index('ticker')
        df_weights_large = pd.DataFrame(columns=['ticker']).set_index('ticker')
    else:
        df_weights = pd.DataFrame(columns=['ticker']).set_index('ticker')

    # For each year, select the top 200 companies by market capitalization
    for year in years:
        if int(year) < 2023:
            # Select year
            df_year = df_metrics[df_metrics['fy_year'] == year]
            # Convert nan values to 0
            df_year['value'] = df_year['value'].fillna(0)
            # Sort by market capitalization (descending)
            df_year = df_year.sort_values(by='value', ascending=False)
            # reset index
            df_year = df_year.reset_index(drop=True)
            # Set the value column of any ticker below the top 200 to zero (according to index)
            df_year.loc[200:, 'value'] = 0
            if args.partition_by_mc:
                # Small cap
                df_year_small = df_year[args.partition_by_mc:]
                df_year_small[f'weigths_{year}'] = df_year_small['value'] / df_year_small['value'].sum()
                df_year_small = df_year_small[['ticker', f'weigths_{year}']]
                df_year_small = df_year_small.set_index('ticker')
                # Append to the dataframe (new column)
                df_weights_small = pd.concat([df_weights_small, df_year_small], axis=1)
                # Large cap
                df_year_large = df_year[:args.partition_by_mc]
                df_year_large[f'weigths_{year}'] = df_year_large['value'] / df_year_large['value'].sum()
                df_year_large = df_year_large[['ticker', f'weigths_{year}']]
                df_year_large = df_year_large.set_index('ticker')
                # Append to the dataframe (new column)
                df_weights_large = pd.concat([df_weights_large, df_year_large], axis=1)
            else:
                # Normalize the market capitalization
                df_year[f'weigths_{year}'] = df_year['value'] / df_year['value'].sum()
                # Only keep ticker and weights
                df_year = df_year[['ticker', f'weigths_{year}']]
                # Set ticker as index
                df_year = df_year.set_index('ticker')
                # Append to the dataframe (new column)
                df_weights = pd.concat([df_weights, df_year], axis=1)

    # Save the weights to a CSV file
    if args.partition_by_mc:
        df_weights_small.to_csv('./data/benchmark_weights_small_cap.csv')
        df_weights_large.to_csv('./data/benchmark_weights_large_cap.csv')
    else:
        df_weights.to_csv('./data/benchmark_weights.csv')


# Add argument parser
parser = argparse.ArgumentParser(description='Optimize portfolio through time')
parser.add_argument('--partition-by-mc', type=int, default=None,
                    help='Partitioning the universe by market capitalization (top vs bottom)')
parser.add_argument('--universe-size', type=int, default=200,
                    help='Number of companies in the expanded universe')
if __name__ == "__main__":
    my_args = parser.parse_args()
    main(my_args)
