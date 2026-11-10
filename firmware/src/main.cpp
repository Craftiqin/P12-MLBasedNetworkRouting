#include <Arduino.h>
#include <WiFi.h>
#include <esp_now.h>
#include <esp_wifi.h>
#include <esp_arduino_version.h>
#include <string.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>

#if P12_NODE_ID == 4
#include "../common/secrets.h"
#endif

#include "config.h"
#include "packet_protocol.h"
#include "sensor_display.h"

struct QueuedPacket { MeshPacket packet; };
struct SeenPacket { uint8_t source; uint32_t sequence; };
struct RxFrame { uint8_t mac[6]; uint16_t len; int16_t rssi_dbm; uint8_t data[250]; };
static QueuedPacket queue[RX_QUEUE_SIZE];
static uint8_t queue_head = 0, queue_tail = 0, queue_count = 0;
static SeenPacket seen[DEDUPE_SIZE];
static uint8_t seen_cursor = 0;
static MeshPacket ack_queue[RX_QUEUE_SIZE];
static uint8_t ack_head = 0, ack_tail = 0, ack_count = 0;
static RxFrame rx_queue[RX_QUEUE_SIZE];
static uint8_t rx_head = 0, rx_tail = 0, rx_count = 0;
static portMUX_TYPE rx_mux = portMUX_INITIALIZER_UNLOCKED;
static MeshPacket in_flight{};
static bool has_in_flight = false, waiting_for_ack = false;
static bool tx_failed = false;
static uint32_t last_send_ms = 0, last_generated_ms = 0, next_sequence = 1;
static uint8_t attempts = 0;
static uint32_t packets_received = 0, packets_forwarded = 0, packets_delivered = 0;
static uint32_t packets_retried = 0, packets_failed = 0;
static bool red_until = false, yellow_until = false, green_until = false;
static uint32_t led_deadline = 0;
#if P12_NODE_ID == 4
static MeshPacket cloud_queue[RX_QUEUE_SIZE];
static uint8_t cloud_head = 0, cloud_tail = 0, cloud_count = 0;
static uint32_t cloud_retry_after_ms = 0;
static bool cloud_wifi_ready = false;
#endif

static bool zeroMac(const uint8_t *mac) {
  for (uint8_t i = 0; i < 6; ++i) if (mac[i] != 0) return false;
  return true;
}

static bool isPeer(uint8_t id) {
  if (NODE_ID == 1) return id == 2 || id == 3;
  if (NODE_ID == 2 || NODE_ID == 3) return id == 1 || id == 4;
  return NODE_ID == 4 && (id == 2 || id == 3);
}

static bool macForNode(uint8_t id, uint8_t *out) {
  if (id < 1 || id > 4 || !isPeer(id) || zeroMac(NODE_MACS[id])) return false;
  memcpy(out, NODE_MACS[id], 6);
  return true;
}

static void ledWrite(uint8_t pin, bool on) {
  digitalWrite(pin, (on == LED_ACTIVE_HIGH) ? HIGH : LOW);
}

static void showStatus(bool red, bool yellow, bool green, uint16_t duration_ms = 120) {
  red_until = red; yellow_until = yellow; green_until = green;
  led_deadline = millis() + duration_ms;
}

static void updateLeds() {
  bool active = static_cast<int32_t>(millis() - led_deadline) < 0;
  ledWrite(LED_RED_PIN, active && red_until);
  ledWrite(LED_YELLOW_PIN, active && yellow_until);
  ledWrite(LED_GREEN_PIN, active && green_until);
}

static bool alreadySeen(uint8_t source, uint32_t sequence) {
  for (uint8_t i = 0; i < DEDUPE_SIZE; ++i)
    if (seen[i].source == source && seen[i].sequence == sequence) return true;
  return false;
}

static void remember(uint8_t source, uint32_t sequence) {
  seen[seen_cursor] = {source, sequence};
  seen_cursor = (seen_cursor + 1) % DEDUPE_SIZE;
}

