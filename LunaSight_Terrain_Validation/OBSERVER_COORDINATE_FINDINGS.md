# Observer Coordinate Findings for LOLA Acquisition

## Authoritative source read

The preserved Horizons response at:

`LunaSight_SPICE_Validation/LunaSight_Crossing_Comparison_20261021/horizons_results/horizons_result_20261021T185427Z.txt`

contains these header values:

- `Center geodetic: 200.0, -88.45, -3.8598E-13`
- `Center cylindric: 200.0, 46.99546, -1736.764`
- `Center pole/equ: MEAN_ME (high precision)`
- `Center radii: 1737.4, 1737.4, 1737.4 km`
- Source: DE441.

Therefore the site latitude convention is explicitly geodetic/planetodetic, not an unknown value. Since the Horizons lunar reference shape in this header is spherical (a=b=c=1737.4 km), planetodetic and planetocentric latitude coincide for this specific spherical coordinate conversion.

## Important frame distinction

The LOLA product family is documented in the product assessment as MOON_ME / DE421. The repository's NAIF file `moon_de440_220930.tf` describes `MOON_ME_DE440_ME421` as closely aligned with the DE421 ME frame, and quantifies a maximum orientation difference from DE421 of about 1.0 m on the lunar surface over 1900–2051 (about 0.534 m over 2000–2040).

That file does **not** establish the exact transformation from the Horizons DE441 high-precision MEAN_ME realization to the LOLA DE421 map frame. It must not be silently treated as an exact DE441-to-DE421 transformation.

## Projection-coordinate rule

Do not type or hard-code X/Y values into the acquisition workflow. The native projected coordinates must be derived from the actual downloaded LOLA raster's embedded CRS and geotransform using GDAL/OSR, after verifying the geographic ellipsoid and projection metadata. The helper `resolve_observer_projection.py` implements this raster-native CRS operation and writes an explicit `frame_compatibility=NOT_ESTABLISHED` status.

A broad extraction buffer can be used to acquire source data for subsequent analysis, but no final site-to-pixel registration or 5 m local accuracy claim is permitted until the DE441-to-DE421 frame relationship is quantified.

## Acquisition decision

- Latitude convention: **RESOLVED** from original Horizons header.
- Longitude convention: **RESOLVED** as east-positive.
- Observer altitude: **RESOLVED** as 0 km (header residual is numerical roundoff).
- Native LOLA map X/Y: **must be derived from actual raster CRS**, not guessed.
- DE441 Horizons MEAN_ME to LOLA MOON_ME/DE421 transformation: **OPEN**.
- Vertical datum compatibility between Horizons site and LOLA elevations: **OPEN**.
- Terrain data coverage and Nodata: **NOT YET TESTED**.
