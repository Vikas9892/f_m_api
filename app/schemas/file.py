from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ProcessingStatus(str, Enum):
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class FileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    filename: str
    file_type: str
    size_bytes: int = Field(ge=0)
    feature_count: int = Field(ge=0)
    crs: str | None
    measurement_crs: str | None
    status: ProcessingStatus
    created_at: datetime
    error_message: str | None = None


class MeasurementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    feature_index: int = Field(ge=0)
    geometry_type: str
    geometry: dict[str, object] | None = None
    crs: str | None = None
    properties: dict[str, object] = Field(default_factory=dict)
    measurement_type: str | None = None
    measurement_value: float | None = None
    measurement_unit: str | None = None
    error: str | None = None


class MeasurementListResponse(BaseModel):
    file_id: str
    filename: str | None = None
    crs: str | None = None
    measurement_crs: str | None = None
    total_features: int = 0
    results: list[MeasurementResponse]


class FileSummaryResponse(BaseModel):
    file_id: str
    filename: str
    status: ProcessingStatus
    crs: str | None
    measurement_crs: str | None
    total_features: int
    geometry_breakdown: dict[str, int]
    total_area_sq_m: float
    total_length_m: float
