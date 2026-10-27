# LunaSight — Challenge Requirements & Technical Specification

**Document ID:** LS-ENG-SPEC-001  
**Version:** 0.1  
**Date:** 15 October 2026  
**Status:** Draft — Scientific Data and Feasibility Validation Required  
**Project:** LunaSight  
**Target Platform:** Android  
**Primary Technology:** Flutter / Dart  
**Competition:** NASA Space Apps Challenge 2026  
**Selected Challenge:** CLPS Lunar Mission Browser

---

## 1. Executive Summary

LunaSight is an interactive lunar mission analysis and comparison application designed to help users explore how the positions of the Sun and Earth change relative to selected locations on the lunar surface over time.

The application will focus on the lighting and direct-to-Earth visibility constraints relevant to lunar south-pole exploration. It will transform scientific geometry and terrain data into an understandable, visually compelling experience.

The project will prioritize scientific traceability, reproducible calculations, clear explanations, and an effective live demonstration.

The engineering approach is evidence-driven. Before committing to the complete application architecture, the team must verify that the selected scientific data sources support the required computations, that the necessary reference frames and time systems can be handled correctly, and that calculated results agree with trusted reference outputs.

### 1.1 Primary objectives

1. Compare two or more candidate lunar locations and selected observation times.
2. Calculate and visualize the Sun's elevation relative to the local horizon.
3. Calculate and visualize Earth's elevation relative to the local horizon.
4. Estimate sunlight availability over a selected time interval.
5. Identify periods of geometric Earth visibility and, when supported by adequate terrain data, possible terrain obstruction.
6. Explain the assumptions, limitations, and sources behind each result.
7. Provide a reliable and engaging demonstration suitable for the competition judging panel.

### 1.2 Non-goals

The initial project will not attempt to:

- Certify landing-site safety.
- Guarantee solar power production or communication success.
- Replace a mission-planning system used by NASA or a spacecraft operator.
- Model every communication subsystem or every physical environmental factor.
- Claim high-resolution terrain obstruction analysis before the terrain data and algorithm have been validated.
- Require a paid API or paid commercial service for its core scientific functionality.

---

## 2. Official Challenge Requirements and Feature Traceability

The challenge statement supplied by the team describes the need to compare lunar landing sites and dates efficiently, visualizing Sun and Earth positions relative to the horizon to assess power-generation potential and direct-to-Earth communication windows.

The following requirements translate that objective into testable engineering work. They are project requirements derived from the challenge, not additional official NASA rules.

| ID | Requirement | Planned implementation | Acceptance evidence |
|---|---|---|---|
| REQ-01 | Compare landing sites | Select and compare at least two defined lunar locations | Both locations appear with their coordinates and computed results |
| REQ-02 | Compare dates and times | Select a date, time, and analysis interval | The displayed geometry updates consistently with the selected time |
| REQ-03 | Visualize the Sun relative to the horizon | Display solar elevation and a local-horizon visualization | Numerical values agree with the validated calculation engine |
| REQ-04 | Visualize Earth relative to the horizon | Display Earth elevation and direction | Numerical values agree with independent reference calculations |
| REQ-05 | Assess sunlight availability | Analyze solar elevation over a time interval | The application identifies illuminated and non-illuminated intervals according to the declared model |
| REQ-06 | Assess direct-to-Earth visibility | Identify periods when Earth is geometrically above the local horizon | Visibility intervals are tested against an independent reference |
| REQ-07 | Account for terrain where possible | Add a terrain-obstruction layer after suitable elevation data are validated | Results distinguish idealized geometric visibility from terrain-aware visibility |
| REQ-08 | Make analysis efficient | Provide presets, comparison panels, and clear visual summaries | A user can complete the demonstration workflow without editing raw scientific parameters |
| REQ-09 | Support different audiences | Include concise explanations and optional technical details | Non-specialists can interpret the principal results; technical users can inspect assumptions |
| REQ-10 | Maintain scientific traceability | Record source, version, units, time system, coordinate frame, and model limitations | Every result can be traced to its inputs and calculation method |
| REQ-11 | Deliver a functional application | Implement the validated analysis workflow in Android Flutter | The release build passes the agreed functional and scientific tests |
| REQ-12 | Demonstrate the challenge's intended value | Present a live comparison of locations and times | The demonstration shows a meaningful, reproducible change in results |

### 2.1 Minimum complete scientific workflow

The first complete workflow must allow the user to:

1. Select a supported lunar location.
2. Select a date and time within the validated data coverage.
3. View the Sun's elevation relative to the local horizon.
4. View Earth's elevation relative to the local horizon.
5. Compare the selected location against another supported location or time.
6. Inspect the analysis interval and its visibility results.
7. Open a source and assumptions panel describing how the results were produced.

A terrain-aware visibility analysis is an important enhancement, but it must not be presented as implemented until the required data and computations have passed their validation gates.

---

## 3. Users and Main User Journeys

