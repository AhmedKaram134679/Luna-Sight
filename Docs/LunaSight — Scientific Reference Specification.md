# LunaSight — Scientific Reference Specification

**Document ID:** LUNASIGHT-SCI-001  
**Version:** 0.1 — Foundational Draft  
**Project:** LunaSight — NASA Space Apps Challenge 2026  
**Application target:** Android  
**Implementation language:** Dart  
**UI framework:** Flutter  
**Document status:** Initial scientific specification; independent validation pending

---

## 1. Purpose

This document defines the initial scientific and computational requirements for LunaSight. It establishes the equations, input conventions, event-detection rules, validation requirements, and known limitations for analyzing the apparent positions of the Sun and Earth from candidate lunar landing sites.

The objective is to create a reproducible scientific calculation layer that can be tested independently of the Flutter user interface.

## 2. Project objectives

The initial scientific scope includes:

1. Calculating the apparent elevation and azimuth of the Sun at a specified lunar location and time.
2. Estimating periods of sunlight and identifying illumination transitions.
3. Calculating the apparent elevation and angular diameter of Earth.
4. Detecting Earth appearance and disappearance events relative to the local horizon.
5. Estimating preliminary direct-to-Earth line-of-sight windows.
6. Comparing candidate locations and mission dates using clearly defined metrics.
7. Recording data provenance, calculation assumptions, and uncertainty.

These calculations alone do not establish landing safety, actual solar-array power output, radio-link quality, or mission feasibility.

## 3. Coordinate and observation conventions

### 3.1 Existing Earth-observation configuration

The following configuration was used for the preliminary Earth-event calculations:

| Parameter | Value |
|---|---|
| Target | Earth |
| Observer | Moon |
| Observer longitude | 200° E |
| Observer latitude | −88.45° |
| Observer altitude | 0 km |
| Reference frame | `MOON_ME` |
| Light propagation | To observer |
| Light-time algorithm | Converged Newtonian |
| Stellar aberration | Corrected |
| Time system | UTC |
| State representation | Azimuth/Elevation |
| Azimuth convention | Increases clockwise |
| Elevation convention | Measured from the XY plane toward +Z |
| State Vector kernel set | `solar_system_v0071.tm` |
| Angular Size kernel set | `solar_system_v0070.tm` |

The State Vector and Angular Size calculations used different versions of the solar-system kernel set. Their results must therefore be treated as preliminary until the difference is assessed or the calculations are repeated using a consistent configuration.

The altitude and longitude/latitude convention must also be preserved when reproducing these calculations.

### 3.2 Generalized calculation configuration

The production calculation engine must not hard-code the preliminary observer location.

Each calculation must explicitly identify:

- Target body.
- Observer body or site.
- Lunar longitude, latitude, and altitude.
- Coordinate frame and longitude convention.
- Observation time and time system.
- Light-time and aberration corrections.
- Data source, kernel versions, and retrieval timestamp.
- Whether the horizon is an ideal geometric horizon or a terrain-derived horizon.

### 3.3 Coordinate conventions

All internal angular calculations must use one consistent convention. Conversion to radians should occur at clearly defined calculation boundaries where required.

The application must not silently mix:

- East-positive and west-positive longitudes.
- Geocentric and topocentric positions.
- Geometric and apparent elevations.
- Different reference frames.
- UTC and local display time.

## 4. Earth angular geometry

Let:

- \(h_E(t)\) be the apparent elevation of Earth's center relative to the selected local horizon.
- \(D_E(t)\) be Earth's apparent angular diameter.
- \(\alpha_E(t)=D_E(t)/2\) be Earth's apparent angular radius.

The angular elevations of the upper and lower limbs, under the spherical angular-disk approximation, are:

\[
h_{\mathrm{upper}}(t)=h_E(t)+\alpha_E(t)
\]

\[
h_{\mathrm{lower}}(t)=h_E(t)-\alpha_E(t)
\]

The disk is partially visible when its upper limb is above the horizon while its lower limb is below it. The disk is fully above the ideal horizon when its lower limb is above it.

These equations describe an angular-disk approximation. They do not account for terrain obstruction, local horizon irregularities, or detailed limb shape.

## 5. Earth-event definitions

### Event E1 — First appearance of Earth's upper limb

Root equation:

\[
f_1(t)=h_E(t)+\alpha_E(t)=0
\]

Required direction: \(f_1\) crosses from negative to positive.

Interpretation: the upper limb begins to rise above the selected horizon.

