import io
import tempfile
import zipfile
from pathlib import Path

import geopandas as gpd
import pytest
from fastapi.testclient import TestClient
from shapely.geometry import LineString, Point, Polygon

from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def sample_kml_bytes() -> bytes:
    gdf = gpd.GeoDataFrame(
        {
            "name": ["Sample Park", "Main Boulevard", "Entrance Gate"],
            "description": ["Public park area", "Primary road", "Entry point"],
        },
        geometry=[
            Polygon([(77.2090, 28.6139), (77.2100, 28.6139), (77.2100, 28.6149), (77.2090, 28.6149), (77.2090, 28.6139)]),
            LineString([(77.2090, 28.6139), (77.2150, 28.6180)]),
            Point(77.2095, 28.6142),
        ],
        crs="EPSG:4326",
    )
    with tempfile.NamedTemporaryFile(suffix=".kml", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        gdf.to_file(tmp_path, driver="KML")
        return tmp_path.read_bytes()
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


@pytest.fixture
def sample_shapefile_zip_bytes() -> bytes:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        shp_path = tmp / "parcels.shp"
        gdf = gpd.GeoDataFrame(
            {"parcel_id": ["P101", "P102"], "zone": ["Commercial", "Residential"]},
            geometry=[
                Polygon([(77.10, 28.50), (77.11, 28.50), (77.11, 28.51), (77.10, 28.51), (77.10, 28.50)]),
                Polygon([(77.12, 28.50), (77.13, 28.50), (77.13, 28.51), (77.12, 28.51), (77.12, 28.50)]),
            ],
            crs="EPSG:4326",
        )
        gdf.to_file(shp_path)

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            for file_path in tmp.iterdir():
                zf.write(file_path, arcname=file_path.name)
        return zip_buffer.getvalue()


def test_upload_kml_and_query_measurements(client, sample_kml_bytes):
    # 1. Upload KML
    response = client.post(
        "/api/files/",
        files={"file": ("city_plan.kml", sample_kml_bytes, "application/vnd.google-earth.kml+xml")},
    )
    assert response.status_code == 201
    file_data = response.json()
    file_id = file_data["id"]
    assert file_data["filename"] == "city_plan.kml"
    assert file_data["file_type"] == "kml"
    assert file_data["feature_count"] == 3
    assert file_data["status"] == "COMPLETED"
    assert "EPSG:4326" in file_data["crs"]
    assert file_data["measurement_crs"] is not None

    # 2. Query File Metadata
    get_file_resp = client.get(f"/api/files/{file_id}/")
    assert get_file_resp.status_code == 200
    assert get_file_resp.json()["id"] == file_id

    # 3. Query Measurements
    measure_resp = client.get(f"/api/files/{file_id}/measurements/")
    assert measure_resp.status_code == 200
    meas_data = measure_resp.json()
    assert meas_data["file_id"] == file_id
    assert meas_data["total_features"] == 3
    results = meas_data["results"]
    assert len(results) == 3

    # Check Polygon
    poly = next(r for r in results if r["geometry_type"] == "Polygon")
    assert poly["measurement_type"] == "area"
    assert poly["measurement_unit"] == "m²"
    assert poly["measurement_value"] > 0
    assert poly["crs"] is not None

    # Check LineString
    line = next(r for r in results if r["geometry_type"] == "LineString")
    assert line["measurement_type"] == "length"
    assert line["measurement_unit"] == "m"
    assert line["measurement_value"] > 0

    # Check Point
    point = next(r for r in results if r["geometry_type"] == "Point")
    assert point["measurement_type"] is None
    assert point["measurement_value"] is None
    assert point["error"] is None

    # 4. Query Summary
    summary_resp = client.get(f"/api/files/{file_id}/summary/")
    assert summary_resp.status_code == 200
    summary = summary_resp.json()
    assert summary["total_features"] == 3
    assert summary["total_area_sq_m"] > 0
    assert summary["total_length_m"] > 0
    assert summary["geometry_breakdown"]["Polygon"] == 1
    assert summary["geometry_breakdown"]["LineString"] == 1
    assert summary["geometry_breakdown"]["Point"] == 1

    # 5. Delete file
    del_resp = client.delete(f"/api/files/{file_id}/")
    assert del_resp.status_code == 204
    assert client.get(f"/api/files/{file_id}/").status_code == 404


def test_upload_shapefile_zip(client, sample_shapefile_zip_bytes):
    response = client.post(
        "/api/files/",
        files={"file": ("parcels.zip", sample_shapefile_zip_bytes, "application/zip")},
    )
    assert response.status_code == 201
    file_data = response.json()
    file_id = file_data["id"]
    assert file_data["filename"] == "parcels.zip"
    assert file_data["file_type"] == "shapefile_zip"
    assert file_data["feature_count"] == 2
    assert file_data["status"] == "COMPLETED"

    meas_resp = client.get(f"/api/files/{file_id}/measurements/")
    assert meas_resp.status_code == 200
    results = meas_resp.json()["results"]
    assert len(results) == 2
    for r in results:
        assert r["geometry_type"] == "Polygon"
        assert r["measurement_type"] == "area"
        assert r["measurement_unit"] == "m²"
        assert r["measurement_value"] > 0


def test_upload_unsupported_file_extension(client):
    response = client.post(
        "/api/files/",
        files={"file": ("notes.txt", b"some plain text", "text/plain")},
    )
    assert response.status_code == 400
    assert "supported" in response.json()["detail"].lower()


def test_upload_empty_file(client):
    response = client.post(
        "/api/files/",
        files={"file": ("empty.kml", b"", "application/xml")},
    )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_get_nonexistent_file(client):
    response = client.get("/api/files/nonexistent-id/")
    assert response.status_code == 404
