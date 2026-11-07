#!/usr/bin/env python3
"""Safely derive and extract per-raster pixel windows for lunar DEM products.

Each source raster is opened independently. Observer coordinates are transformed
using that raster's embedded geographic CRS; no X/Y values are reused across
products. Source files are read-only and outputs are new temporary GeoTIFFs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys

import requests
from pathlib import Path
from typing import Any

from osgeo import gdal, osr


def inverse_affine(gt: tuple[float, ...] | list[float], x: float, y: float) -> tuple[float, float]:
    a, b, c, d = gt[1], gt[2], gt[4], gt[5]
    dx, dy = x - gt[0], y - gt[3]
    det = a * d - b * c
    if not math.isfinite(det) or abs(det) < 1e-30:
        raise ValueError("Raster affine geotransform is singular")
    return ((dx * d - b * dy) / det, (a * dy - dx * c) / det)


def pixel_window_from_map_bounds(
    gt: tuple[float, ...] | list[float],
    width: int,
    height: int,
    bounds: tuple[float, float, float, float],
) -> tuple[int, int, int, int]:
    """Return (xoff,yoff,xsize,ysize) covering map bounds (xmin,ymin,xmax,ymax).

    All four map-space corners are transformed, so rotated affine rasters are
    handled. A window that extends beyond the raster is rejected, not clipped.
    """
    xmin, ymin, xmax, ymax = bounds
    if not all(math.isfinite(v) for v in bounds) or not (xmin < xmax and ymin < ymax):
        raise ValueError(f"Invalid map bounds: {bounds!r}")
    corners = [(xmin, ymin), (xmin, ymax), (xmax, ymin), (xmax, ymax)]
    pixels = [inverse_affine(gt, x, y) for x, y in corners]
    min_col = math.floor(min(p[0] for p in pixels))
    max_col = math.ceil(max(p[0] for p in pixels))
    min_row = math.floor(min(p[1] for p in pixels))
    max_row = math.ceil(max(p[1] for p in pixels))
    xsize, ysize = max_col - min_col, max_row - min_row
    if xsize <= 0 or ysize <= 0:
        raise ValueError(f"Computed non-positive pixel window: {(min_col, min_row, xsize, ysize)}")
    if min_col < 0 or min_row < 0 or max_col > width or max_row > height:
        raise ValueError(
            "Requested extraction lies outside raster: "
            f"window={(min_col, min_row, xsize, ysize)}, raster={(width, height)}"
        )
    return min_col, min_row, xsize, ysize


def observer_map_xy(ds: gdal.Dataset, longitude: float, latitude: float, altitude_m: float = 0.0):
    projection = ds.GetProjection()
    if not projection:
        raise RuntimeError("Source raster has no embedded CRS")
    target = osr.SpatialReference()
    if target.ImportFromWkt(projection) != 0:
        raise RuntimeError("Cannot parse source raster CRS")
    source = target.CloneGeogCS()
    if source is None:
        raise RuntimeError("Cannot derive geographic CRS/ellipsoid from source raster CRS")
    source.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    target.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    transform = osr.CoordinateTransformation(source, target)
    x, y, z = transform.TransformPoint(longitude, latitude, altitude_m)
    if not all(math.isfinite(v) for v in (x, y, z)):
        raise RuntimeError("Observer CRS transformation returned non-finite coordinates")
    linear_units_to_m = target.GetLinearUnits()
    if not math.isfinite(linear_units_to_m) or linear_units_to_m <= 0:
        raise RuntimeError("Raster native CRS has no valid linear-unit conversion to metres")
    return (x, y, z), source.ExportToWkt(), target.ExportToWkt(), linear_units_to_m


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_http_response(url: str, sample_bytes: int = 65536) -> dict[str, Any]:
    """Capture a bounded HTTP Range response without downloading a full DEM."""
    response = requests.get(url, headers={"Range": f"bytes=0-{sample_bytes - 1}", "Accept-Encoding": "identity"},
                            stream=True, timeout=(30, 120), allow_redirects=True)
    digest = hashlib.sha256()
    body = bytearray()
    try:
        for chunk in response.iter_content(chunk_size=8192):
            if not chunk: continue
            piece = chunk[:sample_bytes - len(body)]
            body.extend(piece); digest.update(piece)
            if len(body) >= sample_bytes: break
        content_type = response.headers.get("Content-Type", "")
        prefix = bytes(body[:512]).lstrip().lower()
        looks_html = "html" in content_type.lower() or prefix.startswith((b"<!doctype html", b"<html", b"<head"))
        return {"requested_range": f"bytes=0-{sample_bytes - 1}", "final_url": response.url,
                "redirect_count": len(response.history), "status_code": response.status_code,
                "headers": dict(response.headers), "content_type": content_type,
                "content_range": response.headers.get("Content-Range"),
                "content_length_header": response.headers.get("Content-Length"),
                "sampled_body_bytes": len(body), "sampled_body_sha256": digest.hexdigest(),
                "body_looks_like_html": looks_html,
                "html_preview": bytes(body[:2048]).decode("utf-8", errors="replace") if looks_html else None,
                "range_contract_pass": response.status_code == 206 and response.headers.get("Content-Range", "").startswith(f"bytes 0-{len(body)-1}/")}
    finally:
        response.close()

def extract_one(name: str, url: str, output_dir: Path, longitude: float,
                latitude: float, half_width_m: float) -> dict[str, Any]:
    http_diagnostic = inspect_http_response(url)
    if http_diagnostic["status_code"] not in (200, 206) or http_diagnostic["body_looks_like_html"]:
        raise RuntimeError(f"HTTP preflight rejected raster response: status={http_diagnostic['status_code']} content_type={http_diagnostic['content_type']!r} preview={http_diagnostic['html_preview']!r}")
    source = "/vsicurl/" + url
    gdal.UseExceptions()
    gdal_errors = []
    def capture_gdal_error(error_class, error_number, message):
        gdal_errors.append({"class": int(error_class), "number": int(error_number), "message": str(message)})
    gdal.PushErrorHandler(capture_gdal_error)
    try:
        ds = gdal.Open(source, gdal.GA_ReadOnly)
    finally:
        gdal.PopErrorHandler()
    if ds is None:
        raise RuntimeError(f"GDAL could not open remote source {url}")
    gt = ds.GetGeoTransform(can_return_null=True)
    if gt is None:
        raise RuntimeError("Source raster has no affine geotransform")
    (x, y, z), geographic_wkt, native_wkt, linear_units_to_m = observer_map_xy(ds, longitude, latitude)
    half_width_native = half_width_m / linear_units_to_m
    bounds = (x - half_width_native, y - half_width_native,
              x + half_width_native, y + half_width_native)
    window = pixel_window_from_map_bounds(gt, ds.RasterXSize, ds.RasterYSize, bounds)
    source_width, source_height = ds.RasterXSize, ds.RasterYSize

    output_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(name).name
    output = output_dir / (safe_name.rsplit(".", 1)[0] + "_subset.tif")
    # Use the explicit validated pixel window, not -projwin. This avoids
    # GDAL's ambiguous corner ordering and guarantees positive integer sizes.
    translate_errors = []
    def capture_translate_error(error_class, error_number, message):
        translate_errors.append({"class": int(error_class), "number": int(error_number), "message": str(message)})
    gdal.PushErrorHandler(capture_translate_error)
    try:
        result = gdal.Translate(str(output), ds, srcWin=window,
                                format="GTiff",
                                creationOptions=["TILED=YES", "COMPRESS=DEFLATE"])
    finally:
        gdal.PopErrorHandler()
    if result is None:
        raise RuntimeError("gdal.Translate returned no output dataset")
    result.FlushCache()
    result = None
    ds = None
    out_ds = gdal.Open(str(output), gdal.GA_ReadOnly)
    if out_ds is None:
        raise RuntimeError("Cannot reopen extracted subset")
    output_gt = out_ds.GetGeoTransform()
    output_size = [out_ds.RasterXSize, out_ds.RasterYSize]
    output_ds_wkt = out_ds.GetProjection()
    out_ds = None
    return {
        "product_filename": name, "source_url": url, "http_response_diagnostic": http_diagnostic, "subset_file": str(output),
        "gdal_open_messages": gdal_errors, "gdal_translate_messages": translate_errors,
        "subset_bytes": output.stat().st_size, "subset_sha256": sha256(output),
        "source_dimensions": [int(source_width), int(source_height)],
        "source_geotransform": list(gt), "source_crs_wkt": native_wkt,
        "geographic_crs_wkt": geographic_wkt,
        "observer_map_coordinates": {"x": x, "y": y, "z": z},
        "requested_map_bounds_xmin_ymin_xmax_ymax": list(bounds),
        "native_crs_linear_unit_to_metre": linear_units_to_m,
        "requested_half_width_m": half_width_m,
        "requested_half_width_native_units": half_width_native,
        "pixel_window_xoff_yoff_xsize_ysize": list(window),
        "pixel_window_validation": "PASS_POSITIVE_AND_IN_BOUNDS",
        "pixel_axis_direction": {
            "column_step_x": gt[1], "column_step_y": gt[4],
            "row_step_x": gt[2], "row_step_y": gt[5],
            "row_axis_northing_direction": "decreasing" if gt[5] < 0 else "increasing" if gt[5] > 0 else "rotated_or_degenerate",
        },
        "pixel_spacing_affine_magnitude": {
            "column": math.hypot(gt[1], gt[4]), "row": math.hypot(gt[2], gt[5])
        },
        "subset_dimensions": output_size, "subset_geotransform": list(output_gt),
        "subset_crs_matches_source": output_ds_wkt == native_wkt,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--longitude-east", type=float, required=True)
    parser.add_argument("--latitude", type=float, required=True)
    parser.add_argument("--half-width-m", type=float, required=True)
    parser.add_argument("--include-5m", action="store_true")
    parser.add_argument("--include-20m", action="store_true")
    args = parser.parse_args()
    report: dict[str, Any] = {"schema_version": 2, "status": "RUNNING", "products": [], "errors": [], "selected_products": [],
                              "http_access_context": "Bounded per-product HTTP Range responses are captured separately; GDAL /vsicurl/ does not expose raw response headers."}
    try:
        if not (-360 <= args.longitude_east <= 360 and -90 <= args.latitude <= 90):
            raise ValueError("Observer coordinates outside accepted range")
        if not (math.isfinite(args.half_width_m) and args.half_width_m > 0):
            raise ValueError("half-width-m must be finite and positive")
        sources = json.loads(args.sources.read_text(encoding="utf-8"))
        selected = [(name, entry) for name, entry in sources.items()
                    if ((args.include_20m and name.startswith("LDEM_80S"))
                        or (args.include_5m and name.startswith("ldem_87s")))]
        report["selected_products"] = [name for name, _ in selected]
        for name, entry in selected:
            try:
                report["products"].append(extract_one(name, entry["download_url"], args.output_dir,
                    args.longitude_east, args.latitude, args.half_width_m))
            except Exception as exc:
                report["errors"].append({"product": name, "error": str(exc)})
        if not selected:
            report["status"] = "FAIL_NO_PRODUCTS"
            report["fatal_error"] = "No matching 5m/20m elevation products were found in source manifest"
        elif report["errors"]:
            report["status"] = "FAIL_PARTIAL" if report["products"] else "FAIL"
        else:
            report["status"] = "PASS"
    except Exception as exc:
        report["status"] = "FAIL"
        report["fatal_error"] = str(exc)
    finally:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "selected_products": report["selected_products"],
                      "products": len(report["products"]), "errors": report["errors"],
                      "report": str(args.report)}, indent=2))
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
