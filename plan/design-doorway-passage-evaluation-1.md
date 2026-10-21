---
goal: Prepare an evidence-gated doorway passage prototype without changing production counting
version: '1.0'
date_created: '2026-10-21'
last_updated: '2026-10-21'
owner: Daniel Simpson
status: 'On Hold'
tags: [design, counting, doorway, evaluation, prototype]
---

# Introduction

![Status: On Hold](https://img.shields.io/badge/status-On%20Hold-orange)

Prepare a single-doorway experiment comparing observed outside/doorway/inside journeys with existing tripwire counting. The design interview established event semantics and evaluation principles, but did not authorize counter implementation or settle numerical settings. This plan makes evidence collection, approval, and implementation handoff explicit prerequisites. It does not authorize production replacement.

The plan is On Hold because additional suitable footage and approved benchmark/prototype settings are absent. Documentation and evidence inventory tasks may proceed; prototype coding, tuning, and acceptance scoring may not. Task checkboxes describe work performed under this plan, not earlier conversation work.

## 1. Requirements & Constraints

- **REQ-001**: An entry is actual passage from outside to inside one store through a doorway. An exit is the reverse. An approach followed by an outside turnback produces neither event. Actual entry followed by immediate exit produces one of each.
- **REQ-002**: A doorway is one physical opening into one store. A store may have multiple doorways. A shared arcade entrance must not be labeled as entry to an individual tenant.
- **REQ-003**: The initial prototype scope is one manually annotated doorway with local outside, doorway, and inside observation zones. Automatic door detection and whole-facade approach regions are excluded.
- **REQ-004**: Require an observed outside -> doorway -> inside journey for entry and the reverse for exit, under one continuous track identity without missing observations during the candidate passage. Do not interpolate an unobserved doorway visit or stitch different IDs.
- **REQ-005**: Directional motion is supporting evidence only. No minimum walking speed may be required for a confirmed passage. Pausing in the doorway does not itself create an event.
- **REQ-006**: Report possible passages lacking sufficient evidence as unresolved, separately from confirmed events. Disappearance, appearance, or inward motion alone must not produce a confirmed event.
- **REQ-007**: Use independently reviewed human passage labels, not candidate predictions, to establish truth. MOT17 pedestrian boxes and identities are not store-passage labels.
- **REQ-008**: Evaluate manually checked foot-point trajectories separately from the unchanged detector/tracker pipeline. Only the end-to-end comparison can support replacement.
- **REQ-009**: Use one-to-one event matching by doorway and direction against human-labeled traversal intervals in video time. Duplicates are errors; wrong direction or wrong doorway cannot match the correct event.
- **REQ-010**: Report entry precision, entry recall, exit precision, and exit recall separately. A predicted unresolved case corresponding to a confirmed passage is a miss. Report human-uncertain passages separately; the exact treatment of predictions overlapping those intervals requires approval under DEC-004.
- **REQ-011**: The replacement gate requires no regression in any of the four end-to-end measures and a meaningful improvement in at least one. Combined scores and total-count agreement cannot override this rule. The numerical margin and evidence requirements must be approved before held-out scoring.
- **REQ-012**: Separate development footage from held-out footage. Freeze geometry, noise handling, motion estimation, and matching rules before scoring held-out footage.
- **CON-001**: `data/birdseye_street.mp4` is exploratory material only. Its observed metadata is 3840x2160, 30000/1001 FPS, 869 frames, and approximately 29.01 seconds. One-second Studio F samples do not establish sufficient inside visibility or bidirectional event coverage; they do not establish that no passages occur.
- **CON-002**: Require additional doorway-visible footage before tuning a passage counter or claiming improved accuracy. If suitable footage is absent, record a blocked gate and stop dependent work. Do not weaken the observable-passage requirement.
- **CON-003**: Preserve `src/counter.py`, `src/storefront.py`, `src/calibrate.py`, `src/main.py`, `src/detector.py`, `src/tracker.py`, existing configuration, model weights, CLI behavior, and event formats during this plan. Existing named line endpoints are not approved doorway polygons.
- **CON-004**: No numerical defaults, sample-size targets, matching tolerances, motion windows, zone-boundary rules, or migration behavior may be inferred from this document. Their absence is a blocker, not permission to choose.
- **SEC-001**: Inspect authorized footage locally. Do not upload frames, video, identities, or trajectories to third-party services. Do not commit footage, extracted frames, or personal identifiers as part of this plan.
- **PAT-001**: Keep domain definitions in `GLOSSARY.md`, architectural trade-offs in `docs/adr/0001-evaluate-doorway-passage-before-replacing-tripwires.md`, and executable task details in this plan or its approved successor.
- **GUD-001**: Do not overwrite unrelated untracked files or change the earlier pipeline plan. No implementation is implied by creation or approval of this planning document.

### Gate protocol

Each gate has exactly one result: `blocked` or `passed`. An absent, unapproved, or incomplete prerequisite produces `blocked`; it never receives a guessed value. Record gate results and their evidence in this plan when execution begins. A gate remains blocked until every listed condition is satisfied. No tasks are complete at plan creation.

| Gate | Current result | Conditions required for passed |
|------|----------------|--------------------------------|
| GATE-001 | blocked | Additional authorized footage is locally available; review identifies one physical doorway and observable outside and inside zones; candidate event intervals in both directions and coverage limitations are recorded; development and held-out source intervals are identified without overlap. |
| GATE-002 | blocked | GATE-001 passed; DEC-001 through DEC-006 have explicit user-approved values and rules recorded before tuning or held-out scoring; shared understanding and permission to create the prototype implementation specification are recorded. |
| GATE-003 | blocked | GATE-002 passed; an executable successor plan contains exact schemas, functions, commands, task dependencies, tests, and acceptance rules; user approval explicitly authorizes isolated prototype implementation. |

### Required decision inputs

These are known unresolved decisions, not placeholders for an executor to fill autonomously. No decision is approved by this plan.

| Decision | Required approved input | Missing-input action |
|----------|-------------------------|----------------------|
| DEC-001 | Source footage identifiers; selected doorway/store; visible-zone evidence; development/held-out intervals; minimum confirmed entry and exit counts; negative-scenario coverage; criterion for sufficient evidence. | Keep GATE-002 blocked. |
| DEC-002 | Zone polygon representation and coordinates; overlap/boundary handling; foot-point stability rule; treatment of track starts/ends, static filtering, zone departure, long pauses, and repeated round trips; exact rearming and unresolved-case lifecycle. | Keep GATE-002 blocked. |
| DEC-003 | Directional-motion estimator, coordinate basis, time units, window, noise tolerance, minimum observation requirements, and precise non-counting role. Speed must not veto an otherwise confirmed journey. | Keep GATE-002 blocked. |
| DEC-004 | Annotation schema and independent review procedure; video timestamp/frame convention; event timestamp rule; any matching tolerance; deterministic assignment/tie-breaking; treatment of predictions overlapping human-uncertain intervals. | Keep GATE-002 blocked. |
| DEC-005 | Numerical meaningful-improvement margin; sample sufficiency and statistical evidence rule; zero-denominator metric policy; exact four-metric comparison and insufficient-evidence outcome. | Keep GATE-002 blocked. |
| DEC-006 | Isolated prototype module/runner interfaces; geometry and observation schemas; artifact retention; output/report schemas; frozen baseline configuration; approved execution commands and implementation scope. | Keep GATE-002 blocked. |

## 2. Implementation Steps

### Implementation Phase 1

- **GOAL-001**: Record evidence readiness without changing counting behavior.
- Prerequisites: none. TASK-001 and TASK-002 are independent. TASK-003 depends on TASK-001 and TASK-002.
- Completion criteria: evidence and limitations are recorded; GATE-001 has a justified result. A blocked result completes the inventory task but does not unblock Phase 2.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | In this plan, record the baseline source revision and dirty-worktree state for `src/counter.py:106` (`TripwireCounter`), `src/storefront.py:54` (`StorefrontCounter`), `src/tracker.py:35` (`TrackedObject`), and `src/main.py` (the `tracker.update` / `counter.update` processing loop). Verify symbol locations before recording; line numbers are navigation hints. Record that `StorefrontCounter.__init__` enables `door_mode=True`, that `TrackedObject.foot` supplies bottom-center coordinates, and that production `CountEvent.timestamp` is processing UTC rather than benchmark video time. Do not edit these functions. | | |
| TASK-002 | Inventory additional footage under `data` and locally supplied paths explicitly authorized by the user; record exact paths, file hashes, dimensions, frame-rate/timestamp information, duration, and usage permission in this plan. Inspect candidate passages locally and record source time intervals supporting doorway identity, visible outside/inside, both passage directions, and negative scenarios. Do not designate the existing birdseye clip or MOT annotations as acceptance data. If no qualifying footage exists, record GATE-001 as blocked with the missing conditions; do not fabricate labels. Target functions: none; evidence-only task. | | |
| TASK-003 | After TASK-001 and TASK-002, update the GATE-001 row in this plan. Set passed only when all GATE-001 conditions are documented; otherwise retain blocked and stop dependent tasks. Keep `GLOSSARY.md` definitions and the ADR consistent with verified facts; do not assert that tripwires have been rejected. Target functions: none; documentation-only task. | | |

### Implementation Phase 2

- **GOAL-002**: Validate the approved experiment contract before implementation.
- Prerequisites: TASK-003 complete and GATE-001 passed. TASK-004 must complete before TASK-005.
- Completion criteria: all DEC inputs are explicitly approved and GATE-002 passes; otherwise execution stops with a blocked result.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-004 | Validate the available decision record against DEC-001 through DEC-006 in this plan. Record approved values, their approval source, and unmet inputs in this plan. If any input is missing, retain GATE-002 as blocked and return the corresponding DEC identifiers to the user; do not select defaults or begin annotation/tuning under an invented policy. Design decisions remain outside autonomous execution until the user supplies approval. Target functions: none; contract-validation task. | | |
| TASK-005 | After TASK-004 passes, record the complete frozen contract in this plan and update the existing ADR only for architectural decisions actually approved. Set GATE-002 passed only when all decision inputs and shared-understanding approval are present. Keep the plan On Hold while GATE-003 remains blocked. Target functions: none; documentation-only task. | | |

### Implementation Phase 3

- **GOAL-003**: Produce the deterministic implementation handoff for an isolated experiment.
- Prerequisites: TASK-005 complete and GATE-002 passed. TASK-006 precedes TASK-007.
- Completion criteria: the successor plan is self-contained, contains no unresolved implementation decisions, and GATE-003 records whether explicit implementation authorization exists.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-006 | Create `plan/feature-doorway-passage-prototype-1.md` from the approved DEC-001 through DEC-006 contract. Specify exact new file paths, function signatures, geometry/observation/event/report schemas, baseline adapters, deterministic matching algorithm, error behavior, commands, and dependency edges. Include separate checked-trajectory and end-to-end runs, development-only tuning, frozen held-out scoring, all TEST requirements below, and a no-production-change constraint. Reuse `TrackedObject.foot`, `CentroidTracker.update`, and `TripwireCounter.update` through isolated adapters rather than changing production APIs. Do not implement those adapters or the candidate counter in this task. | | |
| TASK-007 | Validate `plan/feature-doorway-passage-prototype-1.md` against the approved contract and mandatory plan template. Record GATE-003 passed only after the user explicitly authorizes that isolated implementation. With missing authorization, retain blocked and stop. Do not equate a passing future experiment with permission to replace production counting; production migration requires a separate decision and plan. Target functions: none; plan-validation task. | | |

## 3. Alternatives

- **ALT-001**: Immediately replace tripwires with polygon-plus-velocity heuristics. Not selected because inward movement and disappearance do not establish actual passage.
- **ALT-002**: Count inferred entries and observed entries identically. Rejected for the initial experiment; unresolved cases must remain distinguishable.
- **ALT-003**: Use MOT17-09 annotations as the store-counting benchmark. Rejected because pedestrian trajectories do not label store passages.
- **ALT-004**: Automatically detect doors, stitch identities, bridge missing observations, or upgrade tracking in the first experiment. Excluded to isolate the doorway counting model and avoid hiding tracking changes.
- **ALT-005**: Choose thresholds and sample-size requirements now. Rejected because the conversation deliberately deferred them until suitable footage exists.
- **ALT-006**: Score net counts only or tune on all available footage. Rejected because cancellation of errors and test-set tuning can hide regressions.

## 4. Dependencies

- **DEP-001**: Additional locally authorized doorway-visible footage and independently reviewed passage labels; currently unavailable as an approved benchmark.
- **DEP-002**: Explicit approval of DEC-001 through DEC-006. Their absence blocks the successor implementation plan.
- **DEP-003**: Existing `requirements.txt` supplies OpenCV, NumPy, Ultralytics, pytest, and pytest-cov for a later prototype. No dependency installation or manifest change is required for this documentation plan.
- **DEP-004**: Preserve a reproducible baseline including model/configuration hashes, source revision, local changes, and original door-mode behavior. Both counters must consume the same observations in the end-to-end comparison.
- **DEP-005**: Task graph: TASK-001 and TASK-002 -> TASK-003 -> GATE-001 -> TASK-004 -> TASK-005 -> GATE-002 -> TASK-006 -> TASK-007 -> GATE-003. Arrow means prerequisite; gate failure stops downstream work.

## 5. Files

- **FILE-001**: `plan/design-doorway-passage-evaluation-1.md`: this executable readiness and approval plan; record evidence, decisions, and gate outcomes here.
- **FILE-002**: `GLOSSARY.md`: existing domain vocabulary; update only when further terms are explicitly resolved.
- **FILE-003**: `docs/adr/0001-evaluate-doorway-passage-before-replacing-tripwires.md`: existing evidence-gated architecture decision; preserve its explicit non-authorization of replacement.
- **FILE-004**: `plan/feature-doorway-passage-prototype-1.md`: create only in TASK-006 after GATE-002 passes; do not create speculative modules or tests before their interfaces are approved.
- **FILE-005**: `src/counter.py`, `src/storefront.py`, `src/calibrate.py`, `src/main.py`, `src/tracker.py`, `src/detector.py`, `requirements.txt`, `yolov8n.pt`, and `data/birdseye_street.storefronts.json`: read-only baseline references under this plan.
- **FILE-006**: `tests/test_counter.py`, `tests/test_storefront.py`, `tests/test_tracker.py`, and `tests/conftest.py`: existing behavioral and fixture references for the successor plan; do not alter them under this documentation plan.
- **FILE-007**: `data/birdseye_street.mp4` and `data/MOT17-09-DPM/gt/gt.txt`: exploratory video and tracking truth respectively, not accepted passage benchmark inputs.
- **FILE-008**: `plan/feature-pipeline-build-1.md`: historical broader pipeline plan; leave unchanged and do not import its unrelated accuracy targets into this experiment.

## 6. Testing

- **TEST-001**: Validate this document's front matter contains goal, version, date_created, last_updated, owner, status, and tags; status is On Hold with an orange badge; all eight mandatory section headers and task-table columns exist; task identifiers are unique; every prerequisite names an existing task/gate.
- **TEST-002**: Validate gate logic: absent footage blocks GATE-001; any missing DEC approval blocks GATE-002; absent implementation authorization blocks GATE-003. No failure path creates success-shaped metrics or starts dependent work.
- **TEST-003**: In the successor plan, require exact synthetic outcomes: outside/doorway/inside -> one entry; reverse -> one exit; outside/doorway/outside -> zero events; pause -> no event until passage completes; actual round trip -> one event in each direction; repeated complete journeys remain countable.
- **TEST-004**: In the successor plan, test boundary jitter, slow passage, static tracks, partial tracks at clip boundaries, skipped doorway observations, missing detections, changed IDs, and appearance/disappearance. No minimum-speed veto, ID stitching, or unobserved crossing may create a confirmed event. Boundary and rearming expected outputs must be derived from approved DEC-002, not guessed.
- **TEST-005**: In the successor plan, test exact one-to-one matching, duplicate penalties, wrong direction/doorway, video-time conventions, matching boundaries, human uncertainty, and empty prediction/truth sets under approved DEC-004 and DEC-005. An unresolved prediction on a confirmed passage must not increase precision by erasing a false negative.
- **TEST-006**: In the successor plan, test four-metric acceptance: any regression fails regardless of total-count improvement; no meaningful gain fails; inadequate event coverage yields insufficient evidence; undefined metrics follow approved DEC-005 and cannot silently become perfect scores.
- **TEST-007**: Require both checked-trajectory and unchanged end-to-end results, matched observation inputs for both counters, recorded frozen settings, and no tuning from held-out outcomes. Report tracker-caused misses separately without removing them from end-to-end recall.
- **TEST-008**: No runtime tests are needed for this documentation-only plan. After future prototype changes, run the new focused tests plus existing counter/storefront/tracker tests using the configured environment and repository test runner; exact new paths and commands belong in TASK-006 after interfaces are approved.

## 7. Risks & Assumptions

- **RISK-001**: The camera may not expose an observable inside zone. More elaborate motion rules cannot recover evidence that the camera never records.
- **RISK-002**: Greedy centroid identity assignment and conservative no-gap rules may prevent adequate recall. Measure this failure; do not silently relax approved requirements.
- **RISK-003**: Excluding human-uncertain cases without a frozen matching policy can bias evaluation. DEC-004 must settle attribution before scoring.
- **RISK-004**: One short or low-traffic clip cannot establish non-regression reliably. DEC-001 and DEC-005 must define evidence sufficiency before acceptance.
- **RISK-005**: Frame-based thresholds and processing UTC can produce misleading comparisons across rates or machine speeds. Use the approved video-time convention and freeze all units.
- **RISK-006**: Geometry changes, static-object filtering, detection settings, or model changes can confound the comparison. Keep production behavior and end-to-end observation inputs fixed.
- **ASSUMPTION-001**: The current request authorizes creation of this plan only; it does not override the agreed evidence gate or authorize prototype/production code.
- **ASSUMPTION-002**: Suitable footage and approvals may arrive later. Until then, retaining an explicit blocked status is the correct execution outcome.
- **ASSUMPTION-003**: No decision has been made to remove tripwires. A successful prototype would support a later migration discussion, not automatically trigger migration.

## 8. Related Specifications / Further Reading

- [Domain glossary](../GLOSSARY.md)
- [Evidence-gated doorway decision](../docs/adr/0001-evaluate-doorway-passage-before-replacing-tripwires.md)
- [Existing pipeline plan](./feature-pipeline-build-1.md)
- [Tripwire counter and events](../src/counter.py)
- [Storefront line configuration and baseline door mode](../src/storefront.py)
- [Tracker observations and foot points](../src/tracker.py)
- [Production processing loop](../src/main.py)
- [Existing counter tests](../tests/test_counter.py)
- [Existing storefront tests](../tests/test_storefront.py)
