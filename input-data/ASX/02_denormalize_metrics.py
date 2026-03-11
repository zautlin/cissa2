#!/usr/bin/env python3
"""
Financial Metrics Denormalization Script
Transforms individual metric CSV files from WIDE format to LONG format
and consolidates them into a single fact table.

Usage:
    python3 02_denormalize_metrics.py <metric_dir> <output_file>

Example:
    python3 02_denormalize_metrics.py "./extracted-worksheets" "./consolidated-data/financial_metrics_fact_table.csv"

Process:
1. Identify all metric CSV files (fiscal and monthly)
2. Transform each from WIDE to LONG format
3. Consolidate into single fact table with consistent schema
4. Convert Excel date serials (MONTHLY periods) to ISO date format (YYYY-MM-DD)
5. Preserve all original data with no loss
"""

import sys
import csv
import json
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timedelta


def load_metric_config(config_path):
    """
    Load metric configuration from metric_units.json.
    Returns dict mapping worksheet_name (actual CSV filename) to database_name (canonical DB value).
    
    Logic:
      - worksheet_name (e.g., "Op Income.csv") → actual CSV filename to look for
      - database_name (e.g., "OPERATING_INCOME") → value to write to output CSV
    
    Example:
      "Revenue.csv" -> "REVENUE"
      "Op Income.csv" -> "OPERATING_INCOME"
      "Company TSR.csv" -> "COMPANY_TSR"
    """
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            metrics_config = json.load(f)
        
        # Build filename -> database_name mapping using worksheet_name from config
        metric_files = {}
        for metric_data in metrics_config:
            worksheet_name = metric_data.get('worksheet_name', '')
            database_name = metric_data.get('database_name', '')
            
            if not worksheet_name or not database_name:
                continue
            
            # Use worksheet_name directly as the filename
            # This is the source of truth for actual CSV filenames
            metric_files[worksheet_name] = database_name
        
        return metric_files
    
    except FileNotFoundError:
        print(f"❌ Error: Config file not found: {config_path}")
        print("Expected location: backend/database/config/metric_units.json")
        return None
    
    except json.JSONDecodeError as e:
        print(f"❌ Error: Invalid JSON in config file: {e}")
        return None
    
    except Exception as e:
        print(f"❌ Error loading config: {e}")
        return None


def identify_period_type(headers):
    """
    Identify if metric file has annual (FY) or monthly (numeric) periods.
    
    Annual: Columns like "FY 2002", "FY 2003"
    Monthly: Columns with numeric dates (Excel serials, typically 28-33 days apart)
    """
    # Check columns after standard metadata (Num, Ticker, Name, Data FX)
    if len(headers) > 4:
        sample = str(headers[4]).lower()
        if 'fy' in sample or 'year' in sample:
            return 'FISCAL'
    
    # Default to MONTHLY if not annual pattern (numeric date columns)
    return 'MONTHLY'


def extract_risk_free_rate_mapping_from_csv(csv_path):
    """
    Extract geography-to-index-ticker mapping from Rf.csv metadata rows.
    
    Rf.csv structure:
    - Row 1: Headers (Num, Code, Country, FX, Ticker, Bond Name, dates...)
    - Rows 2+: Data rows with one row per country/geography
    
    Returns:
        Dict mapping currency (FX) → ticker
        Example: {"AUD": "GACGB10 Index", "EUR": "GAGB10YR Index"}
    """
    mapping = {}
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            # Read first few rows (one per country)
            for i, row in enumerate(reader):
                if i >= 50:  # Safeguard: stop after 50 rows
                    break
                
                ticker = row.get('Ticker', '').strip()
                fx = row.get('FX', '').strip()
                
                if ticker and fx:
                    mapping[fx] = ticker  # FX code (AUD, EUR, etc.) → Ticker
        
        return mapping
    except Exception as e:
        print(f"  ⚠  Warning: Could not extract risk-free rate mapping from {csv_path}: {e}")
        return {}


