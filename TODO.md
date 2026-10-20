# TODO

Progress tracker for the Store Traffic Counter pipeline. See [plan/feature-pipeline-build-1.md](plan/feature-pipeline-build-1.md) for full task details.

**Legend:** `[ ]` Not started · `[~]` In progress · `[x]` Completed · `[-]` Deferred (out of scope for this PoC)

> **Direction (2026-10-20):** Portfolio PoC, depth over breadth. The system counts generic **Persons** crossing a tripwire (not customers — see [GLOSSARY.md](GLOSSARY.md) and [docs/adr/0001-count-persons-not-customers.md](docs/adr/0001-count-persons-not-customers.md)). Goal: a sourced doorway hero clip exported as MP4 + README GIF, defended by a hand-counted accuracy figure. In scope: **Phase 7** (orchestration) + a **thin slice of Phase 6** (summary JSON only). Deferred: Docker (8), full coverage/CI (9), extended docs (10).

---

## Phase 1: Core Infrastructure & Video Input Handling

- [x] TASK-001 — Create project directory structure (src/, models/, data/, output/, tests/)
- [x] TASK-002 — Initialize virtual environment and requirements.txt (opencv-python, numpy)
- [x] TASK-003 — Create main.py entry point with argparse CLI interface
- [x] TASK-004 — Implement video_loader.py with VideoProcessor class (MP4, AVI, MOV)
- [x] TASK-005 — Add frame extraction with error handling for corrupted files
- [x] TASK-006 — Implement frame validation and logging
- [x] TASK-098 — Add image-sequence input support (MOT17 `%06d.jpg`, parse seqinfo.ini)
- [x] TASK-007 — Create config.py with constants and defaults
- [x] TASK-008 — Write unit tests in tests/test_video_loader.py
- [x] TASK-009 — Add debug logging with --verbose flag

## Phase 2: Person Detection Module

- [x] TASK-010 — Implement detector.py with abstract Detector base class
- [x] TASK-011 — Create YOLODetector subclass (yolov8n / yolov8s)
- [x] TASK-012 — Create OpenCVDetector subclass (HOG + SVM pedestrian detector)
- [x] TASK-013 — Implement confidence threshold filtering
- [x] TASK-014 — Standardize return format {box, confidence, class_label}
- [x] TASK-015 — Add GPU/CPU device selection (--device flag)
- [x] TASK-016 — Implement YOLO model weight auto-download
- [x] TASK-017 — Write unit tests in tests/test_detector.py
- [x] TASK-018 — Add inference timing instrumentation

## Phase 3: Multi-Object Tracking Module

- [x] TASK-019 — Implement tracker.py with CentroidTracker class
- [x] TASK-020 — Define centroid calculation from bounding box
- [x] TASK-021 — Implement Euclidean distance metric between centroids
- [x] TASK-022 — Add configurable max_distance threshold (default 50px)
- [x] TASK-023 — Implement ID persistence and new-ID assignment logic
- [x] TASK-024 — Add 30-frame timeout mechanism for lost IDs
- [x] TASK-025 — Return tracked objects {id, bbox, centroid, confidence, frame_number}
- [x] TASK-026 — Implement frame-to-frame ID history logging
- [x] TASK-027 — Write unit tests in tests/test_tracker.py

## Phase 4: Virtual Tripwire & Counting Logic

- [x] TASK-028 — Implement counter.py with TripwireCounter class
- [x] TASK-029 — Define configurable tripwire line (default horizontal at 50% height)
- [x] TASK-030 — Implement crossing detection via vertical position change
- [x] TASK-031 — Add direction logic (top→bottom = entry, bottom→top = exit)
- [x] TASK-032 — Implement per-object state machine {above, below, crossed}
- [x] TASK-033 — Add hysteresis to prevent double-counting (default 5px)
- [x] TASK-034 — Create CountEvent dataclass
- [x] TASK-035 — Return chronologically ordered events per frame
- [x] TASK-036 — Write unit tests in tests/test_counter.py

## Phase 5: Real-time Visualization & Overlay

- [x] TASK-037 — Implement visualizer.py with VideoVisualizer class
- [x] TASK-038 — Draw bounding boxes with unique colors per tracking ID
- [x] TASK-039 — Overlay tracking ID at centroid (18px font)
- [x] TASK-040 — Draw tripwire line (red, 3px) with IN/OUT direction arrows
- [x] TASK-041 — Display live counter overlay "IN: {n} | OUT: {n}" (24px)
- [x] TASK-042 — Add confidence score display next to bounding box
- [x] TASK-043 — Include frame number and FPS counter
- [x] TASK-044 — Implement --display toggle for headless processing
- [x] TASK-045 — Add option to save annotated output video
- [x] TASK-046 — Implement real-time window with ESC-key exit
- [ ] TASK-099 — Add demo export: short annotated MP4 clip + animated GIF for web embedding
- [ ] TASK-100 — Source a CC0 doorway clip (overhead/angled entrance) for the hero demo
- [ ] TASK-101 — Calibrate tripwire(s) on the doorway clip (src/calibrate.py)
- [ ] TASK-102 — Hand-count the hero clip and record system-vs-actual accuracy
- [x] TASK-047 — Write tests in tests/test_visualizer.py

## Phase 6: Metrics Logging & Data Export

