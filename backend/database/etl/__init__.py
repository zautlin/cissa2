"""
Backend Database ETL Package.

Three-stage financial data pipeline:
1. INGESTION (Stage 1) - Extract, validate, load raw_data
2. PROCESSING (Stage 2) - FY align, impute, write fundamentals
3. CONSUMPTION (Stage 3) - metrics_outputs, optimization_outputs

Usage:
    from sqlalchemy import create_engine
    from backend.database.etl.ingestion import Ingester
    from backend.database.etl.processing import DataQualityProcessor
    
    engine = create_engine("postgresql://user:pass@host/db")
    
    # Stage 1: Ingest
    ingester = Ingester(engine)
    ingester.load_reference_tables(...)
    result = ingester.load_dataset(...)
    
    # Stage 2: Process
    processor = DataQualityProcessor(engine)
    result = processor.process_dataset(...)
"""

__version__ = "1.0.0"
__author__ = "OpenCode"

from .config import create_db_engine, get_db_url
from .ingestion import Ingester
from .processing import DataQualityProcessor
from .validators import validate_numeric
from .fy_aligner import FYAligner
from .imputation_engine import ImputationCascade

__all__ = [
    'create_db_engine',
    'get_db_url',
    'Ingester',
    'DataQualityProcessor',
    'validate_numeric',
    'FYAligner',
    'ImputationCascade',
]
