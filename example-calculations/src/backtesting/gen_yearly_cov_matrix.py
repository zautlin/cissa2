'''
Script to generate yearly covariance matrices from the monthly Company TSR dataset

Note: We calculate the covariance matrices for the top 200 companies according to market capitalization
Or do we build the covariance matrices with all the 500 companies???
'''
import argparse
import os

import pandas as pd

from src.engine.sql import execute_select


def main(args):

    # Create directory if it does not exist
    if not os.path.exists(f'./data/cov_matrices_{args.suffix}'):
        os.makedirs(f'./data/cov_matrices_{args.suffix}')

    # Load benchmark weights
    df_benchmark_weights = pd.read_csv(args.benchmark_weights)

    # Query to extract the market capitalization of all the companies per year
    sql = """
            SELECT * FROM "USR".monthly_data
            WHERE "key" = 'Company TSR';
    """
    df_tsr = execute_select(sql)

    # Convert date to datetime
    df_tsr['date'] = pd.to_datetime(df_tsr['date'], format='%Y-%m-%d')
    # Treat value as float
    df_tsr['value'] = df_tsr['value'].astype(float)

    # Obtain year range
    years = list(range(2002, 2023))

    # For each year, select the top 200 companies by market capitalization
    for year in years:
        print(f'Processing year -> {year}')
        if int(year) < 2023:
            # Select year
            df_tsr_year = df_tsr[df_tsr['date'].dt.year <= year]
            # Sort benchmark companies in the current year
            df_benchmark_year = df_benchmark_weights[['ticker', f'weigths_{year}']].sort_values(by=f'weigths_{year}',
                                                                                                ascending=False)
            # Select top 200 companies
            list_companies = df_benchmark_year['ticker'].tolist()[:args.universe_size]
            # Subset of data
            df_tsr_year.set_index('ticker', inplace=True)
            df_tsr_year = df_tsr_year.loc[list_companies].reset_index()
            # Annualise and convert to fraction
            df_tsr_year['value'] = df_tsr_year['value'] / 100
            # Build covariance matrix with all the historic data of each ticker up to the year
            df_tsr_year = df_tsr_year.pivot(index='date', columns='ticker', values='value')
            # Fillna with zero
            df_tsr_year = df_tsr_year.fillna(0.0)
            # Calculate the covariance matrix
            df_cov_matrix = df_tsr_year.cov()
            # annualised
            df_cov_matrix = df_cov_matrix * 12
            # Save covariance matrix to a CSV file
            df_cov_matrix.to_csv(f'./data/cov_matrices_{args.suffix}/cov_matrix_{year}.csv')


parser = argparse.ArgumentParser(description='Optimize portfolio through time')
parser.add_argument('--suffix', type=str, default=None,
                    help='Suffix to add to the output file')
parser.add_argument('--benchmark-weights', type=str, required=True,
                    help='The file containing the benchmark weights')
parser.add_argument('--universe-size', type=int, default=200,
                    help='The size of the universe to be considered')
if __name__ == "__main__":
    my_args = parser.parse_args()
    main(my_args)
