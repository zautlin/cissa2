import pandas as pd
import numpy as np


def main():

    # Load the data
    df = pd.read_csv('./data/aus_factors_since_1990_July.csv')
    print(df)

    # Convert to datetime
    df['Date'] = pd.to_datetime(df['Date'], format='%m/%d/%Y')

    # Calculate the annualized returns
    df['year'] = df['Date'].dt.year
    df['month'] = df['Date'].dt.month

    df_annual_output = pd.DataFrame(columns=['year', 'BAB', 'MKT', 'SMB', 'HML FF', 'HML Devil', 'UMD'])

    # Iterate over rows
    list_year_range = list(range(2002, 2023))
    counter = 0
    for slctd_year in list_year_range:

        # Select the data for the year
        df_year = df[df['year'] == slctd_year]

        # Calculate the annualized returns
        monthly_returns_bab = df_year['BAB']
        annual_returns_bab = np.prod(1 + monthly_returns_bab) ** (12 / len(monthly_returns_bab)) - 1
        monthly_returns_mkt = df_year['MKT']
        annual_returns_mkt = np.prod(1 + monthly_returns_mkt) ** (12 / len(monthly_returns_mkt)) - 1
        monthly_returns_smb = df_year['SMB']
        annual_returns_smb = np.prod(1 + monthly_returns_smb) ** (12 / len(monthly_returns_smb)) - 1
        monthly_returns_hml_ff = df_year['HML FF']
        annual_returns_hml_ff = np.prod(1 + monthly_returns_hml_ff) ** (12 / len(monthly_returns_hml_ff)) - 1
        monthly_returns_hml_devil = df_year['HML Devil']
        annual_returns_hml_devil = np.prod(1 + monthly_returns_hml_devil) ** (12 / len(monthly_returns_hml_devil)) - 1
        monthly_returns_umd = df_year['UMD']
        annual_returns_umd = np.prod(1 + monthly_returns_umd) ** (12 / len(monthly_returns_umd)) - 1

        # New row
        new_row = [slctd_year, annual_returns_bab, annual_returns_mkt, annual_returns_smb, annual_returns_hml_ff,
                   annual_returns_hml_devil, annual_returns_umd]
        df_annual_output.loc[counter] = new_row
        counter += 1

    # Save the data
    df_annual_output.to_csv('./data/aus_factors_since_2002_annual.csv', index=False)


if __name__ == "__main__":
    main()
