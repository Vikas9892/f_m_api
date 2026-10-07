import hashlib
import json
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.file import GeoFile
from app.models.measurement import FeatureMeasurement
from app.schemas.file import (
    FileResponse,
    FileSummaryResponse,
    MeasurementListResponse,
    MeasurementResponse,
)
from app.services.file_validator import validate_upload
from app.services.geospatial import GeoProcessingError, read_geospatial_file
from app.services.measurement import calculate_measurements

router = APIRouter(prefix="/api/files", tags=["Files"])


@router.post("/", response_model=FileResponse, status_code=201)
async def upload_file(file: UploadFile = File(...), db: Session = Depends(get_db)):
    data = await validate_upload(file)
    filename = file.filename or "upload"
    suffix = Path(filename).suffix.lower()
    file_type = "kml" if suffix == ".kml" else "shapefile_zip"

    file_id = str(uuid4())
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    stored_path = upload_dir / f"{file_id}{suffix}"
    stored_path.write_bytes(data)

    record = GeoFile(
        id=file_id,
        filename=filename,
        file_type=file_type,
        stored_path=str(stored_path),
        sha256=hashlib.sha256(data).hexdigest(),
        size_bytes=len(data),
        status="PROCESSING",
    )
    db.add(record)
    db.commit()

    try:
        gdf = read_geospatial_file(stored_path, file_type)
        if len(gdf) > settings.max_features:
            raise GeoProcessingError(f"Feature count exceeds the {settings.max_features} feature limit.")

        results, measurement_crs = calculate_measurements(gdf)
        record.feature_count = len(gdf)
        record.crs = gdf.crs.to_string() if gdf.crs else None
        record.measurement_crs = measurement_crs
        record.status = "COMPLETED"

        for result in results:
            db.add(FeatureMeasurement(
                file_id=file_id,
                feature_index=result["feature_index"],
                geometry_type=result["geometry_type"],
                crs=result.get("crs") or record.crs,
                properties_json=json.dumps(result["properties"], default=str),
                geometry_json=json.dumps(result["geometry"], default=str),
                measurement_type=result["measurement_type"],
                measurement_value=result["measurement_value"],
                measurement_unit=result["measurement_unit"],
                error=result["error"],
            ))
        db.commit()
    except Exception as exc:
        record.status = "FAILED"
        record.error_message = str(exc)
        db.commit()
        raise HTTPException(422, str(exc)) from exc

    return record


@router.get("/", response_model=list[FileResponse])
def list_files(limit: int = 50, offset: int = 0, db: Session = Depends(get_db)):
    stmt = select(GeoFile).order_by(GeoFile.created_at.desc()).offset(offset).limit(limit)
    return db.scalars(stmt).all()


@router.get("/{file_id}/", response_model=FileResponse)
def get_file(file_id: str, db: Session = Depends(get_db)):
    record = db.get(GeoFile, file_id)
    if not record:
        raise HTTPException(404, "File not found.")
    return record


@router.get("/{file_id}/measurements/", response_model=MeasurementListResponse)
def get_measurements(file_id: str, db: Session = Depends(get_db)):
    record = db.get(GeoFile, file_id)
    if not record:
        raise HTTPException(404, "File not found.")

    rows = db.scalars(
        select(FeatureMeasurement)
        .where(FeatureMeasurement.file_id == file_id)
        .order_by(FeatureMeasurement.feature_index)
    ).all()

    results = [
        MeasurementResponse(
            feature_index=row.feature_index,
            geometry_type=row.geometry_type,
            crs=row.crs or record.crs,
            geometry=json.loads(row.geometry_json) if row.geometry_json else None,
            properties=json.loads(row.properties_json) if row.properties_json else {},
            measurement_type=row.measurement_type,
            measurement_value=row.measurement_value,
            measurement_unit=row.measurement_unit,
            error=row.error,
        )
        for row in rows
    ]
    return MeasurementListResponse(
        file_id=file_id,
        filename=record.filename,
        crs=record.crs,
        measurement_crs=record.measurement_crs,
        total_features=len(results),
        results=results,
    )


@router.get("/{file_id}/summary/", response_model=FileSummaryResponse)
def get_file_summary(file_id: str, db: Session = Depends(get_db)):
    record = db.get(GeoFile, file_id)
    if not record:
        raise HTTPException(404, "File not found.")

    rows = db.scalars(
        select(FeatureMeasurement).where(FeatureMeasurement.file_id == file_id)
    ).all()

    geom_breakdown: dict[str, int] = {}
    total_area = 0.0
    total_length = 0.0

    for r in rows:
        geom_breakdown[r.geometry_type] = geom_breakdown.get(r.geometry_type, 0) + 1
        if r.measurement_type == "area" and r.measurement_value is not None:
            total_area += r.measurement_value
        elif r.measurement_type == "length" and r.measurement_value is not None:
            total_length += r.measurement_value

    return FileSummaryResponse(
        file_id=file_id,
        filename=record.filename,
        status=record.status,
        crs=record.crs,
        measurement_crs=record.measurement_crs,
        total_features=record.feature_count,
        geometry_breakdown=geom_breakdown,
        total_area_sq_m=round(total_area, 4),
        total_length_m=round(total_length, 4),
    )


@router.delete("/{file_id}/", status_code=204)
def delete_file(file_id: str, db: Session = Depends(get_db)):
    record = db.get(GeoFile, file_id)
    if not record:
        raise HTTPException(404, "File not found.")

    if record.stored_path:
        path = Path(record.stored_path)
        if path.exists():
            path.unlink(missing_ok=True)

    db.delete(record)
    db.commit()
    return None

