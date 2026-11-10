# Hardware validation status

Step 5 audit, host test results, resource estimates, and board/API procedures are in [`step5_final_validation_and_demo.md`](step5_final_validation_and_demo.md). No physical hardware tests or ESP32 Arduino board builds have been run; all tests A–I remain pending.

Four ESP32 DevKit V1 nodes and two relay routes are specified in `docs/ESP32_INTEGRATION.md`. Phase 1/2 firmware source exists in `firmware/`; no compile, board assembly, measured radio/energy data or physical tests are recorded. Latest pin map puts sensors/OLED on Node 1.

Power proposal mentions four 18650 cells in 4S, BMS, switch and separate buck converters; current design omits a fuse. This is not a verified bill of materials or construction instruction. Validate cell matching, holder balance taps, protection, compatible 16.8 V CC/CV charger, BMS rating/pinout, overcurrent risk, thermal behavior, regulator margins and USB/external-source isolation with qualified review before assembly. No fuse is included, removing an overcurrent-protection layer. BMS is not a charger. Keep this project status explicit in papers and README.