### 3.1 Intended users

- Lunar mission planners and engineering students.
- Space science educators.
- NASA Space Apps Challenge judges.
- Members of the public interested in lunar exploration.

The application is an educational and analytical prototype, not a flight-qualified mission-planning tool.

### 3.2 Primary user journey

**Open application → Select location → Select date/time → Explore Sun and Earth geometry → Compare alternatives → Review explanation and data sources.**

### 3.3 Comparison journey

1. Select candidate location A.
2. Select candidate location B.
3. Choose a common analysis interval.
4. Compare solar elevation over time.
5. Compare geometric Earth visibility over time.
6. Inspect any differences caused by the local horizon or terrain model.
7. Generate a concise comparison summary.

The interface must not rank one site as universally superior without a clearly defined objective function and appropriate assumptions. A site with more sunlight may not be preferable for every mission.

---

## 4. Scientific Data Sources and Feasibility Assessment

No data source should be treated as fully approved merely because it is published by NASA. The team must identify the specific product, coverage, coordinate system, resolution, licensing or usage conditions, and access method required for the chosen feature.

### 4.1 Primary candidate sources

#### A. NAIF / SPICE

Official resource: https://naif.jpl.nasa.gov/naif/

NAIF provides the SPICE system for computing observation geometry using scientific ancillary data and software. Its capabilities include body positions, reference frames, lighting angles, and geometric event searches. The toolkit and kernels must be selected for the bodies, times, and geometry needed by the application. [1][2]

**Potential use in LunaSight:**

- Calculate the relative positions of the Sun, Earth, and Moon.
- Establish consistent coordinate transformations.
- Compute observer-to-target vectors.
- Calculate surface lighting geometry.
- Determine time windows satisfying defined geometric conditions.

**Validation required:**

- Identify suitable planetary ephemeris kernels.
- Identify suitable lunar orientation and shape information.
- Determine whether a surface observer can be represented accurately for each selected location.
- Confirm the coverage and accuracy of the selected kernels.
- Document time conversion, reference frames, and any light-time or aberration corrections.

**Important implementation consideration:** The official SPICE toolkit is not a pure-Dart library. Direct use inside Flutter may require native integration or another calculation architecture. The team must evaluate the implementation cost before committing to a particular approach.

#### B. JPL Horizons

Official API documentation: https://ssd-api.jpl.nasa.gov/doc/horizons.html

JPL Horizons provides an API for retrieving ephemerides and related astronomical geometry. Its output depends on the query configuration, including the target, observer, time interval, coordinate system, and requested quantities. [3]

**Potential use in LunaSight:**

- Produce independent reference values for selected times.
- Investigate whether the required lunar surface-observer configuration can be supported for the intended calculations.
- Generate comparison data for scientific validation.
- Support development-time checks against the primary calculation engine.

**Limitations and verification requirements:**

- Confirm that the requested observer geometry is supported for each use case.
- Verify the returned reference frame, units, time scale, and corrections.
- Do not assume a generic Moon-centered ephemeris is equivalent to a local surface-horizon calculation.
- Treat an online API as a dependency subject to network availability and service constraints.

Horizons should not be used as the sole source of truth without independently validating the configuration and outputs.

#### C. NASA Planetary Data System — LOLA

Candidate dataset: LRO Moon Laser Altimeter gridded data products.

Dataset information:  
https://pds.nasa.gov/ds-view/pds/viewProfile.jsp?dsid=LRO-L-LOLA-4-GDR-V1.0

The LOLA gridded data products include lunar digital elevation models and related terrain information at multiple resolutions. Product selection must be based on the actual spatial coverage and characteristics required by the application. [4]

**Potential use in LunaSight:**

- Obtain surface elevation near candidate locations.
- Build a terrain-aware horizon profile.
- Estimate whether local topography obstructs a line of sight.
- Support terrain context in the visualization.

**Validation required:**

- Select an appropriate gridded product and resolution.
- Confirm its projection, elevation reference, pixel spacing, and coverage.
- Verify data decoding and coordinate transformations.
- Measure the effect of terrain resolution on calculated horizon obstruction.
- Record gaps, missing cells, and interpolation assumptions.

A terrain grid can support horizon analysis, but it does not automatically provide a complete, high-fidelity model of every local ridge, crater rim, or obstruction.

#### D. NASA lunar illumination reference products

Candidate reference: NASA's South Pole Illumination Map.

https://science.nasa.gov/resource/illumination-map-of-the-moons-south-pole/

NASA publishes an illumination map of the lunar south-polar region derived from Lunar Reconnaissance Orbiter imagery. It provides useful contextual and comparison material for the illumination problem. [5]

**Potential use in LunaSight:**

- Explain why lunar polar lighting is unusual.
- Provide a visual reference for selected south-polar regions.
- Support qualitative checks of the illumination visualization.
- Help identify useful candidate locations for the demonstration.

**Limitations:**

