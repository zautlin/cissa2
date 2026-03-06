# ============================================================================
# FastAPI Configuration and Settings
# ============================================================================
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
import logging
from pathlib import Path
from dotenv import load_dotenv
import os

# Load .env immediately on module import
# Try multiple possible locations
possible_env_paths = [
    Path(".env"),  # Current directory
    Path("../.env"),  # Parent directory
    Path("/home/ubuntu/cissa/.env"),  # Absolute path
]

for env_path in possible_env_paths:
    if env_path.resolve().exists():
        print(f"Loading .env from: {env_path.resolve()}")
        load_dotenv(dotenv_path=str(env_path.resolve()))
        break


class Settings(BaseSettings):
    """Application settings loaded from environment"""
    
    model_config = SettingsConfigDict(
        case_sensitive=True,
        extra='ignore'
    )
    
    # Database - read from DATABASE_URL env var
    DATABASE_URL: str
    
    # Environment
    fastapi_env: str = "development"
    log_level: str = "info"
    workers: int = 1
    
    # Metric Calculation
    metrics_batch_size: int = 1000
    metrics_timeout_seconds: int = 300


@lru_cache()
def get_settings() -> Settings:
    """Singleton settings instance"""
    return Settings()


def get_logger(name: str) -> logging.Logger:
    """Configure and return a logger"""
    logger = logging.getLogger(name)
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    if not logger.handlers:
        logger.addHandler(handler)
    return logger
