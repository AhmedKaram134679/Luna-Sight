#!/usr/bin/env python3
"""Resolve a lunar observer into the native map CRS of a supplied LOLA raster.

This tool uses the raster's own embedded CRS and ellipsoid. It does not assume
that a generic terrestrial EPSG code applies to the Moon. It also does not
perform a DE441-to-DE421 body-fixed frame transformation; that must be
established separately before interpreting sub-pixel site registration.
"""
from __future__ import annotations
import argparse, json, math
from osgeo import gdal, osr


def resolve(raster: str, longitude_east: float, latitude_deg: float,
            altitude_km: float = 0.0) -> dict:
    ds = gdal.Open(raster, gdal.GA_ReadOnly)
    if ds is None:
        raise RuntimeError(f"Cannot open raster: {raster}")
    target = osr.SpatialReference()
    if target.ImportFromWkt(ds.GetProjection()) != 0:
        raise RuntimeError("Raster has no parseable embedded CRS")
    source = target.CloneGeogCS()
    if source is None:
        raise RuntimeError("Could not extract geographic CRS/ellipsoid from raster CRS")
    source.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    target.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    transform = osr.CoordinateTransformation(source, target)
    x, y, z = transform.TransformPoint(longitude_east, latitude_deg, altitude_km * 1000.0)
    if not all(math.isfinite(v) for v in (x, y, z)):
        raise RuntimeError("CRS transformation returned non-finite coordinates")
    gt = ds.GetGeoTransform(can_return_null=True)
    if gt is None:
        raise RuntimeError("Raster has no affine geotransform")
    inv = gdal.InvGeoTransform(gt)
    if not inv:
        raise RuntimeError("Raster geotransform is not invertible")
    pixel, line = gdal.ApplyGeoTransform(inv, x, y)
    corners = [
        gdal.ApplyGeoTransform(gt, 0, 0),
        gdal.ApplyGeoTransform(gt, ds.RasterXSize, 0),
        gdal.ApplyGeoTransform(gt, ds.RasterXSize, ds.RasterYSize),
        gdal.ApplyGeoTransform(gt, 0, ds.RasterYSize),
    ]
    inside = 0 <= pixel < ds.RasterXSize and 0 <= line < ds.RasterYSize
    return {
        "raster": raster,
        "observer_input": {
            "longitude_positive_east_deg": longitude_east,
            "latitude_deg": latitude_deg,
            "latitude_type": "planetodetic/geodetic (confirmed by preserved Horizons response header)",
            "altitude_km": altitude_km,
        },
        "raster_geographic_crs_wkt": source.ExportToWkt(),
        "raster_native_crs_wkt": target.ExportToWkt(),
        "native_map_coordinates_m": {"x": x, "y": y, "z": z},
        "pixel_coordinates": {"column": pixel, "row": line},
        "raster_dimensions": {"width": ds.RasterXSize, "height": ds.RasterYSize},
        "footprint_corners_native_crs": corners,
        "observer_inside_raster_rectangle": inside,
        "frame_compatibility": {
            "status": "NOT_ESTABLISHED",
            "reason": "This CRS operation uses the raster's embedded geographic CRS and ellipsoid. It does not rotate/translate coordinates between the Horizons DE441 MEAN_ME realization and the LOLA product MOON_ME/DE421 realization.",
        },
        "vertical_datum_compatibility": "NOT_ESTABLISHED",
        "acceptance": "COORDINATE_CANDIDATE_ONLY",
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--raster",required=True)
    p.add_argument("--longitude-east",type=float,default=200.0)
    p.add_argument("--latitude",type=float,default=-88.45)
    p.add_argument("--altitude-km",type=float,default=0.0)
    p.add_argument("--output",required=True)
    a=p.parse_args()
    result=resolve(a.raster,a.longitude_east,a.latitude,a.altitude_km)
    with open(a.output,"w",encoding="utf-8") as f:
        json.dump(result,f,indent=2)
        f.write("\\n")
    print(json.dumps({"map_coordinates_m":result["native_map_coordinates_m"],
                      "pixel_coordinates":result["pixel_coordinates"],
                      "inside":result["observer_inside_raster_rectangle"],
                      "acceptance":result["acceptance"]},indent=2))

if __name__=="__main__":
    main()
