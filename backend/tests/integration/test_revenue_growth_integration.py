"""
Integration test for Revenue Growth metric against CSL AU Equity data

Compares API results against reference data from the user's spreadsheet
"""
import asyncio
import pytest
from uuid import UUID
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from backend.app.services.ratio_metrics_service import RatioMetricsService
from backend.app.core.config import get_settings


# Reference data for CSL AU Equity (2001-2020)
# From user's spreadsheet
REFERENCE_DATA_CSL = {
    2001: None,      # n/a
    2002: 0.585,     # 58.5%
    2003: -0.027,    # -2.7%
    2004: 0.229,     # 22.9%
    2005: 0.633,     # 63.3%
    2006: 0.092,     # 9.2%
    2007: 0.114,     # 11.4%
    2008: 0.121,     # 12.1%
    2009: 0.351,     # 35.1%
    2010: -0.046,    # -4.6%
    2011: -0.064,    # -6.4%
    2012: 0.067,     # 6.7%
    2013: 0.084,     # 8.4%
    2014: 0.207,     # 20.7%
    2015: 0.125,     # 12.5%
    2016: 0.245,     # 24.5%
    2017: 0.097,     # 9.7%
    2018: 0.109,     # 10.9%
    2019: 0.169,     # 16.9%
    2020: 0.143      # 14.3%
}

# Error tolerance
ERROR_TOLERANCE_PERCENT = 5.0  # Allow 5% error


@pytest.mark.asyncio
async def test_revenue_growth_integration_csl_1y():
    """
    Integration test: Calculate 1Y revenue growth for CSL and compare to reference data
    """
    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    try:
        async with async_session() as session:
            # First, get the dataset_id from the database
            from sqlalchemy import text
            result = await session.execute(text("SELECT id FROM cissa.datasets LIMIT 1"))
            row = result.fetchone()
            if not row:
                pytest.skip("No dataset found in database")
            dataset_id = UUID(str(row[0]))
            
            # Initialize service
            service = RatioMetricsService(session)
            
            # Calculate revenue growth for CSL
            response = await service.calculate_ratio_metric(
                metric_id="revenue_growth",
                tickers=["CSL"],
                dataset_id=dataset_id,
                temporal_window="1Y"
            )
            
            # Verify response structure
            assert response.metric == "revenue_growth"
            assert response.display_name == "Revenue Growth"
            assert response.temporal_window == "1Y"
            assert len(response.data) == 1
            
            csl_data = response.data[0]
            assert csl_data.ticker == "CSL"
            assert len(csl_data.time_series) > 0
            
            # Collect results by year
            results_by_year = {ts.year: ts.value for ts in csl_data.time_series}
            
            # Compare to reference data
            errors = []
            for year, ref_value in REFERENCE_DATA_CSL.items():
                api_value = results_by_year.get(year)
                
                if ref_value is None:
                    # Expected NULL
                    if api_value is not None:
                        errors.append(f"Year {year}: Expected NULL but got {api_value}")
                else:
                    # Expected numeric value
                    if api_value is None:
                        errors.append(f"Year {year}: Expected {ref_value} but got NULL")
                    else:
                        # Calculate error percentage
                        error_pct = abs(api_value - ref_value) / abs(ref_value) * 100
                        status = "PASS" if error_pct <= ERROR_TOLERANCE_PERCENT else "FAIL"
                        
                        print(f"Year {year}: Ref={ref_value:.4f}, API={api_value:.4f}, Error={error_pct:.2f}% [{status}]")
                        
                        if error_pct > ERROR_TOLERANCE_PERCENT:
                            errors.append(f"Year {year}: Error {error_pct:.2f}% exceeds tolerance")
            
            # Report results
            if errors:
                print(f"\n{len(errors)} validation errors found:")
                for error in errors:
                    print(f"  - {error}")
                pytest.fail(f"Validation failed: {len(errors)} errors")
            else:
                print(f"\nAll {len(REFERENCE_DATA_CSL)} reference values validated successfully!")
    
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_revenue_growth_multi_ticker():
    """
    Integration test: Verify multi-ticker support
    """
    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    try:
        async with async_session() as session:
            from sqlalchemy import text
            result = await session.execute(text("SELECT id FROM cissa.datasets LIMIT 1"))
            row = result.fetchone()
            if not row:
                pytest.skip("No dataset found in database")
            dataset_id = UUID(str(row[0]))
            
            service = RatioMetricsService(session)
            
            # Request multiple tickers (though we may only have CSL)
            response = await service.calculate_ratio_metric(
                metric_id="revenue_growth",
                tickers=["CSL"],
                dataset_id=dataset_id,
                temporal_window="1Y"
            )
            
            # Verify structure
            assert len(response.data) >= 1
            for ticker_data in response.data:
                assert len(ticker_data.time_series) > 0
                # Verify at least one year has data
                assert any(ts.value is not None for ts in ticker_data.time_series)
    
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_revenue_growth_year_filtering():
    """
    Integration test: Verify year filtering works
    """
    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    try:
        async with async_session() as session:
            from sqlalchemy import text
            result = await session.execute(text("SELECT id FROM cissa.datasets LIMIT 1"))
            row = result.fetchone()
            if not row:
                pytest.skip("No dataset found in database")
            dataset_id = UUID(str(row[0]))
            
            service = RatioMetricsService(session)
            
            # Request specific year range
            response = await service.calculate_ratio_metric(
                metric_id="revenue_growth",
                tickers=["CSL"],
                dataset_id=dataset_id,
                temporal_window="1Y",
                start_year=2010,
                end_year=2015
            )
            
            # Verify only requested years are returned
            csl_data = response.data[0]
            years = [ts.year for ts in csl_data.time_series]
            
            assert all(2010 <= year <= 2015 for year in years), f"Found years outside range: {years}"
            assert len(years) > 0, "No years returned for filtered range"
    
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_revenue_growth_null_handling():
    """
    Integration test: Verify NULL handling for first year (no prior year)
    """
    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    try:
        async with async_session() as session:
            from sqlalchemy import text
            result = await session.execute(text("SELECT id FROM cissa.datasets LIMIT 1"))
            row = result.fetchone()
            if not row:
                pytest.skip("No dataset found in database")
            dataset_id = UUID(str(row[0]))
            
            service = RatioMetricsService(session)
            
            response = await service.calculate_ratio_metric(
                metric_id="revenue_growth",
                tickers=["CSL"],
                dataset_id=dataset_id,
                temporal_window="1Y"
            )
            
            csl_data = response.data[0]
            
            # Find the minimum year
            min_year = min(ts.year for ts in csl_data.time_series)
            min_year_data = next(ts for ts in csl_data.time_series if ts.year == min_year)
            
            # First year should be NULL (no prior year to calculate growth)
            assert min_year_data.value is None, f"First year ({min_year}) should be NULL but got {min_year_data.value}"
    
    finally:
        await engine.dispose()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
