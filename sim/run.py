"""CLI runner (SIM-03 tracer slice): sim -> CSV in one runnable path.

  python -m sim.run --scenario weekday --days 1 --seed 0
  python -m sim.run --scenario heatwave --days 2 --seed 3 --out results/heatwave/seed03/

Drives the Plan 01 BuildingSim loop with the Plan 02 scenario world, holding
the Plan 01 5-min control-hook convention (policy called every 5th step,
action held between). Phase-1 policy is AlwaysOffPolicy only — no controllers,
no MQTT bridging, no dashboard code (phase boundary).

Threat T-03-01: --out is constrained under results/; parent-dir segments
are rejected before anything is written.
"""

import argparse
import pathlib

import numpy as np

from sim import config as cfg
from sim import logger as log_mod
from sim import weather as wx
from sim.policy import AlwaysOffPolicy
from sim.simulator import BuildingSim

RESULTS_ROOT = pathlib.Path("results")


def resolve_out(out_str):
    """Constrain output under results/ (T-03-01: reject path traversal)."""
    if ".." in pathlib.PurePosixPath(out_str).parts or ".." in pathlib.PurePath(out_str).parts:
        raise ValueError(f"--out must stay under results/, got {out_str!r}")
    root = (pathlib.Path.cwd() / RESULTS_ROOT).resolve()
    candidate = (pathlib.Path.cwd() / out_str).resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError(f"--out must stay under results/, got {out_str!r}")
    return candidate


def run(scenario, days, seed, out_dir):
    """Full run: returns (telemetry_path, meta_path)."""
    wx.validate_scenario(scenario)
    sim = BuildingSim(rng=np.random.default_rng(seed), scenario=scenario)
    obs = sim.reset(seed=seed)
    policy = AlwaysOffPolicy()
    logger = log_mod.TelemetryLogger()
    action = policy.step(obs)
    total = int(days) * cfg.STEPS_PER_DAY
    for step in range(total):
        if step % cfg.CONTROL_HOOK_STEPS == 0:
            action = policy.step(obs)
        obs = sim.step(action)
        for room in sorted(cfg.ROOMS):
            logger.record(step, room, obs[room], action[room])
    out_dir = pathlib.Path(out_dir)
    telemetry_path = logger.save_csv(out_dir / "telemetry.csv")
    meta_path = log_mod.write_run_meta(out_dir, seed, scenario, days, cfg)
    return telemetry_path, meta_path


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run the building simulator")
    parser.add_argument("--scenario", choices=list(cfg.SCENARIOS), required=True)
    parser.add_argument("--days", type=int, default=1)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)
    if args.days <= 0:
        parser.error("--days must be a positive int")
    out = args.out or f"results/{args.scenario}/seed{args.seed:02d}/"
    out_dir = resolve_out(out)
    telemetry_path, meta_path = run(args.scenario, args.days, args.seed, out_dir)
    print(f"wrote {telemetry_path} + {meta_path}")
    return telemetry_path, meta_path


if __name__ == "__main__":
    main()
