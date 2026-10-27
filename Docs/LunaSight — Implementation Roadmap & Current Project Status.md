# LunaSight — Implementation Roadmap & Current Project Status

**Project:** LunaSight  
**Challenge:** NASA Space Apps Challenge 2026 — CLPS Lunar Mission Browser  
**Target platform:** Android first  
**Technology stack:** Flutter and Dart  
**Document type:** Implementation roadmap and project-status baseline  
**Status:** Working baseline — repository audit and owner review required  
**Last updated:** October 27, 2026

---

## 1. Purpose

This document consolidates the currently established project decisions, verified technical progress, outstanding scientific-validation items, proposed architecture, implementation sequence, acceptance criteria, and coding-agent instructions.

It is intended to guide implementation without restarting completed research or treating unverified work as finished.

**Important status rule:** This document is based on the available project context and supplied test outputs. It does not claim that the original project specification or the complete source repository has been recovered and audited.

### Decision classifications

- **CONFIRMED:** Explicitly established in the available project context.
- **OBSERVED:** Supported by a supplied command output or test result.
- **PROPOSED:** Recommended design decision awaiting confirmation where necessary.
- **OPEN:** Requires investigation, source evidence, or an explicit decision.

---

## 2. Project Vision

LunaSight is intended to help users compare candidate lunar landing sites and mission dates through two important geometric factors:

1. **Solar illumination geometry:** The Sun's position relative to the local lunar horizon, helping users understand potential solar-power opportunities.
2. **Earth visibility geometry:** Earth's position relative to the local lunar horizon, helping users estimate potential direct-to-Earth geometric visibility windows.

The application should turn these data into an accessible, visually compelling comparison experience suitable for a live competition demonstration.

The application must distinguish source-provided measurements from locally derived quantities, approximations, and assumptions.

### Scientific limitations

- Solar elevation alone does not establish actual electrical energy production. Panel orientation, terrain, shadowing, equipment, and system losses may affect the result.
- Earth being geometrically above the horizon does not guarantee a functioning communications link. Terrain obstruction, antenna orientation, link budget, relay requirements, and operational constraints may matter.
- Any site-ranking score must disclose its criteria and assumptions. A heuristic score must not be presented as a validated mission-planning recommendation.
- Scientific outputs must retain their provenance, epoch, units, coordinate-frame semantics, and relevant calculation settings.

---

## 3. Established Project Decisions

| Area | Current decision | Status |
|---|---|---|
| NASA challenge | CLPS Lunar Mission Browser | CONFIRMED |
| Working project name | LunaSight | CONFIRMED |
| Initial platform | Android | CONFIRMED |
| Application framework | Flutter and Dart | CONFIRMED |
| Main user workflow | Compare lunar sites and dates | CONFIRMED |
| Solar analysis | Sun position relative to the local horizon | CONFIRMED |
| Earth analysis | Earth position and potential geometric visibility | CONFIRMED |
| Initial ephemeris provider | NASA/JPL Horizons API | PROPOSED pending capability audit |
| Independent validation | SPICE-based calculations and reference comparisons | CONFIRMED APPROACH |
| Competition-provided API | Not released at the time of this document | CONFIRMED |
| Future provider integration | Keep the architecture replaceable and extensible | PROPOSED |
| Offline access | Local reference data and cached results where appropriate | PROPOSED from prior planning context |
| Architecture | Separate presentation, domain, scientific computation, and data access | PROPOSED |

Horizons is the current leading candidate, not an irrevocably approved final provider. When the competition API becomes available, its documented capabilities must be compared with the application's actual requirements.

Provider selection must consider supported quantities, precision, coordinate frames, time scales, correction settings, coverage, rate limits, availability, and usage terms.

---

## 4. Current Project Status

### 4.1 Horizons API connectivity

**Status: Demonstrated successfully.**

The supplied Python test script successfully queried the JPL Horizons file API:

`https://ssd.jpl.nasa.gov/api/horizons_file.api`

Official API documentation:

`https://ssd-api.jpl.nasa.gov/doc/horizons.html`

The request returned HTTP 200 and identified the source as `NASA/JPL Horizons API`.