- A published illumination image is not a substitute for time-resolved solar geometry.
- Its temporal assumptions, spatial resolution, and intended interpretation must be understood before it is used for quantitative validation.
- The team must not infer exact illumination duration at a site from a static image alone.

### 4.2 Source-selection policy

The project will use a primary computation source and an independent reference source wherever practical.

| Data category | Primary candidate | Validation or supporting source |
|---|---|---|
| Sun/Earth/Moon geometry | Validated SPICE configuration or another verified geometry engine | JPL Horizons where an equivalent query is supported |
| Lunar surface elevation | Suitable LOLA gridded product | Product metadata and independent checks against documented terrain references |
| Illumination context | Time-resolved computed geometry | NASA south-pole illumination products |
| Coordinate definitions | Official source documentation | Independent review by the science/data owner |
| Time handling | Explicitly configured scientific time conversion | Known reference epochs and independent outputs |

The final source selection remains conditional on the feasibility experiments in Section 5.

### 4.3 Data registry

Every data product incorporated into the application must have an entry in a data registry containing:

- Source organization and product name.
- Official URL.
- Dataset or kernel identifier.
- Version, release, or retrieval date.
- Temporal coverage.
- Spatial coverage.
- Coordinate reference frame and projection.
- Units.
- Spatial and temporal resolution.
- License or usage conditions, where applicable.
- Download location or bundled asset identifier.
- Checksums for distributed files where practical.
- Known limitations and validation status.

No scientific asset should enter the production bundle without a registry entry.

---

## 5. Feasibility Experiments and Scientific Validation Gates

The team must validate the scientific core before investing heavily in the user interface.

### Gate G1 — Data accessibility and coverage

**Objective:** Prove that the selected sources contain sufficient information for the required geometry.

Tasks:

1. Retrieve representative SPICE kernels or equivalent geometry inputs.
2. Identify the lunar coordinate frame and body-shape model.
3. Retrieve a small LOLA elevation sample covering a candidate site.
4. Confirm the time range supported by the chosen ephemeris data.
5. Document data sizes, formats, and processing requirements.
6. Verify access and usage conditions.

**Pass condition:** A reproducible, documented data package exists for at least one candidate location and a meaningful time interval.

**Failure response:** Reduce the supported time range, use a simpler explicitly documented geometry model, or replace the data source after scientific review.

### Gate G2 — Surface-observer geometry

**Objective:** Calculate Sun and Earth directions from a defined point on the lunar surface.

Tasks:

1. Define the candidate location in an authoritative lunar coordinate system.
2. Convert the location into the calculation engine's required representation.
3. Establish the local surface normal and local horizon basis.
4. Calculate Sun and Earth direction vectors for selected epochs.
5. Convert the vectors into elevation and azimuth.
6. Compare results against independent reference calculations.

**Pass condition:** The results agree within a predeclared tolerance justified by the source configuration and the intended use.

The tolerance must be established before interpreting the test results; it must not be chosen afterward merely to make the outputs appear acceptable.

### Gate G3 — Terrain-aware horizon analysis

**Objective:** Determine whether terrain materially changes geometric visibility.

Tasks:

1. Decode the selected elevation product.
2. Extract a local terrain window around a test site.
3. Transform terrain points into a consistent local coordinate system.
4. Calculate a horizon profile.
5. Compare unobstructed geometry against terrain-aware line-of-sight results.
6. Investigate resolution and edge effects.

**Pass condition:** The algorithm passes synthetic geometry tests and produces reproducible results on a documented terrain sample.

If this gate is not passed, the application must clearly label results as idealized geometric visibility and must not claim terrain-aware accuracy.

### Gate G4 — Mobile implementation feasibility

**Objective:** Prove that the scientific computation can be delivered reliably on Android.

Evaluate:

- Calculation time for a single epoch.
- Calculation time for a full analysis interval.
- Memory requirements.
- Size of required bundled data.
- Native library compatibility, if applicable.
- Network dependence.
- Behavior without network access.
- Complexity of reproducing the same results on another device.

**Pass condition:** The team selects a documented calculation architecture supported by measured performance and verified results.

### Gate G5 — Scientific acceptance

Before the main implementation is considered ready, the team must have:

- A data registry.
- A documented geometry model.
- A documented time and coordinate convention.
- Independent reference comparisons.
- Automated unit tests for the geometry calculations.
- Explicit known limitations.
- A reproducible demonstration dataset.

---

## 6. Mathematical and Computational Model

All scientific calculations must use a consistent coordinate convention, explicit units, and a documented time system.

The following equations describe the intended geometry. The exact implementation must follow the validated calculation engine's coordinate definitions and reference frames.

### 6.1 Observer position and local horizon

Let the selected surface observer have position vector:

\[
\mathbf r_o
\]

Let the position vector of a target body, such as the Sun or Earth, be:

\[
\mathbf r_t
\]

Both vectors must be expressed in the same reference frame and use the same origin.

