# Report Validation Checklist

## Final artifacts and rendering

- [x] Updated editable report: `IoT_Mesh_Intelligent_Routing_Report_70_Plus_Pages.docx`.
- [x] Current PDF rendered from the DOCX; **77 A4 pages** (pdfinfo).
- [x] Cover/front matter and chapter pagination retained; contents, table list, and figure list reconciled against final PDF pages.
- [x] Figures 5.1–5.2 contain 12 genuine supplier product photographs with visible supplier credits and a source/attribution register in `reports/component_photos/ATTRIBUTION.md`.
- [x] Table 5.1 includes component, role/specification, quantity, verification status, and photo reference.
- [x] Figures 5.3–5.4 remain explicit placeholders for future assembly/measurement photos; no physical hardware photos were invented.
- [x] Figure 4.2 and `diagrams/final_hardware_architecture.svg` show the planned four-node topology and 4S power path; Figure 4.3 reproduces the supplied high-level system block diagram. Both are design diagrams, not board-placement drawings. Editable SVG and matching PNG are present.
- [ ] Current 77-page PDF fully re-rendered and inspected. The saved 75-page page-image bundle is from an earlier PDF and does not validate this version.
- [x] Original report backups remain in the local workspace; duplicate/archive files are excluded from Git.

## Evidence and claim checks

- [x] Python results remain labelled synthetic; INET execution and physical hardware validation remain unverified.
- [x] Saved model limitations remain: zero failure-class recall and seed 3 versus documented/default seed 17 mismatch.
- [x] Product photos are references, not evidence of purchase, exact unit selection, assembly, or testing.
- [x] The sound module is described as a sound-event/intensity proxy, not a calibrated sound-pressure meter.
- [x] OLED and traffic-light meanings are labelled intended firmware behavior, not hardware-tested behavior.
- [x] Current power design omits a fuse; report and diagram state that omission removes an overcurrent-protection layer.
- [x] Power path states 4S battery → compatible BMS → main switch → four separate LM2596 inputs; outputs remain separate. Full-charge requirement is 16.8 V CC/CV; BMS is not a charger and a 1S TP4056 is not for the complete 4S pack.
- [x] Battery-holder wiring must expose BMS balance taps; combined pack leads alone are insufficient. The power subsystem is not physically validated.

## Open before academic submission

- [ ] Provide the approved wooden-board layout image in current project files. None was available; Figures 4.2–4.3 are system/power architecture diagrams, not board-placement drawings. No substitute was invented.
- [ ] Replace student/institution/guide/academic-year placeholders; obtain signatures and institutional formatting approval.
- [ ] Verify exact board, sensor, display, indicator, switch and BMS models; pin mapping, voltage/current, logic levels, driver requirements, BMS pinout/rating, cell condition/matching, holder series wiring and balance taps, 16.8 V CC/CV charger, converter thermal limits, wiring/connectors, and USB/external-supply isolation before energizing.
- [ ] Implement firmware/backend transfer; retain raw logs showing delivery, routes, and recovery.
- [ ] Reconcile model/data/output provenance and regenerate artifacts with recorded source revision, commands, seed, environment, and hashes.
- [ ] Build and run OMNeT++/INET if still in scope; retain native result files.
- [ ] Collect repeated physical PDR, delay/RTT, throughput, route/recovery, and class-sensitive model results. Measure energy only with suitable current instrumentation and defined boundaries.
- [ ] Replace Figures 5.3–5.4 with real assembly and measurement photographs only after implementation.

## Validation not performed

- Project tests were not run for this document task.
- No fresh Python experiment or model training was run; checked-in outputs/model were not reproduced.
- No OMNeT++/INET build/run, device test, electrical measurement, backend request, or institutional review was performed.
