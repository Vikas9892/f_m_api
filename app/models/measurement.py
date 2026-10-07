from uuid import uuid4

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class FeatureMeasurement(Base):
    __tablename__ = "feature_measurements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    file_id: Mapped[str] = mapped_column(ForeignKey("geo_files.id", ondelete="CASCADE"), index=True)
    feature_index: Mapped[int] = mapped_column(Integer)
    geometry_type: Mapped[str] = mapped_column(String(50))
    crs: Mapped[str | None] = mapped_column(String(255), nullable=True)
    properties_json: Mapped[str] = mapped_column(Text, default="{}")
    geometry_json: Mapped[str] = mapped_column(Text, default="{}")
    measurement_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    measurement_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    measurement_unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
