# Lunar Terrain Validation Toolkit

This toolkit validates downloaded lunar DEM rasters without downloading or committing the large source products.

## Safety and scientific status

- It does not compute a terrain horizon or Earth visibility.
- It does not reproject, resample, blend, or modify source rasters.
- It never assumes that a nominal pixel spacing equals effective spatial accuracy.
- It requires the observer latitude type explicitly; the existing LunaSight reference specification records -88.45° but does not settle planetocentric versus planetographic latitude.
- A metadata/coverage PASS means only that the raster metadata and requested geometric coverage passed these checks. It is not scientific approval of the DEM.

## Requirements

- Python 3.10+
- GDAL command-line utility `gdalinfo` on PATH
- Optional: `pyproj` for CRS transformation when raster CRS differs from the supplied geographic CRS.

No paid API is required.

## Inspect one raster

```powershell
python terrain_validate.py inspect --raster "D:\data\dem.tif" --latitude -88.45 --longitude 200 --latitude-type planetocentric --radius-km 5 --output report.json
```

The radius check is a conservative geographic sampling of the requested circle around the observer. It tests the raster footprint; it does not establish that every azimuth ray is supported by valid elevation pixels. Nodata coverage is reported separately.

## Compare overlapping rasters

```powershell
python terrain_validate.py compare --reference "D:\data\lola20.tif" --candidate "D:\data\lola5.tif" --latitude -88.45 --longitude 200 --latitude-type planetocentric --radius-km 2 --output overlap.json
```

The comparison samples common valid pixel-center locations on a bounded deterministic grid, transforms coordinates through the raster CRS, and reports bias, MAE, RMSE, p95 absolute residual, and sample count. This is a diagnostic, not a fusion operation or a formal uncertainty estimate. For a rigorous comparison, align source registration and vertical datums first and use source uncertainty/count layers.

## Output interpretation

Each raster report records:
- dimensions, bands, data types, CRS, geotransform, bounds;
- pixel registration metadata when available;
- nodata, scale, offset, unit and relevant dataset/band metadata;
- observer projected coordinates and geometric coverage checks;
- a sampled valid/nodata status around the observer.

Missing or ambiguous vertical datum, pixel registration, or frame metadata is reported as unresolved; it is never silently inferred.

## Product-specific notes

Supply the actual official downloaded files and their accompanying metadata/uncertainty/count layers. Do not identify a file as a particular LOLA/NAC product from its filename alone. Record the source URL, product identifier, retrieval date, checksum, and metadata sidecars in a provenance manifest before accepting it.
