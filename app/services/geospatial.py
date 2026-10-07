import json
import zipfile
from pathlib import Path

from shapely.geometry import mapping
from tempfile import TemporaryDirectory

import geopandas as gpd

from app.core.config import settings


class GeoProcessingError(Exception):
    pass


def _safe_extract(zip_path: Path, target: Path) -> None:
    with zipfile.ZipFile(zip_path) as zf:
        members = zf.infolist()
        if not members:
            raise GeoProcessingError("Shapefile ZIP is empty.")
        for member in members:
            destination = (target / member.filename).resolve()
            if not str(destination).startswith(str(target.resolve())):
                raise GeoProcessingError("Unsafe ZIP archive: path traversal detected.")
        zf.extractall(target)


def read_geospatial_file(path: Path, file_type: str) -> gpd.GeoDataFrame:
    try:
        if file_type == "kml":
            gdf = gpd.read_file(path)
            # OGC KML 2.2 standard specifies WGS84 geographic coordinates (EPSG:4326)
            if gdf.crs is None:
                gdf.set_crs("EPSG:4326", inplace=True)
            return gdf

        with TemporaryDirectory() as tmp:
            extract_dir = Path(tmp)
            _safe_extract(path, extract_dir)
            shp_files = [
                p for p in extract_dir.rglob("*.shp")
                if not p.name.startswith("._") and "__MACOSX" not in p.parts
            ]
            if not shp_files:
                raise GeoProcessingError("ZIP archive does not contain a .shp file.")
            gdf = gpd.read_file(shp_files[0])
            return gdf
    except GeoProcessingError:
        raise
    except Exception as exc:
        raise GeoProcessingError(f"Unable to parse geospatial file: {exc}") from exc


def serializable_geometry(geometry) -> dict[str, object] | None:
    if geometry is None or geometry.is_empty:
        return None
    return mapping(geometry)


def serializable_properties(row) -> dict[str, object]:
    result = {}
    for key, value in row.items():
        if key == "geometry":
            continue
        try:
            json.dumps(value)
            result[str(key)] = value
        except TypeError:
            result[str(key)] = str(value)
    return result


def select_measurement_crs(gdf: gpd.GeoDataFrame):
    if gdf.crs is None:
        return None
    if gdf.crs.is_projected:
        try:
            unit = gdf.crs.axis_info[0].unit_name.lower()
            if unit in {"metre", "meter", "metres", "meters"}:
                return gdf.crs
        except (IndexError, AttributeError):
            pass

    # Ensure there are valid geometries before estimating UTM CRS
    valid_geoms = gdf[~gdf.geometry.is_empty & gdf.geometry.notna()]
    if valid_geoms.empty:
        return None

    try:
        return valid_geoms.estimate_utm_crs()
    except Exception as exc:
        raise GeoProcessingError(f"Could not select a projected measurement CRS: {exc}") from exc