> **Scope: thin slice.** Only the summary JSON is in scope for the PoC; the per-event CSV log is deferred.

- [ ] TASK-048 — Implement logger.py with DataExporter class (summary JSON only)
- [-] TASK-049 — Create CSV format [timestamp, event_type, person_id, direction, cumulative_in, cumulative_out]
- [-] TASK-050 — Write events to traffic_log_{input_filename}.csv
- [ ] TASK-051 — Create JSON metrics schema (video, frames_processed, duration_sec, per-storefront in/out/net, totals)
- [ ] TASK-052 — Write metrics to metrics_{input_filename}.json
- [-] TASK-053 — Add CSV header row on file creation
- [-] TASK-054 — Implement real-time CSV writing (append per frame)
- [ ] TASK-055 — Add console summary of totals after processing
- [ ] TASK-056 — Create output directory; support --output flag
- [-] TASK-057 — Add microsecond-precision timestamp generation
- [ ] TASK-058 — Write unit tests in tests/test_logger.py

## Phase 7: Pipeline Integration & Main Orchestration

- [ ] TASK-059 — Orchestrate load → detect → track → count → visualize → log in main.py
- [ ] TASK-060 — Implement frame processing loop with corrupted-frame handling
- [ ] TASK-061 — Add per-stage timing instrumentation
- [ ] TASK-062 — Implement graceful error handling with informative messages
- [ ] TASK-063 — Add progress indicator (frame N/Total, ETA) via tqdm
- [ ] TASK-064 — Wire data flow with parallel Visualizer + DataExporter
- [ ] TASK-065 — Add --verbose DEBUG logging with per-frame tracking state
- [ ] TASK-066 — Implement --config option to load JSON settings
- [ ] TASK-067 — Add summary report to console and summary_{input_filename}.txt
- [ ] TASK-068 — Write integration tests in tests/test_pipeline.py

## Phase 8: Docker Containerization

> **Deferred** — out of scope for this portfolio PoC.

- [-] TASK-069 — Create Dockerfile with Python 3.12 base image
- [-] TASK-070 — Install OpenCV system dependencies
- [-] TASK-071 — Copy requirements.txt and install packages
- [-] TASK-072 — Set working directory and copy source
- [-] TASK-073 — Create /app/input and /app/output volume mount points
- [-] TASK-074 — Set entry point to python src/main.py
- [-] TASK-075 — Create .dockerignore
- [-] TASK-076 — Write docker-compose.yml with volumes and GPU option
- [-] TASK-077 — Create build.sh and run.sh convenience scripts
- [-] TASK-078 — Document Docker usage in README

## Phase 9: Testing & Quality Assurance

> **Deferred** — beyond the depth already covered by existing unit tests; full coverage/CI is out of scope for this PoC. Keep the integration test (TASK-080) as an optional stretch.

- [-] TASK-079 — Create conftest.py with pytest fixtures
- [ ] TASK-080 — Write end-to-end integration test (optional stretch)
- [-] TASK-081 — Add assertions for CSV/JSON structure and metric ranges
- [-] TASK-082 — Implement performance test for processing-time constraint (REQ-010)
- [-] TASK-083 — Add edge-case tests (1 person, 50-person crowd, edge tripwire)
- [-] TASK-084 — Create manual overlay inspection checklist
- [-] TASK-085 — Run linting (pylint, flake8) and type checking (mypy)
- [-] TASK-086 — Achieve ≥80% code coverage with pytest-cov
- [-] TASK-087 — Create test report and coverage badge

## Phase 10: Documentation & Deployment Readiness

> **Mostly deferred** — the README is the primary doc for this PoC. Extended docs, benchmarks, and CI are out of scope; the demo clip and portfolio link remain in scope.

- [x] TASK-088 — Update README with installation, usage, and output format
- [-] TASK-089 — Create docs/architecture.md with data flow diagrams
- [-] TASK-090 — Create docs/api.md documenting module interfaces
- [-] TASK-091 — Add Google-format docstrings to all functions and classes
- [-] TASK-092 — Create docs/troubleshooting.md
- [-] TASK-093 — Generate performance benchmarks (FPS, memory)
- [ ] TASK-094 — Source the doorway hero clip (see TASK-100)
- [-] TASK-095 — Add GitHub Actions CI/CD workflow
- [ ] TASK-096 — Create releases/v0.1-poc tag
- [ ] TASK-097 — Add portfolio link and finalize for public deployment

---

## Progress Summary

Deferred tasks (`[-]`) are excluded from the in-scope totals below.

| Phase | Completed | In scope | Deferred |
|-------|-----------|----------|----------|
| 1. Core Infrastructure | 10 | 10 | 0 |
| 2. Person Detection | 9 | 9 | 0 |
| 3. Multi-Object Tracking | 9 | 9 | 0 |
| 4. Tripwire & Counting | 9 | 9 | 0 |
| 5. Visualization + Hero Demo | 11 | 15 | 0 |
| 6. Metrics (thin slice) | 0 | 6 | 5 |
| 7. Pipeline Integration | 0 | 10 | 0 |
| 8. Docker | 0 | 0 | 10 |
| 9. Testing & QA | 0 | 1 | 8 |
| 10. Documentation | 1 | 4 | 6 |
| **Total** | **49** | **73** | **29** |
