import re
from pathlib import Path


ROOT = Path(__file__).parents[1]
ESP = ROOT / "espfirmware"
FIRMWARE = [ESP / f"ESP32_{node:02d}.ino" for node in range(1, 5)]
TREE = ROOT / "simulation/inet/ml-routing/ml/generated/runtime-v2/DecisionTreeModel.h"


def _block(pattern: str, text: str) -> str:
    match = re.search(pattern, text, re.S)
    assert match, pattern
    return match.group(0)


def test_four_standalone_files_embed_exact_tree_and_shared_packet_layout():
    assert sorted(path.name for path in ESP.iterdir()) == [path.name for path in FIRMWARE]
    tree_pattern = r"namespace p12ganesh::ml \{.*?\} // namespace p12ganesh::ml"
    expected_tree = _block(tree_pattern, TREE.read_text())
    packet_pattern = r"struct __attribute__\(\(packed\)\) MeshPacket\s*\{.*?\n\};"
    packets = []
    for path in FIRMWARE:
        source = path.read_text()
        assert _block(tree_pattern, source) == expected_tree
        assert "void setup()" in source and "void loop()" in source
        assert 'EXPERIMENT_ID[] = "EXP-003"' in source
        assert "PROTOCOL_VERSION = 2" in source
        packets.append(_block(packet_pattern, source))
    assert len(set(packets)) == 1
    assert "float model_features[8];" in packets[0]
    assert "uint8_t selected_next_hop_id;" in packets[0]


def test_model_runs_only_after_live_route_features_pass_validity_gate():
    source = (ESP / "ESP32_01.ino").read_text()
    assert source.index("routeFeaturesValid(now, d.features)") < source.index("p12ganesh::ml::predict(d.features)")
    assert "ML INPUTS UNAVAILABLE" in source
    assert "ROUTING_BASELINE_FALLBACK" in source
    assert "ROUTING_NO_VALID_ROUTE" in source
    assert "upper_available" in source and "lower_available" in source
    assert "d.nextHop = safeSelection == 0 ? 2 : 3;" in source
    assert "candidates[0].gatewayAvailable ? 1.0 : 0.0" in source
    assert "candidates[1].gatewayAvailable ? 1.0 : 0.0" in source
    assert "c.responses == 0" in source and "c.gatewayLossPercent > 100" in source
    assert "gatewayAvailabilityKnown = p.feature_valid <= 1" in source
    assert "p.feature_valid != 255" in source
    assert "candidates[0].gatewayAvailabilityKnown && candidates[0].gatewayAvailable" in source
    assert "else d.nextHop = 2" not in source
    for node in (2, 3):
        relay = (ESP / f"ESP32_{node:02d}.ino").read_text()
        assert "gatewayProbeAttempts>=PATH_MIN_SAMPLES?0:255" in relay
        assert 'DROP reason=gateway_path_unavailable' in relay
    assert 'd.reason = "model_predicted_unavailable_candidate"' in source
    assert "proposedCost" not in source and "priorCost" not in source
    assert "ML_ACTIVE" in source and "deliveryState == DELIVERY_CONFIRMED" in source


def test_controlled_baseline_build_skips_inference_and_keeps_default_ml():
    source = (ESP / "ESP32_01.ino").read_text()
    assert "#define P12_FORCE_BASELINE 0" in source
    assert "if (d.featuresValid && !P12_FORCE_BASELINE)" in source
    assert 'd.reason = "baseline_experiment_override"' in source
    assert '"Inference: DISABLED"' in source and '"Pred: BASELINE"' in source
    assert "confirmation_rtt_ms=%lu" in source


def test_export_size_live_feature_mapping_and_end_to_end_confirmation():
    assert TREE.stat().st_size == 2781
    source = (ESP / "ESP32_01.ino").read_text()
    assert "double upper_available, upper_pdr_estimate, upper_latency_ms, upper_hops;" in source
    assert "double lower_available, lower_pdr_estimate, lower_latency_ms, lower_hops;" in source
    assert "candidates[0].pathHops" in source and "candidates[1].pathHops" in source
    assert "DELIVERY_CONFIRMED" in source and "DELIVERY_UNCONFIRMED" in source
    assert "ack.hop_count == 2" in source
    for node in (2, 3):
        relay = (ESP / f"ESP32_{node:02d}.ino").read_text()
        assert "PACKET_DELIVERY_REPORT" in relay
        assert "sendBroadcast(report)" in relay
    gateway = (ESP / "ESP32_04.ino").read_text()
    assert "sendDeliveryReport(p,f.mac)" in gateway


def test_dashboard_derives_route_only_from_live_persisted_records():
    app = (ROOT / "app.py").read_text()
    assert "P12_ROUTING_API_URL = \"https://api.craftiq.in/p12/routing-events\"" in app
    assert "hardware_records(readings)" in app
    assert 'latest_event.get("routingMode") == "ML_ACTIVE"' in app
    assert 'latest_event.get("forwardingResult") == "GATEWAY_RECEIVED"' in app
    assert "P12_STALE_AFTER_SECONDS = 15" in app
    assert '@st.fragment(run_every="5s")' in app
    assert '"Failed transmissions", "N/A' in app
    assert "SIMULATION DATA remains in the simulation tabs" in app