The successful request uses a Horizons input file submitted through multipart form data and requests JSON output.

This confirms connectivity and successful retrieval for the tested request. It does not establish that every quantity needed by LunaSight has been audited or validated.

### 4.2 Earth observer-table experiment

**Status: Data retrieved; scientific interpretation remains under review.**

A supplied Horizons run used:

- Target: Earth (399)
- Center: Moon (301)
- Lunar observer longitude: 200° east
- Lunar observer latitude: −88.45°
- Observer altitude: approximately 0 km
- Ephemeris source shown by Horizons: DE441
- Atmospheric refraction: disabled (`AIRLESS`)
- Interval: November 2, 2026, 14:12:30–14:12:50 UTC
- Sampling: one-second intervals
- Requested quantities: `4,13,20,21`

The output included apparent azimuth and elevation, equatorial angular diameter, apparent range and range-rate, and one-way down-leg light time.

At 14:12:30 UTC, the supplied output reported:

- Earth-center elevation: −0.970998°
- Equatorial angular diameter: 7013.649 arcseconds
- One-way down-leg light time: 0.02085710 minutes, approximately 1.251426 seconds

These values describe the specified request and observer configuration; they are not universal constants.

### 4.3 SPICE-based Earth-limb experiment

**Status: Preliminary result recorded; final reconciliation remains open.**

The project context records a SPICE validation script named `validate_earth_limb.py`. The script used local SPICE kernels, including leap-second, planetary-constant, planetary-ephemeris, lunar-orientation, and Earth-orientation/frame data.

The recorded SPICE result placed an ellipsoidal Earth upper-limb crossing between 14:12:47 and 14:12:48 UTC, with a linearly interpolated estimate near **14:12:47.395 UTC**.

Previously reported SPICE center light-time values were approximately 1.25143 seconds and agreed closely with Horizons at comparable epochs.

This crossing estimate is a result of the current calculation procedure. It must not yet be described as independently validated or release-approved.

### 4.4 Open scientific discrepancy

The Horizons approximation

`Earth center elevation + (equatorial angular diameter / 7200)`

estimates a spherical upper limb. It is not equivalent to the projected limb of an oblate ellipsoid.

The discrepancy has not been conclusively isolated. Potential factors to examine include:

- Observer and target reference frames.
- Lunar and Earth orientation data.
- Epoch and time-scale handling.
- Apparent-position correction settings.
- Definition of the horizon and Earth limb.
- The method used to evaluate the projected ellipsoid.

**Decision:** Keep this issue open, but do not let it block unrelated application foundations. Do not present the disputed crossing as a validated production result.

### 4.5 Flutter repository status

**Status: Not verified in this document.**

The current Flutter repository path, source tree, dependencies, tests, assets, build status, and Git state have not been audited here.

The implementation agent must inspect the actual repository before creating a scaffold, changing dependencies, or modifying source files. It must not assume the project is empty.

---

## 5. Proposed First Demonstrable Release

The first complete judging-oriented workflow should allow a user to:

1. Open LunaSight and understand its purpose.
2. Select a lunar candidate site from a curated, source-backed catalogue.
3. Select a date/time or comparison interval supported by the data layer.
4. Inspect Sun geometry at the selected site and epoch.
5. Inspect Earth geometry at the selected site and epoch.
6. Compare two or more sites or dates using consistent metrics.
7. Understand the source, units, timestamp, method, and limitations of the displayed values.
8. Access packaged or cached reference information offline, where supported, with freshness clearly indicated.

Candidate sites and their coordinates must be backed by identifiable sources. Do not invent coordinates or claim that a site is an officially endorsed CLPS landing site without evidence.

### Out of scope unless separately approved

Do not claim to provide:

- Certified landing-site safety assessments.
- Full mission trajectory or navigation design.
- Validated terrain-shadow predictions without suitable elevation data and tested geometry.
- Electrical-energy or battery predictions without a documented power-system model.
- Guaranteed communications availability or a complete radio-frequency link budget.
- Live spacecraft telemetry that the selected source does not provide.

---

## 6. Proposed Architecture

