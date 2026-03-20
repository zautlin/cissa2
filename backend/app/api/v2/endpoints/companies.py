from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from pydantic import BaseModel
from typing import List, Optional

from app.core.database import get_db
from app.core.config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v2", tags=["companies"])


class Company(BaseModel):
    ticker: str
    company_name: Optional[str]
    sector: Optional[str]
    exchange: Optional[str]


@router.get("/companies", response_model=List[Company])
async def list_companies(db: AsyncSession = Depends(get_db)) -> List[Company]:
    """
    Return all companies from cissa.companies with ticker, name, sector, and exchange.
    Sectors are derived from the BICS level-1 classification where available,
    falling back to the sector column.
    """
    try:
        result = await db.execute(text("""
            SELECT
                ticker,
                name        AS company_name,
                COALESCE(bics_level_1, sector) AS sector,
                currency    AS exchange
            FROM cissa.companies
            ORDER BY ticker
        """))
        rows = result.mappings().all()
        return [Company(**row) for row in rows]
    except Exception as e:
        logger.error(f"Error fetching companies: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch companies: {e}",
        )
