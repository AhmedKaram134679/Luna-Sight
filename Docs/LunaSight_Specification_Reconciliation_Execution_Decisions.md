# LunaSight --- Specification Reconciliation & Execution Decisions

**Project:** LunaSight\
**Challenge:** NASA Space Apps Challenge 2026 --- CLPS Lunar Mission
Browser\
**Target:** Android first; Flutter and Dart\
**Status:** Working baseline --- owner review required\
**Purpose:** Reconcile existing specifications without restarting
completed research, embedding unapproved scientific assumptions, or
blocking unrelated application foundations.

## 1. Source documents

This document coordinates, but does not replace, the following existing
documents:

1.  `Docs/LunaSight — Challenge Requirements & Technical Specification.md`
2.  `Docs/LunaSight — Scientific Reference Specification.md`
3.  `Docs/LunaSight — Scientific Data Contract & Validation Specification.md`
4.  `Docs/LunaSight — Scientific Calculation Contract & Implementation Plan.md`
5.  `Docs/LunaSight — Implementation Roadmap & Current Project Status.md`

### Decision labels

-   **CONFIRMED:** Established in project context and not contradicted
    by a more specific decision.
-   **OBSERVED:** Supported by a recorded test or repository inspection;
    do not generalize beyond what was tested.
-   **PROPOSED:** Recommended design awaiting owner approval when it
    changes scope or product commitments.
-   **OPEN:** Needs evidence, reconciliation, or an explicit decision.
-   **VALIDATION-PENDING:** An output or method exists but has not
    passed its acceptance tests.
-   **DEFERRED:** Excluded until a stated prerequisite is met.

The presence of a requirement in a document does not prove that it has
been implemented or scientifically validated.

## 2. Reconciled project baseline

  -----------------------------------------------------------------------
  Area                    Working baseline        Status
  ----------------------- ----------------------- -----------------------
  Project/challenge       LunaSight / CLPS Lunar  CONFIRMED
                          Mission Browser         

  Platform/stack          Android first; Flutter  CONFIRMED
                          and Dart                

  Main workflow           Compare supported lunar CONFIRMED
                          sites and times         

  Solar analysis          Sun geometry relative   CONFIRMED
                          to the local lunar      
                          horizon                 

  Earth analysis          Earth geometry and      CONFIRMED
                          potential geometric     
                          visibility              

  Candidate ephemeris     NASA/JPL Horizons       PROPOSED pending
  provider                                        capability audit

  Independent comparison  SPICE-based             CONFIRMED approach;
                          calculations and        results need individual
                          compatible references   validation

  Offline behavior        Local use only of       PROPOSED pending scope
                          packaged/cached         confirmation
                          supported data and      
                          results                 

  Architecture            Separate presentation,  PROPOSED
                          domain, scientific      
                          calculation, and data   
                          access                  

  Terrain-aware           Only after suitable     DEFERRED
  visibility              data and model          
                          validation              

  Electrical energy       Not implied by solar    OUT OF SCOPE without an
  prediction              elevation alone         approved power-system
                                                  model

  Guaranteed              Not implied by          OUT OF SCOPE without
  communications          geometric Earth         additional
                          visibility              link/operational
                                                  analysis
  -----------------------------------------------------------------------

Every displayed scientific quantity must retain its provenance,
epoch/time semantics, coordinate frame, units, model/correction
settings, data coverage, validation status, assumptions, and limitations
as applicable.

## 3. Phase-order reconciliation

The documents use different stage names (including Stage A/B and phases
0--8). For execution tracking, use the operational sequence below while
retaining original stage names when referencing the source documents.

  --------------------------------------------------------------------------
  Operational phase          Purpose                 Exit evidence
  -------------------------- ----------------------- -----------------------
  0 ---                      Establish actual        Audit report, source
  Repository/specification   repository state and    map, open-decision
  audit                      reconcile requirements  register

  1 --- Provider capability  Check required          Data registry,
  audit                      quantities and their    reproducible requests,
                             semantics               capability findings

  2 --- Scientific           Define models, events,  Versioned cases and
  contracts/validation       reference cases,        test methodology
  harness                    acceptance criteria     

  3 --- Application          Establish Flutter       Build, baseline tests,
  foundation                 structure and shared    analysis
                             infrastructure          

  4 --- Site catalogue/data  Add source-backed       Contract/provenance
  layer                      sites, coverage,        tests
                             caching, errors         

  5 --- Solar/Earth analysis Integrate only          Feature-specific tests
                             calculations with       and correct status
                             explicit status         display

  6 --- Comparison           Compare consistent      Reproducible,
                             metrics across          interpretable
                             supported sites/times   comparisons

  7 --- Reliability/polish   Offline behavior,       Relevant acceptance
                             accessibility,          tests
                             performance, UI clarity 

  8 --- Final                Verify release build    Device/build evidence
  validation/demo            and rehearse demo       and demo checklist
  --------------------------------------------------------------------------