The implementation must separate UI code, scientific calculations, domain models, and provider-specific data access.

The following is a proposed structure, to be adapted after inspecting the actual repository:

```text
lib/
  app/
    routing/
    theme/
  core/
    errors/
    result/
    time/
    units/
    provenance/
    networking/
    persistence/
  features/
    site_catalog/
      data/
      domain/
      presentation/
    mission_comparison/
      data/
      domain/
      presentation/
    solar_geometry/
      data/
      domain/
      presentation/
    earth_visibility/
      data/
      domain/
      presentation/
    settings/
      data/
      domain/
      presentation/
```

### Architectural responsibilities

**Presentation layer**
- Site and date selection.
- Visualizations and comparison views.
- Loading, error, empty, and offline states.
- Explanations and scientific caveats.

**Domain layer**
- Site and epoch models.
- Typed scientific quantities.
- Provider-independent interfaces.
- Comparison rules and use cases.

**Data layer**
- Horizons adapter.
- Future competition API adapter.
- Local reference-data source.
- Cache implementation.
- Response parsing and validation.

**Scientific computation**
- Isolated, unit-aware, testable algorithms.
- Explicit assumptions and validity limits.
- Independent reference tests for significant calculations.

**Provenance**
- Provider and dataset identifiers.
- Acquisition timestamp.
- Epoch represented by the result.
- Target, observer, coordinate frame, units, and correction settings.
- Clear distinction between source-provided and locally derived values.

Do not impose this exact directory tree if the existing repository already has a sound equivalent structure. Preserve existing architecture where possible.

### Provider abstraction

UI widgets and domain logic must not issue raw Horizons HTTP requests directly.

Define provider-independent contracts for the required data products. Provider adapters must normalize data into documented domain models while retaining provenance and rejecting malformed or inconsistent responses.

The future competition API should be integrable without requiring a rewrite of the UI or domain layer.

Do not assume the future API will be interchangeable with Horizons until its documentation has been reviewed.

### Security and API access

Do not embed private API credentials in Flutter client code. Inspect authentication and usage terms before selecting the final provider.

If a private credential or privileged server-side operation is required, evaluate an appropriate backend or another approved access method. Do not introduce paid infrastructure without explicit owner approval.

---

## 7. Scientific Data and Validation Policy

### 7.1 Provider capability audit

Before locking the provider, document for every required quantity:

- Target and observer identifiers.
- Endpoint and request parameters.
- Coordinate frame and observer-site definition.
- Geometric, astrometric, or apparent interpretation.
- Epoch and time-scale semantics.
- Light-time, aberration, gravitational-deflection, orientation, and refraction settings where applicable.
- Units, precision, missing-value behavior, and sampling interval.
- Availability, rate limits, and usage restrictions.
- Whether the quantity is returned directly or derived locally.

A successful HTTP response is not sufficient evidence that the data are scientifically suitable.

### 7.2 Calculation boundaries

Scientific calculations must not be embedded only in UI widgets.

Each derived quantity must have:
- A documented formula or algorithm.
- Explicit input and output units.
- Stated assumptions and validity limits.
- Unit tests, including boundary cases.
- Reference comparisons and tolerances where appropriate.

For Earth visibility, distinguish explicitly between:

1. Earth-center elevation.
2. Spherical angular-diameter approximation.
3. Ellipsoidal limb elevation.
4. Terrain-obstructed visibility, if terrain data are later supported.

These quantities are not interchangeable.

### 7.3 Independent validation

For each significant calculation:

1. Define reproducible reference cases.
2. Record inputs, epochs, frames, correction settings, and relevant source/kernel versions.
3. Compare against an independent method or authoritative reference when available.
4. Define tolerances before accepting the result.
5. Investigate discrepancies instead of loosening tolerances to force a pass.
6. Preserve scripts and expected outputs.
7. Mark unresolved results as experimental or unavailable rather than implying scientific certainty.

SPICE may remain a local validation tool. It does not need to be bundled into the Android application unless a separate decision establishes that requirement.

---

## 8. Offline and Cache Requirements

