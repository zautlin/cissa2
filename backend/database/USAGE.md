# Financial Data Pipeline - Usage Guide

**Last Updated**: 2026-03-03  
**Python Version**: 3.8+  
**Database**: PostgreSQL 16

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Common Usage Patterns](#common-usage-patterns)
3. [API Reference](#api-reference)
4. [Advanced Patterns](#advanced-patterns)
5. [FAQ](#faq)
6. [Troubleshooting](#troubleshooting)

---

## Quick Start

### Installation

```bash
# Clone repository
cd /home/ubuntu/cissa

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install pandas sqlalchemy psycopg2-binary
```

### Basic Pipeline Execution

```python
from backend.database.etl.config import engine
from backend.database.etl.ingestion import Ingester
from backend.database.etl.processing import DataQualityProcessor
from sqlalchemy import text
from datetime import datetime

# Step 1: Create dataset version
with engine.begin() as conn:
    result = conn.execute(text("""
        INSERT INTO dataset_versions (dataset_name, version_number, status)
        VALUES ('ASX_' || to_char(NOW(), 'YYYYMMDD'), 1, 'PENDING')
        RETURNING dataset_id
    """))
    dataset_id = result.scalar()

print(f"Created dataset: {dataset_id}")

# Step 2: Ingest raw data
ingester = Ingester(engine)
ingest_result = ingester.load_dataset(
    dataset_id=dataset_id,
    csv_path="input-data/ASX/consolidated-data/financial_metrics_fact_table.csv",
    base_csv_path="input-data/ASX/extracted-worksheets/Base.csv",
    fy_dates_csv_path="input-data/ASX/extracted-worksheets/FY Dates.csv"
)
print(f"Ingested: {ingest_result['total_rows']} rows")

# Step 3: Process (FY align + impute)
processor = DataQualityProcessor(engine)
process_result = processor.process_dataset(dataset_id=dataset_id)
print(f"Processed: {process_result['fundamentals_rows']} fundamentals rows")

# Step 4: Query cleaned data
with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT ticker, metric_name, fiscal_year, value, imputation_source
        FROM fundamentals
        WHERE dataset_id = :dataset_id
        LIMIT 10
    """), {"dataset_id": dataset_id})
    
    for row in result:
        print(f"{row}")
```

---

## Common Usage Patterns

### Pattern 1: Load Reference Data (One-Time Setup)

```python
from backend.database.etl.ingestion import Ingester
from backend.database.etl.config import engine

ingester = Ingester(engine)

# Load static reference tables
ingester.load_reference_tables(
    base_csv="input-data/ASX/extracted-worksheets/Base.csv",
    fy_dates_csv="input-data/ASX/extracted-worksheets/FY Dates.csv",
    metrics_csv="input-data/ASX/consolidated-data/financial_metrics_fact_table.csv"
)

print("✓ Reference data loaded")
```

---

### Pattern 2: Process a Single Bloomberg Upload

```python
from backend.database.etl.ingestion import Ingester
from backend.database.etl.processing import DataQualityProcessor
from backend.database.etl.config import engine
from sqlalchemy import text
import uuid

# Create dataset version
dataset_id = str(uuid.uuid4())
with engine.begin() as conn:
    conn.execute(text("""
        INSERT INTO dataset_versions (dataset_id, dataset_name, version_number, status)
        VALUES (:dataset_id, :name, 1, 'PENDING')
    """), {
        "dataset_id": dataset_id,
        "name": f"Bloomberg_Upload_{dataset_id[:8]}"
    })

# Stage 1: Ingest
ingester = Ingester(engine)
ingest_result = ingester.load_dataset(
    dataset_id=dataset_id,
    csv_path="input-data/ASX/consolidated-data/financial_metrics_fact_table.csv",
    base_csv_path="input-data/ASX/extracted-worksheets/Base.csv",
    fy_dates_csv_path="input-data/ASX/extracted-worksheets/FY Dates.csv"
)

print(f"Stage 1 complete: {ingest_result['valid_rows']} valid rows")

# Stage 2: Process
processor = DataQualityProcessor(engine)
process_result = processor.process_dataset(dataset_id=dataset_id)

print(f"Stage 2 complete: {process_result['fundamentals_rows']} fundamentals")
print(f"Dataset {dataset_id} ready for downstream analysis")
```

---

### Pattern 3: Query Cleaned Data by Company

```python
from backend.database.etl.config import engine
from sqlalchemy import text

dataset_id = "550e8400-e29b-41d4-a716-446655440000"
ticker = "ANZ"

with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT 
            metric_name,
            fiscal_year,
            value,
            imputation_source,
            confidence_level,
            data_quality_flags
        FROM fundamentals
        WHERE dataset_id = :dataset_id 
          AND ticker = :ticker
        ORDER BY fiscal_year DESC, metric_name
    """), {"dataset_id": dataset_id, "ticker": ticker})
    
    for row in result:
        print(f"{row.fiscal_year} {row.metric_name}: {row.value} ({row.imputation_source})")
```

**Output**:
```
2024 Net Income: 5432000 (RAW)
2024 Revenue: 32100000 (RAW)
2023 Net Income: 5100000 (FORWARD_FILL)
2023 Revenue: 30500000 (RAW)
```

---

### Pattern 4: Analyze Imputation Distribution

```python
from backend.database.etl.config import engine
from sqlalchemy import text

dataset_id = "550e8400-e29b-41d4-a716-446655440000"

with engine.connect() as conn:
    # Distribution by imputation source
    print("Imputation Distribution:")
    result = conn.execute(text("""
        SELECT 
            imputation_source,
            COUNT(*) as count,
            ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) as percentage
        FROM fundamentals
        WHERE dataset_id = :dataset_id
        GROUP BY imputation_source
        ORDER BY count DESC
    """), {"dataset_id": dataset_id})
    
    for row in result:
        print(f"  {row.imputation_source}: {row.count} ({row.percentage}%)")
    
    # By metric type
    print("\nBy Metric Type:")
    result = conn.execute(text("""
        SELECT 
            m.metric_type,
            COUNT(*) as count
        FROM fundamentals f
        JOIN metrics_catalog m ON f.metric_name = m.metric_name
        WHERE f.dataset_id = :dataset_id
        GROUP BY m.metric_type
    """), {"dataset_id": dataset_id})
    
    for row in result:
        print(f"  {row.metric_type}: {row.count}")
```

**Output**:
```
Imputation Distribution:
  RAW: 35000 (72.92%)
  FORWARD_FILL: 5000 (10.42%)
  INTERPOLATED: 4000 (8.33%)
  SECTOR_MEDIAN: 3000 (6.25%)
  MARKET_MEDIAN: 1000 (2.08%)
  MISSING: 0 (0.00%)

By Metric Type:
  FISCAL: 40000
  MONTHLY: 8000
```

---

### Pattern 5: Validation Report

```python
from backend.database.etl.config import engine
from sqlalchemy import text

dataset_id = "550e8400-e29b-41d4-a716-446655440000"

with engine.connect() as conn:
    # Check ingestion validation
    print("Raw Data Validation Report:")
    result = conn.execute(text("""
        SELECT 
            validation_status,
            COUNT(*) as count
        FROM raw_data
        WHERE dataset_id = :dataset_id
        GROUP BY validation_status
    """), {"dataset_id": dataset_id})
    
    for row in result:
        print(f"  {row.validation_status}: {row.count}")
    
    # Rejection reasons
    print("\nRejection Reasons:")
    result = conn.execute(text("""
        SELECT 
            rejection_reason,
            COUNT(*) as count
        FROM raw_data
        WHERE dataset_id = :dataset_id
          AND validation_status = 'REJECTED'
        GROUP BY rejection_reason
        ORDER BY count DESC
        LIMIT 10
    """), {"dataset_id": dataset_id})
    
    for row in result:
        print(f"  {row.rejection_reason}: {row.count}")
    
    # Data quality summary
    print("\nData Quality Summary:")
    result = conn.execute(text("""
        SELECT 
            quality_metadata ->> 'total_raw_values' as total_raw,
            quality_metadata ->> 'valid_raw_values' as valid_raw,
            quality_metadata ->> 'imputation_attempts' as imputation_attempts,
            quality_metadata ->> 'successful_imputations' as successful_imputations
        FROM dataset_versions
        WHERE dataset_id = :dataset_id
    """), {"dataset_id": dataset_id})
    
    row = result.first()
    if row:
        print(f"  Total raw values: {row.total_raw}")
        print(f"  Valid raw values: {row.valid_raw}")
        print(f"  Imputation attempts: {row.imputation_attempts}")
        print(f"  Successful imputations: {row.successful_imputations}")
```

---

### Pattern 6: Time Series Analysis

```python
from backend.database.etl.config import engine
from sqlalchemy import text

dataset_id = "550e8400-e29b-41d4-a716-446655440000"
ticker = "NAB"
metric = "Net Income"

with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT 
            fiscal_year,
            value,
            imputation_source,
            confidence_level
        FROM fundamentals
        WHERE dataset_id = :dataset_id
          AND ticker = :ticker
          AND metric_name = :metric
        ORDER BY fiscal_year
    """), {
        "dataset_id": dataset_id,
        "ticker": ticker,
        "metric": metric
    })
    
    print(f"Time Series: {ticker} {metric}")
    print("-" * 50)
    for row in result:
        confidence_indicator = "✓" if row.confidence_level >= 0.9 else "⚠"
        print(f"{row.fiscal_year}: {row.value:>12} {confidence_indicator} {row.imputation_source}")
```

---

### Pattern 7: Cross-Company Comparison

```python
from backend.database.etl.config import engine
from sqlalchemy import text

dataset_id = "550e8400-e29b-41d4-a716-446655440000"
fiscal_year = 2024
metric = "Revenue"

with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT 
            f.ticker,
            f.value,
            f.imputation_source,
            c.sector
        FROM fundamentals f
        JOIN companies c ON f.ticker = c.ticker
        WHERE f.dataset_id = :dataset_id
          AND f.fiscal_year = :fiscal_year
          AND f.metric_name = :metric
        ORDER BY f.value DESC
        LIMIT 20
    """), {
        "dataset_id": dataset_id,
        "fiscal_year": fiscal_year,
        "metric": metric
    })
    
    print(f"Top 20 by {metric} (FY {fiscal_year})")
    print("-" * 60)
    for row in result:
        print(f"{row.ticker:8} {row.sector:20} {row.value:>15} ({row.imputation_source})")
```

---

## API Reference

### Ingester Class

```python
from backend.database.etl.ingestion import Ingester

ingester = Ingester(engine)
```

#### Methods

##### `load_reference_tables(base_csv, fy_dates_csv, metrics_csv)`

Load static reference data (one-time setup).

```python
ingester.load_reference_tables(
    base_csv="input-data/ASX/extracted-worksheets/Base.csv",
    fy_dates_csv="input-data/ASX/extracted-worksheets/FY Dates.csv",
    metrics_csv="input-data/ASX/consolidated-data/financial_metrics_fact_table.csv"
)
```

**Parameters:**
- `base_csv` (str): Path to Base.csv containing company master data
- `fy_dates_csv` (str): Path to FY Dates.csv containing fiscal year mappings
- `metrics_csv` (str): Path to financial metrics fact table CSV

**Returns:** None

**Raises:** 
- `FileNotFoundError`: If any CSV file not found
- `ValueError`: If CSV format invalid

---

##### `load_dataset(dataset_id, csv_path, base_csv_path, fy_dates_csv_path)`

Load raw financial data for a dataset (Stage 1 - Ingestion).

```python
result = ingester.load_dataset(
    dataset_id="550e8400-e29b-41d4-a716-446655440000",
    csv_path="input-data/ASX/consolidated-data/financial_metrics_fact_table.csv",
    base_csv_path="input-data/ASX/extracted-worksheets/Base.csv",
    fy_dates_csv_path="input-data/ASX/extracted-worksheets/FY Dates.csv"
)
```

**Parameters:**
- `dataset_id` (str): UUID of dataset_versions record
- `csv_path` (str): Path to financial metrics CSV to ingest
- `base_csv_path` (str): Path to Base.csv for company reference
- `fy_dates_csv_path` (str): Path to FY Dates.csv for FY mapping

**Returns:** Dictionary with:
- `total_rows` (int): Total rows processed
- `valid_rows` (int): Rows that passed validation
- `invalid_rows` (int): Rows that failed validation
- `dataset_id` (str): UUID of loaded dataset

**Example:**
```python
result = ingester.load_dataset(
    dataset_id=dataset_id,
    csv_path="input-data/ASX/consolidated-data/financial_metrics_fact_table.csv",
    base_csv_path="input-data/ASX/extracted-worksheets/Base.csv",
    fy_dates_csv_path="input-data/ASX/extracted-worksheets/FY Dates.csv"
)
print(f"Valid: {result['valid_rows']}, Invalid: {result['invalid_rows']}")
```

---

### DataQualityProcessor Class

```python
from backend.database.etl.processing import DataQualityProcessor

processor = DataQualityProcessor(engine)
```

#### Methods

##### `process_dataset(dataset_id)`

Run FY alignment + 7-step imputation cascade (Stage 2 - Processing).

```python
result = processor.process_dataset(dataset_id="550e8400-e29b-41d4-a716-446655440000")
```

**Parameters:**
- `dataset_id` (str): UUID of dataset_versions record to process

**Returns:** Dictionary with:
- `fundamentals_rows` (int): Total rows written to fundamentals table
- `imputation_sources` (dict): Count of each imputation source
  - Example: `{'RAW': 35000, 'FORWARD_FILL': 5000, ...}`
- `dataset_id` (str): UUID of processed dataset
- `status` (str): Final status ('PROCESSED' or 'ERROR')
- `error_message` (str, optional): If status is 'ERROR'

**Example:**
```python
result = processor.process_dataset(dataset_id=dataset_id)
print(f"Fundamentals rows: {result['fundamentals_rows']}")
print(f"Imputation sources: {result['imputation_sources']}")
```

---

### FYAligner Class

```python
from backend.database.etl.fy_aligner import FYAligner
from backend.database.etl.config import engine

aligner = FYAligner(engine)
```

#### Methods

##### `align_to_fiscal_year(ticker, calendar_year, period_type)`

Map calendar year to fiscal year.

```python
fy = aligner.align_to_fiscal_year(
    ticker="ANZ",
    calendar_year=2024,
    period_type="ANNUAL"
)
```

**Parameters:**
- `ticker` (str): Company ticker
- `calendar_year` (int): Calendar year to align
- `period_type` (str): 'ANNUAL' or 'MONTHLY'

**Returns:** Fiscal year (int)

**Raises:**
- `KeyError`: If company not found or FY mapping not available

---

### ImputationCascade Class

```python
from backend.database.etl.imputation_engine import ImputationCascade
from backend.database.etl.config import engine

cascade = ImputationCascade(engine)
```

#### Methods

##### `impute_value(ticker, metric_name, fiscal_year, raw_value)`

Execute 7-step imputation cascade for a single value.

```python
result = cascade.impute_value(
    ticker="ANZ",
    metric_name="Revenue",
    fiscal_year=2024,
    raw_value=None  # Will be imputed
)
```

**Parameters:**
- `ticker` (str): Company ticker
- `metric_name` (str): Metric name
- `fiscal_year` (int): Fiscal year
- `raw_value` (float or None): Raw value (None if missing)

**Returns:** Dictionary with:
- `value` (float): Imputed or raw value
- `source` (str): One of RAW, FORWARD_FILL, BACKWARD_FILL, INTERPOLATE, SECTOR_MEDIAN, MARKET_MEDIAN, MISSING
- `confidence_level` (float): 0.0-1.0 confidence score

**Example:**
```python
result = cascade.impute_value(
    ticker="ANZ",
    metric_name="Revenue",
    fiscal_year=2023,
    raw_value=None
)
print(f"Imputed: {result['value']} ({result['source']})")
```

---

### Validators

```python
from backend.database.etl.validators import validate_numeric

# Validate a string value to extract numeric value
result = validate_numeric("$1,234,567.89")
```

#### Functions

##### `validate_numeric(value_string)`

Extract numeric value from string, handling currency, percentages, thousands separators.

**Parameters:**
- `value_string` (str): Raw string value from Excel

**Returns:** Tuple of (float or None, error_message or None)

**Example:**
```python
# Valid numbers
validate_numeric("1234.56")  # → (1234.56, None)
validate_numeric("$1,234.56")  # → (1234.56, None)
validate_numeric("1,234%")  # → (1234.0, None)
validate_numeric("-$5.5M")  # → (-5500000.0, None)

# Invalid numbers
validate_numeric("N/A")  # → (None, "Non-numeric marker")
validate_numeric("")  # → (None, "Empty string")
```

---

## Advanced Patterns

### Pattern A: Custom Validation Report

```python
from backend.database.etl.config import engine
from sqlalchemy import text
import json

dataset_id = "550e8400-e29b-41d4-a716-446655440000"

with engine.connect() as conn:
    # Get detailed validation log
    result = conn.execute(text("""
        SELECT 
            ticker,
            metric_name,
            COUNT(*) as total,
            COUNT(CASE WHEN validation_status = 'VALID' THEN 1 END) as valid,
            COUNT(CASE WHEN validation_status = 'REJECTED' THEN 1 END) as rejected,
            100.0 * COUNT(CASE WHEN validation_status = 'VALID' THEN 1 END) / COUNT(*) as valid_pct
        FROM raw_data
        WHERE dataset_id = :dataset_id
        GROUP BY ticker, metric_name
        HAVING COUNT(*) > 0
        ORDER BY valid_pct ASC, ticker
        LIMIT 50
    """), {"dataset_id": dataset_id})
    
    print("Companies/Metrics with Validation Issues")
    print("-" * 70)
    print(f"{'Ticker':<8} {'Metric':<25} {'Total':<6} {'Valid':<6} {'Valid %':<8}")
    print("-" * 70)
    
    for row in result:
        if row.valid_pct < 100:
            print(f"{row.ticker:<8} {row.metric_name:<25} {row.total:<6} {row.valid:<6} {row.valid_pct:.1f}%")
```

---

### Pattern B: Confidence Score Analysis

```python
from backend.database.etl.config import engine
from sqlalchemy import text

dataset_id = "550e8400-e29b-41d4-a716-446655440000"

with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT 
            CASE 
                WHEN confidence_level >= 0.95 THEN 'Very High (≥0.95)'
                WHEN confidence_level >= 0.90 THEN 'High (0.90-0.95)'
                WHEN confidence_level >= 0.75 THEN 'Medium (0.75-0.90)'
                ELSE 'Low (<0.75)'
            END as confidence_band,
            COUNT(*) as count,
            ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) as percentage
        FROM fundamentals
        WHERE dataset_id = :dataset_id
        GROUP BY confidence_band
        ORDER BY confidence_level DESC
    """), {"dataset_id": dataset_id})
    
    print("Confidence Score Distribution")
    print("-" * 50)
    for row in result:
        bar = "█" * int(row.percentage / 5)
        print(f"{row.confidence_band:<20} {row.count:>6} ({row.percentage:>5.1f}%) {bar}")
```

---

### Pattern C: Sector-Level Analysis

```python
from backend.database.etl.config import engine
from sqlalchemy import text

dataset_id = "550e8400-e29b-41d4-a716-446655440000"

with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT 
            c.sector,
            COUNT(DISTINCT f.ticker) as companies,
            COUNT(*) as data_points,
            COUNT(CASE WHEN f.imputation_source = 'RAW' THEN 1 END)::float / COUNT(*) as raw_pct,
            AVG(f.confidence_level) as avg_confidence
        FROM fundamentals f
        JOIN companies c ON f.ticker = c.ticker
        WHERE f.dataset_id = :dataset_id
        GROUP BY c.sector
        ORDER BY companies DESC
    """), {"dataset_id": dataset_id})
    
    print("Sector Summary")
    print("-" * 70)
    print(f"{'Sector':<25} {'Cos':<5} {'Points':<8} {'Raw %':<8} {'Avg Conf':<10}")
    print("-" * 70)
    
    for row in result:
        print(f"{row.sector:<25} {row.companies:<5} {row.data_points:<8} {row.raw_pct*100:>6.1f}% {row.avg_confidence:>8.3f}")
```

---

## FAQ

### Q: What should I do if ingestion fails?

**A:** Check the dataset_versions table for error_message:

```python
from backend.database.etl.config import engine
from sqlalchemy import text

with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT status, error_message FROM dataset_versions
        WHERE dataset_id = :id
    """), {"id": dataset_id})
    
    row = result.first()
    print(f"Status: {row.status}")
    print(f"Error: {row.error_message}")
```

---

### Q: How do I re-process a dataset?

**A:** 
1. Delete existing rows from raw_data and fundamentals
2. Re-run ingestion and processing

```python
from backend.database.etl.config import engine
from sqlalchemy import text

dataset_id = "550e8400-e29b-41d4-a716-446655440000"

with engine.begin() as conn:
    conn.execute(text("""
        DELETE FROM fundamentals WHERE dataset_id = :id
    """), {"id": dataset_id})
    
    conn.execute(text("""
        DELETE FROM raw_data WHERE dataset_id = :id
    """), {"id": dataset_id})
    
    conn.execute(text("""
        UPDATE dataset_versions SET status = 'PENDING' WHERE dataset_id = :id
    """), {"id": dataset_id})

# Now re-run ingestion and processing
```

---

### Q: Can I query data while processing is running?

**A:** Yes, but you'll only see data that's been committed. The fundamentals table is written in a transaction that commits on success. For progress tracking during long processing, query the dataset_versions.quality_metadata field.

---

### Q: How do I handle company ticker changes?

**A:** Update the companies table with the new ticker and ensure fiscal_year_mapping has entries for the new ticker.

```python
from backend.database.etl.config import engine
from sqlalchemy import text

# Update company
with engine.begin() as conn:
    conn.execute(text("""
        UPDATE companies 
        SET ticker = :new_ticker 
        WHERE ticker = :old_ticker
    """), {"new_ticker": "NEW", "old_ticker": "OLD"})
```

---

## Troubleshooting

### Issue: "dataset_id not found"

**Solution:** Verify the dataset_id exists in dataset_versions:

```python
from backend.database.etl.config import engine
from sqlalchemy import text

with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT dataset_id, dataset_name, status FROM dataset_versions
        ORDER BY created_at DESC LIMIT 10
    """))
    
    for row in result:
        print(f"{row.dataset_id} | {row.dataset_name} | {row.status}")
```

---

### Issue: "Column not found: raw_value"

**Solution:** Ensure raw_data table has all required columns. Check schema:

```python
from backend.database.etl.config import engine
from sqlalchemy import inspect

inspector = inspect(engine)
columns = inspector.get_columns('raw_data')
for col in columns:
    print(f"  {col['name']}: {col['type']}")
```

---

### Issue: Memory error during large dataset processing

**Solution:** Process in chunks using batch processing:

```python
from backend.database.etl.config import engine
from sqlalchemy import text
import pandas as pd

dataset_id = "550e8400-e29b-41d4-a716-446655440000"
chunk_size = 5000

with engine.connect() as conn:
    offset = 0
    while True:
        result = conn.execute(text("""
            SELECT * FROM raw_data 
            WHERE dataset_id = :id
            LIMIT :limit OFFSET :offset
        """), {"id": dataset_id, "limit": chunk_size, "offset": offset})
        
        rows = result.fetchall()
        if not rows:
            break
        
        # Process chunk
        print(f"Processing rows {offset} to {offset + len(rows)}")
        
        offset += chunk_size
```

---

---

**Last Updated**: 2026-03-03  
**Maintained By**: Data Engineering Team
