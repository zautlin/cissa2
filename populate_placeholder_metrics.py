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
DATASET_ID = UUID("13d1f4ca-6c72-4be2-9d21-b86bf685ceb2")
PARAM_SET_ID = UUID("15d7dc52-4e6f-44ec-9aff-0be42ff11031")
TICKER = "BHP AU Equity"
YEAR_START = 2002
YEAR_END = 2022

# Metric data: name -> list of values (2002-2022 for all metrics)
# For metrics 1-10: None value for 2002, then data for 2003-2022
# For metrics 11-15: None value for 2002, then data for 2003-2022
# Percentages stored as decimals (e.g., 15.5% -> 0.155)
# Negative values represented in data
# None values for 2002 in all metrics
METRICS_DATA = {
    "TER": [
        None, 0.454, -0.321, -0.622, 0.902, 0.533, 0.621, 0.661, 0.232, -0.087,
        0.035, 0.039, 0.226, 0.592, 0.099, 0.322, 0.321, 0.250, 0.413, 0.130, 0.350
    ],
    "TER-Ke": [
        None, 0.354, -0.416, -0.717, 0.807, 0.433, 0.516, 0.551, 0.117, -0.202,
        -0.070, -0.071, 0.121, 0.502, 0.014, 0.237, 0.246, 0.180, 0.343, 0.060, 0.285
    ],
    "TERA": [
        None, 0.354, -0.368, -0.654, 0.709, 0.204, 0.405, 0.269, 0.421, -0.072,
        -0.053, 0.046, 0.233, 0.390, -0.004, 0.324, 0.271, 0.089, 0.308, -0.024, 0.367
    ],
    "TRTE": [
        None, 2235.0, -2291.0, -3173.0, 1724.0, 2337.0, 3941.0, 6460.0, 3731.0, -1700.0,
        680.0, 701.0, 3916.0, 11837.0, 2967.0, 10162.0, 12901.0, 12809.0, 25869.0, 11328.0, 34067.0
    ],
    "WP": [
        None, 5417.0, 7817.0, 5584.0, 2093.0, 4819.0, 7015.0, 10852.0, 17960.0, 21909.0,
        21288.0, 19879.0, 19173.0, 21782.0, 32562.0, 34283.0, 43209.0, 54808.0, 66942.0, 93241.0, 103757.0
    ],
    "WC": [
        None, 1743.0, -2969.0, -3657.0, 1542.0, 1899.0, 3275.0, 5385.0, 1878.0, -3959.0,
        -1342.0, -1269.0, 2094.0, 10039.0, 416.0, 7477.0, 9887.0, 9223.0, 21490.0, 5228.0, 27735.0
    ],
    "WC TERA": [
        None, 1746.0, -2625.0, -3338.0, 1355.0, 893.0, 2570.0, 2632.0, 6788.0, -1415.0,
        -1030.0, 817.0, 4040.0, 7801.0, -132.0, 10233.0, 10906.0, 4577.0, 19295.0, -2086.0, 35740.0
    ],
    "RA MM": [
        None, -0.001, -0.048, -0.063, 0.098, 0.230, 0.111, 0.282, -0.305, -0.129,
        -0.016, -0.116, -0.112, 0.112, 0.018, -0.087, -0.025, 0.091, 0.035, 0.084, -0.082
    ],
    "TSR": [
        None, 0.454, -0.321, -0.622, 0.902, 0.533, 0.621, 0.661, 0.232, -0.087,
        0.035, 0.039, 0.226, 0.592, 0.099, 0.322, 0.321, 0.250, 0.413, 0.130, 0.350
    ],
    "EP PCT": [
        None, -0.001, 0.050, -0.038, 0.076, 0.117, -0.055, 0.164, 0.180, 0.281,
        0.092, 0.105, 0.138, 0.225, 0.371, 0.439, 0.449, 0.504, 0.587, 0.549, 0.460
    ],
    "Calc EP": [
        None, -1, 43, -46, 98, 263, -131, 323, 428, 813, 491, 460, 557, 843, 1159, 1388, 1462, 1558, 1994, 2380, 2748
    ],
    "Calc PAT_Ex": [
        None, 78, 124, 70, 220, 488, 117, 539, 702, 1146, 1053, 941, 983, 1180, 1424, 1657, 1707, 1774, 2231, 2684, 3136
    ],
    "Calc XO_Cost_Ex": [
        None, 0, 0, 0, -80, -253, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
    ],
    "Calc FC": [
        None, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
    ],
    "Calc 1Y FV ECF": [
        None, 21, -251, 16, -746, 369, 513, 129, 189, -1316, 2037, 1259, 1284, 1809, 1381, 1565, 1873, 1469, 1290, 1044, 1180
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
    print(f"  Years: {YEAR_START}-{YEAR_END} (21 years)")
    print(f"  Metrics: {len(METRICS_DATA)}")
    print(f"\n  Note: All metrics (1-15) have 21 year entries (2002-2022)")
    print(f"        But 2002 values are skipped (None), so only 20 years per metric")
    print(f"        Actual records to insert: 300 (15 metrics × 20 years)")
    
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
                    expected_count = YEAR_END - YEAR_START + 1
                    if len(values) != expected_count:
                        print(f"\n❌ ERROR: Metric '{metric_name}' has {len(values)} values, expected {expected_count}")
                        return
                    
                    # Iterate through each year
                    for idx, year in enumerate(range(YEAR_START, YEAR_END + 1)):
                        value = values[idx]
                        
                        # Skip None values (2002 for metrics 1-15)
                        if value is None:
                            continue
                        
                        # Create metadata indicating this is temporary
                        metadata = {
                            "type": "temporary",
                            "placeholder": True,
                            "created_at": datetime.utcnow().isoformat(),
                            "note": "UI development placeholder - awaiting actual calculation logic"
                        }
                        
                        # SQL INSERT statement for non-NULL values
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
                    
                    print(f"✓ Inserted 20 records for '{metric_name}' (2003-2022, skipped 2002)")
            
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
                print(f"  {year} | {metric:<20} | {value}")
            
            print(f"\n" + "=" * 80)
            print("✅ PLACEHOLDER METRICS POPULATION COMPLETE")
            print("=" * 80 + "\n")
    
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