Offline-first behavior is a proposed requirement that must be reconciled with the original specification.

The implementation should:

- Package a curated, versioned site catalogue with source metadata.
- Cache successful results where appropriate and permitted.
- Distinguish live, cached, packaged, stale, and unavailable data.
- Store the retrieval timestamp separately from the represented epoch.
- Never display stale data as freshly retrieved data.
- Handle timeouts, network failures, server errors, malformed responses, and unsupported dates.
- Define cache retention and eviction behavior.
- Explain when a requested result cannot be evaluated offline.
- Include every result-affecting input in cache keys, including site, target, epoch, frame, and correction settings.

Cached values must not be treated as a substitute for a valid calculation.

---

## 9. Proposed User Experience

The following screen groups are proposed; their implementation status has not been verified.

### 9.1 Home / Mission Overview
- Brief explanation of LunaSight.
- Entry point to site/date comparison.
- Clear data-availability status.

### 9.2 Site Selection
- Curated site catalogue.
- Coordinates and source provenance.
- No unsupported claims about official status.

### 9.3 Time Selection
- UTC-backed internal timestamps.
- Correct and explicit display-time conversion.
- Clear handling of unsupported time ranges.

### 9.4 Site Analysis
- Sun azimuth/elevation and documented illumination indicators.
- Earth azimuth/elevation and geometric visibility indicators.
- Units, epoch, source, and caveats.

### 9.5 Comparison
- Consistent metrics across sites and dates.
- Clear separation of source values and derived scores.
- Transparent ranking criteria rather than an unexplained “best site” verdict.

### 9.6 Data and Method Details
- Provider and dataset.
- Retrieval time and represented epoch.
- Coordinate frame and correction configuration.
- Scientific assumptions and known limitations.

### 9.7 Settings / Data Management
- Cache status and refresh controls.
- Relevant display preferences.
- No exposed credentials or secrets.

---

## 10. Implementation Roadmap

### Phase 0 — Repository and Specification Audit

**Status: Not verified**

Tasks:
- Inspect the actual project directory and Git status.
- Identify existing code, dependencies, assets, scripts, tests, and documentation.
- Locate the authoritative project specification and its latest revision.
- Preserve all existing work.
- Produce an audit report listing verified facts, gaps, and proposed file changes.

**Acceptance criteria**
- Current repository state is documented.
- No source files are changed during the audit.
- Existing requirements are mapped to this roadmap or flagged as conflicts.
- Unknowns are explicitly recorded.

### Phase 1 — Data Provider Capability Audit

**Status: Partially started; not closed**

Tasks:
- Enumerate the quantities required for the first demonstrable workflow.
- Map each quantity to documented Horizons request parameters and response fields.
- Record frames, time scales, corrections, and units.
- Document network, authentication, usage, and offline implications.
- Establish how a future competition API will be evaluated.

**Acceptance criteria**
- A data contract exists for each required quantity.
- Reproducible sample requests and sanitized response fixtures are stored.
- Unit and frame conversions are tested.
- Provider selection is explicitly approved.
- Unsupported capabilities are not claimed.

### Phase 2 — Scientific Domain Models and Validation Harness

**Status: Partially started; important validation remains open**

Tasks:
- Define typed models with explicit units and provenance.
- Separate API parsing from calculation code.
- Preserve existing Horizons/SPICE scripts and outputs.
- Create reproducible reference cases for Sun and Earth geometry.
- Continue the limb discrepancy investigation when required to validate that feature.

**Acceptance criteria**
- Tests cover parsing, invalid values, units, and boundary cases.
- Independent comparisons meet documented tolerances, or discrepancies are explicitly classified.
- Unvalidated limb calculations cannot be represented as release-approved results.
- Validation commands and expected outputs are documented.

### Phase 3 — Application Foundation

**Status: Not verified**

Tasks:
- Implement or adapt the Flutter scaffold after Phase 0.
- Establish routing, theme, and state management consistent with the existing project.
- Add typed error states and structured diagnostics.
- Establish static analysis and test organization.
- Ensure no secrets are embedded in the client.

