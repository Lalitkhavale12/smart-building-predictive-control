# Phase 02 Discussion Log

**Date:** 2026-09-29
**Mode:** --auto (all gray areas auto-selected with recommended defaults, single pass)

## Areas Discussed

### Topic contract
- Options: hierarchical building/{room}/... (recommended) / flat
- Selected: hierarchical + iot/topics.py single source of truth

### Client & broker
- Options: local Mosquitto + paho-mqtt 2.1.0 VERSION2 (recommended) / public broker
- Selected: local Mosquitto 2.0.22, mosquitto.conf checked in; tests brokerless via fake

### ESP32 virtualization
- Options: Python shim + checked-in sketch, Wokwi manual (recommended) / Wokwi in CI
- Selected: Esp32Node shim; esp32_node.ino + contract test; Wokwi manual demo

### QoS & reliability
- Options: telemetry QoS0 / commands QoS1 / retained status+LWT; no retained commands; forecasts never over MQTT (recommended)
- Selected: yes to all

### Fault tolerance
- Options: kill-a-node + packet-drop with numbers (recommended) / demo-only
- Selected: tests with numbers

## Deferred Ideas
- None

## the agent's Discretion
- Backoff schedule, float precision, fake-broker shape, TLS comment block