### Event E2 — Entire Earth disk becomes visible

Root equation:

\[
f_2(t)=h_E(t)-\alpha_E(t)=0
\]

Required direction: \(f_2\) crosses from negative to positive.

Interpretation: the lower limb rises above the horizon.

### Event E3 — Earth's lower limb begins to disappear

Root equation:

\[
f_3(t)=h_E(t)-\alpha_E(t)=0
\]

Required direction: \(f_3\) crosses from positive to negative.

Interpretation: the lower limb begins to pass below the horizon.

### Event E4 — Earth's upper limb disappears

Root equation:

\[
f_4(t)=h_E(t)+\alpha_E(t)=0
\]

Required direction: \(f_4\) crosses from positive to negative.

Interpretation: the last visible part of Earth disappears below the horizon.

The event detector must verify both the root condition and the direction of crossing. A root without a verified direction is not sufficient to classify an event.

## 6. Preliminary Earth-event results

The following results were derived from the previously supplied WGC2 tables for the observer location in Section 3.1.

| Event | Preliminary UTC estimate | Status |
|---|---|---|
| E1 — First upper-limb appearance | 2026-11-02 11:24:46.5 | Calculated; validation pending |
| E2 — Entire disk visible | 2026-11-03 17:09:58.3 | Calculated; validation pending |
| E3 — Lower-limb disappearance begins | 2026-11-16 20:35:03.1 | Calculated; validation pending |
| E4 — Entire disk disappears | 2026-11-18 04:05:32.7 | Calculated; validation pending |

The values were estimated by interpolation between one-minute samples. State Vector data used kernel set v0071, whereas Angular Size data used v0070.

These timestamps are not independently validated event times and must not be presented as guaranteed sub-second-accurate results.

## 7. Event detection and numerical method

### 7.1 Initial detection

For each event function \(f(t)\):

1. Obtain time-ordered samples of the required elevation and angular diameter.
2. Calculate the event function at each sample.
3. Identify intervals containing a sign change.
4. Verify the expected direction of crossing.
5. Refine the root inside the interval.
6. Re-evaluate the function at the estimated event time.
7. Store the root estimate, residual, method, and validation status.

### 7.2 Linear interpolation

For a sign-changing interval \([t_0,t_1]\), with \(f_0=f(t_0)\) and \(f_1=f(t_1)\), the initial estimate is:

\[
t_* = t_0 - f_0
\frac{t_1-t_0}{f_1-f_0}
\]

This is a numerical estimate, not a guarantee of the true root. The error depends on the curvature of the event function, sampling interval, input precision, and consistency of the source data.

### 7.3 Production refinement

The production implementation should use a bracketed root-finding method, such as bisection or Brent's method, when the underlying position and angular-size calculations can be evaluated at arbitrary times.

If only precomputed samples are available, the application must report that the event time is sample-interpolated and must not imply precision unsupported by the data.

### 7.4 Direction verification

A root is classified by evaluating the event function on both sides of the root:

- Negative to positive: rising through the horizon boundary.
- Positive to negative: setting through the horizon boundary.

Near tangencies or local maxima/minima, sign-change detection alone may miss a contact without crossing. Such cases require additional sampling or extremum analysis.

## 8. Solar position and illumination requirements

Let \(h_S(t)\) be the apparent elevation of the Sun's center relative to the selected horizon.

The initial geometric conditions are:

- Sun center above the ideal horizon: \(h_S(t)>0\).
- Sun center below the ideal horizon: \(h_S(t)<0\).

These conditions are suitable for an initial solar-center analysis but do not fully describe the visibility of the solar disk or terrain obstruction.

The engine must distinguish:

1. Sun-center elevation.
2. First appearance of the solar disk.
3. Entire solar disk above the horizon.
4. First disappearance of the solar disk.
5. Complete disappearance of the solar disk.

Solar-disk event calculations must use an appropriate apparent solar angular radius and verified sign conventions.

### Preliminary relative illumination indicator

For an unobstructed horizontal surface and a point-source approximation, a preliminary geometric indicator is:

\[
I_{\mathrm{rel}}=\max(0,\sin h_S)
\]

This is not a physical irradiance value and must not be labeled as generated electrical power. A solar-array estimate requires additional assumptions, including panel orientation, incident irradiance, terrain shading, hardware efficiency, and relevant environmental conditions.

## 9. Preliminary direct-to-Earth visibility

The first Earth-visibility calculation is a geometric line-of-sight estimate relative to the selected horizon.

