# ============================================================================
# SQLAlchemy ORM Model for Metrics Output
# ============================================================================
from datetime import datetime
from uuid import UUID
from sqlalchemy import String, Integer, Numeric, ForeignKey, Index, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSON


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all ORM models."""
    pass


class MetricsOutput(Base):
    """
    ORM model for metrics_outputs table.
    
    Represents calculated metrics derived from fundamentals + parameter sets.
    One row per (dataset, param_set, ticker, fiscal_year, metric).
    """
    __tablename__ = "metrics_outputs"
    __table_args__ = (
        # Uniqueness constraint: one row per (dataset, params, ticker, fiscal_year, metric)
        Index(
            "idx_metrics_outputs_unique",
            "dataset_id",
            "param_set_id",
            "ticker",
            "fiscal_year",
            "output_metric_name",
            unique=True,
        ),
        # Access pattern indexes
        Index("idx_metrics_outputs_dataset", "dataset_id"),
        Index("idx_metrics_outputs_param_set", "param_set_id"),
        Index("idx_metrics_outputs_ticker_fy", "ticker", "fiscal_year"),
        {"schema": "cissa"},
    )

    # Primary key: auto-incrementing BIGINT
    metrics_output_id: Mapped[int] = mapped_column(primary_key=True)

    # Foreign keys
    dataset_id: Mapped[UUID] = mapped_column(
        ForeignKey("cissa.dataset_versions.dataset_id", ondelete="CASCADE"),
        nullable=False,
    )
    param_set_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("cissa.parameter_sets.param_set_id", ondelete="CASCADE"),
        nullable=True,
    )

    # Data fields
    ticker: Mapped[str] = mapped_column(String, nullable=False)
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    output_metric_name: Mapped[str] = mapped_column(String, nullable=False)
    output_metric_value: Mapped[float] = mapped_column(Numeric, nullable=False)

    # Metadata: flexible storage for metric-specific attributes
    metric_metadata: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False, name="metadata")

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
    )
