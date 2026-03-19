#!/usr/bin/env python3
"""
Manual TER calculation for CSL to validate the corrected formula.
Uses interval-based lag for Load TRTE calculation.
"""

import pandas as pd
import numpy as np

# CSL data extracted from database
data = {
    'fiscal_year': [2000, 2001, 2002, 2003, 2004, 2005, 2006, 2007, 2008, 2009, 2010],
    'Calc MC': [
        4924.72566, 7139.16359, 5099.5646, 1911.27105, 4380.79932, 
        6348.54533, 9776.53375, 16107.696, 19649.30142, 19265.54671, 17908.99468
    ],
    'Calc KE': [0.1, 0.095, 0.095, 0.095, 0.1, 0.105, 0.105, 0.115, 0.115, 0.105, 0.105],
    'Calc 1Y FV ECF': [np.nan, 20.796542, -251.137285, 15.701425, -745.867586, 368.836545, 513.461505, 129.102816, 189.194697, -1315.98846, 2037.049669],
    'Calc 3Y FV ECF': [np.nan, np.nan, -249.203669, -235.372383, -1128.25811, -358.460701, 288.646130, 1093.849274, 892.622722, -1296.01485, 1222.316020],
    'Calc 5Y FV ECF': [np.nan, np.nan, np.nan, np.nan, -1300.893463, -689.191919, 118.656930, 527.135052, 775.116044, -669.891939, 2148.598536],
    'Calc 10Y FV ECF': [np.nan, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan, -2545.402491, 2845.713664]
}

df = pd.DataFrame(data)

print("=" * 100)
print("CSL TER MANUAL CALCULATION WITH INTERVAL-BASED LAG")
print("=" * 100)

def calculate_ter_interval(df, interval, fv_ecf_col):
    """Calculate TER for a specific interval using correct interval-based lag."""
    results = []
    
    for idx, row in df.iterrows():
        year = int(row['fiscal_year'])
        
        # Get FV ECF value
        fv_ecf = row[fv_ecf_col]
        if pd.isna(fv_ecf):
            results.append({
                'year': year,
                'interval': interval,
                'status': 'NULL - no FV ECF',
                'open_mc': np.nan,
                'load_trte': np.nan,
                'load_ter': np.nan,
                'calc_ke': row['Calc KE'],
                'wc': np.nan,
                'wp': np.nan,
                'ter': np.nan
            })
            continue
        
        # Get current year Calc MC
        calc_mc_current = row['Calc MC']
        
        # Get Calc MC from N years ago (interval-based lag)
        lag_year = year - interval
        lag_mc_rows = df[df['fiscal_year'] == lag_year]
        
        if len(lag_mc_rows) == 0:
            results.append({
                'year': year,
                'interval': interval,
                'status': f'NULL - no data {interval} years ago ({lag_year})',
                'open_mc': np.nan,
                'load_trte': np.nan,
                'load_ter': np.nan,
                'calc_ke': row['Calc KE'],
                'wc': np.nan,
                'wp': np.nan,
                'ter': np.nan
            })
            continue
        
        calc_mc_lag = lag_mc_rows.iloc[0]['Calc MC']
        
        # Step 1: Calculate Load TRTE
        # Load TRTE = Calc {interval}Y FV ECF + (Calc MC(year) - Calc MC(year - interval))
        load_trte = fv_ecf + (calc_mc_current - calc_mc_lag)
        
        # Step 2: Calculate Load TER
        # Load TER = (1 + Load TRTE / Open MC)^(1/interval) - 1
        open_mc = calc_mc_lag
        exponent_ter = 1.0 / interval
        
        if open_mc == 0:
            load_ter = np.nan
        else:
            load_ter = np.power(1 + (load_trte / open_mc), exponent_ter) - 1
        
        # Step 3: Calculate WC and WP
        # WC = Open MC × (1 + Load TER)^interval - Open MC × (1 + Calc KE)^interval
        # WP = Open MC × (1 + Calc KE)^interval
        calc_ke = row['Calc KE']
        
        if pd.isna(load_ter):
            wc = np.nan
            wp = np.nan
            ter = np.nan
        else:
            wc = open_mc * np.power(1 + load_ter, interval) - open_mc * np.power(1 + calc_ke, interval)
            wp = open_mc * np.power(1 + calc_ke, interval)
            
            # Step 4: Calculate final TER
            # TER = ((WC + WP) / Open MC)^(1/interval) - 1
            ratio_wc_wp = (wc + wp) / open_mc
            ter = np.power(ratio_wc_wp, exponent_ter) - 1
        
        results.append({
            'year': year,
            'interval': interval,
            'status': 'CALCULATED',
            'lag_year': lag_year,
            'fv_ecf': fv_ecf,
            'calc_mc_current': calc_mc_current,
            'calc_mc_lag': calc_mc_lag,
            'mc_change': calc_mc_current - calc_mc_lag,
            'open_mc': open_mc,
            'load_trte': load_trte,
            'load_ter': load_ter,
            'calc_ke': calc_ke,
            'wc': wc,
            'wp': wp,
            'ter': ter
        })
    
    return pd.DataFrame(results)

