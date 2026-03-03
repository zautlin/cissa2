"""
Database configuration and connection setup.

Loads environment variables from ../datahex-local/.env file if available,
otherwise falls back to system environment variables.
"""

import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool

# Load environment variables from .env file (if available)
try:
    from dotenv import load_dotenv
    # Try to find .env in ../datahex-local/ relative to this file
    # Structure: /home/ubuntu/cissa/backend/database/etl/config.py
    #           -> /home/ubuntu/datahex-local/.env
    env_path = Path(__file__).parent.parent.parent.parent / "datahex-local" / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        print(f"Loaded environment from {env_path}")
    else:
        # Fallback: try loading from current directory or parent
        fallback_path = Path.cwd() / ".env"
        if fallback_path.exists():
            load_dotenv(fallback_path)
            print(f"Loaded environment from {fallback_path}")
except ImportError:
    # python-dotenv not installed, use system environment variables
    pass


def get_db_url() -> str:
    """
    Build PostgreSQL connection URL from environment variables.
    
    Reads from:
    - POSTGRES_HOST (default: "localhost")
    - POSTGRES_PORT (default: "5432")
    - POSTGRES_USER (default: "postgres")
    - POSTGRES_PASSWORD (default: "changeme")
    - POSTGRES_DB (default: "rozetta")
    
    Returns:
        str: PostgreSQL connection URL
    """
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "changeme")
    database = os.getenv("POSTGRES_DB", "rozetta")
    
    return f"postgresql://{user}:{password}@{host}:{port}/{database}"


def create_db_engine(echo: bool = False):
    """
    Create SQLAlchemy database engine.
    
    Args:
        echo: If True, log all SQL statements
        
    Returns:
        Engine: SQLAlchemy database engine
    """
    db_url = get_db_url()
    engine = create_engine(db_url, echo=echo, poolclass=NullPool)
    return engine


if __name__ == "__main__":
    # Test connection
    engine = create_db_engine()
    with engine.connect() as conn:
        result = conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        print("✓ Database connection successful")
