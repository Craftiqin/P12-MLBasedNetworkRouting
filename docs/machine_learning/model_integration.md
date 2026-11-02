# Model integration boundary

Python integration exists: model predicts one-hop success probability for currently available, non-history next-hop candidates that leave a shortest continuation. Cost combines `1 - predicted_success` and modeled tail success; 0.08 margin can retain previous choice. No candidates triggers minimum-hop fallback. Packet history and hop limit guard loops.

There is no C++ model export/inference, INET routing module, `AodvRouter` modification, feature telemetry adapter, or ESP32 firmware. INET configs all use AODV. `delivery_tree.json` contains evaluation metadata, not a model serialization. Any future integration needs parity tests, only-past-observable features, paired AODV comparison, loop/fallback tests, runtime and resource measurement.
