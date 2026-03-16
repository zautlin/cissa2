# ============================================================================
# Pydantic Models for Dataset Statistics
# ============================================================================
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class CompaniesStats(BaseModel):
    """Statistics about companies in the dataset"""
    count: Optional[int] = Field(None, description="Total number of distinct companies (tickers)")


class SectorsStats(BaseModel):
    """Statistics about sectors in the dataset"""
    count: Optional[int] = Field(None, description="Total number of distinct sectors")


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
    companies: CompaniesStats = Field(..., description="Company statistics")
    sectors: SectorsStats = Field(..., description="Sector statistics")
    data_coverage: DataCoverage = Field(..., description="Data coverage period")
    raw_metrics: RawMetricsStats = Field(..., description="Raw metrics statistics")
