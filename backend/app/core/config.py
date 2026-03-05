# ============================================================================
# FastAPI Configuration and Settings
# ============================================================================
from pydantic_settings import BaseSettings
from functools import lru_cache
import logging


class Settings(BaseSettings):
    """Application settings loaded from .env file"""
    
    # Database
    database_url: str
    
    # Environment
    fastapi_env: str = "development"
    log_level: str = "info"
    workers: int = 1
    
    # Metric Calculation
    metrics_batch_size: int = 1000
    metrics_timeout_seconds: int = 300
    
    class Config:
        env_file = ".env"
        case_sensitive = False


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
