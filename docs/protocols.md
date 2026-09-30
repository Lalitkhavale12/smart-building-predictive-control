# Telemetry Protocol Comparison (Unit 4 + Tutorials)

One-page syllabus note: why this project uses MQTT for room telemetry, and
how the lab broker differs from a production deployment.

## Comparison table

| Criterion | MQTT (chosen) | HTTP | CoAP |
|---|---|---|---|
| Overhead per message | ~2 B fixed header + topic name | ~200+ B headers per request/response | ~4 B fixed header |
| Interaction pattern | Pub/sub via broker (push on change) | Request/response (client polls) | Request/response (+ observe extension) |
| QoS / reliability | QoS 0/1/2 + retained messages + last-will (LWT) | TCP retry only; app must dedupe/retry | Confirmable messages; no broker persistence |
| Suitability here | Many-to-many rooms↔controller; retained setpoints; LWT fault-tolerance story | Polling wastes the ESP32 loop; no LWT equivalent | Built for constrained nodes, but no mature local broker on student laptops |

(Table values are illustrative per course slides — Unit 4 lecture + Tutorials.)

## Why MQTT won here

- One shared topics contract (`topics.py`) used by simulator, MQTT bridge, and
  ESP32 firmware — rooms publish telemetry, the controller subscribes, and
  setpoints flow back on the same broker.
- Retained setpoints: a (re)connecting node immediately receives the latest
  setpoint without asking.
- Last-will (LWT) gives the IOT-04 sensor-failure robustness story for free:
  a dead node is detected by the broker, not by polling timeouts.

## MQTT security note (3 steps)

1. **Lab (convenience only):** anonymous localhost broker — `mosquitto.conf`
   runs `listener 1883` with `allow_anonymous true`. Fine for a lab laptop,
   never for a shared LAN.
2. **Checked-in path:** commented TLS block in `mosquitto.conf` (Unit-3
   security note) — `listener 8883` with `cafile` / `certfile` / `keyfile`
   placeholders, currently disabled. Reference it; cert paths stay placeholders.
3. **Production checklist:** enable auth (`password_file` + per-room ACLs), TLS
   everywhere (port 8883, no plaintext 1883 off localhost), `allow_anonymous
   false` on any LAN listener, rotate credentials per deployment.
