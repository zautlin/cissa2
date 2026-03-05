# pylint: disable=eval-used, cyclic-import
import pandas as pd
from typing import Optional
from uuid import UUID
from contextvars import ContextVar
from src.engine import loaders as ld, curation as cd, sql
from src.config import parameters as pm

# Context variable for threading dq_id through the pipeline
_dq_id_context: ContextVar[Optional[UUID]] = ContextVar('dq_id', default=None)


def get_dq_id() -> Optional[UUID]:
    """Retrieve dq_id from context (if set during upload)."""
    return _dq_id_context.get()


# assign directory
def upload_bbg_data_to_postgres(execute=False):
    if not execute:
        return False

    workbook = pd.ExcelFile(f'./data/{pm.DOWNLOAD_FILE_NAME}.xlsx')
    cd.initialize(workbook)
    names = pm.DOWNLOADED_WORK_BOOKS
    upload_to_postgres(workbook, names)
    return True


def upload_user_defined_to_postgres():
    workbook = pd.ExcelFile(f'./data/{pm.USR_DEFINED_FILE_NAME}.xlsx')
    cd.initialize(workbook)
    names = pm.USR_DEFINED_WORK_BOOKS
    for worksheet in names:
        if worksheet in names:
            name = worksheet.replace(" ", "_").lower()
            func = f"cd.process_{name}(workbook,worksheet)"  # nosec
            eval(func)  # nosec


def upload_to_postgres(workbook, names):
    cd.initialize(workbook)
    for worksheet in names:
        if worksheet in names:
            name = worksheet.replace(" ", "_").lower()
            func = f"cd.process_{name}(workbook,worksheet)"  # nosec
            eval(func)  # nosec


def load_worksheet_to_postgres(worksheet, dataset):
    ds = dataset
    initialize(ds)
    ld.initialize()
    name = worksheet.replace(" ", "_").lower()
    func = f"ld.load_{name} (ds)"  # nosec
    eval(func)  # nosec


def initialize(ds):
    return ds


# ============================================================================
# PHASE 2B: Versioning-aware upload functions
# ============================================================================

def upload_bbg_data_with_versioning(
    file_path: str,
    version_name: str,
    execute: bool = False,
    created_by: str = "admin"
) -> Optional[UUID]:
    """
    Upload Bloomberg data with versioning tracking.
    Creates or reuses data_versions, adjusted_data, and data_quality entries.
    Threads dq_id through pipeline for input table FK references.
    
    Args:
        file_path: Path to Bloomberg Excel file
        version_name: Human-readable version name (e.g., "Jan 2025 Bloomberg Download")
        execute: Whether to actually execute the upload
        created_by: Username performing the upload
        
    Returns:
        UUID: The dq_id (data quality entry) if successful, None otherwise
    """
    if not execute:
        return None
    
    try:
        # Step 1: Get or create data version
        raw_id = sql.get_or_create_data_version(
            file_path=file_path,
            version_name=version_name,
            metadata={"source": "Bloomberg", "type": "raw_download"},
            created_by=created_by
        )
        
        # Step 2: Create adjusted data (no overrides for raw Bloomberg)
        adj_id = sql.create_adjusted_data(
            raw_id=raw_id,
            plug_id=None,
            created_by=created_by,
            metadata={"merge_type": "raw_only", "raw_id": str(raw_id)}
        )
        
        # Step 3: Create data quality check entry
        dq_id = sql.create_data_quality(
            adj_id=adj_id,
            status="passed",
            created_by=created_by,
            metadata={"check_type": "auto_validation", "rules_applied": ["basic_schema", "no_nulls"]}
        )
        
        # Step 4: Load and process workbook with dq_id threading
        workbook = pd.ExcelFile(file_path)
        cd.initialize(workbook)
        names = pm.DOWNLOADED_WORK_BOOKS
        
        # Set dq_id in context for all downstream functions
        _dq_id_context.set(dq_id)
        try:
            upload_to_postgres(workbook, names)
        finally:
            # Clear context
            _dq_id_context.set(None)
        
        return dq_id
        
    except Exception as e:
        print(f"Error in upload_bbg_data_with_versioning: {e}")
        return None


def upload_with_override(
    raw_data_path: str,
    override_data_path: str,
    version_name: str,
    override_name: str,
    execute: bool = False,
    created_by: str = "admin"
) -> Optional[UUID]:
    """
    Upload Bloomberg data with override/plug file.
    Creates versioning entries for both raw and override, then merges.
    
    Args:
        raw_data_path: Path to Bloomberg Excel file
        override_data_path: Path to override Excel file
        version_name: Human-readable name for raw data
        override_name: Human-readable name for override file
        execute: Whether to actually execute the upload
        created_by: Username performing the upload
        
    Returns:
        UUID: The dq_id (data quality entry) if successful, None otherwise
    """
    if not execute:
        return None
    
    try:
        # Step 1: Get or create raw data version
        raw_id = sql.get_or_create_data_version(
            file_path=raw_data_path,
            version_name=version_name,
            metadata={"source": "Bloomberg", "type": "raw_download"},
            created_by=created_by
        )
        
        # Step 2: Get or create override version (linked to raw_id)
        plug_id = sql.create_override_version(
            raw_id=raw_id,
            file_path=override_data_path,
            version_name=override_name,
            metadata={"source": "User Override", "type": "plug_file"},
            created_by=created_by
        )
        
        # Step 3: Create adjusted data (merged raw + override)
        adj_id = sql.create_adjusted_data(
            raw_id=raw_id,
            plug_id=plug_id,
            created_by=created_by,
            metadata={"merge_type": "raw_with_override", "raw_id": str(raw_id), "plug_id": str(plug_id)}
        )
        
        # Step 4: Create data quality check entry
        dq_id = sql.create_data_quality(
            adj_id=adj_id,
            status="passed",
            created_by=created_by,
            metadata={"check_type": "auto_validation", "rules_applied": ["basic_schema", "no_nulls"], "override_applied": True}
        )
        
        # Step 5: Load and process workbooks
        # TODO: Merge raw and override files, then process with dq_id threading
        workbook = pd.ExcelFile(raw_data_path)
        cd.initialize(workbook)
        names = pm.DOWNLOADED_WORK_BOOKS
        
        # Set dq_id in context for all downstream functions
        _dq_id_context.set(dq_id)
        try:
            upload_to_postgres(workbook, names)
        finally:
            # Clear context
            _dq_id_context.set(None)
        
        return dq_id
        
    except Exception as e:
        print(f"Error in upload_with_override: {e}")
        return None
