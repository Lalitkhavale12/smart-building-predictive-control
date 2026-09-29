/* Virtual ESP32 sensor node — Wokwi manual-demo path (Phase 2, D-08/D-09).
 *
 * One sketch parameterized by ROOM_ID (change ROOM_ID plus the three topic
 * literals together; tests/test_sketch_contract.py pins them to iot/topics.py).
 * Physics lives in Python (sim/); DHT reads below are a stub. Wokwi run is
 * manual, never in CI.
 */

#include <WiFi.h>
#include <PubSubClient.h>
#include <DHT.h>

#define ROOM_ID "classroom_A"
#define DHT_PIN 15
#define DHT_TYPE DHT22

// Contract literals — must equal topics.py output for ROOM_ID (see contract test).
#define TELEMETRY_TOPIC "building/classroom_A/telemetry"
#define COMMAND_FILTER "building/classroom_A/command/#"
#define STATUS_TOPIC "building/classroom_A/status"

// Local Mosquitto via the Wokwi Private Gateway (F1 -> Enable Private Wokwi
// IoT Gateway); from inside the simulation the member laptop is
// host.wokwi.internal. LAN fallback: replace with the broker host's LAN IP
// (e.g. 192.168.1.50). Last resort: test.mosquitto.org (flaky, demo only).
#define MQTT_HOST "host.wokwi.internal"
#define MQTT_PORT 1883

DHT dht(DHT_PIN, DHT_TYPE);
WiFiClient espClient;
PubSubClient client(espClient);

void onCommand(char* topic, byte* payload, unsigned int length) {
  // Apply setpoint to local relay/LED GPIOs (demo path only).
}

void reconnect() {
  while (!client.connected()) {
    String clientId = String("esp32-") + ROOM_ID;
    // LWT: retained offline status fires on unexpected death (D-10).
    // Overload: connect(id, user, pass, willTopic, willQos, willRetain, willMessage).
    if (client.connect(clientId.c_str(), nullptr, nullptr, STATUS_TOPIC, 1, true, "{\"state\":\"offline\"}")) {
      client.subscribe(COMMAND_FILTER, 1);  // commands QoS 1, never retained
      client.publish(STATUS_TOPIC, "{\"state\":\"online\"}", true);  // retained presence
    } else {
      delay(2000);  // manual-demo backoff; Python bridge uses 1..30 s exponential
    }
  }
}

void setup() {
  Serial.begin(115200);
  dht.begin();
  WiFi.begin("Wokwi-GUEST", "", 6);  // open AP; channel 6 skips the ~4 s scan
  while (WiFi.status() != WL_CONNECTED) { delay(250); }
  client.setServer(MQTT_HOST, MQTT_PORT);
  client.setBufferSize(512);  // default 256 B incl. header is too tight for JSON
  client.setCallback(onCommand);
}

void loop() {
  if (!client.connected()) { reconnect(); }
  client.loop();
  // DHT stub: read dht.readTemperature()/readHumidity() here, build the D-03
  // JSON (timestamp,room,T_in_C,T_out_C,RH_pct,occupancy,HVAC_state,power_kW,
  // light_on) and publish to TELEMETRY_TOPIC at QoS 0 (PubSubClient can only
  // publish QoS 0; it can subscribe at QoS 0/1).
  // client.publish(TELEMETRY_TOPIC, payload);  // QoS 0, not retained
  delay(60000);  // 1-min cadence matches sim DT_S
}