The observer-to-target vector is:

\[
\mathbf d=\mathbf r_t-\mathbf r_o
\]

The corresponding unit direction vector is:

\[
\hat{\mathbf d}=\frac{\mathbf d}{\|\mathbf d\|}
\]

Let \(\hat{\mathbf u}\) be the unit vector representing the local up direction at the selected surface point.

The target elevation above the local tangent plane is:

\[
e=\arcsin\left(
\operatorname{clamp}
\left(\hat{\mathbf d}\cdot\hat{\mathbf u},-1,1\right)
\right)
\]

The result is converted to degrees for display.

Interpretation:

- \(e>0^\circ\): the target is above the idealized local tangent horizon.
- \(e=0^\circ\): the target lies on the idealized local horizon.
- \(e<0^\circ\): the target is below the idealized local horizon.

**Critical limitation:** This equation alone describes the idealized local horizon. It does not prove that a ridge or crater rim does not obstruct the target.

The local up vector must be defined consistently with the chosen surface model. A radial vector and a terrain-derived surface normal are not always equivalent.

### 6.2 Local azimuth

For an understandable local visualization, define:

- \(\hat{\mathbf n}\): local north.
- \(\hat{\mathbf e}\): local east.
- \(\hat{\mathbf u}\): local up.

For a target direction vector, its horizontal components are:

\[
d_N=\hat{\mathbf d}\cdot\hat{\mathbf n}
\]

\[
d_E=\hat{\mathbf d}\cdot\hat{\mathbf e}
\]

A local azimuth convention can then be defined as:

\[
A=\operatorname{atan2}(d_E,d_N)
\]

Normalize the result to the interval from \(0^\circ\) to \(360^\circ\).

This convention measures azimuth clockwise from local north. The implementation must verify that the selected reference frame and orientation conventions support this interpretation.

### 6.3 Solar illumination classification

For the idealized horizon model, direct sunlight is geometrically possible when:

\[
e_{\text{Sun}}>0^\circ
\]

For numerical robustness, the application should use a documented threshold around the horizon and avoid treating a tiny numerical difference from zero as a meaningful operational distinction.

If terrain-aware visibility is available, define a local horizon obstruction angle \(H(A)\) for the target's azimuth. A simplified terrain-aware criterion is:

\[
e_{\text{Sun}}>H(A_{\text{Sun}})
\]

The precise definition of \(H\), its interpolation, and its reference direction must be specified by the terrain algorithm.

This criterion is only as reliable as the terrain model, surface normal, and resolution used to construct the horizon profile.

### 6.4 Illumination duration

For an analysis interval from \(t_0\) to \(t_1\), sample solar visibility at times \(t_i\).

Define an indicator function:

\[
I_i=
\begin{cases}
1 & \text{if the declared visibility criterion is met}\\
0 & \text{otherwise}
\end{cases}
\]

A simple sampled estimate of illuminated duration is:

\[
T_{\text{lit}}\approx\sum_i I_i\Delta t_i
\]

where \(\Delta t_i\) represents the duration associated with the sample.

The application must handle transitions between visible and non-visible states carefully. A refined implementation should locate the transition times through interpolation or an event-search method, rather than assuming that every transition occurs exactly at a sample timestamp.

The UI must display the sampling resolution and identify the output as an estimate unless transition times are calculated and validated with a more precise method.

### 6.5 Earth geometric visibility

Earth's geometric visibility can initially be classified using:

\[
e_{\text{Earth}}>0^\circ
\]

A terrain-aware classification can instead compare the Earth's elevation with the local horizon obstruction angle.

For each selected interval, the system should identify:

- Start and end times of each visibility interval.
- Total geometrically visible duration.
- Total duration below the modeled horizon.
- The model used to determine visibility.
- Any uncertainty or data gaps that affect the result.

This is a geometric visibility calculation, not a radio-link budget.

### 6.6 Solar power interpretation

Solar elevation is useful for evaluating sunlight geometry, but it does not directly determine electrical power output.

For a simplified flat panel, the ideal incident solar power may be represented as:

\[
P_{\text{incident}}=S\,A\,\max(0,\cos\theta)
\]

where:

- \(S\) is the assumed solar irradiance at the Moon.
- \(A\) is the panel area.
- \(\theta\) is the angle between the panel normal and the direction to the Sun.

This equation is a simplified illustration, not a complete power-system model.

Actual electrical power depends on panel efficiency, panel orientation, temperature, degradation, system losses, and other engineering parameters. Those values must not be invented or presented as measured mission data.

For the initial release, prioritize solar elevation and sunlight duration. Add a clearly labeled illustrative power estimate only if the assumptions and inputs can be documented.

### 6.7 Terrain line-of-sight analysis

A terrain-aware line-of-sight algorithm requires:

1. A valid surface observer position.
2. A consistent target direction.
3. A terrain dataset covering the relevant azimuths and distances.
4. A method for comparing the target ray with terrain elevations.
5. A defined interpolation and missing-data policy.