#if P12_NODE_ID == 4
static void beginGatewayWifi() {
  if (WIFI_SSID[0] == '\0' || API_AUTH_TOKEN[0] == '\0') {
    Serial.println("API_DISABLED reason=configure_common_secrets");
    return;
  }
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  uint32_t started = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - started < 15000) delay(100);
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("API_WIFI_ERROR reason=connect_timeout");
    WiFi.disconnect(false, true);
    WiFi.mode(WIFI_STA);
    esp_wifi_set_channel(ESPNOW_CHANNEL, WIFI_SECOND_CHAN_NONE);
    return;
  }
  uint8_t channel = 0;
  wifi_second_chan_t secondary;
  esp_wifi_get_channel(&channel, &secondary);
  if (channel != ESPNOW_CHANNEL) {
    Serial.printf("API_WIFI_ERROR reason=router_channel_mismatch expected=%u actual=%u\n", ESPNOW_CHANNEL, channel);
    WiFi.disconnect(false, true);
    WiFi.mode(WIFI_STA);
    esp_wifi_set_channel(ESPNOW_CHANNEL, WIFI_SECOND_CHAN_NONE);
    return;
  }
  cloud_wifi_ready = true;
  Serial.printf("API_WIFI_READY ip=%s channel=%u\n", WiFi.localIP().toString().c_str(), channel);
}

static bool enqueueCloud(const MeshPacket &packet) {
  if (cloud_count == RX_QUEUE_SIZE) return false;
  cloud_queue[cloud_tail] = packet;
  cloud_tail = (cloud_tail + 1) % RX_QUEUE_SIZE;
  ++cloud_count;
  return true;
}

static String jsonMetric(int32_t value, int32_t unknown, float divisor = 1.0f) {
  if (value == unknown) return "null";
  return String(static_cast<float>(value) / divisor, divisor == 1.0f ? 0 : 2);
}

static String jsonUnsignedMetric(uint32_t value, uint32_t unknown, float divisor = 1.0f) {
  if (value == unknown) return "null";
  return String(static_cast<float>(value) / divisor, divisor == 1.0f ? 0 : 2);
}

static bool postTelemetry(const MeshPacket &packet) {
  if (!cloud_wifi_ready || WiFi.status() != WL_CONNECTED) return false;
  WiFiClientSecure tls;
  tls.setCACert(ROOT_CA_CERTIFICATE);
  HTTPClient http;
  http.setTimeout(5000);
  if (!http.begin(tls, API_URL)) return false;
  http.addHeader("Content-Type", "application/json");
  http.addHeader("Authorization", String("Bearer ") + API_AUTH_TOKEN);

  String body = "{";
  body += "\"projectId\":\"" + String(packet.project_id) + "\",";
  body += "\"networkId\":\"" + String(packet.network_id) + "\",";
  body += "\"experimentId\":\"" + String(packet.experiment_id) + "\",";
  body += "\"sourceNodeId\":" + String(packet.source_id) + ",";
  body += "\"gatewayNodeId\":" + String(GATEWAY_ID) + ",";
  body += "\"forwardingNodeId\":" + String(packet.forwarding_node_id) + ",";
  body += "\"nextHopId\":" + String(packet.next_hop_id) + ",";
  body += "\"routingAlgorithm\":" + String(packet.routing_algorithm) + ",";
  body += "\"sequence\":" + String(packet.sequence) + ",";
  body += "\"sourceUptimeMs\":" + String(packet.source_uptime_ms) + ",";
  body += "\"hopCount\":" + String(packet.hop_count) + ",";
  body += "\"temperatureC\":" + jsonMetric(packet.temperature_centi_c, METRIC_UNKNOWN_I16, 100.0f) + ",";
  body += "\"humidityPercent\":" + jsonUnsignedMetric(packet.humidity_centi_percent, METRIC_UNKNOWN_U16, 100.0f) + ",";
  body += "\"lightStatus\":" + jsonMetric(packet.light_status, LIGHT_UNKNOWN) + ",";
  body += "\"soundDetected\":";
  body += packet.sound_detected == LIGHT_UNKNOWN ? "null," : packet.sound_detected ? "true," : "false,";
  body += "\"rssiDbm\":" + jsonMetric(packet.last_hop_rssi_dbm, METRIC_UNKNOWN_I16) + ",";
  body += "\"latencyMs\":" + jsonUnsignedMetric(packet.latency_ms, METRIC_UNKNOWN_U16) + ",";
  body += "\"packetLossPercent\":" + jsonUnsignedMetric(packet.packet_loss_percent, 255) + ",";
  body += "\"throughputBps\":" + jsonUnsignedMetric(packet.throughput_bps, METRIC_UNKNOWN_U32);
  body += "}";

  int status = http.POST(body);
  String response = status > 0 ? http.getString() : "";
  http.end();
  if (status >= 200 && status < 300 && response.indexOf("\"success\":true") >= 0) {
    Serial.printf("API_ACCEPTED project=%s network=%s src=%u seq=%lu hops=%u\n",
                  packet.project_id, packet.network_id, packet.source_id,
                  static_cast<unsigned long>(packet.sequence), packet.hop_count);
    return true;
  }
  Serial.printf("API_POST_FAILED seq=%lu status=%d\n", static_cast<unsigned long>(packet.sequence), status);
  return false;
}

