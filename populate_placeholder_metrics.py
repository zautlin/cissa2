#!/usr/bin/env python3
"""
Populate Placeholder Metrics for UI Development
Inserts sample metric data for BHP AU Equity (2003-2022) into cissa.metrics_outputs.
Marks all records as "temporary" in metadata field.
"""

import asyncio
import json
from datetime import datetime
from uuid import UUID
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

# Configuration
DATASET_ID = UUID("523eeffd-9220-4d27-927b-e418f9c21d8a")
PARAM_SET_ID = UUID("71a0caa6-b52c-4c5e-b550-1048b7329719")
TICKER = "BHP AU Equity"
YEAR_START = 2003
YEAR_END = 2022

# Metric data: name -> list of 20 values (2003-2022)
# Percentages stored as decimals (e.g., 15.5% -> 0.155)
# Negative values represented in data
METRICS_DATA = {
    "TER": [
        0.155, 0.016, -0.079, 0.477, 0.477, 0.628, 0.229, 0.268, -0.179,
        0.111, 0.190, -0.262, 0.031, 0.186, -0.157, -0.277, 0.288, 0.522, 0.328, -0.076
    ],
    "TER-Ke": [
        0.035, -0.099, -0.194, 0.367, 0.367, 0.518, 0.119, 0.148, -0.299,
        0.001, 0.075, -0.372, -0.064, 0.096, -0.252, -0.362, 0.208, 0.442, 0.248, -0.151
    ],
    "TERA": [
        0.036, -0.024, -0.096, 0.233, 0.086, 0.396, -0.163, 0.481, -0.157,
        0.019, 0.202, -0.248, -0.187, 0.076, -0.145, -0.331, 0.097, 0.399, 0.146, -0.050
    ],
    "TRTE": [
        5455.0, 600.0, -3032.0, 25636.0, 37183.0, 69018.0, 39461.0, 53194.0, -43453.0,
        21489.0, 39749.0, -61003.0, 5207.0, 31080.0, -29949.0, -39893.0, 28580.0, 64640.0, 59273.0, -15749.0
    ],
    "WP": [
        39407.0, 42913.0, 42779.0, 59612.0, 86616.0, 121980.0, 191361.0, 222071.0, 272370.0,
        214449.0, 233592.0, 258773.0, 183303.0, 181995.0, 209177.0, 156173.0, 107205.0, 133849.0, 194962.0, 223745.0
    ],
    "WC": [
        1233.0, -3826.0, -7444.0, 19729.0, 28599.0, 56930.0, 20498.0, 29401.0, -72635.0,
        237.0, 15657.0, -86647.0, -10695.0, 16053.0, -48097.0, -52128.0, 20639.0, 54725.0, 44831.0, -31359.0
    ],
    "WC TERA": [
        1266.0, -911.0, -3668.0, 12505.0, 6702.0, 43501.0, -28042.0, 95327.0, -38288.0,
        3659.0, 42271.0, -57883.0, -31320.0, 12696.0, -27726.0, -47667.0, 9636.0, 49411.0, 26315.0, -10455.0
    ],
    "RA MM": [
        -0.001, -0.076, -0.098, 0.135, 0.281, 0.122, 0.282, -0.332, -0.141,
        -0.018, -0.127, -0.123, 0.123, 0.020, -0.107, -0.031, 0.111, 0.043, 0.103, -0.100
    ],
    "TSR": [
        0.155, 0.016, -0.079, 0.477, 0.477, 0.628, 0.229, 0.268, -0.179,
        0.111, 0.190, -0.262, 0.031, 0.186, -0.157, -0.277, 0.288, 0.522, 0.328, -0.076
    ],
}


