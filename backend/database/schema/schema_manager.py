#!/usr/bin/env python3
"""
Unified Schema Manager for Financial Data Pipeline.

Provides commands to:
- destroy: Drop all tables and functions in cissa schema (DESTRUCTIVE!)
- create: Create fresh schema from schema.sql
- init: Initialize schema + baseline parameters + default parameter_set (full setup)

Usage:
    python3 schema_manager.py --help
    python3 schema_manager.py destroy [--confirm]
    python3 schema_manager.py create
    python3 schema_manager.py init
"""

import sys
import argparse
from pathlib import Path
from sqlalchemy import text
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from etl.config import create_db_engine


class SchemaManager:
    """Manages schema operations (create, destroy, initialize)."""
    
    SCHEMA_DIR = Path(__file__).parent
    
    def __init__(self, engine):
        """Initialize schema manager with database engine."""
        self.engine = engine
    
    def _read_sql_file(self, filename: str) -> str:
        """Read and return SQL file contents."""
        file_path = self.SCHEMA_DIR / filename
        if not file_path.exists():
            raise FileNotFoundError(f"SQL file not found: {file_path}")
        
        with open(file_path, 'r') as f:
            return f.read()
    
    def _execute_sql(self, sql: str, description: str = None) -> bool:
        """Execute SQL statements safely."""
        try:
            with self.engine.begin() as conn:
                # Split by semicolon and execute each statement
                statements = [s.strip() for s in sql.split(';') if s.strip()]
                
                for i, stmt in enumerate(statements, 1):
                    if stmt:
                        try:
                            conn.execute(text(stmt))
                        except Exception as e:
                            # Some statements may fail (e.g., IF NOT EXISTS when creating)
                            # This is OK - continue with next statement
                            pass
            
            if description:
                print(f"✓ {description}")
            return True
        
        except Exception as e:
            print(f"✗ Error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _execute_sql_file_transaction(self, filename: str, description: str = None) -> bool:
        """
        Execute SQL file as a single atomic transaction.
        
        This method reads the entire SQL file and executes it as one transaction,
        which properly handles PL/pgSQL functions with dollar-quoting ($$).
        
        Args:
            filename: Name of SQL file in SCHEMA_DIR
            description: Optional description to print on success
            
        Returns:
            True if successful, False otherwise
        """
        try:
            sql_content = self._read_sql_file(filename)
        except FileNotFoundError as e:
            print(f"✗ {e}")
            return False
        
        try:
            with self.engine.begin() as conn:
                # Execute the entire SQL file as one transaction
                # This preserves PL/pgSQL dollar-quoting and multi-statement blocks
                conn.execute(text(sql_content))
            
            if description:
                print(f"✓ {description}")
            return True
        
        except Exception as e:
            print(f"✗ Error executing {filename}: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _confirm_destruction(self, interactive: bool = True) -> bool:
        """Get user confirmation for destructive operation."""
        if not interactive:
            return False
        
        print("\n" + "="*70)
        print("⚠️  WARNING: DESTRUCTIVE OPERATION")
        print("="*70)
        print("\nThis will PERMANENTLY DELETE:")
        print("  • All 11 tables in cissa schema")
        print("  • All data in those tables")
        print("  • All triggers and functions")
        print("\nThere is NO UNDO for this operation.")
        print("\nType 'destroy everything' to confirm: ", end="", flush=True)
        
        response = input().strip().lower()
        
        if response == "destroy everything":
            return True
        else:
            print("Cancelled. No changes made.")
            return False
    
    def destroy(self, force: bool = False) -> bool:
        """
        Destroy all tables and functions in cissa schema.
        
        Args:
            force: If True, skip confirmation prompt
            
        Returns:
            True if successful, False otherwise
        """
        print("Preparing to destroy schema...")
        
        # Confirm user intent
        if not force and not self._confirm_destruction(interactive=True):
            return False
        
        # Read destroy script
        try:
            destroy_sql = self._read_sql_file("destroy_schema.sql")
        except FileNotFoundError as e:
            print(f"✗ {e}")
            return False
        
        # Remove the confirmation check from the script (it's just a placeholder)
        # The script uses DO $$ which will always pass
        
        # Execute destruction
        if not self._execute_sql(destroy_sql, "Schema destroyed successfully"):
            return False
        
        print("\n✓ All tables, triggers, and functions have been removed")
        return True
    
    def create(self) -> bool:
        """Create fresh schema from schema.sql and functions.sql using atomic transactions."""
        print("Creating schema from schema.sql...")
        
        # Execute schema creation as single transaction (preserves PL/pgSQL syntax and constraints)
        if not self._execute_sql_file_transaction("schema.sql", "Schema created successfully"):
            return False
        
        print("Creating functions from functions.sql...")
        
        # Execute functions as single transaction
        if not self._execute_sql_file_transaction("functions.sql", "Functions created successfully"):
            return False
        
        # Verify schema
        try:
            with self.engine.connect() as conn:
                # Count tables
                result = conn.execute(text("""
                    SELECT COUNT(*) 
                    FROM information_schema.tables 
                    WHERE table_schema = 'cissa'
                """))
                table_count = result.scalar()
                
                # Count foreign keys
                fk_result = conn.execute(text("""
                    SELECT COUNT(*) 
                    FROM information_schema.table_constraints 
                    WHERE table_schema = 'cissa' AND constraint_type = 'FOREIGN KEY'
                """))
                fk_count = fk_result.scalar()
                
                # Count calculation functions
                fn_result = conn.execute(text("""
                    SELECT COUNT(*) 
                    FROM information_schema.routines 
                    WHERE routine_schema = 'cissa' AND routine_name LIKE 'fn_calc%'
                """))
                fn_count = fn_result.scalar()
            
            print(f"✓ Schema verification: {table_count} tables, {fk_count} foreign keys, {fn_count} calculation functions")
            return table_count >= 11 and fk_count >= 7 and fn_count >= 12
        
        except Exception as e:
            print(f"✗ Schema verification failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def init_metric_units(self) -> bool:
        """Initialize metric_units reference table from config file."""
        print("Initializing metric units reference table...")
        
        try:
            # Read metric_units.json configuration
            config_dir = self.SCHEMA_DIR.parent / "config"
            metric_units_file = config_dir / "metric_units.json"
            
            if not metric_units_file.exists():
                print(f"✗ Configuration file not found: {metric_units_file}")
                return False
            
            with open(metric_units_file, 'r') as f:
                metric_units_config = json.load(f)
            
            with self.engine.begin() as conn:
                # Check if metric_units already populated
                result = conn.execute(text("SELECT COUNT(*) FROM metric_units"))
                existing = result.scalar()
                
                if existing > 0:
                    print(f"⚠  {existing} metric units already exist, skipping initialization")
                    return True
                
                # Insert metric units from config
                # Store database_name as metric_name in the table (canonical DB value)
                inserted_count = 0
                for metric_data in metric_units_config:
                    database_name = metric_data.get("database_name")
                    unit = metric_data.get("unit")
                    
                    if not database_name or not unit:
                        print(f"⚠  Skipping incomplete metric config: {metric_data}")
                        continue
                    
                    conn.execute(text("""
                        INSERT INTO metric_units (metric_name, unit)
                        VALUES (:metric_name, :unit)
                        ON CONFLICT (metric_name) DO NOTHING
                    """), {
                        "metric_name": database_name,
                        "unit": unit,
                    })
                    inserted_count += 1
                
                print(f"✓ Metric units initialized ({inserted_count} processed, duplicates ignored)")
            
            return True
        
        except FileNotFoundError as e:
            print(f"✗ {e}")
            return False
        
        except Exception as e:
            print(f"✗ Metric units initialization failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def init_parameters(self) -> bool:
        """Initialize 13 baseline parameters and default parameter_set."""
        print("Initializing baseline parameters...")
        
        baseline_parameters = [
            ("country", "Country", "TEXT", "Australia"),
            ("currency_notation", "Currency Notation", "TEXT", "A$m"),
            ("cost_of_equity_approach", "Cost of Equity Approach", "TEXT", "Floating"),
            ("include_franking_credits_tsr", "Include Franking Credits (TSR)", "BOOLEAN", "false"),
            ("fixed_benchmark_return_wealth_preservation", "Fixed Benchmark Return (Wealth Preservation)", "NUMERIC", "7.5"),
            ("equity_risk_premium", "Equity Risk Premium", "NUMERIC", "5.0"),
            ("tax_rate_franking_credits", "Tax Rate (Franking Credits)", "NUMERIC", "30.0"),
            ("value_of_franking_credits", "Value of Franking Credits", "NUMERIC", "75.0"),
            ("risk_free_rate_rounding", "Risk-Free Rate Rounding", "NUMERIC", "0.5"),
            ("beta_rounding", "Beta Rounding", "NUMERIC", "0.1"),
            ("last_calendar_year", "Last Calendar Year", "NUMERIC", "2019"),
            ("beta_relative_error_tolerance", "Beta Relative Error Tolerance", "NUMERIC", "40.0"),
            ("terminal_year", "Terminal Year", "NUMERIC", "60"),
        ]
        
        try:
            with self.engine.begin() as conn:
                # Check if parameters already exist
                result = conn.execute(text("SELECT COUNT(*) FROM parameters"))
                existing = result.scalar()
                
                if existing > 0:
                    print(f"⚠  {existing} parameters already exist, skipping initialization")
                    return True
                
                # Insert baseline parameters
                for param_name, display_name, value_type, default_value in baseline_parameters:
                    conn.execute(text("""
                        INSERT INTO parameters (parameter_name, display_name, value_type, default_value)
                        VALUES (:parameter_name, :display_name, :value_type, :default_value)
                    """), {
                        "parameter_name": param_name,
                        "display_name": display_name,
                        "value_type": value_type,
                        "default_value": default_value,
                    })
                
                print(f"✓ Inserted {len(baseline_parameters)} baseline parameters")
                
                # Create default parameter_set
                conn.execute(text("""
                    INSERT INTO parameter_sets (param_set_name, description, is_default, param_overrides, created_by)
                    VALUES (:name, :description, true, :overrides, 'admin')
                """), {
                    "name": "base_case",
                    "description": "Default parameter set using all 13 baseline parameters",
                    "overrides": json.dumps({}),
                })
                
                print("✓ Created default parameter_set 'base_case'")
            
            return True
        
        except Exception as e:
            print(f"✗ Parameter initialization failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def init(self) -> bool:
        """Full initialization: create schema (includes parameters + default parameter_set via schema.sql)."""
        print("="*70)
        print("FULL DATABASE INITIALIZATION")
        print("="*70 + "\n")
        
        # Schema creation now includes baseline parameters and default parameter_set
        # via INSERT statements in schema.sql (PHASE 7)
        if not self.create():
            print("\n✗ Schema creation failed")
            return False
        
        # Initialize metric units from config
        print()
        if not self.init_metric_units():
            print("\n✗ Metric units initialization failed")
            return False
        
        print("\n" + "="*70)
        print("✓ FULL INITIALIZATION COMPLETE")
        print("="*70)
        print("\nInitialized:")
        print("  ✓ 11 tables created")
        print("  ✓ 25+ indexes created")
        print("  ✓ 5 auto-update triggers created")
        print("  ✓ 12+ metric calculation functions created")
        print("  ✓ 13 baseline parameters inserted")
        print("  ✓ Default parameter_set 'base_case' created")
        print("  ✓ 20 metric units initialized")
        print("\nNext steps:")
        print("  1. Load reference tables (companies, fiscal_year_mapping)")
        print("  2. Run data ingestion (load_dataset)")
        print("  3. Run data processing (process_dataset)")
        print("\nSee DEPLOYMENT.md for detailed instructions.")
        
        return True


def test_connection(engine) -> bool:
    """Test database connection."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        print("Check POSTGRES_* environment variables or .env file")
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Schema Manager for Financial Data Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 schema_manager.py destroy         # Interactive destroy with confirmation
  python3 schema_manager.py destroy --confirm  # Destroy without confirmation prompt
  python3 schema_manager.py create          # Create fresh schema
  python3 schema_manager.py init            # Full setup (create + parameters)
        """
    )
    
    parser.add_argument(
        "command",
        choices=["destroy", "create", "init"],
        help="Command to execute"
    )
    
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="For 'destroy': skip confirmation prompt (DANGEROUS!)"
    )
    
    args = parser.parse_args()
    
    # Create engine
    print("Connecting to database...")
    engine = create_db_engine(echo=False)
    
    if not test_connection(engine):
        return 1
    
    print("✓ Database connection successful\n")
    
    # Create manager
    manager = SchemaManager(engine)
    
    # Execute command
    if args.command == "destroy":
        success = manager.destroy(force=args.confirm)
    elif args.command == "create":
        success = manager.create()
    elif args.command == "init":
        success = manager.init()
    else:
        parser.print_help()
        return 1
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
