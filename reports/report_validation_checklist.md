# Report Validation Checklist

## Final artifacts and rendering

- [x] Editable DOCX: `IoT_Mesh_Intelligent_Routing_Report_70_Plus_Pages.docx`.
- [x] Rendered PDF: `IoT_Mesh_Intelligent_Routing_Report_70_Plus_Pages.pdf`.
- [x] Final rendered page count: **73 A4 pages**.
- [x] Reference inspected: `MiniProject_RCC_v1 (1).pdf` (63 pages); its formal cover, certificate, acknowledgment, abstract, contents, numbered chapters, figures/tables, references, and appendices informed structure only. RCC student/project content was not reused.
- [x] Front matter uses Roman folios (cover unnumbered); main chapters restart at Arabic page 1.
- [x] Contents, table list, and figure list reconciled against rendered headings/captions and page positions.
- [x] All 73 rendered pages reviewed in page contact sheets; cover, preliminary matter, hardware figures/tables, results charts, appendices, and references additionally reviewed at full resolution. No clipping or overflow found.
- [x] Final hardware diagram is an editable SVG with a PNG embedded in the DOCX. Photo slots are labelled placeholders, not evidence of completed assembly.
- [x] Report includes chapters 1–10 and appendices A–P.

## Evidence and claim checks

- [x] Stored `trial_results.csv`: 70 algorithm-level rows = seven scenarios × five trials × two routing modes, or 35 paired scenario/trial units; not 70 independent experiments.
- [x] Stored aggregate values and plots trace to checked-in CSVs; they are synthetic Python-simulator outputs, not radio or hardware results.
- [x] Saved Decision Tree metadata discloses held-out strong-condition evaluation, zero failure-class recall, confusion matrix, and seed 3 versus documented/default seed 17 provenance mismatch.
- [x] OMNeT++/INET is described as configured but unverified; no build/run or raw result files were claimed.
- [x] Physical ESP32 assembly, firmware, embedded inference, backend transfer, measurements, and energy results remain unimplemented/unverified.
- [x] Hardware chapter uses four ESP32 DevKit V1 38-pin boards, exact planned node/sensor/indicator roles, 4S battery arithmetic, separated 5 V converter outputs, and explicit electrical commissioning gates. Unverified component specifications remain marked.
- [x] Bibliographic entries were checked against publisher/official documentation where available; references are not copied from the RCC template.

## Open before academic submission

- [ ] Replace student name, register number, institution, department, guide, chairperson, examiner, address, and academic-year placeholders with verified details; obtain signatures and institutional formatting approval.
- [ ] Add real photographs to Figures 5.1–5.2 only after hardware assembly and measurement setup exist.
- [ ] Confirm exact board revision, sensor/display/traffic-light module SKUs, pin map, module voltage/current, and any required drivers.
- [ ] Verify matched cell condition, holder terminals, 4S wiring, BMS data sheet/pinout/rating, compatible 16.8 V CC/CV charger, final fuse rating, wiring, converter module ratings, thermal behavior, and USB/external-supply isolation before energizing the pack.
- [ ] Implement firmware and configured FastAPI/backend transfer; preserve logs proving packet receipt and route behavior.
- [ ] Reconcile model/data/output provenance and regenerate artifacts with a recorded source revision, command, seed, environment, and hashes.
- [ ] Build and run OMNeT++/INET if it remains in scope; retain native `.sca`, `.vec`, and route/event outputs.
- [ ] Collect repeated physical PDR, delay/RTT, throughput, route/recovery, and class-sensitive model results. Measure energy only with suitable current instrumentation and defined boundaries.
- [ ] Confirm reference citation style, access dates, and department requirements.

## Validation not performed

- Project tests were not run for this document task; test definitions are summarized as definitions only.
- No fresh Python experiment or model training was run; checked-in CSV/model artifacts were inspected, not reproduced.
- No OMNeT++/INET build or run, device test, electrical measurement, backend request, or institutional review was performed.