**Acceptance criteria**
- The app launches on the target Android environment.
- No duplicate scaffold or unnecessary rewrite is introduced.
- Static analysis and baseline tests pass.
- Loading, error, empty, and offline states are represented.

### Phase 4 — Site Catalogue and Data Layer

**Status: Not verified**

Tasks:
- Add curated, source-backed site records.
- Implement provider and local/cache sources behind appropriate contracts.
- Validate API responses before domain mapping.
- Add timeouts and bounded retries where appropriate.
- Implement freshness and cache behavior.

**Acceptance criteria**
- Site coordinates have traceable provenance.
- Network failures do not crash the app.
- Cache keys include all result-affecting inputs.
- Live and cached data are distinguishable.
- Adapter tests use fixtures and do not depend on live network access.

### Phase 5 — Solar and Earth Analysis

**Status: Not verified**

Tasks:
- Display Sun and Earth geometry for selected sites and epochs.
- Show units, source, epoch, and data status.
- Implement only derived metrics with documented formulas and assumptions.
- Distinguish geometric visibility from operational communications claims.

**Acceptance criteria**
- UI values trace back to tested domain models.
- Calculations are not embedded solely in widgets.
- Results remain consistent when changing sites, times, or providers.
- Missing or invalid data is never replaced with fabricated values.

### Phase 6 — Site and Date Comparison

**Status: Not verified**

Tasks:
- Compare multiple supported sites and/or dates.
- Define transparent comparison metrics.
- Show trade-offs instead of unsupported definitive recommendations.
- Ensure visual comparisons remain readable on the target device.

**Acceptance criteria**
- Each metric has consistent units and semantics.
- Rankings are reproducible and explainable.
- Incomplete data and unsupported inputs are handled explicitly.
- At least one meaningful comparison scenario is reproducible.

### Phase 7 — Offline, Reliability, Accessibility, and Polish

**Status: Not verified**

Tasks:
- Test offline startup and reference-data access.
- Review loading, timeout, retry, and stale-data states.
- Check text scaling, contrast, tap targets, and supported screen sizes.
- Review performance and memory use.
- Remove debug-only behavior and accidental sensitive logging.

**Acceptance criteria**
- The app remains usable within its documented offline scope.
- Freshness and limitations are understandable.
- Defined smoke tests produce no uncaught exceptions.
- Accessibility and layout checks pass for supported sizes.

### Phase 8 — Final Validation and Judging Demo

**Status: Not verified**

Tasks:
- Run the full test suite and static analysis.
- Build and install a release-mode Android artifact.
- Rehearse a demo using fixed, reproducible scenarios.
- Prepare an explanation of sources, methods, assumptions, and limitations.
- Reassess the competition API after its documentation becomes available.

**Acceptance criteria**
- The release build installs and launches on a real or appropriately documented target device.
- Demo results can be reproduced.
- Known critical scientific or runtime defects are not concealed.
- Unresolved limitations are disclosed.
- The competition-API decision is documented when possible.

---

## 11. Cross-Cutting Quality Requirements

### Engineering quality
- Follow existing repository conventions where sound.
- Prefer small, cohesive, testable components.
- Use explicit domain models rather than passing loosely structured maps through the app.
- Handle errors intentionally; do not silently swallow exceptions.
- Keep provider-specific parsing inside adapters.
- Avoid unnecessary dependencies and paid services.
- Do not use TODOs, placeholder implementations, fake production data, or incomplete stubs to stand in for required functionality.
- If a requirement cannot be completed safely because data or scientific validation is missing, report the blocker rather than fabricate a result.

### Scientific integrity
- Preserve units and provenance.
- Distinguish source values from derived values.
- Distinguish geometric visibility from operational availability.
- Document approximations and validity domains.
- Never claim independent validation succeeded unless it was actually performed and its evidence recorded.
- Do not change test tolerances without scientific justification.

### Security
- Do not commit credentials, tokens, or private configuration.
- Do not log secrets or unnecessary personal data.
- Respect provider terms and usage limits.
- Obtain owner approval before introducing paid services or hosted infrastructure.

---

## 12. Coding-Agent Instructions

These rules must be included in future implementation prompts.