static void publishNextTelemetry() {
  if (!cloud_count || static_cast<int32_t>(millis() - cloud_retry_after_ms) < 0) return;
  if (postTelemetry(cloud_queue[cloud_head])) {
    cloud_head = (cloud_head + 1) % RX_QUEUE_SIZE;
    --cloud_count;
    cloud_retry_after_ms = millis();
  } else {
    cloud_retry_after_ms = millis() + 5000;
  }
}
#endif

static bool enqueueData(const MeshPacket &packet) {
  if (queue_count == RX_QUEUE_SIZE) return false;
  queue[queue_tail] = {packet};
  queue_tail = (queue_tail + 1) % RX_QUEUE_SIZE;
  ++queue_count;
  return true;
}

static bool enqueueAck(uint8_t destination, const MeshPacket &data) {
  if (ack_count == RX_QUEUE_SIZE) return false;
  MeshPacket ack{};
  ack.version = PROTOCOL_VERSION;
  ack.type = PACKET_ACK;
  strncpy(ack.project_id, PROJECT_ID, sizeof(ack.project_id) - 1);
  strncpy(ack.network_id, NETWORK_ID, sizeof(ack.network_id) - 1);
  strncpy(ack.experiment_id, EXPERIMENT_ID, sizeof(ack.experiment_id) - 1);
  ack.source_id = NODE_ID;
  ack.destination_id = NODE_ID;
  ack.next_hop_id = destination;
  ack.forwarding_node_id = NODE_ID;
  ack.routing_algorithm = ROUTING_FIXED;
  ack.sequence = data.sequence;
  ack_queue[ack_tail] = ack;
  ack_tail = (ack_tail + 1) % RX_QUEUE_SIZE;
  ++ack_count;
  return true;
}

