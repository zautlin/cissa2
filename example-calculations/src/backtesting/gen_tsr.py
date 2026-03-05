'''
Script to extract the annual TSR for each company

'''
import pandas as pd

from src.engine.sql import execute_select


def main():

    # Query to extract the market capitalization of all the companies per year
    sql = """
            SELECT * FROM "USR".annual_data
            WHERE "key" = 'FY TSR';
        """
    df_tsr = execute_select(sql)

    # Treat value as float
    df_tsr['value'] = df_tsr['value'].astype(float)

    # Obtain year range
    years = df_tsr['fy_year'].unique()
    years.sort()

    # Create a pandas dataframe to store the weights for each year
    df_weights = pd.DataFrame(columns=['ticker']).set_index('ticker')

    # For each year, select the top 200 companies by market capitalization
    for year in years:
        if int(year) < 2023:
            # Select year
            df_year = df_tsr[df_tsr['fy_year'] == year]
            # Sort by market capitalization (descending)
            df_year = df_year.sort_values(by='value', ascending=False)
            # reset index
            df_year = df_year.reset_index(drop=True)
            # Normalize the market capitalization
            df_year[f'tsr_{year}'] = df_year['value'] / 100
            # Only keep ticker and weights
            df_year = df_year[['ticker', f'tsr_{year}']]
            # Set ticker as index
            df_year = df_year.set_index('ticker')
            # Append to the dataframe (new column)
            df_weights = pd.concat([df_weights, df_year], axis=1)

    # Save the weights to a CSV file
    df_weights.to_csv('./data/universe_tsr_2002_2022.csv')


if __name__ == "__main__":
    main()
