# Hardware validation status

Four ESP32 DevKit V1 nodes, two relay routes, source-side DHT11/LDR/sound sensor/OLED and per-node indicators are a planned prototype concept in `ARCHITECTURE.md` and `docs/ESP32_INTEGRATION.md`. No firmware, board assembly, measured radio/energy data or physical tests are in repository.

Power proposal mentions four 18650 cells in 4S, BMS, switch and separate buck converters; current design omits a fuse. This is not a verified bill of materials or construction instruction. Validate cell matching, holder balance taps, protection, compatible 16.8 V CC/CV charger, BMS rating/pinout, overcurrent risk, thermal behavior, regulator margins and USB/external-source isolation with qualified review before assembly. No fuse is included, removing an overcurrent-protection layer. BMS is not a charger. Keep this project status explicit in papers and README.
