import geopandas as gpd
from shapely.geometry import LineString, Point, Polygon

from app.services.measurement import calculate_measurements


def test_geographic_polygon_is_measured_in_square_metres():
    gdf = gpd.GeoDataFrame(
        {"name": ["plot"]},
        geometry=[Polygon([(77.0, 23.0), (77.001, 23.0), (77.001, 23.001), (77.0, 23.001)])],
        crs="EPSG:4326",
    )
    results, measurement_crs = calculate_measurements(gdf)
    assert measurement_crs is not None
    assert results[0]["crs"] == "EPSG:4326"
    assert results[0]["measurement_type"] == "area"
    assert results[0]["measurement_unit"] == "m²"
    assert results[0]["measurement_value"] > 0


def test_linestring_is_measured_in_metres():
    gdf = gpd.GeoDataFrame(
        geometry=[LineString([(77.0, 23.0), (77.01, 23.01)])],
        crs="EPSG:4326",
    )
    results, measurement_crs = calculate_measurements(gdf)
    assert measurement_crs is not None
    assert results[0]["measurement_type"] == "length"
    assert results[0]["measurement_unit"] == "m"
    assert results[0]["measurement_value"] > 0


def test_point_has_no_measurement():
    gdf = gpd.GeoDataFrame(geometry=[Point(77, 23)], crs="EPSG:4326")
    results, _ = calculate_measurements(gdf)
    assert results[0]["geometry_type"] == "Point"
    assert results[0]["measurement_value"] is None
    assert results[0]["error"] is None


def test_missing_crs_skips_metric_measurement():
    gdf = gpd.GeoDataFrame(geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])])
    results, measurement_crs = calculate_measurements(gdf)
    assert measurement_crs is None
    assert results[0]["measurement_value"] is None
    assert "CRS is missing" in results[0]["error"]


def test_empty_geometry_handled_gracefully():
    gdf = gpd.GeoDataFrame(geometry=[Polygon()], crs="EPSG:4326")
    results, _ = calculate_measurements(gdf)
    assert results[0]["measurement_value"] is None
    assert "Empty geometry" in results[0]["error"]


def test_projected_crs_reused_directly():
    # EPSG:32643 is UTM Zone 43N (units in metres)
    gdf = gpd.GeoDataFrame(
        geometry=[Polygon([(300000, 2500000), (300100, 2500000), (300100, 2500100), (300000, 2500100)])],
        crs="EPSG:32643",
    )
    results, measurement_crs = calculate_measurements(gdf)
    assert measurement_crs == "EPSG:32643"
    assert results[0]["measurement_type"] == "area"
    assert results[0]["measurement_value"] == 10000.0  # 100m x 100m = 10,000 m²