The initial terrain algorithm should be validated against synthetic test cases with known outcomes:

- Flat terrain with an unobstructed target.
- A ridge that clearly blocks the target.
- A ridge below the target direction.
- A target at the horizon.
- Incomplete terrain coverage.

The team must not claim that a local terrain window accounts for every possible obstruction if the data do not cover the entire relevant line of sight.

### 6.8 Time handling

The application must distinguish among:

- User-entered date and time.
- UTC or another explicitly defined display time standard.
- The time representation required by the scientific computation engine.
- The epoch and time scale associated with the reference data.

The UI must state the time standard used for analysis. It must not silently interpret a date/time in the user's device timezone if the scientific calculation expects another standard.

### 6.9 Numerical safeguards

All calculations must handle:

- Zero-length or invalid direction vectors.
- Floating-point values slightly outside valid inverse-trigonometric ranges.
- Missing ephemeris coverage.
- Unsupported dates.
- Invalid coordinates.
- Missing terrain cells.
- Failed or incomplete data requests.
- Inconsistent units or reference frames.

Invalid scientific inputs must result in a clear error or unavailable result, not a fabricated numeric value.

---

## 7. Application Architecture

### 7.1 Architectural principles

The application will follow a layered, testable architecture with clear boundaries between:

- Presentation.
- Application use cases.
- Domain models and scientific rules.
- Data access.
- Scientific computation.
- Visualization and reporting.

The geometry engine must be replaceable without rewriting the UI.

The final architecture depends on the feasibility gates. No native library, online API, or offline data package is approved until it has passed the relevant tests.

### 7.2 Proposed logical architecture

**Presentation layer**

- Home and mission overview.
- Location selector.
- Date/time controls.
- Sun and Earth visualization.
- Comparison dashboard.
- Analysis interval timeline.
- Scientific assumptions and source details.

**Application layer**

- Load supported locations.
- Calculate geometry for a selected epoch.
- Analyze a time interval.
- Compare candidate locations.
- Produce an explanatory result summary.
- Retrieve calculation provenance.

**Domain layer**

- Lunar location.
- Analysis interval.
- Observer geometry.
- Solar geometry result.
- Earth visibility result.
- Terrain horizon profile.
- Data provenance.
- Scientific validation status.

**Data layer**

- Dataset registry.
- Supported location catalog.
- Validated ephemeris inputs or computed samples.
- Terrain tiles or extracted elevation data.
- Reference test fixtures.
- Local cache and data integrity checks.

**Scientific computation boundary**

Define an interface such as `LunarGeometryEngine` that exposes the operations required by the application without exposing a particular implementation to the UI.

Potential implementations include:

1. A native SPICE-based engine.
2. A validated precomputed-data approach for a defined location and time range.
3. Another scientific geometry engine, provided it is independently validated.

A precomputed-data implementation must clearly restrict analysis to its supported coverage. It must not interpolate or extrapolate beyond that coverage without a validated method.

### 7.3 Recommended implementation decision

Begin with a small proof of concept, not the complete application.

Evaluate the native scientific engine and the precomputed-data alternative against the same reference cases. Compare scientific agreement, Android integration complexity, runtime performance, package size, and offline behavior.

Select the final approach only after the results are documented.

### 7.4 Proposed project structure

```text
lib/
  app/
    app.dart
    routing/
    theme/

  core/
    errors/
    logging/
    result/
    units/
    time/

  features/
    mission_overview/
      presentation/
      application/

    location_selection/
      presentation/
      application/
      domain/
      data/

    geometry_analysis/
      presentation/
      application/
      domain/
      data/

    comparison/
      presentation/
      application/
      domain/

    scientific_sources/
      presentation/
      application/
      domain/

  scientific/
    geometry_engine/
      lunar_geometry_engine.dart
      models/
      validation/

    terrain/
      horizon_profile.dart
      terrain_visibility.dart

  shared/
    widgets/
    formatting/
    accessibility/
```

This is a proposed structure, not a claim that these files already exist. The final folder layout may change during implementation while preserving the architectural boundaries.

### 7.5 Domain model requirements

Scientific models must explicitly represent:

- Position and direction vectors.
- Coordinate frame and units.
- Time epoch and time standard.
- Surface location and its coordinate convention.
- Sun and Earth elevation and azimuth.
- Visibility classification.
- Terrain-model availability.
- Source dataset version.
- Calculation method and known limitations.

Avoid passing unlabelled numeric values through the application. An angle expressed in radians must not be accidentally treated as degrees, and coordinates from one frame must not be silently interpreted as coordinates from another.

### 7.6 Error handling

The application must distinguish among:

- Invalid user input.
- Unsupported date or location.
- Missing scientific data.
- Network failure.
- Calculation failure.
- Terrain coverage limitations.
- Successful calculation with reduced confidence or simplified assumptions.

