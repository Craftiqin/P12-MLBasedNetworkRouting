#pragma once

#include <Arduino.h>

static constexpr uint8_t PROTOCOL_VERSION = 1;
static constexpr uint8_t PACKET_DATA = 1;
static constexpr uint8_t PACKET_ACK = 2;
static constexpr uint8_t ROUTING_FIXED = 1;
static constexpr uint8_t LIGHT_UNKNOWN = 255;
static constexpr int16_t METRIC_UNKNOWN_I16 = INT16_MIN;
static constexpr uint16_t METRIC_UNKNOWN_U16 = UINT16_MAX;
static constexpr uint32_t METRIC_UNKNOWN_U32 = UINT32_MAX;

// Fixed-size binary frame. ESP-NOW supplies the link CRC; fields are versioned.
struct __attribute__((packed)) MeshPacket {
  uint8_t version;
  uint8_t type;
  char project_id[8];
  char network_id[12];
  char experiment_id[8];
  uint8_t source_id;
  uint8_t destination_id;
  uint8_t next_hop_id;
  uint8_t forwarding_node_id;
  uint8_t routing_algorithm;
  uint32_t sequence;
  uint32_t source_uptime_ms;
  uint8_t hop_count;
  uint8_t hop_limit;
  int16_t temperature_centi_c;
  uint16_t humidity_centi_percent;
  uint8_t light_status;
  uint8_t sound_detected;
  int16_t last_hop_rssi_dbm;
  uint16_t latency_ms;
  uint8_t packet_loss_percent;
  uint32_t throughput_bps;
};

static_assert(sizeof(MeshPacket) <= 250, "ESP-NOW v1 payload limit exceeded");
