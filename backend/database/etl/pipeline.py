#!/usr/bin/env python3
"""
Master Data Ingestion Pipeline Orchestrator

Executes complete data pipeline:
1. Extract Excel to CSV (01_extract_excel_to_csv.py)
2. Denormalize metrics (02_denormalize_metrics.py)
3. Load reference tables (Stage 1a)
4. Ingest raw data (Stage 1b) with numeric validation
5. Process data (Stage 2) with FY alignment and imputation

Usage:
    python3 pipeline.py --input <excel_file> [--mode full|step-by-step]
    python3 pipeline.py --help

Example:
    python3 pipeline.py \
        --input "input-data/ASX/raw-data/Bloomberg Download data.xlsx" \
        --mode full
"""

import sys
import argparse
import subprocess
import logging
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy import text

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from etl.config import create_db_engine
from etl.ingestion import Ingester
from etl.processing import DataQualityProcessor


class PipelineLogger:
    """Custom logger for pipeline execution."""
    
    def __init__(self, log_file: Path):
        """Initialize logger with file and console output."""
        self.log_file = log_file
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Create logger
        self.logger = logging.getLogger("pipeline")
        self.logger.setLevel(logging.DEBUG)
        
        # File handler
        fh = logging.FileHandler(log_file)
        fh.setLevel(logging.DEBUG)
        
        # Console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        
        # Formatter
        formatter = logging.Formatter('%(message)s')
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)
        
        self.logger.addHandler(fh)
        self.logger.addHandler(ch)
    
    def info(self, msg: str):
        """Log info message."""
        self.logger.info(msg)
    
    def error(self, msg: str):
        """Log error message."""
        self.logger.error(f"❌ {msg}")
    
    def success(self, msg: str):
        """Log success message."""
        self.logger.info(f"✓ {msg}")
    
    def section(self, title: str):
        """Log section header."""
        self.logger.info("\n" + "="*70)
        self.logger.info(title)
        self.logger.info("="*70)