static void processPacket(const uint8_t *mac, const uint8_t *data, int len, int16_t rssi_dbm) {
  if (len != sizeof(MeshPacket)) return;
  MeshPacket packet{};
  memcpy(&packet, data, sizeof(packet));
  if (packet.version != PROTOCOL_VERSION || packet.source_id < 1 || packet.source_id > 4 ||
      packet.destination_id < 1 || packet.destination_id > 4 ||
      strncmp(packet.project_id, PROJECT_ID, sizeof(packet.project_id)) != 0 ||
      strncmp(packet.network_id, NETWORK_ID, sizeof(packet.network_id)) != 0 ||
      strncmp(packet.experiment_id, EXPERIMENT_ID, sizeof(packet.experiment_id)) != 0)
    return;
  uint8_t previous_hop = 0;
  for (uint8_t id = 1; id <= 4; ++id) {
    uint8_t peer_mac[6];
    if (macForNode(id, peer_mac) && memcmp(mac, peer_mac, 6) == 0) previous_hop = id;
  }
  if (!previous_hop) return;

  if (packet.type == PACKET_ACK && packet.next_hop_id == NODE_ID) {
    if (has_in_flight && waiting_for_ack && packet.sequence == in_flight.sequence &&
        packet.source_id == in_flight.next_hop_id) {
      waiting_for_ack = false;
      has_in_flight = false;
      attempts = 0;
      Serial.printf("ACK node=%u seq=%lu from=%u\n", NODE_ID,
                    static_cast<unsigned long>(packet.sequence), packet.source_id);
      showStatus(false, false, true);
    }
    return;
  }
  if (packet.type != PACKET_DATA || packet.next_hop_id != NODE_ID || packet.destination_id != GATEWAY_ID ||
      packet.source_id == NODE_ID || packet.hop_count >= packet.hop_limit)
    return;

  packet.last_hop_rssi_dbm = rssi_dbm;
  ++packets_received;
  bool duplicate = alreadySeen(packet.source_id, packet.sequence);
  if (!duplicate && NODE_ID != GATEWAY_ID && queue_count == RX_QUEUE_SIZE) {
    Serial.printf("DROP node=%u seq=%lu reason=queue_full\n", NODE_ID,
                  static_cast<unsigned long>(packet.sequence));
    showStatus(true, false, false);
    return;
  }
  enqueueAck(previous_hop, packet);
  if (duplicate) {
    Serial.printf("DUPLICATE node=%u src=%u seq=%lu acked=1\n", NODE_ID, packet.source_id,
                  static_cast<unsigned long>(packet.sequence));
    return;
  }
  remember(packet.source_id, packet.sequence);
  ++packet.hop_count;
  if (NODE_ID == GATEWAY_ID) {
    ++packets_delivered;
    Serial.printf("DELIVERED project=%s network=%s node=ESP32_04 src=%u seq=%lu hops=%u temp_centi_c=%d humidity_centi_pct=%u light=%u sound=%u rssi_dbm=%d\n",
                  packet.project_id, packet.network_id, packet.source_id,
                  static_cast<unsigned long>(packet.sequence), packet.hop_count,
                  packet.temperature_centi_c, packet.humidity_centi_percent,
                  packet.light_status, packet.sound_detected, packet.last_hop_rssi_dbm);
#if P12_NODE_ID == 4
    if (!enqueueCloud(packet)) Serial.printf("API_QUEUE_FULL seq=%lu\n", static_cast<unsigned long>(packet.sequence));
#endif
    showStatus(false, false, true);
    return;
  }
  if (!enqueueData(packet)) {
    Serial.printf("DROP node=%u seq=%lu reason=queue_full\n", NODE_ID,
                  static_cast<unsigned long>(packet.sequence));
    showStatus(true, false, false);
    return;
  }
  Serial.printf("RECEIVED node=%u src=%u seq=%lu prev=%u hops=%u rssi_dbm=%d\n", NODE_ID,
                packet.source_id, static_cast<unsigned long>(packet.sequence), previous_hop,
                packet.hop_count, packet.last_hop_rssi_dbm);
  showStatus(false, true, false);
}

#if ESP_ARDUINO_VERSION_MAJOR >= 3
static void onPacket(const esp_now_recv_info_t *info, const uint8_t *data, int len) {
  if (len <= 0 || len > 250) return;
  portENTER_CRITICAL(&rx_mux);
  if (rx_count < RX_QUEUE_SIZE) {
    RxFrame &frame = rx_queue[rx_tail];
    memcpy(frame.mac, info->src_addr, 6);
    frame.len = static_cast<uint16_t>(len);
    frame.rssi_dbm = info->rx_ctrl ? info->rx_ctrl->rssi : METRIC_UNKNOWN_I16;
    memcpy(frame.data, data, len);
    rx_tail = (rx_tail + 1) % RX_QUEUE_SIZE;
    ++rx_count;
  }
  portEXIT_CRITICAL(&rx_mux);
}
#else
static void onPacket(const uint8_t *mac, const uint8_t *data, int len) {
  if (len <= 0 || len > 250) return;
  portENTER_CRITICAL(&rx_mux);
  if (rx_count < RX_QUEUE_SIZE) {
    RxFrame &frame = rx_queue[rx_tail];
    memcpy(frame.mac, mac, 6);
    frame.len = static_cast<uint16_t>(len);
    frame.rssi_dbm = METRIC_UNKNOWN_I16;
    memcpy(frame.data, data, len);
    rx_tail = (rx_tail + 1) % RX_QUEUE_SIZE;
    ++rx_count;
  }
  portEXIT_CRITICAL(&rx_mux);
}
#endif

static void onSent(const uint8_t *, esp_now_send_status_t status) {
  if (status != ESP_NOW_SEND_SUCCESS && has_in_flight) tx_failed = true;
}