Every failure must be visible to the user in understandable language, with technical details available when useful.

---

## 8. User Interface and Visualization Requirements

### 8.1 Main screen

The main screen should provide:

- A clear application identity.
- A concise explanation of the current analysis.
- Access to candidate locations.
- Date and time controls.
- A prominent comparison action.
- A visible indication of the active model and data coverage.

### 8.2 Location comparison screen

For each candidate location, display:

- Location name.
- Latitude and longitude, including the coordinate convention.
- Selected analysis time.
- Solar elevation.
- Earth elevation.
- Geometric visibility status.
- Terrain-aware status, if available.
- Data and model notes.

The comparison must make the units and interpretation obvious.

### 8.3 Horizon visualization

The horizon display should illustrate:

- The local horizon.
- The Sun's apparent direction.
- Earth's apparent direction.
- Numeric elevation angles.
- The difference between an idealized horizon and a terrain-derived horizon.

The visualization must not imply that the Sun or Earth is physically close to the observer. It is a local directional representation, not a scale model of the solar system.

### 8.4 Timeline

The timeline should display intervals when:

- The Sun satisfies the chosen illumination criterion.
- Earth satisfies the chosen geometric visibility criterion.
- Terrain obstruction changes the classification, if that feature is available.

Use distinct labels for computed states and unsupported or unavailable intervals.

### 8.5 Explanation panel

Each result should answer:

- What was calculated?
- Which data and model were used?
- What does the result mean?
- What does it not mean?
- What are the principal uncertainties or limitations?

### 8.6 Accessibility and clarity

- Use readable labels and sufficient contrast.
- Do not rely on color alone to distinguish states.
- Provide numeric values alongside graphics.
- Explain technical terms in plain language.
- Ensure that loading and error states are clear.
- Avoid excessive scientific jargon on the main screen.

---

## 9. Work Breakdown and Team Responsibilities

The team has six or more members with varying skill levels. Roles below describe responsibilities, not assumptions about individual members' expertise. They may be combined or split as necessary.

| Role | Main responsibilities | Required deliverables |
|---|---|---|
| Team leader / application architect | Scope, technical decisions, Flutter integration, milestones, and coordination | Approved specification, architecture decisions, integrated application |
| Scientific data owner | Source discovery, metadata, coordinate systems, coverage, and data provenance | Data registry and source validation report |
| Geometry and mathematics owner | Surface-observer calculations, time handling, and reference comparisons | Calculation specification and validated test cases |
| Terrain and visualization owner | Elevation processing, horizon model, and visual representation | Terrain feasibility results and visualization components |
| UI/UX owner | User journeys, screen layouts, terminology, and accessibility | Approved interface design and interaction flow |
| Testing and demonstration owner | Test planning, regression checks, reproducibility, and judging presentation | Test report, demo script, and known-limitations list |

### 9.1 Shared responsibilities

All team members must:

- Review scientific claims before they appear in the demo.
- Keep assumptions and limitations documented.
- Report defects with reproducible steps.
- Avoid merging unvalidated scientific changes into the main branch.
- Review the final demonstration for consistency with the implemented features.

The team leader owns the final decision to accept a technical change into the integrated build.

---

## 10. Development Plan and Milestones

Milestones are defined by completion evidence rather than assumed calendar durations. The schedule should be set after the first feasibility experiment and adjusted to the competition deadline.

### Phase 0 — Requirements baseline

Tasks:

- Confirm the official challenge statement and relevant competition submission requirements.
- Freeze the initial scope.
- Establish the requirements traceability table.
- Define candidate locations and a representative analysis interval.
- Create the data registry.

**Exit criteria:** The team agrees on what the first scientifically defensible version must do.

### Phase 1 — Data and geometry feasibility

Tasks:

- Retrieve and inspect the candidate datasets.
- Establish coordinate and time conventions.
- Calculate Sun and Earth directions at selected epochs.
- Compare the results against independent reference outputs.
- Test the feasibility of terrain-aware visibility.

**Exit criteria:** Gates G1 and G2 pass; Gate G3 is either passed or explicitly deferred.

### Phase 2 — Technical architecture proof

Tasks:

- Compare candidate computation architectures.
- Test Android compatibility.
- Measure runtime, memory, and data-package size.
- Implement the calculation-engine boundary.
- Establish automated scientific tests.

**Exit criteria:** Gate G4 passes and the chosen architecture is documented.

### Phase 3 — Core application

Tasks:

- Implement location selection.
- Implement date/time controls.
- Display Sun and Earth geometry.
- Implement interval analysis.
- Implement comparison.
- Display scientific provenance and limitations.

**Exit criteria:** The minimum complete scientific workflow is functional.

### Phase 4 — Terrain analysis and advanced visualization

Tasks:

- Implement the terrain horizon model if Gate G3 passes.
- Visualize terrain obstruction.
- Improve interval transitions and timeline readability.
- Add explanatory summaries.
- Improve loading, error, and data-coverage states.

