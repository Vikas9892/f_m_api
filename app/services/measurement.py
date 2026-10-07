import geopandas as gpd

from app.services.geospatial import (
    select_measurement_crs,
    serializable_geometry,
    serializable_properties,
)


def calculate_measurements(gdf: gpd.GeoDataFrame) -> tuple[list[dict], str | None]:
    measurement_crs = None
    projected = gdf

    source_crs_str = gdf.crs.to_string() if gdf.crs is not None else None

    if gdf.crs is not None:
        target_crs = select_measurement_crs(gdf)
        if target_crs is not None:
            measurement_crs = target_crs.to_string()
            if gdf.crs != target_crs:
                projected = gdf.to_crs(target_crs)

    results = []
    for feature_index, (_, row) in enumerate(gdf.iterrows()):
        geometry = row.geometry
        geometry_type = geometry.geom_type if geometry is not None else "Unknown"
        item = {
            "feature_index": feature_index,
            "geometry_type": geometry_type,
            "geometry": serializable_geometry(geometry),
            "crs": source_crs_str,
            "properties": serializable_properties(row),
            "measurement_type": None,
            "measurement_value": None,
            "measurement_unit": None,
            "error": None,
        }

        try:
            if geometry is None or geometry.is_empty:
                item["error"] = "Empty geometry; measurement skipped."
            elif gdf.crs is None and geometry_type not in {"Point", "MultiPoint"}:
                item["error"] = "Source CRS is missing; area/length measurement skipped to avoid incorrect units."
            elif geometry_type in {"Polygon", "MultiPolygon"}:
                item["measurement_type"] = "area"
                proj_geom = projected.geometry.iloc[feature_index]
                item["measurement_value"] = round(float(proj_geom.area), 4)
                item["measurement_unit"] = "m²"
            elif geometry_type in {"LineString", "MultiLineString"}:
                item["measurement_type"] = "length"
                proj_geom = projected.geometry.iloc[feature_index]
                item["measurement_value"] = round(float(proj_geom.length), 4)
                item["measurement_unit"] = "m"
            elif geometry_type in {"Point", "MultiPoint"}:
                # Points have no length or area measurement
                pass
            else:
                item["error"] = f"Measurement not supported for geometry type '{geometry_type}'."
        except Exception as exc:
            item["error"] = f"Measurement failed: {exc}"

        results.append(item)

    return results, measurement_crs

