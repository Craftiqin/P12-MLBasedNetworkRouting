#pragma once

#include <Arduino.h>

#ifndef P12_NODE_ID
#error "Set P12_NODE_ID through a PlatformIO node environment"
#endif

static constexpr uint8_t NODE_ID = P12_NODE_ID;
static constexpr uint8_t GATEWAY_ID = 4;
static constexpr char PROJECT_ID[] = "P12-IOT";
static constexpr char NETWORK_ID[] = "P12-MESH-01";
static constexpr char EXPERIMENT_ID[] = "EXP-001";
#define API_URL "https://api.craftiq.in/p12/iot-data"
static constexpr uint8_t ESPNOW_CHANNEL = 1;
static constexpr uint8_t MAX_HOPS = 4;
static constexpr uint32_t SEND_INTERVAL_MS = 3000;
static constexpr uint32_t ACK_TIMEOUT_MS = 350;
static constexpr uint8_t MAX_RETRIES = 3;
static constexpr uint8_t RX_QUEUE_SIZE = 8;
static constexpr uint8_t DEDUPE_SIZE = 32;

// Replace with WiFi.macAddress() output from each board. Keep leading zeros.
static constexpr uint8_t NODE_MACS[5][6] = {
    {0, 0, 0, 0, 0, 0},
    {0, 0, 0, 0, 0, 0}, // ESP32_01
    {0, 0, 0, 0, 0, 0}, // ESP32_02
    {0, 0, 0, 0, 0, 0}, // ESP32_03
    {0, 0, 0, 0, 0, 0}, // ESP32_04
};

// RGB pins reserved on all boards. Set false for common-anode/inverted driver.
static constexpr uint8_t LED_RED_PIN = 21;
static constexpr uint8_t LED_YELLOW_PIN = 22;
static constexpr uint8_t LED_GREEN_PIN = 23;
static constexpr bool LED_ACTIVE_HIGH = true;

// Node 1 sensor/display pins from latest hardware specification.
static constexpr uint8_t DHT11_PIN = 17;
static constexpr uint8_t LDR_DO_PIN = 18;
static constexpr uint8_t SOUND_OUT_PIN = 19;
static constexpr uint8_t OLED_SCL_PIN = 16;
static constexpr uint8_t OLED_SDA_PIN = 15;
static constexpr uint8_t LIGHT_BRIGHT_LEVEL = HIGH;
static constexpr uint8_t SOUND_DETECTED_LEVEL = HIGH;
