# P12-IOT ESP32 firmware

Firmware implementation: Node 1 DHT11/LDR/sound sampling and SH1106 dashboard, shared ESP-NOW framing and relay code, and Node 4 HTTPS telemetry posting. One PlatformIO source builds four node variants; current bring-up sends Node 1 packets to Node 2 first. No board has been flashed or radio-tested.

## Four-node layout

```text
                       Node 2 (relay A)
                      /                 \
Node 1 (sensor/source) -----                ----- Node 4 (gateway)
                      \                 /
                       Node 3 (relay B)
```

Every line is a direct ESP-NOW peer link. Current bring-up selects Node 2 as first hop; Node 2 forwards toward Node 4. Node 3 remains alternate relay for later route-selection phase. Latest hardware spec places sensors at Node 1.

## Build and board settings

- PlatformIO project: this directory; board target `esp32dev` (ESP32 Dev Module / classic ESP32-WROOM-32 class).
- USB upload: select the serial port; `pio run -d firmware -e node_01 -t upload` (replace environment for each board).
- Serial monitor: `pio device monitor -b 115200` (add `-p <port>` when multiple boards are connected).
- Radio: ESP-NOW channel 1, unencrypted peers. Nodes 1–3 do not join a router. Node 4 joins Wi-Fi for HTTPS; configure the access point on channel 1 so ESP-NOW remains on the same channel.
- Libraries: Arduino-ESP32 framework, ESP-NOW/Wi-Fi, Adafruit DHT sensor, Adafruit Unified Sensor, Adafruit GFX, Adafruit SH110X.
- RGB LED: GPIO 21/22/23, active-high by default; edit `LED_ACTIVE_HIGH` for common-anode/inverted drivers. These pins stay reserved.
- Node 1 sensor/display pins: DHT11 17, LDR DO 18, sound OUT 19, SH1106 SCL 16/SDA 15.
- Gateway HTTPS endpoint: `API_URL` in `include/config.h` (`https://api.craftiq.in/p12/iot-data`). Copy `common/secrets.h.example` to ignored `common/secrets.h`; fill Wi-Fi SSID/password and the device bearer token. Keep the supplied GTS Root R4 certificate unchanged. Node 4 validates TLS with that CA and hostname, then posts sensor, network, node, sequence, experiment, and routing fields. Missing metrics go as JSON `null`.

Before peer communication, upload once to each board, record its `BOOT ... mac=` line, then replace all four zero MAC entries in `include/config.h` with actual MACs. Rebuild and upload all four. MACs are hardware-specific; placeholders intentionally prevent invented addresses. Boards know only direct peers: 1↔2, 1↔3, 2↔4, 3↔4.

Build all four variants with `pio run -d firmware`. Build one with `pio run -d firmware -e node_01`. Code includes receive/send callback signatures for Arduino-ESP32 core 2.x and 3.x; use a recent PlatformIO Espressif32 platform and retain the platform lock produced for a reproducible lab run.

## Bring-up sequence

1. Connect one board by USB. Build/upload a node environment; open serial at 115200; record MAC. Repeat for all four.
2. Fill MAC table, build/upload matching environment to each board. Confirm each prints `READY` without `ERROR peer_setup`.
3. Place Node 1 near relay 2/3 and Node 4 near both relays. Power all four. Keep a serial monitor on each board.
4. Node 1 samples sensors every 2 seconds and sends current readings to Node 2 every 3 seconds. Node 1 logs `SENSOR`, `SOURCE_SEND`, and received `ACK`; Node 2 logs `RECEIVED`, `ACK_SEND`, `FORWARD`. Once Node 4 firmware is flashed with matching MAC table, it logs `DELIVERED ... hops=2`.
5. Compare source sequence numbers with Node 4 delivered sequence numbers over a stated interval. `STATS` and `SEND_FAILED` logs expose hop retries and local send failures. Save all four serial logs with board IDs, date, channel and physical placement.
6. For basic direct-peer validation, use Node 1 near the selected relay, then move/disable one relay and record whether only its route fails. Automatic route discovery/recovery is not implemented in this phase.
7. Ensure the CraftIQ API has the additive P12 telemetry table and `P12_IOT_INGEST_TOKEN` set as a Worker secret. Set same token in Node 4's ignored `common/secrets.h`. Check Worker logs for `API_ACCEPTED`; `API_POST_FAILED` reports rejected or unreachable posts. The API token and Wi-Fi credentials stay out of source control.

## Protocol and limits

`MeshPacket` is packed, fixed-size and versioned. It carries project/network IDs, source/destination/current-forwarder/next-hop IDs, sequence, source uptime, hop count/limit, sensor fields, last-hop RSSI and metric slots. Invalid/unavailable measurements use sentinel values. ESP-NOW sends frame to configured direct peer. Relay ACKs previous hop, forwards toward Node 4; timeout triggers up to three retransmissions. Source sequence stays unchanged during forwarding.

This milestone does not implement neighbor discovery, adaptive route tables, ML, end-to-end ACK to Node 1, durable queueing, cloud upload, API auth/schema validation, or route recovery after relay failure. ACK confirms next-hop receipt only. Retry and delivery counters reset on reboot. Arduino-ESP32 Core 3 receive metadata supplies last-hop RSSI; Core 2 reports unknown. Latency/loss/throughput fields remain unknown until measured. Do not interpret simulation results as hardware data.

## Wiring and safety

Keep all GPIO at ESP32-safe 3.3 V levels. In particular, verify each sensor module's output voltage before connection; GPIO18 is digital-only LDR DO in the stated configuration. Do not connect a 5 V output directly to a GPIO. Verify LED module polarity/current and use suitable resistors/drivers. The RGB pins listed above are reserved on every board. Power/battery concept remains electrically unverified; use known-good, current-limited USB/bench supply for firmware bring-up.
