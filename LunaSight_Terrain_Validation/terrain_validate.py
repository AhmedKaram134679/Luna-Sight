#!/usr/bin/env python3
"""Read-only metadata, footprint and overlap diagnostics for lunar DEM rasters.

Requires GDAL's gdalinfo CLI. pyproj is optional for coordinate transformations.
No raster is modified and no terrain horizon is calculated.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


def run_gdalinfo(path: Path) -> dict[str, Any]:
    executable = shutil.which("gdalinfo")
    if not executable:
        raise RuntimeError("gdalinfo was not found on PATH; install GDAL before inspecting rasters")
    proc = subprocess.run(
        [executable, "-json", "-mdd", "all", str(path)],
        check=False, capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"gdalinfo failed for {path}: {proc.stderr.strip()}")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"gdalinfo returned invalid JSON for {path}") from exc


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def transform_lonlat(lon: float, lat: float, target_wkt: str) -> tuple[float, float]:
    try:
        from pyproj import CRS, Transformer
    except ImportError as exc:
        raise RuntimeError("pyproj is required because the raster CRS is not geographic WGS84") from exc
    source = CRS.from_epsg(4326)
    target = CRS.from_wkt(target_wkt)
    transformer = Transformer.from_crs(source, target, always_xy=True)
    x, y = transformer.transform(lon, lat)
    if not (math.isfinite(x) and math.isfinite(y)):
        raise RuntimeError("Coordinate transformation produced non-finite coordinates")
    return float(x), float(y)


def _geographic_xy(lon: float, lat: float, wkt: str) -> tuple[float, float] | None:
    try:
        from pyproj import CRS
        crs = CRS.from_wkt(wkt)
        if crs.is_geographic:
            return lon, lat
    except Exception:
        return None
    return None


def _corners(gt: list[float], width: int, height: int) -> list[tuple[float, float]]:
    # Pixel-corner footprint. Pixel-center sampling is handled separately.
    return [
        (gt[0], gt[3]),
        (gt[0] + width * gt[1], gt[3] + width * gt[4]),
        (gt[0] + height * gt[2], gt[3] + height * gt[5]),
        (gt[0] + width * gt[1] + height * gt[2],
         gt[3] + width * gt[4] + height * gt[5]),
    ]


def _point_in_polygon(point: tuple[float, float], polygon: list[tuple[float, float]]) -> bool:
    x, y = point
    inside = False
    j = len(polygon) - 1
    for i in range(len(polygon)):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > y) != (yj > y)):
            crossing_x = (xj - xi) * (y - yi) / ((yj - yi) or 1e-300) + xi
            if x < crossing_x:
                inside = not inside
        j = i
    return inside


def _pixel_from_map(x: float, y: float, gt: list[float]) -> tuple[float, float]:
    # Invert the full affine transform, including rotation terms.
    a, b, c, d, e, f = gt[1], gt[2], gt[4], gt[5], x - gt[0], y - gt[3]
    det = a * e - b * c
    if abs(det) < 1e-30:
        raise RuntimeError("Raster geotransform is singular")
    return ((d * e - b * f) / det, (a * f - d * c) / det)


def _sample_dem(path: Path, pixel: float, line: float, band_index: int = 1) -> dict[str, Any]:
    try:
        from osgeo import gdal
    except ImportError as exc:
        raise RuntimeError("Python GDAL bindings (osgeo) are required to sample raster values") from exc
    ds = gdal.Open(str(path), gdal.GA_ReadOnly)
    if ds is None:
        raise RuntimeError(f"GDAL could not open raster: {path}")
    band = ds.GetRasterBand(band_index)
    col, row = int(math.floor(pixel)), int(math.floor(line))
    if col < 0 or row < 0 or col >= ds.RasterXSize or row >= ds.RasterYSize:
        return {"status": "outside"}
    arr = band.ReadAsArray(col, row, 1, 1)
    value = float(arr[0, 0])
    nodata = band.GetNoDataValue()
    valid = math.isfinite(value) and (nodata is None or value != nodata)
    return {"status": "valid" if valid else "nodata", "value": value if valid else None,
            "pixel_column": col, "pixel_row": row, "nodata": nodata}


def inspect_raster(path: Path, latitude: float, longitude: float,
                   latitude_type: str, radius_km: float) -> dict[str, Any]:
    if not path.is_file():
        raise RuntimeError(f"Raster does not exist: {path}")
    info = run_gdalinfo(path)
    size = info.get("size")
    gt = info.get("geoTransform")
    bands = info.get("bands", [])
    if not size or not gt or len(gt) != 6 or not bands:
        raise RuntimeError("Raster lacks required size, affine geotransform, or band metadata")
    wkt = info.get("coordinateSystem", {}).get("wkt")
    if not wkt:
        raise RuntimeError("Raster CRS is missing; refusing to guess its projection")
    if not (-90 <= latitude <= 90 and math.isfinite(longitude)):
        raise ValueError("Invalid observer coordinates")
    if radius_km < 0:
        raise ValueError("radius-km must be non-negative")

    geographic = _geographic_xy(longitude, latitude, wkt)
    if geographic is not None:
        x, y = geographic
        crs_transform = "identity geographic coordinates; latitude datum semantics still require confirmation"
    else:
        x, y = transform_lonlat(longitude, latitude, wkt)
        crs_transform = "pyproj EPSG:4326 to raster CRS; lunar datum/frame compatibility NOT established"

    px, py = _pixel_from_map(x, y, gt)
    corners = _corners(gt, int(size[0]), int(size[1]))
    footprint_polygon = corners
    center_inside = _point_in_polygon((x, y), footprint_polygon)
    # Circle perimeter samples in local tangent-plane approximation, transformed pointwise.
    # This is a conservative coverage probe, not a geodesic guarantee.
    perimeter = []
    if radius_km:
        angular = radius_km / 1737.4
        for i in range(72):
            bearing = 2 * math.pi * i / 72
            dlat = angular * math.cos(bearing)
            coslat = max(abs(math.cos(math.radians(latitude))), 1e-8)
            dlon = angular * math.sin(bearing) / coslat
            lat2 = max(-90.0, min(90.0, latitude + math.degrees(dlat)))
            lon2 = longitude + math.degrees(dlon)
            if geographic is not None:
                perimeter.append((lon2, lat2))
            else:
                perimeter.append(transform_lonlat(lon2, lat2, wkt))
    perimeter_inside = all(_point_in_polygon(p, footprint_polygon) for p in perimeter)
    sample = _sample_dem(path, px, py)

    band_reports = []
    for index, band in enumerate(bands, start=1):
        band_reports.append({
            "band": index, "type": band.get("type"), "description": band.get("description"),
            "unit": band.get("unit"), "noDataValue": band.get("noDataValue"),
            "scale": band.get("scale"), "offset": band.get("offset"),
            "metadata": band.get("metadata", {}),
        })
    metadata = info.get("metadata", {})
    all_metadata_text = json.dumps({"dataset": metadata, "bands": band_reports}, ensure_ascii=False).lower()
    vertical_hints = [term for term in ("vertical", "datum", "radius", "elevation", "height")
                      if term in all_metadata_text]
    pixel_registration = metadata.get("AREA_OR_POINT") or info.get("metadata", {}).get("", {}).get("AREA_OR_POINT")

    return {
        "schema_version": 1,
        "raster": str(path.resolve()),
        "sha256": sha256_file(path),
        "driver": info.get("driverShortName"),
        "dimensions_pixels": size,
        "crs_wkt": wkt,
        "geotransform": gt,
        "bounds_map_coordinates": corners,
        "pixel_registration_AREA_OR_POINT": pixel_registration or "UNSPECIFIED",
        "observer_input": {"longitude_positive_east_degrees": longitude,
                           "latitude_degrees": latitude, "latitude_type": latitude_type,
                           "latitude_type_is_product_compatible": False},
        "observer_map_coordinates": {"x": x, "y": y, "pixel": px, "line": py,
                                     "transformation": crs_transform},
        "coverage": {"observer_inside_footprint": center_inside,
                     "sampled_radius_km": radius_km,
                     "perimeter_samples": len(perimeter),
                     "all_perimeter_samples_inside": perimeter_inside,
                     "coverage_status": "PASS_GEOMETRIC_ONLY" if center_inside and perimeter_inside else "FAIL"},
        "observer_pixel_sample": sample,
        "bands": band_reports,
        "dataset_metadata": metadata,
        "vertical_metadata_keyword_hints": vertical_hints,
        "vertical_datum_status": "REQUIRES_EXPLICIT_SOURCE_METADATA_REVIEW",
        "frame_and_lunar_datum_status": "NOT_VALIDATED_BY_GEOGRAPHIC_CRS_TRANSFORM",
        "limitations": [
            "A projected coordinate transform does not prove lunar body-fixed frame or vertical-datum compatibility.",
            "Latitude type and longitude convention must match the source product definition.",
            "Footprint perimeter probing does not prove every ray or every cell is valid.",
            "Pixel spacing is not effective spatial resolution or elevation uncertainty.",
            "A valid observer pixel does not establish complete azimuthal terrain coverage.",
        ],
    }


def compare_rasters(reference: Path, candidate: Path, latitude: float, longitude: float,
                    latitude_type: str, radius_km: float, grid_size: int = 25) -> dict[str, Any]:
    if grid_size < 3 or grid_size > 201:
        raise ValueError("grid-size must be between 3 and 201")
    ref_report = inspect_raster(reference, latitude, longitude, latitude_type, radius_km)
    cand_report = inspect_raster(candidate, latitude, longitude, latitude_type, radius_km)
    if not ref_report["coverage"]["observer_inside_footprint"] or not cand_report["coverage"]["observer_inside_footprint"]:
        raise RuntimeError("Both rasters must cover the observer before overlap comparison")
    try:
        import numpy as np
        from osgeo import gdal, osr
    except ImportError as exc:
        raise RuntimeError("numpy and Python GDAL bindings are required for raster overlap comparison") from exc

    def open_ds(path: Path):
        ds = gdal.Open(str(path), gdal.GA_ReadOnly)
        if ds is None:
            raise RuntimeError(f"Cannot open {path}")
        return ds

    ref_ds, cand_ds = open_ds(reference), open_ds(candidate)
    ref_gt, cand_gt = ref_ds.GetGeoTransform(), cand_ds.GetGeoTransform()
    ref_srs, cand_srs = osr.SpatialReference(), osr.SpatialReference()
    ref_srs.ImportFromWkt(ref_ds.GetProjection())
    cand_srs.ImportFromWkt(cand_ds.GetProjection())
    transform = osr.CoordinateTransformation(ref_srs, cand_srs)
    ref_band, cand_band = ref_ds.GetRasterBand(1), cand_ds.GetRasterBand(1)
    values = []
    angular = radius_km / 1737.4
    for iy in range(grid_size):
        for ix in range(grid_size):
            north = (iy / (grid_size - 1) * 2 - 1) * angular
            east = (ix / (grid_size - 1) * 2 - 1) * angular
            lat = max(-90, min(90, latitude + math.degrees(north)))
            lon = longitude + math.degrees(east / max(abs(math.cos(math.radians(latitude))), 1e-8))
            # Comparison coordinates are geographic placeholders only; source latitude semantics
            # must be reconciled externally before this diagnostic can be accepted.
            rx, ry = transform_lonlat(lon, lat, ref_ds.GetProjection()) if not _geographic_xy(lon, lat, ref_ds.GetProjection()) else (lon, lat)
            cx, cy, _ = transform.TransformPoint(rx, ry)
            rpx, rpy = _pixel_from_map(rx, ry, list(ref_gt))
            cpx, cpy = _pixel_from_map(cx, cy, list(cand_gt))
            rcol, rrow, ccol, crow = map(lambda v: int(math.floor(v)), (rpx, rpy, cpx, cpy))
            if not (0 <= rcol < ref_ds.RasterXSize and 0 <= rrow < ref_ds.RasterYSize
                    and 0 <= ccol < cand_ds.RasterXSize and 0 <= crow < cand_ds.RasterYSize):
                continue
            rv = float(ref_band.ReadAsArray(rcol, rrow, 1, 1)[0, 0])
            cv = float(cand_band.ReadAsArray(ccol, crow, 1, 1)[0, 0])
            rn, cn = ref_band.GetNoDataValue(), cand_band.GetNoDataValue()
            if not (math.isfinite(rv) and math.isfinite(cv)
                    and (rn is None or rv != rn) and (cn is None or cv != cn)):
                continue
            rv = rv * (ref_band.GetScale() or 1.0) + (ref_band.GetOffset() or 0.0)
            cv = cv * (cand_band.GetScale() or 1.0) + (cand_band.GetOffset() or 0.0)
            ru, cu = ref_band.GetUnitType(), cand_band.GetUnitType()
            if ru and cu and ru != cu:
                raise RuntimeError(f"Band units differ ({ru!r} vs {cu!r}); explicit unit conversion is required")
            values.append(rv - cv)
    if not values:
        raise RuntimeError("No common valid raster samples were found in the requested comparison region")
    arr = np.asarray(values, dtype=float)
    return {
        "schema_version": 1, "reference": str(reference), "candidate": str(candidate),
        "sample_count": int(arr.size), "difference_definition": "reference_elevation_minus_candidate_elevation",
        "units": ref_band.GetUnitType() or "UNSPECIFIED",
        "bias": float(arr.mean()), "mae": float(np.abs(arr).mean()),
        "rmse": float(np.sqrt(np.mean(arr ** 2))),
        "p95_absolute_residual": float(np.percentile(np.abs(arr), 95)),
        "latitude_type": latitude_type,
        "acceptance": "DIAGNOSTIC_ONLY_NOT_ACCEPTED",
        "limitations": [
            "Requires independent confirmation of common vertical datum, frame, latitude semantics and pixel registration.",
            "Nearest pixel sampling is a diagnostic and does not resample or fuse either source.",
            "No source uncertainty/count weighting is applied.",
            "This comparison does not calculate terrain horizon sensitivity.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("inspect", "compare"):
        p = sub.add_parser(name)
        p.add_argument("--latitude", type=float, required=True)
        p.add_argument("--longitude", type=float, required=True)
        p.add_argument("--latitude-type", choices=("planetocentric", "planetographic", "unknown"), required=True)
        p.add_argument("--radius-km", type=float, default=0.0)
        p.add_argument("--output", type=Path, required=True)
        if name == "inspect":
            p.add_argument("--raster", type=Path, required=True)
        else:
            p.add_argument("--reference", type=Path, required=True)
            p.add_argument("--candidate", type=Path, required=True)
            p.add_argument("--grid-size", type=int, default=25)
    args = parser.parse_args()
    try:
        if args.command == "inspect":
            result = inspect_raster(args.raster, args.latitude, args.longitude,
                                    args.latitude_type, args.radius_km)
        else:
            result = compare_rasters(args.reference, args.candidate, args.latitude,
                                     args.longitude, args.latitude_type, args.radius_km, args.grid_size)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps({"status": "REPORT_WRITTEN", "output": str(args.output),
                          "coverage": result.get("coverage"),
                          "sample_count": result.get("sample_count")}, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