def detect_dataset_geography(base_csv_path):
    """
    Detect dataset geography from Base.csv currency.
    
    Reads the first company row and extracts the Data FX column value.
    Defaults to "AUD" if detection fails.
    
    Returns:
        Currency code (e.g., "AUD", "USD", "GBP", "EUR")
    """
    try:
        with open(base_csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            first_row = next(reader)
            currency = first_row.get('Data FX', '').strip()
            if currency:
                print(f"  📍 Dataset geography detected: {currency}")
                return currency
    except FileNotFoundError:
        print(f"  ⚠  Warning: Base.csv not found at {base_csv_path}")
    except StopIteration:
        print(f"  ⚠  Warning: Base.csv is empty")
    except Exception as e:
        print(f"  ⚠  Warning: Could not detect geography from {base_csv_path}: {e}")
    
    # Default fallback
    print(f"  📍 Using default geography: AUD")
    return "AUD"


def convert_excel_date_to_iso(excel_serial):
    """
    Convert Excel date serial number to ISO format (YYYY-MM-DD).
    
    Excel epoch: December 30, 1899
    Example: 29920 -> 1981-12-14
    Example: 30008 -> 1982-03-12
    """
    try:
        # Excel's epoch is December 30, 1899
        excel_epoch = datetime(1899, 12, 30)
        # Add the serial number as days
        date_obj = excel_epoch + timedelta(days=int(excel_serial))
        # Return ISO format
        return date_obj.strftime('%Y-%m-%d')
    except (ValueError, TypeError):
        # If conversion fails, return original value
        return excel_serial


def process_metric_file(csv_path, metric_name, metric_dir, 
                       dataset_geography=None, rff_mapping=None):
    """
    Process a single metric CSV file and denormalize from WIDE to LONG format.
    
    Args:
        csv_path: Path to metric CSV file
        metric_name: Canonical metric name (e.g., "RISK_FREE_RATE")
        metric_dir: Directory containing metric files
        dataset_geography: Currency code of dataset (e.g., "AUD") - optional
        rff_mapping: Dict mapping currency → risk-free-rate ticker - optional
    
    Returns:
        List of tuples: (ticker, period, period_type, metric, value, currency)
    """
    records = []
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames
            
            if not headers:
                print(f"  ⊘ No headers found in {csv_path.name}")
                return records
            
            # Identify period type
            period_type = identify_period_type(headers)
            
            # Standard columns (metadata)
            standard_cols = {'Num', 'Ticker', 'Name', 'Data FX'}
            period_cols = [h for h in headers if h not in standard_cols]
            
            # Process each row (company/entity)
            for row in reader:
                ticker = row.get('Ticker', '').strip()
                currency = row.get('Data FX', '').strip()
                
                # Skip if no ticker
                if not ticker:
                    continue
                
                # RISK_FREE_RATE filtering: only ingest for the correct index for this geography
                if metric_name == "RISK_FREE_RATE":
                    if rff_mapping and dataset_geography:
                        allowed_ticker = rff_mapping.get(dataset_geography)
                        if allowed_ticker and ticker != allowed_ticker:
                            # Skip this ticker - not the risk-free rate index for this geography
                            continue
                    else:
                        # No mapping available - log warning and use default (Australia)
                        if dataset_geography and dataset_geography != "AUD":
                            print(f"    ⚠  Warning: Could not map risk-free rate for {dataset_geography}, using AUD default")
                            allowed_ticker = rff_mapping.get("AUD") if rff_mapping else None
                            if allowed_ticker and ticker != allowed_ticker:
                                continue
                
                # Process each period column
                for period_col in period_cols:
                    value = row.get(period_col, '').strip()
                    
                    # Skip empty values
                    if not value:
                        continue
                    
                    # Skip #N/A values
                    if value == '#N/A' or value == '#REF!':
                        continue
                    
                    # Create record tuple
                    # For MONTHLY periods, convert Excel serial to ISO date
                    period_value = period_col
                    if period_type == 'MONTHLY':
                        period_value = convert_excel_date_to_iso(period_col)
                    
                    record = (
                        ticker,
                        period_value,
                        period_type,
                        metric_name,
                        value,
                        currency
                    )
                    records.append(record)
        
        return records
    
    except Exception as e:
        print(f"  ❌ Error processing {csv_path.name}: {e}")
        return records


def denormalize_metrics(metric_dir, output_file, config_path=None):
    """
    Main function: Process all metric files and create denormalized fact table.
    
    Args:
        metric_dir: Directory containing metric CSV files
        output_file: Output CSV file path
        config_path: Path to metric_units.json config file
                    Defaults to backend/database/config/metric_units.json
    """
    # Determine config path if not provided
    if config_path is None:
        # Try to find config relative to script location
        script_dir = Path(__file__).parent
        # Go up to project root, then to backend/database/config
        config_path = script_dir.parent.parent / 'backend' / 'database' / 'config' / 'metric_units.json'
    
    # Load metric configuration
    METRIC_FILES = load_metric_config(config_path)
    
    if METRIC_FILES is None:
        sys.exit(1)
    
    metric_path = Path(metric_dir)
    
    if not metric_path.exists():
        print(f"❌ Error: Directory not found: {metric_dir}")
        sys.exit(1)
    
    output_path = Path(output_file)
    
    print("=" * 80)
    print("📊 FINANCIAL METRICS DENORMALIZATION")
    print("=" * 80)
    print(f"Metric directory: {metric_path}")
    print(f"Output file:      {output_path}")
    print(f"Config source:    {config_path}")
    print()
    
    # Extract risk-free rate mapping from Rf.csv
    print("Initializing geography-aware filtering:")
    rff_mapping = {}
    rff_csv_path = metric_path / 'Rf.csv'
    if rff_csv_path.exists():
        rff_mapping = extract_risk_free_rate_mapping_from_csv(rff_csv_path)
        if rff_mapping:
            print(f"  📊 Risk-free rate mapping extracted: {len(rff_mapping)} geographies")
            for fx, ticker in sorted(rff_mapping.items()):
                print(f"     {fx:3s} → {ticker}")
        else:
            print(f"  ⚠  Warning: No risk-free rate mapping extracted from Rf.csv")
    else:
        print(f"  ⚠  Warning: Rf.csv not found at {rff_csv_path}")
    
    # Detect dataset geography from Base.csv
    base_csv_path = metric_path / 'Base.csv'
    dataset_geography = detect_dataset_geography(base_csv_path)
    print()
    
    # Collect all records
    all_records = []
    stats = {
        'files_processed': 0,
        'files_found': 0,
        'total_records': 0,
        'fiscal_records': 0,
        'monthly_records': 0,
    }
    
    print("Processing metric files:")
    print()
    
    # Process each metric file
    for filename, database_name in sorted(METRIC_FILES.items()):
        csv_path = metric_path / filename
        
        if not csv_path.exists():
            print(f"  ⊘ {filename:25} → NOT FOUND")
            continue
        
        stats['files_found'] += 1
        print(f"  → {filename:25} ({database_name})")
        
        # Process the file with geography-aware parameters
        records = process_metric_file(
            csv_path, 
            database_name, 
            metric_path,
            dataset_geography=dataset_geography,
            rff_mapping=rff_mapping
        )
        
        if records:
            all_records.extend(records)
            
            # Count by period type
            fiscal_count = sum(1 for r in records if r[2] == 'FISCAL')
            monthly_count = sum(1 for r in records if r[2] == 'MONTHLY')
            
            # Show if RISK_FREE_RATE was filtered
            if database_name == 'RISK_FREE_RATE' and rff_mapping:
                allowed_ticker = rff_mapping.get(dataset_geography, "UNKNOWN")
                print(f"     ✓ Extracted {len(records):,} records (filtered to {allowed_ticker})")
            else:
                print(f"     ✓ Extracted {len(records):,} records")
            
            stats['files_processed'] += 1
            stats['total_records'] += len(records)
            stats['fiscal_records'] += fiscal_count
            stats['monthly_records'] += monthly_count
            
            if fiscal_count > 0:
                print(f"       - Fiscal:  {fiscal_count:,}")
            if monthly_count > 0:
                print(f"       - Monthly: {monthly_count:,}")
        else:
            print(f"     ⊘ No valid records found")
    
    print()
    
    # Verify we found files
    if stats['files_processed'] == 0:
        print("❌ Error: No metric files found to process")
        sys.exit(1)
    
    # Write fact table CSV
    print(f"Writing fact table: {output_path}")
    
    try:
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Write header
            writer.writerow(['Ticker', 'Period', 'Period_Type', 'Metric', 'Value', 'Currency'])
            
            # Write all records
            writer.writerows(all_records)
        
        print(f"✓ Fact table created successfully")
        
    except Exception as e:
        print(f"❌ Error writing fact table: {e}")
        sys.exit(1)
    
    # Print summary
    print()
    print("=" * 80)
    print("✅ DENORMALIZATION COMPLETE")
    print("=" * 80)
    print(f"Metric files found:      {stats['files_found']}")
    print(f"Metric files processed:  {stats['files_processed']}")
    print(f"Total records created:   {stats['total_records']:,}")
    print(f"  - Fiscal records:      {stats['fiscal_records']:,}")
    print(f"  - Monthly records:     {stats['monthly_records']:,}")
    print(f"Output file:             {output_path}")
    print(f"File size:               {output_path.stat().st_size / (1024*1024):.2f} MB")
    print("=" * 80)
    print()
    
    # Print data dimensions
    print("Data Dimensions:")
    
    # Count unique values
    tickers = set(r[0] for r in all_records)
    periods = set(r[1] for r in all_records)
    metrics = set(r[3] for r in all_records)
    currencies = set(r[5] for r in all_records)
    
    print(f"  Unique tickers:    {len(tickers)}")
    print(f"  Unique periods:    {len(periods)}")
    print(f"  Unique metrics:    {len(metrics)}")
    print(f"  Unique currencies: {len(currencies)}")
    print()
    
    print("Metrics included:")
    for metric in sorted(metrics):
        print(f"  • {metric}")
    print()


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 02_denormalize_metrics.py <metric_dir> <output_file>")
        print()
        print("Example:")
        print('  python3 02_denormalize_metrics.py "./extracted-worksheets" "./consolidated-data/financial_metrics_fact_table.csv"')
        sys.exit(1)
    
    metric_dir = sys.argv[1]
    output_file = sys.argv[2]
    
    denormalize_metrics(metric_dir, output_file)