async def main():
    """Main function to populate placeholder metrics"""
    print("\n" + "=" * 80)
    print("POPULATE PLACEHOLDER METRICS FOR UI DEVELOPMENT")
    print("=" * 80)
    
    print(f"\nConfiguration:")
    print(f"  Dataset ID: {DATASET_ID}")
    print(f"  Parameter Set ID: {PARAM_SET_ID}")
    print(f"  Ticker: {TICKER}")
    print(f"  Years: {YEAR_START}-{YEAR_END} (20 years)")
    print(f"  Metrics: {len(METRICS_DATA)}")
    print(f"  Total records to insert: {len(METRICS_DATA) * (YEAR_END - YEAR_START + 1)}")
    
    # Create async engine
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    try:
        async with async_session() as session:
            # Begin transaction
            async with session.begin():
                total_inserted = 0
                
                # Iterate through each metric
                for metric_name, values in METRICS_DATA.items():
                    if len(values) != (YEAR_END - YEAR_START + 1):
                        print(f"\n❌ ERROR: Metric '{metric_name}' has {len(values)} values, expected 20")
                        return
                    
                    # Iterate through each year
                    for idx, year in enumerate(range(YEAR_START, YEAR_END + 1)):
                        value = values[idx]
                        
                        # Create metadata indicating this is temporary
                        metadata = {
                            "type": "temporary",
                            "placeholder": True,
                            "created_at": datetime.utcnow().isoformat(),
                            "note": "UI development placeholder - awaiting actual calculation logic"
                        }
                        
                        # SQL INSERT statement
                        sql = text("""
                            INSERT INTO cissa.metrics_outputs 
                            (dataset_id, param_set_id, ticker, fiscal_year, output_metric_name, 
                             output_metric_value, metadata)
                            VALUES 
                            (:dataset_id, :param_set_id, :ticker, :fiscal_year, :output_metric_name,
                             :output_metric_value, :metadata)
                        """)
                        
                        await session.execute(
                            sql,
                            {
                                "dataset_id": str(DATASET_ID),
                                "param_set_id": str(PARAM_SET_ID),
                                "ticker": TICKER,
                                "fiscal_year": year,
                                "output_metric_name": metric_name,
                                "output_metric_value": value,
                                "metadata": json.dumps(metadata),
                            }
                        )
                        total_inserted += 1
                    
                    print(f"✓ Inserted {YEAR_END - YEAR_START + 1} records for '{metric_name}'")
            
            print(f"\n✅ Successfully inserted {total_inserted} placeholder metric records")
            
            # Verify insertion
            result = await session.execute(
                text("""
                    SELECT COUNT(*) as count, COUNT(DISTINCT output_metric_name) as unique_metrics
                    FROM cissa.metrics_outputs
                    WHERE dataset_id = :dataset_id 
                      AND param_set_id = :param_set_id
                      AND ticker = :ticker
                      AND metadata->>'type' = 'temporary'
                """),
                {
                    "dataset_id": str(DATASET_ID),
                    "param_set_id": str(PARAM_SET_ID),
                    "ticker": TICKER,
                }
            )
            row = result.fetchone()
            
            print(f"\nVerification:")
            print(f"  Total temporary records in DB: {row[0]}")
            print(f"  Unique metrics: {row[1]}")
            
            # Show sample records
            result = await session.execute(
                text("""
                    SELECT fiscal_year, output_metric_name, output_metric_value
                    FROM cissa.metrics_outputs
                    WHERE dataset_id = :dataset_id 
                      AND param_set_id = :param_set_id
                      AND ticker = :ticker
                      AND metadata->>'type' = 'temporary'
                    ORDER BY output_metric_name, fiscal_year
                    LIMIT 5
                """),
                {
                    "dataset_id": str(DATASET_ID),
                    "param_set_id": str(PARAM_SET_ID),
                    "ticker": TICKER,
                }
            )
            
            print(f"\nSample records:")
            for row in result:
                year, metric, value = row
                print(f"  {year} | {metric:<12} | {value}")
            
            print(f"\n" + "=" * 80)
            print("✅ PLACEHOLDER METRICS POPULATION COMPLETE")
            print("=" * 80 + "\n")
    
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