**Rule:** Application foundations and UI scaffolding may proceed in
parallel with scientific validation if they do not embed unapproved
assumptions. Scientific outputs must not be described as validated
before their applicable acceptance criteria pass.

## 4. Decision register

### DEC-01 --- Final data provider

**State:** Horizons is the leading candidate, not an approved universal
provider. A successful request proves connectivity for that request
only.

**Needed:** Audit each required quantity, observer/target semantics,
frames, time scales, corrections, angular-size definitions, coverage,
limits, availability, usage terms, and reproducibility. Compare against
compatible independent references.

**Until resolved:** Keep provider access replaceable; do not claim that
every required quantity has been validated.

### DEC-02 --- Earth visibility event definition

**State:** Earth-center elevation, a spherical angular-disk
approximation, a projected ellipsoidal limb, and terrain obstruction are
different concepts.

**Needed:** Specify the event (which limb and crossing direction),
observer/local horizon, frame, epoch/time scale, shape model,
apparent/geometric corrections, independent reference, and numerical
acceptance criteria.

**Until resolved:** Keep event calculation separate from presentation.
Unvalidated event times remain validation-pending. Terrain obstruction
is a separate model.

### DEC-03 --- Offline scope

**State:** The Data Contract treats local availability of core data as a
decision; the Roadmap calls offline-first behavior proposed pending
reconciliation.

**Working policy:** Offline use covers only packaged/cached data and
results with known scope and provenance. Missing local coverage must be
explicit; never fabricate a result.

**Needed:** Approve the initial offline catalogue, time coverage,
package-size target, cache/update policy, and whether local computation
or precomputed results suffice.

**Until resolved:** Offline-aware contracts/states are allowed; a full
local ephemeris engine or large kernel package is not assumed.

### DEC-04 --- Initial site catalogue

**State:** The reference site is the initial validation anchor; the Data
Contract proposes adding two or three further sites.

**Needed:** Select sites only with documented coordinates, conventions,
elevation/reference, provenance, and status. Test sites must not be
described as officially endorsed CLPS landing sites without an
authoritative source.

### DEC-05 --- Numerical acceptance tolerances

**State:** Existing documents contain provisional targets, including a
candidate `0.01°` comparison target for selected center-elevation cases
and timing targets for compatible event references. These are not
universal guarantees.

**Needed:** Approve tolerances per observable only after defining the
reference configuration, model, observable, and expected uncertainty.

Distinguish solver precision, source-data uncertainty, model agreement,
observed reference residual, and precision displayed to users. A root
finder converging to a fraction of a second does not establish
equivalent physical accuracy.

### DEC-06 --- Supported time range

**State:** The first release needs explicit supported temporal coverage;
the validated interval is not frozen in this reconciliation baseline.

**Needed:** Publish a range supported by source coverage, reproducible
calculations, and acceptance tests. Requests outside it must be rejected
or clearly labelled.

### DEC-07 --- UI work before scientific closure

**Allowed:** Flutter structure, navigation shell, generic models,
provenance components, loading/error/unavailable/out-of-coverage states,
accessibility foundations, and testable interfaces.

**Conditional:** Site selection, time controls, and result panels may be
built against approved contracts. Fixtures must be identified as
test/reference data, not production calculations.

**Blocked:** Presenting disputed calculations as approved results or
freezing UX around an unapproved event definition.

### DEC-08 --- Competition API

The Roadmap records that the competition API was not released at the
time of that document. Recheck its current availability and documented
capabilities before final provider selection; do not assume the old
status remains current.

### DEC-09 --- Coordinate/time conventions

The reference experiment records lunar longitude `200° E` and latitude
`−88.45°`; a signed-longitude representation such as `−160°` may be
equivalent under a compatible convention, but this must be documented,
not assumed.

**Needed:** Canonical longitude convention, latitude type, body-fixed
frame, local horizon axes, elevation reference, time-scale conversions,
and correction settings. Preserve raw historical inputs and settings; do
not silently rewrite coordinates or mix UTC, TT, and TDB.

## 5. Existing experiments and scientific status

### Horizons connectivity

