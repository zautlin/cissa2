# ============================================================================
# Pydantic Models for Dataset Statistics
# ============================================================================
from pydantic import BaseModel, Field
from typing import Optional, Dict, List
from datetime import datetime


class Company(BaseModel):
    """Represents a company with its ticker, name, and sector"""
    ticker: str = Field(..., description="Ticker symbol")
    company_name: str = Field(..., description="Company name")
    sector: str = Field(..., description="Sector classification")


class Sector(BaseModel):
    """Represents a sector with its name and company count"""
    name: str = Field(..., description="Sector name")
    company_count: int = Field(..., description="Number of companies in this sector")


class CompaniesStats(BaseModel):
    """Statistics about companies in the dataset"""
    count: int = Field(..., description="Total number of distinct companies (tickers)")
    items: List[Company] = Field(..., description="List of companies with ticker, name, and sector")


class SectorsStats(BaseModel):
    """Statistics about sectors in the dataset"""
    count: int = Field(..., description="Total number of distinct sectors")
    items: List[Sector] = Field(..., description="List of sectors with company counts")


class DataCoverage(BaseModel):
    """Time period coverage of the raw data"""
    min_year: Optional[int] = Field(None, description="Earliest fiscal year in dataset")
    max_year: Optional[int] = Field(None, description="Latest fiscal year in dataset")


class RawMetricsStats(BaseModel):
    """Statistics about raw metrics in fundamentals"""
    count: Optional[int] = Field(None, description="Total number of distinct raw metric names")


class DatasetStatistics(BaseModel):
    """Complete statistics for a dataset"""
    dataset_id: str = Field(..., description="UUID of the dataset")
    dataset_created_at: Optional[datetime] = Field(None, description="When the dataset was created")
    country: Optional[str] = Field(None, description="Country/geography for the dataset")
    companies: CompaniesStats = Field(..., description="Company statistics with list")
    sectors: SectorsStats = Field(..., description="Sector statistics with list")
    data_coverage: DataCoverage = Field(..., description="Data coverage period")
    raw_metrics: RawMetricsStats = Field(..., description="Raw metrics statistics")


class AllDatasetsStatistics(BaseModel):
    """Statistics for all datasets"""
    datasets: Dict[str, DatasetStatistics] = Field(..., description="Statistics keyed by dataset_id")