class PipelineOrchestrator:
    """Orchestrates the complete data ingestion pipeline."""
    
    def __init__(self, excel_file: str, log_file: Path):
        """
        Initialize orchestrator.
        
        Args:
            excel_file: Path to Bloomberg Excel file
            log_file: Path to log file
        """
        self.excel_file = Path(excel_file).resolve()
        self.logger = PipelineLogger(log_file)
        self.start_time = datetime.now()
        self.results = {}
        self.dataset_id = None
        
        # Paths - scripts are in input-data/ASX/ (parent of raw-data/)
        self.scripts_dir = self.excel_file.parent.parent  # input-data/ASX/
        self.extracted_dir = self.scripts_dir / "extracted-worksheets"
        self.consolidated_file = self.scripts_dir / "consolidated-data" / "financial_metrics_fact_table.csv"
        
        # Database
        self.engine = None
        self.ingester = None
        self.processor = None
    
    def run_full(self) -> bool:
        """Run complete pipeline."""
        self.logger.section("FINANCIAL DATA PIPELINE - FULL EXECUTION")
        self.logger.info(f"Started: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        self.logger.info(f"Excel File: {self.excel_file}\n")
        
        try:
            # Initialize database connection
            if not self._initialize_database():
                return False
            
            # Stage 0: Extract Excel
            if not self._stage_0_extract():
                return False
            
            # Stage 0.5: Denormalize
            if not self._stage_0_5_denormalize():
                return False
            
            # Stage 1a: Load references
            if not self._stage_1a_load_references():
                return False
            
            # Stage 1b: Ingest raw data
            if not self._stage_1b_ingest_data():
                return False
            
            # Stage 2: Process data
            if not self._stage_2_process_data():
                return False
            
            # Final summary
            self._log_final_summary()
            return True
        
        except Exception as e:
            self.logger.error(f"Pipeline execution failed: {e}")
            import traceback
            self.logger.info(traceback.format_exc())
            return False
    
    def _initialize_database(self) -> bool:
        """Initialize database connection."""
        self.logger.section("DATABASE CONNECTION")
        
        try:
            self.engine = create_db_engine(echo=False)
            
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            
            self.logger.success("Database connection successful")
            self.ingester = Ingester(self.engine)
            self.processor = DataQualityProcessor(self.engine)
            
            # Check schema
            with self.engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT COUNT(*) FROM information_schema.tables 
                    WHERE table_schema = 'cissa'
                """))
                table_count = result.scalar()
            
            self.logger.info(f"Schema 'cissa' exists with {table_count} tables")
            return True
        
        except Exception as e:
            self.logger.error(f"Database connection failed: {e}")
            return False
    
    def _stage_0_extract(self) -> bool:
        """Stage 0: Extract Excel to CSV."""
        self.logger.section("STAGE 0: EXCEL EXTRACTION")
        
        try:
            # Verify input file
            if not self.excel_file.exists():
                self.logger.error(f"Excel file not found: {self.excel_file}")
                return False
            
            self.logger.info(f"Input file: {self.excel_file}")
            self.logger.info(f"Output directory: {self.extracted_dir}\n")
            
            # Run extraction script (located in input-data/ASX/)
            script_path = self.scripts_dir / "01_extract_excel_to_csv.py"
            result = subprocess.run(
                [sys.executable, str(script_path), str(self.excel_file), str(self.extracted_dir)],
                cwd=str(self.scripts_dir),
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode != 0:
                self.logger.error(f"Excel extraction failed: {result.stderr}")
                return False
            
            # Log output
            for line in result.stdout.split('\n'):
                if line.strip():
                    self.logger.info(line)
            
            # Verify extracted files
            csv_files = list(self.extracted_dir.glob("*.csv"))
            self.logger.success(f"Extracted {len(csv_files)} CSV files")
            
            self.results['stage_0_extract'] = {
                'status': 'SUCCESS',
                'files_created': len(csv_files),
                'output_dir': str(self.extracted_dir),
            }
            
            return True
        
        except subprocess.TimeoutExpired:
            self.logger.error("Excel extraction timeout (>300s)")
            return False
        except Exception as e:
            self.logger.error(f"Excel extraction error: {e}")
            return False
    
    def _stage_0_5_denormalize(self) -> bool:
        """Stage 0.5: Denormalize metrics."""
        self.logger.section("STAGE 0.5: METRICS DENORMALIZATION")
        
        try:
            # Verify extracted directory
            if not self.extracted_dir.exists():
                self.logger.error(f"Extracted worksheets directory not found: {self.extracted_dir}")
                return False
            
            self.logger.info(f"Input directory: {self.extracted_dir}")
            self.logger.info(f"Output file: {self.consolidated_file}\n")
            
            # Create output directory
            self.consolidated_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Run denormalization script
            script_path = self.scripts_dir / "02_denormalize_metrics.py"
            result = subprocess.run(
                [sys.executable, str(script_path), str(self.extracted_dir), str(self.consolidated_file)],
                cwd=str(self.scripts_dir),
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode != 0:
                self.logger.error(f"Denormalization failed: {result.stderr}")
                return False
            
            # Log output
            for line in result.stdout.split('\n'):
                if line.strip():
                    self.logger.info(line)
            
            # Verify output file
            if not self.consolidated_file.exists():
                self.logger.error(f"Consolidated file not created: {self.consolidated_file}")
                return False
            
            # Count rows in consolidated file
            row_count = sum(1 for _ in open(self.consolidated_file)) - 1  # Subtract header
            self.logger.success(f"Consolidated fact table created: {row_count:,} rows")
            
            self.results['stage_0_5_denormalize'] = {
                'status': 'SUCCESS',
                'output_file': str(self.consolidated_file),
                'row_count': row_count,
            }
            
            return True
        
        except subprocess.TimeoutExpired:
            self.logger.error("Denormalization timeout (>300s)")
            return False
        except Exception as e:
            self.logger.error(f"Denormalization error: {e}")
            return False
    
    def _stage_1a_load_references(self) -> bool:
        """Stage 1a: Load reference tables."""
        self.logger.section("STAGE 1A: LOAD REFERENCE TABLES")
        
        try:
            base_csv = self.extracted_dir / "Base.csv"
            fy_dates_csv = self.extracted_dir / "FY Dates.csv"
            
            if not base_csv.exists() or not fy_dates_csv.exists():
                self.logger.error(f"Reference files not found")
                return False
            
            self.logger.info(f"Base.csv: {base_csv}")
            self.logger.info(f"FY Dates.csv: {fy_dates_csv}\n")
            
            result = self.ingester.load_reference_tables(
                base_csv=str(base_csv),
                fy_dates_csv=str(fy_dates_csv),
            )
            
            self.logger.success(f"Companies loaded: {result['companies']['loaded']}")
            self.logger.success(f"FY mappings loaded: {result['fy_dates']['loaded']}")
            
            self.results['stage_1a_references'] = {
                'status': 'SUCCESS',
                'companies_loaded': result['companies']['loaded'],
                'fy_mappings_loaded': result['fy_dates']['loaded'],
            }
            
            return True
        
        except Exception as e:
            self.logger.error(f"Reference table loading failed: {e}")
            import traceback
            self.logger.info(traceback.format_exc())
            return False
    
    def _stage_1b_ingest_data(self) -> bool:
        """Stage 1b: Ingest raw data."""
        self.logger.section("STAGE 1B: INGEST RAW DATA")
        
        try:
            if not self.consolidated_file.exists():
                self.logger.error(f"Consolidated file not found: {self.consolidated_file}")
                return False
            
            self.logger.info(f"Consolidated fact table: {self.consolidated_file}\n")
            
            result = self.ingester.load_dataset(
                csv_path=str(self.consolidated_file),
                base_csv_path=str(self.extracted_dir / "Base.csv"),
                fy_dates_csv_path=str(self.extracted_dir / "FY Dates.csv"),
            )
            
            self.dataset_id = result['dataset_id']
            
            self.logger.success(f"Dataset ID: {result['dataset_id']}")
            self.logger.success(f"Dataset Name: {result['dataset_name']}")
            self.logger.success(f"Version: {result['version_number']}")
            self.logger.info(f"\nIngestion Statistics & Reconciliation:")
            self.logger.info(f"  CSV file rows: {result['total_csv_rows']:,}")
            self.logger.info(f"  Rows with valid ticker/period/metric: {result['total_rows_processed']:,}")
            self.logger.info(f"  Rows with unparseable values (rejected): {result['rejected_rows']:,}")
            self.logger.info(f"  Duplicate (ticker, metric, period) combinations: {result['duplicate_combinations']:,}")
            self.logger.info(f"  Unique rows in raw_data: {result['unique_rows_in_db']:,}")
            
            # Verify reconciliation
            expected = result['total_rows_processed'] - result['rejected_rows'] - result['duplicate_combinations']
            actual = result['unique_rows_in_db']
            reconcile_ok = expected == actual
            status = "✓" if reconcile_ok else "✗"
            self.logger.info(f"\n  Reconciliation: {status}")
            self.logger.info(f"    Formula: processed - rejects - duplicates = unique_in_db")
            self.logger.info(f"    Calculation: {result['total_rows_processed']:,} - {result['rejected_rows']:,} - {result['duplicate_combinations']:,} = {expected:,}")
            self.logger.info(f"    Actual in DB: {actual:,}")
            
            if result['validation_summary']:
                self.logger.info(f"\n  Rejection Reasons (top 5):")
                for reason, count in sorted(result['validation_summary'].items(), key=lambda x: x[1], reverse=True)[:5]:
                    pct = 100 * count / result['rejected_rows'] if result['rejected_rows'] > 0 else 0
                    self.logger.info(f"    - {reason}: {count:,} ({pct:.1f}%)")
            
            # Log L1 metrics calculation results
            if result.get('l1_metrics'):
                l1_result = result['l1_metrics']
                if l1_result.get('status') == 'success':
                    self.logger.success(f"L1 Metrics: {l1_result.get('calculated', 0)}/15 metrics calculated")
                    self.logger.info(f"  - Metrics stored: {l1_result.get('calculated', 0)}")
                elif l1_result.get('status') == 'partial':
                    self.logger.info(f"⚠ L1 Metrics: {l1_result.get('calculated', 0)}/15 metrics (partial)")
                    if l1_result.get('failed', 0) > 0:
                        self.logger.info(f"  - Failed: {l1_result.get('failed', 0)}")
                        for error in l1_result.get('errors', [])[:3]:  # Show first 3 errors
                            self.logger.info(f"    • {error}")
                else:
                    self.logger.error(f"L1 Metrics calculation failed: {l1_result.get('message', 'Unknown error')}")
            else:
                self.logger.info("L1 Metrics: Not calculated (upgrade required)")
            
            self.results['stage_1b_ingest'] = {
                'status': 'SUCCESS',
                'dataset_id': result['dataset_id'],
                'dataset_name': result['dataset_name'],
                'version_number': result['version_number'],
                'total_csv_rows': result['total_csv_rows'],
                'total_rows_processed': result['total_rows_processed'],
                'rejected_rows': result['rejected_rows'],
                'duplicate_combinations': result['duplicate_combinations'],
                'unique_rows_in_db': result['unique_rows_in_db'],
                'reconciliation_ok': reconcile_ok,
                'validation_summary': result['validation_summary'],
                'l1_metrics': result.get('l1_metrics', {}),
            }
            
            # Display data quality notice if duplicates were found
            if result['duplicate_combinations'] > 0:
                self.logger.info("")
                self.logger.info(f"⚠ Data Quality Notice: {result['duplicate_combinations']:,} duplicate records detected and logged")
                self.logger.info(f"  Review imputation_audit_trail with imputation_step = 'DATA_QUALITY_DUPLICATE'")
            
            return True
        
        except Exception as e:
            self.logger.error(f"Data ingestion failed: {e}")
            import traceback
            self.logger.info(traceback.format_exc())
            return False
    
    def _stage_2_process_data(self) -> bool:
        """Stage 2: Process data (FY align + impute)."""
        self.logger.section("STAGE 2: DATA PROCESSING (FY ALIGN + IMPUTE)")
        
        try:
            if not self.dataset_id:
                self.logger.error("Dataset ID not set")
                return False
            
            self.logger.info(f"Dataset ID: {self.dataset_id}\n")
            
            result = self.processor.process_dataset(dataset_id=self.dataset_id)
            
            self.logger.success(f"Processing complete")
            self.logger.info(f"\nResults:")
            self.logger.info(f"  Fundamentals rows: {result['fundamentals_rows']:,}")
            
            if 'quality_metadata' in result and result['quality_metadata']:
                quality = result['quality_metadata']
                fill_rate = quality.get('fill_rate', 0)
                self.logger.info(f"  Fill rate: {fill_rate:.1%}")
                
                self.logger.info(f"\nImputation Distribution:")
                imputation_sources = {
                    'RAW': quality.get('RAW', 0),
                    'FORWARD_FILL': quality.get('FORWARD_FILL', 0),
                    'BACKWARD_FILL': quality.get('BACKWARD_FILL', 0),
                    'INTERPOLATED': quality.get('INTERPOLATED', 0),
                    'SECTOR_MEDIAN': quality.get('SECTOR_MEDIAN', 0),
                    'MARKET_MEDIAN': quality.get('MARKET_MEDIAN', 0),
                    'MISSING': quality.get('MISSING', 0),
                }
                
                total = sum(imputation_sources.values())
                for source, count in sorted(imputation_sources.items(), key=lambda x: x[1], reverse=True):
                    if count > 0:
                        pct = 100 * count / total if total > 0 else 0
                        self.logger.info(f"  - {source:20s}: {count:8,d} ({pct:5.1f}%)")
            
            self.results['stage_2_process'] = {
                'status': 'SUCCESS',
                'fundamentals_rows': result['fundamentals_rows'],
                'quality_metadata': result.get('quality_metadata', {}),
            }
            
            # AUTO-TRIGGER L1 METRICS (after fundamentals are populated)
            self.logger.section("AUTO-CALCULATING L1 METRICS")
            self.logger.info("Triggering L1 metrics calculation (now that fundamentals are ready)...")
            
            try:
                l1_result = self.ingester._auto_calculate_l1_metrics(self.dataset_id)
                
                if l1_result.get('status') == 'success':
                    self.logger.success(f"✓ L1 Metrics: {l1_result.get('calculated', 0)}/15 metrics calculated")
                    self.logger.info(f"  - Metrics stored: {l1_result.get('calculated', 0)}")
                elif l1_result.get('status') == 'partial':
                    self.logger.info(f"⚠ L1 Metrics: {l1_result.get('calculated', 0)}/15 metrics (partial)")
                    if l1_result.get('failed', 0) > 0:
                        self.logger.info(f"  - Failed: {l1_result.get('failed', 0)}")
                        for error in l1_result.get('errors', [])[:3]:  # Show first 3 errors
                            self.logger.info(f"    • {error}")
                else:
                    self.logger.error(f"L1 Metrics calculation failed: {l1_result.get('message', 'Unknown error')}")
                
                self.results['stage_2_process']['l1_metrics'] = l1_result
            except Exception as e:
                self.logger.error(f"L1 metrics calculation error: {e}")
                import traceback
                self.logger.info(traceback.format_exc())
                self.results['stage_2_process']['l1_metrics'] = {
                    'status': 'error',
                    'message': str(e)
                }
            
            return True
        
        except Exception as e:
            self.logger.error(f"Data processing failed: {e}")
            import traceback
            self.logger.info(traceback.format_exc())
            return False
    
    def _log_final_summary(self):
        """Log final execution summary."""
        self.logger.section("FINAL SUMMARY")
        
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()
        
        # Overall status
        all_success = all(
            self.results.get(stage, {}).get('status') == 'SUCCESS'
            for stage in [
                'stage_0_extract',
                'stage_0_5_denormalize',
                'stage_1a_references',
                'stage_1b_ingest',
                'stage_2_process',
            ]
        )
        
        status_str = "✓ ALL STAGES COMPLETED SUCCESSFULLY" if all_success else "❌ PIPELINE FAILED"
        self.logger.info(status_str)
        self.logger.info(f"\nTotal Duration: {duration:.1f} seconds ({duration/60:.1f}m)")
        self.logger.info(f"Completed: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Database state
        if self.engine:
            try:
                with self.engine.connect() as conn:
                    companies = conn.execute(text("SELECT COUNT(*) FROM cissa.companies")).scalar()
                    raw_data = conn.execute(text("SELECT COUNT(*) FROM cissa.raw_data")).scalar()
                    fundamentals = conn.execute(text("SELECT COUNT(*) FROM cissa.fundamentals")).scalar()
                
                self.logger.info(f"\nDatabase State:")
                self.logger.info(f"  Companies: {companies:,}")
                self.logger.info(f"  Raw data rows: {raw_data:,}")
                self.logger.info(f"  Fundamentals rows: {fundamentals:,}")
            except:
                pass
        
        self.logger.info(f"\nPipeline execution log: {self.logger.log_file}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Financial Data Pipeline Orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 pipeline.py --input "input-data/ASX/raw-data/Bloomberg Download data.xlsx" --mode full
  python3 pipeline.py --input "input-data/ASX/raw-data/Bloomberg Download data.xlsx" --mode step-by-step
        """
    )
    
    parser.add_argument(
        "--input",
        required=True,
        help="Path to Bloomberg Excel file"
    )
    
    parser.add_argument(
        "--mode",
        choices=["full", "step-by-step"],
        default="full",
        help="Execution mode (default: full)"
    )
    
    args = parser.parse_args()
    
    # Create log file
    log_dir = Path("backend/database/ingestion_process/logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"pipeline_{timestamp}.log"
    
    # Create orchestrator
    orchestrator = PipelineOrchestrator(args.input, log_file)
    
    # Run pipeline
    if args.mode == "full":
        success = orchestrator.run_full()
    else:
        # Step-by-step mode not implemented yet (for future enhancement)
        success = orchestrator.run_full()
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