# Calculate for all intervals
intervals = [1, 3, 5, 10]
all_results = []

for interval in intervals:
    fv_ecf_col = f'Calc {interval}Y FV ECF'
    results = calculate_ter_interval(df, interval, fv_ecf_col)
    all_results.append(results)

# Print results for each interval
for interval in intervals:
    print(f"\n{'=' * 100}")
    print(f"INTERVAL: {interval}Y TER")
    print(f"{'=' * 100}")
    
    results = all_results[interval - 1] if interval == 1 else all_results[intervals.index(interval)]
    
    # Only show calculated rows
    calc_rows = results[results['status'] == 'CALCULATED']
    
    for _, row in calc_rows.iterrows():
        print(f"\nYear {int(row['year'])}:")
        print(f"  Status: {row['status']}")
        print(f"  Lookback period: {int(row['lag_year'])} to {int(row['year'])}")
        print(f"  FV ECF: {row['fv_ecf']:.2f}")
        print(f"  Calc MC ({int(row['year'])}): {row['calc_mc_current']:.2f}")
        print(f"  Calc MC ({int(row['lag_year'])}): {row['calc_mc_lag']:.2f}")
        print(f"  MC Change: {row['mc_change']:.2f}")
        print(f"  Open MC: {row['open_mc']:.2f}")
        print(f"  Load TRTE: {row['load_trte']:.2f}")
        print(f"  Load TER: {row['load_ter']:.6f} ({row['load_ter']*100:.2f}%)")
        print(f"  Calc KE: {row['calc_ke']:.6f} ({row['calc_ke']*100:.2f}%)")
        print(f"  WC: {row['wc']:.2f}")
        print(f"  WP: {row['wp']:.2f}")
        print(f"  >>> TER: {row['ter']:.6f} ({row['ter']*100:.2f}%)")

# Summary table for key years
print(f"\n{'=' * 100}")
print("SUMMARY: KEY VALIDATION POINTS")
print(f"{'=' * 100}")

summary_points = [
    (2001, 1),
    (2003, 3),
    (2005, 5),
    (2010, 10)
]

for year, interval in summary_points:
    results = all_results[intervals.index(interval)]
    row = results[(results['year'] == year) & (results['status'] == 'CALCULATED')]
    
    if len(row) > 0:
        row = row.iloc[0]
        print(f"\nCSL {year} {interval}Y TER:")
        print(f"  Calculated TER: {row['ter']:.6f} ({row['ter']*100:.2f}%)")
    else:
        null_row = results[results['year'] == year]
        if len(null_row) > 0:
            print(f"\nCSL {year} {interval}Y TER: NULL ({null_row.iloc[0]['status']})")