#if ESP_ARDUINO_VERSION_MAJOR >= 3
static void onSent(const wifi_tx_info_t *, esp_now_send_status_t status) {
  if (status != ESP_NOW_SEND_SUCCESS && has_in_flight) tx_failed = true;
}
#endif

static bool addPeer(uint8_t id) {
  uint8_t mac[6];
  if (!macForNode(id, mac)) return false;
  esp_now_peer_info_t peer{};
  memcpy(peer.peer_addr, mac, 6);
  peer.channel = ESPNOW_CHANNEL;
  peer.encrypt = false;
  esp_err_t result = esp_now_add_peer(&peer);
  return result == ESP_OK || result == ESP_ERR_ESPNOW_EXIST;
}

static bool sendPacket(const MeshPacket &packet) {
  uint8_t mac[6];
  if (!macForNode(packet.next_hop_id, mac)) return false;
  return esp_now_send(mac, reinterpret_cast<const uint8_t *>(&packet), sizeof(packet)) == ESP_OK;
}

static void startNextSend() {
  if (ack_count) {
    MeshPacket ack = ack_queue[ack_head];
    if (sendPacket(ack)) {
      Serial.printf("ACK_SEND node=%u to=%u seq=%lu\n", NODE_ID, ack.next_hop_id,
                    static_cast<unsigned long>(ack.sequence));
      ack_head = (ack_head + 1) % RX_QUEUE_SIZE;
      --ack_count;
    }
    return;
  }
  if (waiting_for_ack) {
    if (!tx_failed && millis() - last_send_ms < ACK_TIMEOUT_MS) return;
    if (attempts <= MAX_RETRIES) {
      ++attempts;
      ++packets_retried;
      tx_failed = false;
      if (sendPacket(in_flight)) {
        last_send_ms = millis();
        Serial.printf("RETRY node=%u seq=%lu attempt=%u\n", NODE_ID,
                      static_cast<unsigned long>(in_flight.sequence), attempts);
      }
      return;
    }
    Serial.printf("SEND_FAILED node=%u seq=%lu attempts=%u\n", NODE_ID,
                  static_cast<unsigned long>(in_flight.sequence), attempts);
    ++packets_failed;
    waiting_for_ack = false;
    has_in_flight = false;
    attempts = 0;
    showStatus(true, false, false);
    return;
  }
  if (queue_count) {
    QueuedPacket item = queue[queue_head];
    queue_head = (queue_head + 1) % RX_QUEUE_SIZE;
    --queue_count;
    uint8_t next_hop = GATEWAY_ID;
    item.packet.next_hop_id = next_hop;
    item.packet.forwarding_node_id = NODE_ID;
    in_flight = item.packet;
    has_in_flight = true;
    waiting_for_ack = true;
    attempts = 1;
    tx_failed = false;
    if (sendPacket(in_flight)) {
      last_send_ms = millis();
      ++packets_forwarded;
      Serial.printf("FORWARD node=%u seq=%lu next=%u hops=%u\n", NODE_ID,
                    static_cast<unsigned long>(in_flight.sequence), next_hop, in_flight.hop_count);
    } else {
      tx_failed = true;
    }
  }
}