The Roadmap records HTTP 200 and successful retrieval for a tested
Horizons request. This is an observed connectivity result, not proof
that all required quantities are suitable. Preserve the exact request,
settings, response, and retrieval date; do not repeat the same
connectivity test without a specific reason.

### Earth observer-table experiment

The Roadmap records an Earth (399) observer-table experiment from a
lunar location near longitude `200° E`, latitude `−88.45°`,
approximately zero altitude, with Horizons/DE441 and an airless
configuration. Output includes center elevation, equatorial angular
diameter, apparent range/range-rate, and one-way light time. These
values belong to that request and epoch; they are not universal
constants.

Preserve this as a reference observation with exact inputs. It is not,
by itself, a validated limb-crossing result.

### SPICE Earth-limb experiment

The Roadmap records a preliminary ellipsoidal upper-limb crossing near
`2026-11-02 14:12:47.395 UTC`, and notes that it is not independently
validated or release-approved. A kernel-set discrepancy was recorded:
state-vector data labelled v0071 versus angular-size data labelled
v0070.

Preserve the original scripts, kernels/versions, settings, logs, and
outputs. Reproduce the result before changing it; align frames,
epoch/time scales, orientation data, corrections, and event definition;
compare like-for-like quantities; record residuals and acceptance
criteria before promoting the result.

### Spherical disk versus projected ellipsoid

`Earth center elevation + (equatorial angular diameter / 7200)` is a
spherical angular-radius approximation for the disk edge under the
relevant convention. It is not generally equivalent to a projected
ellipsoidal limb. Compare the methods only after aligning observer
geometry, time, frame, apparent/geometric convention, and shape
assumptions. Terrain obstruction is separate.

### Required result states

Every result must expose an appropriate status, at minimum:

-   **Validated:** passed acceptance tests for this observable and
    supported domain.
-   **Preliminary:** calculated, but validation is incomplete.
-   **Approximation:** intentionally simplified model with disclosed
    limitations.
-   **Unavailable:** no supported data/result for this request.
-   **Out of coverage:** request outside supported site/time/data
    coverage.
-   **Error:** retrieval or calculation failed.

Different observables may have different statuses; one global validation
flag is insufficient.

## 6. Work allowed before scientific closure

### Allowed

-   Inspect and document the actual repository tree, Git state, tests,
    and dependencies.
-   Preserve existing files, experiments, logs, and kernels.
-   Define generic site, epoch, provenance, coverage, and result-status
    models after field semantics are agreed.
-   Separate presentation, domain, scientific calculation, and data
    access.
-   Add generic error/loading/coverage states and contract tests.
-   Build a Flutter shell that does not embed unvalidated numerical
    outputs.
-   Prepare a data registry and reproducible validation-harness layout.
-   Test deterministic non-scientific transformations and invariants.

### Conditional

-   Site UI after the site model and catalogue contract are approved.
-   Time controls after supported range/time semantics are explicit.
-   Result panels against approved contracts and clearly labelled test
    fixtures.
-   Caching after identity, provenance, freshness, and invalidation
    rules are defined.

### Blocked until evidence exists

-   Declaring a final provider for all features.
-   Promoting the disputed Earth-limb crossing to validated.
-   Claiming terrain-aware visibility without suitable elevation data
    and validated geometry.
-   Predicting electrical energy without an approved power-system model.
-   Claiming communication availability without suitable
    link/operational analysis.
-   Claiming universal site/date support without coverage evidence.

## 7. Minimum data registry

For each source/product, record: stable ID/name; producing organization
and authoritative location; product/API/kernel name and version;
retrieval/package date; temporal/spatial coverage; target/observer
semantics; frame/time scale; units and angle conventions;
model/correction settings; usage conditions; integrity metadata where
applicable; intended use; limitations; validation cases/status; and
maintenance responsibility.

Each site record should contain stable ID, display name,
latitude/longitude with explicit conventions, elevation/reference,
body-fixed frame, coordinate provenance, validation status, and whether
it is a test candidate or has authoritative mission relevance.

Do not invent missing fields. Mark them open and identify the evidence
needed.

## 8. Validation workflow

For every observable/event:

1.  Define it mathematically and operationally.
2.  Freeze site, epoch, frame, time-scale, model, and correction
    semantics.
3.  Record source/product and version.
4.  Reproduce the existing procedure before modifying it.
5.  Obtain an independent reference with compatible semantics.
6.  Record residuals and distinguish model mismatch from numerical
    error.
7.  Apply a documented, observable-specific tolerance.
8.  State coverage and limits of extrapolation.
9.  Assign validation status.
10. Preserve the case as an automated test or controlled fixture with
    provenance.
