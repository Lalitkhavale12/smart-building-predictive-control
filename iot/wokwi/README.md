# Wokwi hardware path — virtual ESP32 node

The only file that runs on "hardware" in this project is
`iot/esp32_node.ino`. It is a real, compilable ESP32 sketch; it runs on a
**virtual** board in Wokwi, not on a physical one. This folder supplies the two
project files Wokwi needs so the setup is paste-ready instead of wired by hand.

| File | Purpose |
|---|---|
| `diagram.json` | ESP32 DevKit-C v4 + DHT22 on GPIO15, matching `#define DHT_PIN 15` |
| `libraries.txt` | Pins `PubSubClient` and `DHT sensor library` |

## Why this path exists

`sim/` computes room temperature from the 1R1C model in `sim/config.py`, so the
scenarios (heatwave, exam-day, five seeds) are reproducible. A physical DHT22
would read whatever the real room is, which is not a scenario. The firmware
therefore proves the **transport** — connect, subscribe QoS 1, retained
presence, last-will — while the sensing stays simulated. See `README.md`
("Simulated IoT") for the same limitation stated for the report.

## Steps

1. Open <https://wokwi.com>, **New Project → ESP32** (Arduino C++).
2. Paste `iot/esp32_node.ino` over `sketch.ino`. Do not edit it — the topic
   literals are pinned to `iot/topics.py` by `tests/test_sketch_contract.py`.
3. Replace the contents of the two project files that Wokwi creates by
   default — **no upload needed** (importing from disk is a paid feature;
   editing in the browser is free). Click each file in the left file list,
   `Ctrl+A`, `Ctrl+V`:

   - `libraries.txt` ← `PubSubClient` and `DHT sensor library`, one per line
   - `diagram.json` ← this folder's copy

   `libraries.txt` is optional: Wokwi auto-installs both libraries from the
   `#include` lines because both are in its registry, so the file only pins
   versions. If the part IDs differ in your Wokwi version, wire the DHT22 once
   in the GUI and let Wokwi rewrite `diagram.json`.
4. Press **F1 → "Enable Private Wokwi IoT Gateway"**. Without this,
   `host.wokwi.internal` does not resolve to your laptop and the board cannot
   reach the local broker.
5. Start the broker from the repo root, with output so you can watch traffic:

   ```powershell
   & "C:\Program Files\mosquitto\mosquitto.exe" -c mosquitto.conf -v
   ```

6. Press ▶ in Wokwi.

## Expected output

Broker window:

```
building/classroom_A/status  {"state":"online"}     (retained)
```

Wokwi serial monitor (115200 baud): stays **empty**. The sketch calls
`Serial.begin()` but never prints, and the telemetry publish on line 68 is
commented out by design — so the broker window is the only evidence.

Closing or crashing the simulation fires the last-will from line 42:

```
building/classroom_A/status  {"state":"offline"}    (retained)
```

That pair is the demo. It is the same message contract the Python node and
`iot/bridge.py` use, which is what `tests/test_sketch_contract.py` protects.

## What is deliberately not implemented

- `onCommand()` (line 33) is empty — no relay or LED is actuated.
- `readTemperature()` is never called — the DHT22 reads but nothing is
  published; the payload is built in Python.
- No OTA, no TLS, no credentials — `mosquitto.conf` runs `allow_anonymous true`
  for a localhost-only lab, with the 8883/TLS block left commented for any LAN
  beyond localhost.

Making the sketch publish real readings is a code change, not a config change:
uncomment line 68 and build the D-03 JSON (timestamp, room, T_in_C, T_out_C,
RH_pct, occupancy, HVAC_state, power_kW, light_on).

## Compile check without a browser

```powershell
arduino-cli core install esp32:esp32
arduino-cli lib install PubSubClient "DHT sensor library"
arduino-cli compile --fqbn esp32:esp32:esp32 iot/esp32_node.ino
```

Wokwi runs are manual and never in CI — a browser and a gateway cannot be
scripted, so the test suite can only pin the topic literals.