static void generateSourcePacket() {
  if (NODE_ID != 1 || has_in_flight || queue_count || millis() - last_generated_ms < SEND_INTERVAL_MS)
    return;
  last_generated_ms = millis();
  MeshPacket packet{};
  packet.version = PROTOCOL_VERSION;
  packet.type = PACKET_DATA;
  strncpy(packet.project_id, PROJECT_ID, sizeof(packet.project_id) - 1);
  strncpy(packet.network_id, NETWORK_ID, sizeof(packet.network_id) - 1);
  strncpy(packet.experiment_id, EXPERIMENT_ID, sizeof(packet.experiment_id) - 1);
  packet.source_id = NODE_ID;
  packet.destination_id = GATEWAY_ID;
  packet.next_hop_id = 2;
  packet.forwarding_node_id = NODE_ID;
  packet.routing_algorithm = ROUTING_FIXED;
  packet.sequence = next_sequence++;
  packet.source_uptime_ms = millis();
  packet.hop_count = 0;
  packet.hop_limit = MAX_HOPS;
#if P12_NODE_ID == 1
  packet.temperature_centi_c = source_readings.temperature_centi_c;
  packet.humidity_centi_percent = source_readings.humidity_centi_percent;
  packet.light_status = source_readings.light_status;
  packet.sound_detected = source_readings.sound_detected;
#endif
  packet.last_hop_rssi_dbm = METRIC_UNKNOWN_I16;
  packet.latency_ms = METRIC_UNKNOWN_U16;
  packet.packet_loss_percent = 255;
  packet.throughput_bps = METRIC_UNKNOWN_U32;
  in_flight = packet;
  has_in_flight = true;
  waiting_for_ack = true;
  attempts = 1;
  tx_failed = false;
  if (sendPacket(in_flight)) {
    last_send_ms = millis();
    Serial.printf("SOURCE_SEND project=%s network=%s node=ESP32_01 seq=%lu first_hop=ESP32_%02u routing=fixed\n",
                  packet.project_id, packet.network_id,
                  static_cast<unsigned long>(packet.sequence), packet.next_hop_id);
  } else {
    tx_failed = true;
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(LED_RED_PIN, OUTPUT); pinMode(LED_YELLOW_PIN, OUTPUT); pinMode(LED_GREEN_PIN, OUTPUT);
  updateLeds();
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  if (esp_wifi_set_channel(ESPNOW_CHANNEL, WIFI_SECOND_CHAN_NONE) != ESP_OK) {
    Serial.println("ERROR wifi_channel_setup");
  }
#if P12_NODE_ID == 4
  beginGatewayWifi();
#endif
  Serial.printf("BOOT node=%u role=%s mac=%s channel=%u\n", NODE_ID,
                NODE_ID == 1 ? "sensor-source" : NODE_ID == 4 ? "gateway" : "relay",
                WiFi.macAddress().c_str(), ESPNOW_CHANNEL);
#if P12_NODE_ID == 1
  beginSourceSensors();
#endif
  if (zeroMac(NODE_MACS[NODE_ID])) Serial.println("ERROR replace this node MAC in include/config.h");
  if (esp_now_init() != ESP_OK) { Serial.println("ERROR esp_now_init"); return; }
  esp_now_register_recv_cb(onPacket);
  esp_now_register_send_cb(onSent);
  for (uint8_t id = 1; id <= 4; ++id) if (isPeer(id) && !addPeer(id))
    Serial.printf("ERROR peer_setup node=%u\n", id);
  Serial.println("READY; phase routes: ESP32_01->ESP32_02->ESP32_04");
}

void loop() {
  RxFrame incoming{};
  bool have_incoming = false;
  portENTER_CRITICAL(&rx_mux);
  if (rx_count) {
    incoming = rx_queue[rx_head];
    rx_head = (rx_head + 1) % RX_QUEUE_SIZE;
    --rx_count;
    have_incoming = true;
  }
  portEXIT_CRITICAL(&rx_mux);
  if (have_incoming) processPacket(incoming.mac, incoming.data, incoming.len, incoming.rssi_dbm);
#if P12_NODE_ID == 1
  uint32_t now_ms = millis();
  bool readings_updated = updateSourceReadings(now_ms);
  static uint32_t last_display_ms = 0;
  if (readings_updated || now_ms - last_display_ms >= 500) {
    last_display_ms = now_ms;
    renderSourceDisplay(next_sequence, waiting_for_ack, 2);
  }
#endif
  generateSourcePacket();
  startNextSend();
#if P12_NODE_ID == 4
  publishNextTelemetry();
#endif
  updateLeds();
  static uint32_t last_stats = 0;
  if (millis() - last_stats >= 10000) {
    last_stats = millis();
    Serial.printf("STATS node=%u rx=%lu forwarded=%lu delivered=%lu retries=%lu failed=%lu\n",
                  NODE_ID, static_cast<unsigned long>(packets_received),
                  static_cast<unsigned long>(packets_forwarded),
                  static_cast<unsigned long>(packets_delivered),
                  static_cast<unsigned long>(packets_retried),
                  static_cast<unsigned long>(packets_failed));
  }
  delay(1);
}
