'''
Script to map ticker symbols on the MSCI file and the bloomberg file (the one used for CISSA)
'''
import pandas as pd


def main():

    list_bloomberg_tickers = pd.read_csv('./data/benchmark_weights.csv')['ticker'].tolist()
    list_bloomberg_tickers = [ticker.strip().replace(' AU Equity', '') for ticker in list_bloomberg_tickers]
    list_msci_tickers = pd.read_csv('./data/msci_weights.csv')['Ticker'].unique().tolist()

    print(f'number of unique MSCI tickers -> {len(list_msci_tickers)}')

    # Check if all tickers in bloomberg are in msci
    counter = 0
    list_missing = []
    for ticker in list_msci_tickers:
        ticker_clean = ticker.split()[0]
        if ticker_clean not in list_bloomberg_tickers:
            counter += 1
            list_missing.append(ticker)
            print(f'{ticker} not in bloomberg')

    print(f'Number of tickers not matching -> {counter}')

    df_out = pd.DataFrame()
    df_out['missing_tickers'] = list_missing
    df_out.to_csv('./data/missing_tickers.csv', index=False)


if __name__ == '__main__':
    main()
