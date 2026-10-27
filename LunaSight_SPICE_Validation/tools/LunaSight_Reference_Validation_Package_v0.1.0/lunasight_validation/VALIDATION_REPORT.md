# LunaSight — Reference-Site Scientific Validation Package

**Package status:** Initial diagnostic package; NOT a completed independent validation.
**Test epoch:** 2026-11-01 UTC
**Observer:** Lunar fixed point, Moon-centered body-fixed frame `MOON_ME`
**Observer coordinates:** planetodetic longitude 200° (equivalent to -160°), latitude -88.45°, altitude 0 km
**Target:** EARTH

## Executive result

The supplied exports are sufficient to identify a key model/definition issue and prepare the repeatable validation workflow. They are **not yet sufficient to declare the Earth-limb event time validated**.

- The Angular Size export reports `Computation method = Maximum radius`, `Target = EARTH`, `Observer = MOON`, converged Newtonian light time, stellar aberration correction, UTC output, and kernel `solar_system_v0070.tm`.
- The fixed-point State Vector export reports a topocentric observer at `(200°, -88.45°, 0 km)`, `MOON_ME`, converged Newtonian light time, stellar aberration correction, and kernel `solar_system_v0071.tm`.
- These exports use **different kernel meta-kernel versions** and different observer definitions (`MOON` center for Angular Size versus a fixed surface point for State Vector). The Angular Size value must not be combined with the fixed-point elevation as though they were a single internally consistent run without explicitly documenting the approximation.
- The Angular Size values near 07:40 UTC are about 1.9704°. A spherical sanity check using an Earth equatorial radius near 6378 km and a geocentric range near 371,000 km predicts a **full angular diameter** near 1.97°, not a radius near 1.97°. This is strong numerical evidence that the displayed value behaves like a diameter, but it does **not** replace authoritative confirmation of the UI's `Maximum radius` semantics.
- The previous candidate event near `2026-11-01 07:40:30 UTC` remains **UNVERIFIED**. Do not publish it as an accepted result.

## Source files included

1. `raw_sources/New Text Document(1).txt` — Angular Size time series, including 2026-11-01 06:00 through 2026-11-02 16:00 UTC at 10-minute sampling; kernel `solar_system_v0070.tm`.
2. `raw_sources/نص ملصق (3).txt` — fixed-point State Vector at 2026-11-01 08:30–09:30 UTC at 1-minute sampling; kernel metadata as exported in the source.
3. `raw_sources/نص ملصق(6).txt` — fixed-point State Vector range/rectangular data from 2026-11-01 to 2026-11-20 at hourly sampling; kernel `solar_system_v0071.tm`.

The source files are preserved as supplied. Their metadata and values are not silently normalized or edited.

## Current checks

### Check A — Angular-size magnitude

At 2026-11-01 07:40 UTC, the Angular Size export reports `1.97041376°`. A simple spherical comparison at a representative Earth range around 370,912 km gives:

`2 × asin(6378.137 / 370912) ≈ 1.9706°`.

That is close to the reported value and consistent with a full angular diameter. The calculation is a **sanity check only**: it uses an approximate spherical Earth radius, a representative range from a separate export, and mismatched kernel versions. It is not a high-precision reference result.

### Check B — Event definitions

For a simple circular-disk model with center elevation `h` and angular radius `r`:

- upper limb crosses horizon when `h + r = 0`;
- lower limb crosses horizon when `h - r = 0`.

The rising/setting direction must be checked separately. The event intended by the product must be named (first appearance, full appearance, start of disappearance, or fully disappeared).

### Check C — Event-finding method

Do not use the closest one-minute row as the event time. First bracket the root, then refine it numerically, and test that the event direction and neighboring states agree with the definition. NAIF SPICE Geometry Finder documentation explains that search step size affects event-detection completeness, while convergence tolerance controls root refinement. See the links below.

## Required next data capture

Repeat both calculations with a matched configuration and export sufficient samples around the event window:

1. Use the same kernel meta-kernel version for all outputs where possible; record exact kernel names.
2. Use the same observer location and reference frame for the Earth center/elevation and Earth limb/shape calculation.
3. Export fixed-point topocentric Earth elevation at **one-second or finer sampling** over a bracket around the candidate, or export values at two or more well-defined bracket endpoints and evaluate with a supported event-finding method.
4. Capture the precise Angular Size/target-shape definition from the interface documentation or a configuration detail that states whether the reported angle is full diameter or angular radius.
5. If using SPICE GF occultation tools, confirm the model is actually equivalent to the surface-point Earth-limb event being sought; a body-center observer or an occultation between whole bodies is not automatically the same calculation as a surface observer's horizon crossing.
6. Save original input settings, full table, kernel list, and checksum for every reference run.

## Independent validation plan

JPL Horizons is the reference source for observer tables and angular-diameter context. For a truly independent event-time check, compare a separately configured calculation or independently implemented root solve against the same explicitly defined geometric event. A second export from the same setup is a reproducibility check, not an independent validation.

Reference documentation:

- JPL Horizons manual: https://ssd.jpl.nasa.gov/horizons/manual.html
- NAIF Geometry Finder required reading: https://naif.jpl.nasa.gov/pub/naif/toolkit_docs/C/req/gf.html
- NAIF `gfoclt_c` reference: https://naif.jpl.nasa.gov/pub/naif/toolkit_docs/C/cspice/gfoclt_c.html

## Acceptance gates

The candidate event may be marked **VALIDATED** only after all gates pass:

- [ ] Same site and coordinate interpretation in both calculations.
- [ ] Same kernel/model set, or a quantified and justified model difference.
- [ ] Angular radius versus full diameter semantics confirmed.
- [ ] Event type and direction explicitly named.
- [ ] A bracketed root is refined using a documented numerical method.
- [ ] A separate reference result agrees within the project-approved tolerance.
- [ ] Raw inputs, output tables, source URLs, kernel versions, and checksums are archived.

Until then the event status is **UNVERIFIED**.
