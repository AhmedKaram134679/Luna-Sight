# LunaSight — Lunar Terrain DEM Acquisition Manifest

Status: acquisition plan and reproducibility contract. No raster download or scientific coverage result is claimed by this file.

## Target site and unresolved convention

- Nominal observer longitude: 200° east.
- Nominal observer latitude: -88.45°.
- Observer altitude: 0 km in the existing reference setup.
- **Blocking issue:** the scientific reference specification does not unambiguously identify whether -88.45° is planetocentric or planetographic. Do not run a site-coverage acceptance test until this is resolved from the original Horizons/SPICE observer configuration.
- Target lunar frame/datum compatibility with the terrain product must be established independently; a map CRS transformation alone does not do that.

## Acquisition order

### Required regional baseline — LOLA 80°S to 90°S, 20 m/pixel

NASA GSFC Planetary Geodesy and Altimetry Group (PGDA), product page:
https://pgda.gsfc.nasa.gov/products/90

Acquire the official south-polar large-area DEM and the accompanying layers exposed by the product page, prioritizing:
- elevation DEM;
- effective spatial resolution;
- elevation uncertainty/error;
- shot/measurement count or coverage support;
- any product metadata/readme and ancillary files.

The product family is commonly identified by filenames containing `LDEM_80S_20MPP`; filenames alone are not proof of identity. Record the exact product ID and file links from the live product page at download time.

### Required high-resolution supplement — LOLA south-pole 5 m/pixel mosaic

NASA GSFC PGDA product page:
https://pgda.gsfc.nasa.gov/products/81

Acquire:
- elevation mosaic covering 87°S–90°S;
- any published uncertainty, count, source-footprint or support layers;
- the product readme/metadata.

The 5 m/pixel grid spacing is not equivalent to 5 m independent measurement resolution. Product documentation reports interpolation/fill in some cells and typical RMS residuals of 30–55 cm against constituent fields. Keep validity/support layers alongside the elevation mosaic.

### Optional independent local cross-check — LROC NAC 4 m/pixel

USGS Astrogeology product page:
https://astrogeology.usgs.gov/search/map/moon_lro_south_pole_dem

Use the specific `MOON_LRO_NAC_DEM_89S210E_4mp.tif` product only after confirming its metadata and footprint. Its published footprint is limited and must not be treated as a complete regional horizon dataset.

## Download procedure (Windows PowerShell)

1. Open each official product page above.
2. Download the original elevation raster and all relevant support/uncertainty/count layers. Do not use rendered map tiles, screenshots, JPEG previews, or resampled web maps.
3. Preserve the original filenames and directory structure. Do not rename files to imply a product identity.
4. Store data outside the Git repository, for example:

```powershell
New-Item -ItemType Directory -Force D:\LunaSightData\LOLA80S20, D:\LunaSightData\LOLA5M, D:\LunaSightData\LROC_NAC | Out-Null
```

5. For every downloaded file, record:
   - exact official product identifier;
   - direct download URL copied from the official page;
   - retrieval date/time UTC;
   - original filename and byte size;
   - SHA-256 checksum;
   - accompanying readme/metadata filename;
   - license/usage statement if provided.
6. Do not commit large DEM rasters to GitHub. Only small manifests and diagnostic reports belong in the repository.

## Verify files locally

Run `gdalinfo -json -mdd all <file>` on every raster and preserve the complete output. Confirm:
- CRS/projection and all projection parameters;
- dimensions and affine geotransform;
- pixel registration (`AREA_OR_POINT`);
- band type, scale, offset and unit;
- NoData value;
- vertical datum/reference radius;
- frame and longitude/latitude conventions;
- raster footprint and any metadata describing interpolation or fill.

Do not infer missing metadata from the product name.

## Required validation sequence

1. Resolve the observer latitude convention from the original source configuration.
2. Confirm product identity and checksum.
3. Confirm each DEM's footprint covers the observer and declared search radius.
4. Check valid-data support and NoData around the observer; a footprint intersection alone is insufficient.
5. Compare LOLA 20 m and LOLA 5 m only in their common valid region, after confirming compatible vertical datum, frame, registration and units.
6. Compare the LROC NAC patch independently where it overlaps both LOLA products; do not blend it.
7. Report bias, MAE, RMSE, 95th-percentile absolute residual, sample count, and spatial residual maps. Stratify results by source support/uncertainty where available.
8. Keep source layers separate and preserve provenance per sample.
9. Only after all above checks pass, perform horizon sensitivity analysis across DEM resolutions, interpolation methods and uncertainty bounds.

## Important limitation of the current validator

The current `terrain_validate.py` is an initial read-only diagnostic. Its coverage probe and raster comparison are not yet an approved lunar-geodesy pipeline. In particular, the comparison path must not be treated as scientifically accepted until lunar coordinate transformations, latitude semantics, vertical datum, and raster registration are explicitly handled and independently tested. Do not use its output as a terrain-horizon result.

## Acceptance record template

For each file, create a record containing:

```json
{
  "official_product_id": null,
  "official_product_page": null,
  "direct_download_url": null,
  "retrieved_utc": null,
  "original_filename": null,
  "bytes": null,
  "sha256": null,
  "gdalinfo_report": null,
  "crs_and_frame_verified": false,
  "vertical_datum_verified": false,
  "latitude_longitude_convention_verified": false,
  "pixel_registration_verified": false,
  "nodata_and_support_layers_verified": false,
  "observer_coverage_verified": false,
  "review_status": "NOT_REVIEWED"
}
```