The application must distinguish:

- Any part of Earth's disk visible.
- The entire disk visible.
- The Earth center visible.
- A usable communication link, if link-budget and antenna information are available.

Visibility of Earth's disk does not by itself guarantee radio communication. A realistic communication analysis may require antenna pointing constraints, terrain clearance, spacecraft or ground-station geometry, link budget, and operational restrictions.

## 10. Terrain and horizon model

The ideal horizon is the initial baseline model.

A terrain-aware model must compare the apparent elevation of the target with the local terrain elevation in the corresponding azimuth direction. The implementation must document the terrain dataset, its resolution, its reference frame, and its uncertainty.

Until a suitable terrain model is integrated, all horizon-based outputs must be labeled as ideal-horizon estimates.

## 11. Data provenance and reproducibility

Each scientific result must preserve:

- Target and observer.
- Observer coordinates and their conventions.
- Observation time and time scale.
- Reference frame.
- Position representation.
- Light-time and aberration corrections.
- Angular-size method.
- Kernel or ephemeris identifiers and versions.
- Original input samples or a reproducible source reference.
- Calculation method and software version.
- Numerical residual and validation status.
- Known limitations and uncertainty notes.

The application must not silently combine incompatible datasets. If inputs come from different kernel versions or different apparent/geometric conventions, the mismatch must be resolved or explicitly reported.

## 12. Validation requirements

Before scientific calculations are approved for production, the following tests are required.

### Earth-event tests

- Verify the four event equations independently.
- Confirm the expected sign and crossing direction.
- Reproduce the four preliminary timestamps from preserved input samples.
- Recalculate using consistent kernel versions where available.
- Compare refined event times against an independently evaluated reference.
- Test tangencies, near-horizon cases, and missing samples.
- Confirm that UTC and local-time display conversions do not change the underlying event instant.

### Solar tests

- Verify solar azimuth and elevation at multiple times and locations.
- Check solar-disk boundary events.
- Verify illumination intervals and durations.
- Compare against a compatible independent ephemeris or reference calculation.

### Comparison tests

- Use multiple lunar sites and multiple dates.
- Confirm that identical inputs produce reproducible results.
- Test missing data, invalid coordinates, and unsupported terrain information.
- Ensure that outputs distinguish verified results from estimates.

Numerical tolerances must be established from the chosen reference method and data precision before the tests are declared passed.

## 13. Initial architecture requirements

The scientific engine must be independent of Flutter presentation code.

Suggested logical components:

- `ObservationConfiguration`: observer, target, coordinates, time, frame, and corrections.
- `EphemerisDataSource`: acquisition and provenance of scientific input data.
- `AngularGeometry`: angular-disk and limb calculations.
- `HorizonEventDetector`: event-function evaluation, crossing detection, and root refinement.
- `SolarIlluminationCalculator`: solar position and illumination intervals.
- `EarthVisibilityCalculator`: geometric Earth visibility intervals.
- `SiteComparisonService`: standardized metrics across sites and dates.
- `ScientificResult`: value, units, time, source, method, uncertainty, and validation status.

These are proposed component responsibilities, not a claim that the classes already exist.

## 14. Remaining work before production approval

1. Confirm and document the authoritative source and reproducible configuration for each calculation.
2. Resolve or quantify the mixed-kernel-version issue in the preliminary Earth events.
3. Obtain and validate solar position data for the selected lunar sites and dates.
4. Complete solar-disk and illumination-event calculations.
5. Complete preliminary Earth visibility intervals across the intended comparison set.
6. Define the solar-energy and communication metrics the first release will actually display.
7. Establish numerical tolerances and complete independent validation.
8. Approve the scientific reference dataset and test suite.
9. Implement the calculation engine and integrate it with the Flutter application.
10. Complete Android integration testing and prepare the competition demonstration.

## 15. Approval criteria

The scientific reference specification can be promoted to a production-approved version when:

- The selected models and coordinate conventions are documented.
- Every displayed metric has a defined mathematical meaning and unit.
- Reference results can be reproduced from preserved inputs.
- Independent comparisons satisfy documented tolerances.
- Known limitations are visible to developers and reflected in user-facing explanations.
- The test suite passes for the supported calculation scope.

**Current decision:** The four Earth-event calculations are retained as preliminary reference cases. They are not yet certified scientific ground truth. Work proceeds next with source and configuration verification, then solar calculations, then implementation of the validated calculation layer.