11. Ensure UI labels and limitations match the status.
12. Record the evidence and approval for any status transition.

Do not choose a tolerance solely because it makes the current output
pass.

## 9. Coding-agent rules

Any coding agent must:

1.  Read this document and relevant source documents.
2.  Inspect the actual repository, branch, working tree, architecture,
    tests, and dependencies.
3.  Report the verified baseline before changing files.
4.  Preserve existing work unless a specific justified change is
    approved.
5.  Implement only the approved phase; avoid unrelated changes.
6.  Deliver complete implementations and relevant tests; no TODO-only
    stubs or fake science.
7.  Keep calculations behind explicit contracts; do not couple UI
    directly to a provider.
8.  Preserve provenance and validation status through all layers.
9.  Avoid major dependencies, native libraries, backends, paid services,
    or large data packages without demonstrated need and approval when
    scope/cost changes.
10. Run available formatter, analyzer, tests, and build checks; report
    exact commands/results.
11. Separate facts, observations, proposals, and open issues in the
    report.
12. Update docs when decisions/contracts change.

### Red flags --- prohibited without explicit approval

-   Wholesale rewrites of app or docs.
-   Deleting previous experiments, outputs, or kernels for convenience.
-   Changing scientific definitions merely to force agreement.
-   Treating Horizons and SPICE settings as equivalent without checking
    semantics.
-   Treating HTTP success as scientific validation.
-   Hiding failures or fabricating/defaulting scientific values.
-   Silently changing coordinates, units, frames, time scales, or event
    definitions.
-   Claiming terrain, power, communications, or mission-safety
    capability without implementation and validation.
-   Adding paid infrastructure/dependencies without demonstrated need
    and approval.
-   Marking a feature complete when its acceptance criteria have not
    passed.

## 10. Next-phase outputs

### Phase 0 closure

-   [ ] Repository inventory and actual Git/branch state.
-   [ ] Source-document map and reconciliation register.
-   [ ] Confirmed/proposed/open decisions.
-   [ ] Inventory of existing experiments and artifacts.
-   [ ] Explicit list of files changed, if any.
-   [ ] Owner review of decisions that change product scope.

### Phase 1 provider audit

-   [ ] Data registry, with unknown fields explicitly marked.
-   [ ] Capability matrix for Sun/Earth position, angular size/shape,
    and time-dependent events.
-   [ ] Exact inputs/settings for the successful Horizons retrieval.
-   [ ] Inventory of SPICE scripts, kernel versions, and reference
    outputs actually present and reproducible.
-   [ ] Evidence gaps for required calculations.
-   [ ] Provider recommendation including limitations, offline
    implications, and cost.
-   [ ] No result promoted to validated without passing its own
    acceptance tests.

### Application-foundation entry criteria

Foundation work may begin once Phase 0 has established the actual
repository baseline and generic domain contracts are clear enough. It
does **not** require closure of the disputed Earth-limb event, provided
the implementation does not embed that event as approved.

## 11. Change control

For each changed decision: identify its DEC ID; state old and proposed
decisions; explain the reason; cite new evidence or owner instruction;
list affected documents/contracts/tests/code; define regression actions;
preserve previous outputs/provenance; and update this register and
relevant source documents.

Do not silently change a scientific decision in one document while
leaving conflicting instructions in another.

## 12. Owner-review checklist

These product-level decisions require explicit review before becoming
final commitments:

-   [ ] Initial offline scope and packaged-data expectations.
-   [ ] Earth event definitions exposed in the first release.
-   [ ] Initial candidate-site catalogue and source-backed coordinates.
-   [ ] Supported date/time interval.
-   [ ] Acceptance criteria for each scientific observable.
-   [ ] Final provider/retrieval strategy after capability audit.
-   [ ] Whether terrain analysis belongs in the first release or a later
    validated phase.

Non-conflicting foundation work can proceed without waiting for every
item, subject to the rules above.

## 13. Current conclusion

The documents provide a coherent direction but do not yet form one fully
reconciled implementation contract. The main scientific issue is the
definition and independent validation of Earth-limb events. Separate
product decisions remain open for offline coverage, provider selection,
candidate-site scope, and supported time coverage.

The next step is to preserve existing evidence, close the
repository/specification baseline, perform only the missing
provider-capability checks, and start application foundations behind
stable contracts. This avoids both restarting completed work and
presenting unresolved science as established fact.

**Document status:** Working baseline pending owner review.\
**This document does not certify any scientific calculation or claim
that the application is implemented.**
