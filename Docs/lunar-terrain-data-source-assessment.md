# LunaSight — Lunar Terrain Data Source Assessment

Status: source assessment; no terrain engine implementation or scientific result is claimed.
Target observer: 200°E, 88.45°S (planetocentric/geodetic convention must be confirmed against the existing site definition before sampling).

## Decision summary

Use a layered terrain-data strategy for the south-polar site:

1. **Regional baseline:** NASA/GSFC LOLA south-polar LDEM, specifically the 80°S–90°S 20 m/pixel product (current product naming includes `LDEM_80S_20MPP_ADJ`). It covers the target latitude and provides a broad polar context suitable for initial horizon-profile work.
2. **High-resolution local supplement:** the LOLA 87°S–90°S 5 m/pixel south-pole DEM mosaic. It provides finer gridding around the target and reports typical RMS residuals of 30–55 cm against its constituent fields. Its values are interpolated surface elevations; 5 m pixel spacing must not be described as 5 m independent measurement accuracy.
3. **Independent local cross-check:** USGS LROC NAC DEM `MOON_LRO_NAC_DEM_89S210E_4mp.tif`. Its published footprint is 88.56358884°S–88.33003614°S and 141.2910715°E–309.96354392°E, so the nominal target (200°E, 88.45°S) lies inside the footprint. This is a regional patch, not a substitute for the broad-area DEM.

SLDEM2015 is not suitable as the primary dataset at this site: its coverage is limited to ±60° latitude.

## Published product facts

### A. LOLA 80S 20MPP polar DEM
- Product family: LRO LOLA polar gridded elevation products.
- Coverage: 80°S to the south pole.
- Nominal pixel scale: 20 m/pixel.
- Projection: south-polar stereographic.
- Reference frame/datum: MOON_ME, JPL DE421 convention; heights are relative to the lunar reference sphere as specified by the product.
- Use: broad-area regional terrain baseline.
- Caveat: gridded/interpolated altimetry; inspect LOLA count/effective-resolution and uncertainty layers before interpreting local slopes or narrow ridges.

### B. LOLA 87S 5MPP south-pole mosaic
- Coverage: 87°S to 90°S.
- Nominal pixel scale: 5 m/pixel.
- Projection: south-polar stereographic; MOON_ME / DE421.
- Construction: 97 individual 20 km × 20 km fields with 2 km overlaps; aligned and blended.
- Published typical RMS residual against constituent fields: 30–55 cm.
- Caveats: interpolated empty pixels exist; pixel spacing is not equivalent to effective independent spatial resolution. Use count and uncertainty products where available.

### C. USGS LROC NAC 4 m/pixel patch
- Product: `MOON_LRO_NAC_DEM_89S210E_4mp.tif`.
- Published footprint: 88.56358884°S to 88.33003614°S; 141.2910715°E to 309.96354392°E.
- Nominal target (200°E, 88.45°S) falls inside this footprint.
- Projection: polar stereographic; planetocentric latitude; positive-east longitude, 0–360°.
- Use: independent high-resolution local terrain cross-check and local refinement only within its actual footprint.
- Caveat: verify raster nodata, source image geometry, vertical datum, and registration against LOLA before blending or using it as a continuous horizon surface.

## Mandatory compatibility checks before engine use

1. Confirm the existing observer latitude type (planetocentric vs planetographic), longitude convention, lunar body-fixed frame, reference radius, and height datum from the original observer definition.
2. Establish a documented transformation from each product's MOON_ME / DE421 frame and map projection into the engine's chosen lunar body-fixed frame. Do not assume DE421 and DE441 frame conventions are interchangeable without a quantified transformation.
3. Read and honor the source labels/metadata, scale factors, offsets, units, pixel registration convention, nodata values, and longitude wrap.
4. Verify that all three products cover the intended observer and required horizon-search radius. The 4 m NAC patch is not complete coverage for a long-range horizon profile.
5. Compare elevations and slopes in overlapping regions using explicit tolerances derived from source uncertainty; report bias, RMS, robust percentiles, and spatially coherent residuals. Do not silently average disagreements.
6. Preserve source provenance per sampled cell and distinguish measured/track-supported terrain from interpolated or filled cells.
7. Perform sensitivity analysis of the computed horizon angle and Earth-visibility result against DEM resolution, interpolation method, and uncertainty. A terrain pixel size alone is not an uncertainty estimate.

## Initial implementation recommendation

- Start with the 20 m LOLA 80S product as the broad-area input.
- Add the 5 m LOLA south-pole mosaic as a higher-resolution layer in its 87°S–90°S coverage.
- Load the 4 m NAC patch as an independent validation/refinement layer only where its footprint and metadata are valid.
- Keep the layers separate in the data model. Do not fuse them until co-registration and overlap residual tests pass.
- For each azimuth, compute terrain horizon elevation from the observer's actual surface location using the DEM and a declared lunar shape/datum. Keep geometric terrain obstruction separate from Earth ephemeris/apparent-direction calculations.

## Explicit non-goals in this source-assessment change

- No changes to DE441 solar-bent-limb equations, crossing-time extraction, or historical roots.
- No edits to Horizons outputs or previous validation artifacts.
- No changes to Flutter UI or `main`.
- No claim that terrain coverage or Earth visibility has been computed.
- No download of multi-gigabyte DEM rasters into Git.

## Primary references

- NASA GSFC PGDA, A New View of the Lunar South Pole from LOLA: https://pgda.gsfc.nasa.gov/products/90
- NASA GSFC PGDA, South Pole LOLA DEM Mosaic: https://pgda.gsfc.nasa.gov/products/81
- NASA GSFC PGDA, High-Resolution LOLA Topography for Lunar South Pole Sites: https://pgda.gsfc.nasa.gov/products/78
- USGS Astrogeology, LROC South Pole DEM metadata: https://astrogeology.usgs.gov/search/map/moon_lro_south_pole_dem
- NASA GSFC PGDA, SLDEM2015: https://pgda.gsfc.nasa.gov/products/54
- Barker et al. (2023), A New View of the Lunar South Pole from LOLA, Planetary Science Journal, DOI: 10.3847/PSJ/acf3e1
- Barker et al. (2021), Improved LOLA Elevation Maps for South Pole Landing Sites, DOI: 10.1016/j.pss.2020.105119