def test_gateway_keeps_https_contract_and_five_second_publishing():
    gateway = (ESP / "ESP32_04.ino").read_text()
    assert '#define API_URL "https://api.craftiq.in/p12/iot-data"' in gateway
    assert "#define API_PUBLISH_INTERVAL 5000UL" in gateway
    assert "tls.setCACert(ROOT_CA_CERTIFICATE)" in gateway
    assert "setInsecure" not in gateway
    assert 'j+=",\\\"experimentId\\\":\\\""' in gateway
    assert "routingAlgorithm" in gateway and "p.routing_algorithm" in gateway
    assert '#define ROUTING_EVENTS_URL "https://api.craftiq.in/p12/routing-events"' in gateway
    assert "makeRoutingJson" in gateway and "qCount>=QUEUE_SIZE||routeCount>=QUEUE_SIZE" in gateway
    assert "UPLOAD_BACKPRESSURE" in gateway and "not_acked_retry=true" in gateway
    assert "ROUTING_EVENT_RETRY" in gateway
    assert "ROUTING_EVENT_EVICTED" not in gateway
    assert "static void uploadTask(void*)" in gateway
    assert "servicePublish()" not in gateway
    assert "xQueueSend(rxQueue,&f,0)!=pdTRUE" in gateway
    assert "rx_queue_overflow=%lu" in gateway
    assert "WIFI_CHANNEL_CHANGED old_channel=%u new_channel=%u" in gateway
    assert "GATEWAY_CHANNEL_SET channel=%u source=associated_ap" in gateway
    assert "esp_wifi_set_channel" not in gateway
    assert "portMUX_TYPE uploadQueueMux" in gateway


def test_sensor_packets_keep_two_second_cadence_and_gateway_channel_is_dynamic():
    source = (ESP / "ESP32_01.ino").read_text()
    gateway = (ESP / "ESP32_04.ino").read_text()
    assert "#define SEND_INTERVAL 2000UL" in source
    assert "#define SENSOR_INTERVAL 2000UL" in source
    assert "#define API_PUBLISH_INTERVAL 5000UL" in gateway
    assert "Configure the Wi-Fi access point to fixed channel 1" not in gateway
    assert "WiFi.channel()" in gateway and "meshChannel=WiFi.channel()" in gateway
    for node in FIRMWARE:
        source = node.read_text()
        assert "static constexpr uint8_t PACKET_GATEWAY_BEACON = 8;" in source
        assert "static constexpr uint8_t PACKET_CHANNEL_SYNC_REQUEST = 9;" in source
        assert "static constexpr uint8_t PACKET_CHANNEL_SYNC_RESPONSE = 10;" in source
        assert "static constexpr uint8_t PACKET_CHANNEL_SYNC_ACK = 11;" in source
        assert "static constexpr uint8_t PACKET_CHANNEL_CHANGE_NOTICE = 12;" in source
        assert "SYNC_MARKER" in source and "validChannelSyncPacket" in source
        assert "peer.channel = 0;" in source
    for node in FIRMWARE[:3]:
        source = node.read_text()
        assert "CHANNEL_BEACON_TIMEOUT_MS" in source
        assert "CHANNEL_SCAN_DWELL_MS" in source
        assert "CHANNEL_SYNC_MAX_RETRIES" in source
        assert "esp_wifi_set_channel(scanChannel,WIFI_SECOND_CHAN_NONE)" in source
        assert "channelState != CHANNEL_STATE_SYNCED" in source
    assert "MESH_READY channel=%u synchronized_nodes=3" in gateway
    assert "CHANNEL_CHANGE_NOTICE" in gateway


def test_channel_sync_recovery_protocol_contract():
    nodes = [path.read_text() for path in FIRMWARE[:3]]
    gateway = FIRMWARE[3].read_text()
    for source in nodes:
        assert "esp_wifi_get_country(&country)" in source
        assert "min(13,(int)country.schan+(int)country.nchan-1)" in source
        assert "esp_wifi_set_channel(scanChannel,WIFI_SECOND_CHAN_NONE)" in source
        assert "CHANNEL_SCAN_DWELL_MS = 350UL" in source
        assert "CHANNEL_BEACON_TIMEOUT_MS = 1800UL" in source
        assert "CHANNEL_SYNC_MAX_RETRIES = 4" in source
        assert "CHANNEL_SYNC_LOST" in source and 'startChannelScan("gateway_beacon_timeout")' in source
        assert "p.source_id!=GATEWAY_ID" in source
        assert "p.destination_id!=NODE_ID && p.destination_id!=255" in source
        assert "memcmp(frame.mac,gatewayMac" in source
        assert "p.sequence==syncSequence && p.source_uptime_ms==syncNonceUptime" in source
        assert "void loop()" in source and "serviceChannelSync()" in source
    assert "WiFi.channel()" in gateway
    assert "wifiReady||WiFi.status()!=WL_CONNECTED" in gateway
    assert "WIFI_CHANNEL_CHANGED old_channel=%u new_channel=%u" in gateway
    assert "memset(channelSyncAckAt,0,sizeof(channelSyncAckAt))" in gateway
    assert "channelNoticePending=true" in gateway
    assert "CHANNEL_NODE_LEASE_MS = 15000UL" in gateway
    assert "p.sequence==channelSyncRequestSequence[slot]" in gateway
    assert "p.source_uptime_ms==channelSyncRequestUptime[slot]" in gateway
    assert "memcmp(frame.mac,channelSyncMac[slot],6)==0" in gateway
    assert "synchronized_nodes=3" in gateway
    assert "meshChannel=WiFi.channel()" in gateway
    assert "esp_wifi_set_channel" not in gateway