### Required behavior

1. Read this roadmap and the authoritative project specification before editing code.
2. Inspect the actual repository and Git status first.
3. Identify the exact files to be changed and provide a concise plan.
4. Preserve existing working code, scripts, kernels, test fixtures, and documentation.
5. Implement the approved phase end-to-end, including tests and documentation.
6. Run formatting, static analysis, tests, and relevant builds; report actual outcomes.
7. Separate verified facts, assumptions, and unresolved issues.
8. Keep provider-specific behavior behind an abstraction.
9. Use source-backed site data and reproducible fixtures.
10. Return an English completion report containing changed files, implementation decisions, commands run, test results, and remaining risks.

### Red flags — prohibited without explicit owner approval

- Do not rewrite the whole app merely for stylistic preference.
- Do not delete or overwrite existing code, validation scripts, kernels, data, or documentation without a demonstrated need.
- Do not invent site coordinates, ephemeris values, API capabilities, test results, or rankings.
- Do not treat a spherical angular-diameter estimate as an exact ellipsoidal limb calculation.
- Do not claim that Earth visibility guarantees communication or that solar elevation guarantees usable power.
- Do not embed private API secrets in Flutter client code.
- Do not add paid APIs, paid infrastructure, or mandatory account dependencies without approval.
- Do not introduce fake implementations, empty methods, placeholder screens, or TODO-only deliverables.
- Do not suppress failing tests or relax tolerances merely to obtain a pass.
- Do not claim tests passed when they were not run.
- Do not modify unrelated files or broadly update dependencies without necessity.
- Do not wait for the competition API to build components that can already be developed against provider-independent contracts.

---

## 13. Open Decisions Register

| ID | Open item | Why it matters | Next action |
|---|---|---|---|
| O-01 | Original requirements document and latest revision | Prevent missing or contradictory requirements | Locate during Phase 0 |
| O-02 | Actual repository path and Flutter project state | Prevent duplicate or destructive work | Inspect repository first |
| O-03 | Final provider choice | Required data and coordinate semantics may differ | Complete Phase 1 audit |
| O-04 | Approved candidate-site catalogue | Site coordinates and status must be traceable | Identify and cite authoritative sources |
| O-05 | Scientific tolerances | Required to assess accuracy | Define per quantity before acceptance |
| O-06 | Earth-limb discrepancy | Affects validated horizon windows | Keep open; investigate when required |
| O-07 | Exact offline scope | Determines packaging and cache policy | Reconcile with original specification |
| O-08 | Comparison metrics and scoring | Prevent arbitrary rankings | Define transparent criteria |
| O-09 | Competition API specification | May change provider selection | Reassess when released |
| O-10 | Demo device and judging flow | Affects layout and rehearsed scenario | Confirm before final polish |

---

## 14. Immediate Next Actions

Execute the following sequence:

1. Audit the actual LunaSight project directory and Git status **without modifying files**.
2. Locate the original `LunaSight — Challenge Requirements & Technical Specification` and later decisions.
3. Reconcile the original requirements with this roadmap and produce a repository/specification audit report.
4. Complete the Horizons capability and data-contract audit for the first demonstrable workflow.
5. Begin implementation in small, accepted phases, starting with the foundation supported by the repository audit.
6. Keep the Earth-limb discrepancy recorded as an open scientific-validation item. It must not block unrelated application work, and its current result must not be presented as validated.

---

## 15. Definition of Done

LunaSight is ready for its intended judging demonstration when:

- The implemented scope matches the reconciled project requirements.
- Site and date inputs are source-backed and validated.
- Sun and Earth outputs include units, epochs, coordinate semantics, and provenance.
- Significant derived calculations have reproducible tests and documented tolerances.
- Comparison criteria are transparent and do not overstate operational certainty.
- Network failures and documented offline scenarios are handled gracefully.
- The Android release build has been installed and smoke-tested.
- The demo can be reproduced from documented inputs.
- Known limitations and the future competition-API integration plan are documented honestly.

---

**End of working baseline.**

This roadmap is a planning artifact. It is not evidence that unverified implementation phases have been completed.