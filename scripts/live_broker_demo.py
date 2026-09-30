"""Live-broker end-to-end demo (rehearsal pack).

Drives BuildingSim + a C-policy (C3 SetbackPolicy) through the as-built
``iot/bridge.py`` + ``iot/node.py`` path for N steps and prints per-step
telemetry plus a final kWh/comfort line.

Two modes, exit 0 in both (a MODE: line always states which):

- LIVE (``MODE: live-broker``): a real broker answers on localhost:1883 and
  paho-mqtt imports — one Esp32Node per room + TelemetryBridge over real
  paho wrappers, same contract the integration tests assert
  (``tests/test_integration_mqtt.py``).
- SIMULATED (``MODE: simulated``): no broker (this laptop has Mosquitto NOT
  installed) — identical node/bridge/policy/sim wiring over
  ``tests.fakes.FakeBroker``, the same double the bridge/fault suites prove
  (``tests/test_bridge.py``, ``tests/test_faults.py``).

Repo code only: sim / iot / ctrl / tests.fakes. Stdlib + numpy otherwise.

Usage:
  python scripts/live_broker_demo.py --steps 12 --scenario weekday
  python scripts/live_broker_demo.py --steps 30 --scenario heatwave --seed 1
"""

import argparse
import pathlib
import socket
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import numpy as np

from ctrl.baselines import SetbackPolicy
from iot.bridge import TelemetryBridge
from iot.node import Esp32Node
from sim import config as cfg
from sim.metrics import comfort_flag
from sim.simulator import BuildingSim
from sim import weather as wx

BROKER_HOST, BROKER_PORT = "localhost", 1883


def broker_present(timeout=1.0):
    """Read-only TCP probe — no publishes, no side effects."""
    try:
        with socket.create_connection((BROKER_HOST, BROKER_PORT), timeout=timeout):
            return True
    except OSError:
        return False


def paho_present():
    try:
        import paho.mqtt.client  # noqa: F401
        return True
    except ImportError:
        return False


def run_demo(steps, scenario, seed, live, start_minute=0):
    """Wire sim + 4 nodes + C3 bridge; step N times. Returns (energy_kwh, comfort)."""
    sim = BuildingSim(rng=np.random.default_rng(seed), scenario=scenario)
    obs = sim.reset(seed=seed)
    policy = SetbackPolicy()  # C3 setback — zero-config, the honest baseline

    off = {room: {"hvac": "OFF", "light": 0} for room in cfg.ROOMS}
    while sim.minute < start_minute:  # sim-time fast-forward (OFF hold, no physics change)
        obs = sim.step(off)
    if start_minute:
        print(f"fast-forwarded to minute={sim.minute} (OFF hold); demo covers next {steps} steps")

    if live:
        factory = None  # default paho factory inside MqttClientWrapper
    else:
        from tests.fakes import FakeBroker, FakeClient
        broker = FakeBroker()
        factory = lambda client_id: FakeClient(client_id, broker)  # noqa: E731

    nodes = {room: Esp32Node(room, client_factory=factory) for room in cfg.ROOMS}
    bridge = TelemetryBridge(sim, policy, client_factory=factory)
    for node in nodes.values():
        node.connect(BROKER_HOST, BROKER_PORT)
    bridge.connect(BROKER_HOST, BROKER_PORT)
    if live:
        time.sleep(0.5)  # real broker: let CONNACK + subscriptions settle

    last_action = {room: {"hvac": "OFF", "light": 0} for room in cfg.ROOMS}
    total_kwh, occ_steps, comfy_steps = 0.0, 0, 0
    for step in range(steps):
        for room in cfg.ROOMS:  # nodes publish current obs as telemetry
            nodes[room].publish_telemetry(
                obs[room], hvac_state=last_action[room]["hvac"],
                light_on=last_action[room]["light"], step=sim.minute,
            )
        if live:
            time.sleep(0.2)  # real broker: let telemetry arrive before drain
        action, obs = bridge.tick()  # drain -> C3 step -> QoS1 commands -> sim.step
        last_action = action
        for room in cfg.ROOMS:
            nodes[room].poll_commands()
        step_kw = sum(obs[r]["power_kW"] for r in cfg.ROOMS)
        total_kwh += step_kw * cfg.DT_H
        for room in cfg.ROOMS:
            if obs[room]["occupancy"] > 0:
                occ_steps += 1
                if comfort_flag(obs[room]["T_in"], obs[room]["RH"], 1):
                    comfy_steps += 1
        occ_n = sum(obs[r]["occupancy"] for r in cfg.ROOMS)
        t_mean = sum(obs[r]["T_in"] for r in cfg.ROOMS) / len(cfg.ROOMS)
        acts = ",".join(f"{r.split('_')[0][:3]}:{action[r]['hvac']}" for r in cfg.ROOMS)
        print(f"step={step:3d} minute={sim.minute:4d} occ={occ_n:2d} "
              f"T_in_mean={t_mean:5.2f}C power={step_kw:5.3f}kW [{acts}]")
    for node in nodes.values():
        node.wrapper.disconnect()
    bridge.wrapper.disconnect()

    comfort = 100.0 * comfy_steps / occ_steps if occ_steps else float("nan")
    return total_kwh, comfort


def main():
    ap = argparse.ArgumentParser(description="Live-or-simulated MQTT demo: sim+C3 over iot/bridge.")
    ap.add_argument("--steps", type=int, default=12)
    ap.add_argument("--scenario", default="weekday",
                    choices=["weekday", "weekend", "heatwave", "exam-day"])
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--start-minute", type=int, default=0,
                    help="sim-time fast-forward under OFF hold before the demo steps "
                         "(e.g. 530 catches the ~09:00 weekday arrival)")
    args = ap.parse_args()
    wx.validate_scenario(args.scenario)

    live = broker_present() and paho_present()
    if live:
        print("MODE: live-broker (localhost:1883, paho-mqtt, real roundtrip)")
    else:
        reason = "no broker on localhost:1883" if not broker_present() else "paho-mqtt not installed"
        print(f"MODE: simulated (FakeBroker — {reason}; unit suite covers the live path)")
    kwh, comfort = run_demo(args.steps, args.scenario, args.seed, live, args.start_minute)
    c_str = f"{comfort:.1f}%" if comfort == comfort else "n/a (no occupied steps)"
    print(f"RESULT steps={args.steps} scenario={args.scenario} seed={args.seed} "
          f"policy=C3-setback energy_kWh={kwh:.4f} comfort={c_str}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