**Exit criteria:** Each enabled feature passes its own acceptance tests.

### Phase 5 — Integration and validation

Tasks:

- Run the complete test suite.
- Validate scientific outputs.
- Test offline and failure behavior according to the chosen architecture.
- Test on the intended Android devices.
- Verify that every visible feature corresponds to the requirements.
- Prepare the release build.

**Exit criteria:** Gate G5 passes, all critical defects are resolved, and the release is reproducible.

### Phase 6 — Competition presentation

Tasks:

- Prepare a reliable demonstration dataset.
- Rehearse the primary comparison scenario.
- Prepare a concise explanation of the science.
- Demonstrate limitations honestly.
- Verify the application works on the presentation device.
- Prepare a backup recording or screenshots in case of technical failure.

**Exit criteria:** The team can demonstrate the complete workflow and explain the calculation chain without relying on unsupported claims.

---

## 11. Testing Strategy

### 11.1 Unit tests

Test:

- Vector subtraction and normalization.
- Dot products and angle calculations.
- Inverse-trigonometric input handling.
- Azimuth normalization.
- Time conversions.
- Illumination classification.
- Visibility interval construction.
- Terrain horizon comparisons.
- Invalid or missing data handling.

### 11.2 Scientific reference tests

For each reference case, record:

- Input location.
- Input epoch and time standard.
- Source data and versions.
- Reference frame.
- Target body.
- Reference result.
- LunaSight result.
- Difference and acceptance tolerance.
- Test status.

The team must use equivalent configurations when comparing results. Different time scales, coordinate frames, observer definitions, or aberration corrections can produce legitimate differences.

### 11.3 Integration tests

Verify that:

- Location selection updates all relevant results.
- Date/time changes trigger the correct recalculation.
- Comparison results use the intended locations and interval.
- The timeline matches the numerical analysis.
- Source information matches the actual calculation path.
- Errors propagate to the UI without displaying stale values as current results.

### 11.4 Terrain tests

Use synthetic terrain cases with known visibility outcomes, followed by documented real terrain samples.

Test incomplete coverage and low-resolution terrain explicitly. A terrain algorithm must not report an unobstructed line of sight when the relevant terrain coverage is missing.

### 11.5 Mobile and performance tests

Verify:

- Startup and navigation.
- Calculation responsiveness.
- Memory use.
- App lifecycle behavior.
- Recovery from failed calculations.
- Behavior when the network is unavailable, if offline operation is supported.
- Data integrity and version compatibility.
- Installation and execution on the intended Android version.

Performance targets should be defined after the feasibility prototype establishes realistic measurements.

### 11.6 Acceptance criteria

A feature is accepted only when:

1. Its requirement is identified.
2. Its calculation or behavior is documented.
3. Its tests pass.
4. Its limitations are documented.
5. Its UI description matches what is actually computed.
6. Its result can be reproduced using recorded inputs and data versions.

---

## 12. Demonstration Plan for the Judging Panel

The demonstration should communicate the scientific problem first, then show how LunaSight makes the comparison easier.

### Suggested sequence

**Step 1 — Introduce the challenge**

Explain that a lunar location's usefulness depends partly on when the Sun and Earth are positioned relative to its local horizon.

**Step 2 — Select a candidate location**

Open a supported location and show its coordinates and the selected time.

**Step 3 — Inspect Sun and Earth geometry**

Show their elevations relative to the local horizon and explain what positive or negative elevation means.

**Step 4 — Compare a second location**

Keep the analysis interval consistent and show how the geometry differs.

**Step 5 — Explore time-dependent conditions**

Move through the analysis timeline and identify changes in illumination or geometric Earth visibility.

**Step 6 — Explain the science**

Open the data and assumptions panel. Identify the sources, coordinate conventions, model, and validation status.

**Step 7 — State the limitations**

Explain why geometric Earth visibility does not guarantee an operational radio link and why solar elevation does not alone determine usable electrical power.

**Step 8 — End with the practical value**

Show how a user can compare candidate conditions through one coherent workflow rather than interpreting disconnected data products.

### Demonstration reliability

The primary scenario should use prevalidated locations and times. If live online data retrieval is not essential to the validated design, avoid making the demonstration depend on a network request that could fail during judging.

The team must never substitute prerecorded values for live calculations without clearly disclosing that the displayed result is precomputed.

---

## 13. Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Incorrect coordinate frame | Scientifically invalid angles | Centralize frame definitions and validate against reference outputs |
| Incorrect time conversion | Wrong visibility intervals | Explicitly define and test time standards |
| Insufficient terrain coverage | False obstruction or visibility conclusions | Display coverage limitations and disable unsupported claims |
| Native scientific integration is too complex | Delays to the Android build | Test alternatives early and keep the geometry engine replaceable |
| Online service is unavailable | Failed live analysis | Validate an offline or precomputed-data strategy where feasible |
| Large scientific assets | Slow installation or high memory use | Measure assets early and use only required coverage and resolution |
| Overstated solar power claims | Misleading conclusions | Present geometric indicators separately from electrical power estimates |
| Overstated communication claims | Misleading mission interpretation | Label the output as geometric Earth visibility unless a validated link model exists |
| Attractive but scientifically incorrect visualization | Loss of credibility | Tie every visualization to tested numeric outputs |
| Schedule overrun | Incomplete final submission | Prioritize the minimum complete scientific workflow before advanced features |

