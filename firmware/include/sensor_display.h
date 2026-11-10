#pragma once

#if P12_NODE_ID == 1

#include <Arduino.h>
#include <Wire.h>
#include <DHT.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SH110X.h>
#include <math.h>

#include "config.h"
#include "packet_protocol.h"

struct SourceReadings {
  int16_t temperature_centi_c = METRIC_UNKNOWN_I16;
  uint16_t humidity_centi_percent = METRIC_UNKNOWN_U16;
  uint8_t light_status = LIGHT_UNKNOWN;
  uint8_t sound_detected = LIGHT_UNKNOWN;
};

static DHT source_dht(DHT11_PIN, DHT11);
static Adafruit_SH1106G source_display(128, 64, &Wire, -1);
static SourceReadings source_readings;
static uint32_t last_sensor_read_ms = 0;
static bool display_ready = false;

static void beginSourceSensors() {
  pinMode(LDR_DO_PIN, INPUT);
  pinMode(SOUND_OUT_PIN, INPUT);
  source_dht.begin();
  Wire.begin(OLED_SDA_PIN, OLED_SCL_PIN);
  display_ready = source_display.begin(0x3C, true);
  if (!display_ready) Serial.println("SENSOR_ERROR oled_not_found addr=0x3C");
  source_display.clearDisplay();
  source_display.setTextColor(SH110X_WHITE);
  source_display.setTextSize(1);
  source_display.setCursor(0, 0);
  source_display.println("P12-IOT ESP32_01");
  source_display.println("Starting sensors...");
  if (display_ready) source_display.display();
  Serial.println("SENSORS_READY node=1 dht11=17 ldr_do=18 sound=19 oled=sh1106");
}

static bool updateSourceReadings(uint32_t now_ms) {
  if (now_ms - last_sensor_read_ms < 2000) return false;
  last_sensor_read_ms = now_ms;

  float temperature = source_dht.readTemperature();
  float humidity = source_dht.readHumidity();
  if (isnan(temperature) || isnan(humidity)) {
    source_readings.temperature_centi_c = METRIC_UNKNOWN_I16;
    source_readings.humidity_centi_percent = METRIC_UNKNOWN_U16;
    Serial.println("SENSOR_ERROR dht11_read_failed");
  } else {
    source_readings.temperature_centi_c = static_cast<int16_t>(lroundf(temperature * 100.0f));
    source_readings.humidity_centi_percent = static_cast<uint16_t>(lroundf(humidity * 100.0f));
  }

  source_readings.light_status = digitalRead(LDR_DO_PIN) == LIGHT_BRIGHT_LEVEL ? 1 : 0;
  source_readings.sound_detected = digitalRead(SOUND_OUT_PIN) == SOUND_DETECTED_LEVEL ? 1 : 0;
  Serial.printf("SENSOR node=1 temperature_centi_c=%d humidity_centi_pct=%u light=%s sound=%u\n",
                source_readings.temperature_centi_c, source_readings.humidity_centi_percent,
                source_readings.light_status ? "BRIGHT" : "DARK", source_readings.sound_detected);
  return true;
}

static void renderSourceDisplay(uint32_t sequence, bool waiting_ack, uint8_t next_hop) {
  if (!display_ready) return;
  source_display.clearDisplay();
  source_display.setCursor(0, 0);
  source_display.println("P12-IOT  ESP32_01");
  source_display.print("Temp: ");
  if (source_readings.temperature_centi_c == METRIC_UNKNOWN_I16) source_display.println("-- C");
  else { source_display.print(source_readings.temperature_centi_c / 100.0f, 1); source_display.println(" C"); }
  source_display.print("Humidity: ");
  if (source_readings.humidity_centi_percent == METRIC_UNKNOWN_U16) source_display.println("-- %");
  else { source_display.print(source_readings.humidity_centi_percent / 100.0f, 1); source_display.println(" %"); }
  source_display.printf("Light: %s\n", source_readings.light_status == LIGHT_UNKNOWN ? "UNKNOWN" : source_readings.light_status ? "BRIGHT" : "DARK");
  source_display.printf("Sound: %s\n", source_readings.sound_detected == LIGHT_UNKNOWN ? "UNKNOWN" : source_readings.sound_detected ? "DETECTED" : "CLEAR");
  source_display.printf("Seq: %lu -> ESP32_%02u\n", static_cast<unsigned long>(sequence), next_hop);
  source_display.printf("Route: FIXED  %s\n", waiting_ack ? "WAIT ACK" : "READY");
  source_display.display();
}

#endif