---

## 14. Scope Prioritization

### Priority A — Required for the first complete version

- Supported lunar location selection.
- Date/time selection within validated coverage.
- Sun elevation.
- Earth elevation.
- Time-dependent analysis.
- Comparison between locations or times.
- Source and assumptions information.
- Automated scientific tests.
- Reliable Android demonstration.

### Priority B — Add when validated

- Terrain-aware horizon obstruction.
- Refined visibility event times.
- More candidate locations.
- Expanded supported time ranges.
- Additional comparison metrics.
- Exportable scientific comparison summary.

### Priority C — Consider only if time and evidence permit

- Illustrative solar panel output estimates.
- Advanced terrain visualization.
- Expanded location catalogs.
- Additional mission-planning context.

No lower-priority feature should delay the scientifically validated core.

---

## 15. Definition of Done

LunaSight is ready for the competition demonstration when all of the following are true:

- The core user workflow is complete.
- The selected scientific sources are documented.
- The calculation engine has passed the agreed reference tests.
- The supported time range and location coverage are explicit.
- The displayed angles use documented units and conventions.
- Comparison results are reproducible.
- Terrain-aware claims are enabled only if the terrain model passes validation.
- Scientific limitations are visible to the user.
- Critical defects are resolved.
- The Android build has been tested on the presentation device.
- The team can explain the source-to-result calculation chain.
- The demonstration does not depend on unsupported scientific claims.

---

## 16. Immediate Action Items

The next actions, in order, are:

1. **Create the data registry** for candidate ephemeris, lunar orientation, terrain, and illumination-reference products.
2. **Select one initial lunar test location** and a small set of test epochs.
3. **Prove the Sun/Earth surface-observer geometry** using a documented scientific engine.
4. **Generate independent reference results** using a compatible reference configuration.
5. **Define numerical acceptance tolerances** before judging the results.
6. **Evaluate terrain coverage and resolution** for the chosen location.
7. **Measure Android integration feasibility** for the candidate computation approaches.
8. **Record the Gate G1–G5 results** and decide which features can be approved for implementation.
9. **Freeze the initial architecture** only after the evidence supports it.
10. **Begin the full Flutter implementation** once the scientific core and its boundaries are sufficiently established.

---

## 17. References

**[1] NASA NAIF — SPICE**

https://naif.jpl.nasa.gov/

Official information about SPICE, observation geometry, kernels, and supported toolkit environments.

**[2] NASA NAIF — SPICE Tutorials**

https://naif.jpl.nasa.gov/naif/tutorials.html

Reference material covering time systems, frames, kernels, observation geometry, and geometric event calculations.

**[3] NASA/JPL — Horizons API Documentation**

https://ssd-api.jpl.nasa.gov/doc/horizons.html

Official API documentation for ephemeris queries and their configuration.

**[4] NASA Planetary Data System — LOLA Gridded Data Record**

https://pds.nasa.gov/ds-view/pds/viewProfile.jsp?dsid=LRO-L-LOLA-4-GDR-V1.0

Dataset description for lunar elevation and related gridded products. The exact product, resolution, and metadata must be confirmed before implementation.

**[5] NASA Science — Illumination Map of the Moon's South Pole**

https://science.nasa.gov/resource/illumination-map-of-the-moons-south-pole/

NASA reference material for understanding the lunar south-polar illumination environment.

**[6] NASA Space Apps Challenge 2026 — CLPS Lunar Mission Browser**

https://www.spaceappschallenge.org/2026/challenges/clps-lunar-mission-browser/

Official challenge page. The team must confirm the final submission instructions, judging criteria, and any additional event requirements directly from the official event materials.

---

## 18. Document Status and Change Control

**Current status:** Initial engineering specification; scientific feasibility is not yet certified.

This document defines the proposed scope, requirements, validation approach, and architecture options. It does not claim that the data pipelines, geometry calculations, terrain analysis, or Flutter features have already been implemented.

Any future change affecting the scientific model, supported time range, data source, coordinate convention, visibility definition, or public-facing claim must be documented and reviewed before being treated as accepted.

The next document should be a **LunaSight — Scientific Data Feasibility & Validation Report**, recording the actual datasets inspected, the exact calculation configuration, reference results, discrepancies, and pass/fail outcomes for the feasibility gates.

**Engineering principle:** Every result presented by LunaSight must be explainable, traceable to its inputs, and consistent with the capabilities and limitations of the validated model.
