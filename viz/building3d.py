"""3D building twin (viz): 3 floors, fed by simulation telemetry.

Floor map (locked): F1 = classroom_A + classroom_B, F2 = office + lab,
F3 = open terrace + utility box, visual-only (grey, never colored by data).

Reads saved telemetry frames only (same viewer rule as the dashboard):
per-room hourly means for a chosen (controller, scenario, seed). No sim
imports, no reruns. Render with plotly Mesh3d cuboids colored by T_in.
"""

import pathlib

import pandas as pd
import plotly.graph_objects as go

ROOT = pathlib.Path(__file__).resolve().parent.parent
MATRIX = ROOT / "results" / "full_matrix"

# (room, floor, x0, x1, y0, y1, z0, z1, simulated)
ROOMS = [
    ("classroom_A", 1, 0, 10, 0, 8, 0.0, 3.2, True),
    ("classroom_B", 1, 10, 20, 0, 8, 0.0, 3.2, True),
    ("office", 2, 0, 10, 0, 8, 3.2, 6.4, True),
    ("lab", 2, 10, 20, 0, 8, 3.2, 6.4, True),
    ("terrace", 3, 0, 20, 0, 8, 6.4, 6.7, False),
]

T_MIN, T_MAX = 20.0, 30.0  # colorscale range for T_in (degC)


def cuboid_mesh(x0, x1, y0, y1, z0, z1, value, name, hover, showscale=False):
    """One colored cuboid trace; value is broadcast to all 8 vertices."""
    x = [x0, x0, x1, x1, x0, x0, x1, x1]
    y = [y0, y1, y1, y0, y0, y1, y1, y0]
    z = [z0, z0, z0, z0, z1, z1, z1, z1]
    i = [7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2]
    j = [3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3]
    k = [0, 7, 2, 3, 6, 7, 1, 1, 5, 5, 7, 6]
    return go.Mesh3d(
        x=x, y=y, z=z, i=i, j=j, k=k,
        intensity=[value] * 8,
        colorscale="RdYlBu_r", cmin=T_MIN, cmax=T_MAX,
        showscale=showscale,
        colorbar=dict(title="T_in (C)") if showscale else None,
        name=name, hovertemplate=hover + "<extra></extra>",
        flatshading=True,
    )


def grey_box(x0, x1, y0, y1, z0, z1, name, hover):
    x = [x0, x0, x1, x1, x0, x0, x1, x1]
    y = [y0, y1, y1, y0, y0, y1, y1, y0]
    z = [z0, z0, z0, z0, z1, z1, z1, z1]
    i = [7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2]
    j = [3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3]
    k = [0, 7, 2, 3, 6, 7, 1, 1, 5, 5, 7, 6]
    return go.Mesh3d(
        x=x, y=y, z=z, i=i, j=j, k=k, color="lightgrey", opacity=0.5,
        name=name, hovertemplate=hover + "<extra></extra>", flatshading=True,
    )


def room_hourly(controller, scenario, seed):
    """Per-room hourly means from a saved telemetry frame."""
    path = MATRIX / controller / scenario / f"seed{seed:02d}" / "telemetry.csv"
    frame = pd.read_csv(path, parse_dates=["timestamp"])
    frame["hour"] = frame["timestamp"].dt.hour
    agg = frame.groupby(["room", "hour"]).agg(
        T_in_C=("T_in_C", "mean"), RH_pct=("RH_pct", "mean"),
        occupancy=("occupancy", "mean"), power_kW=("power_kW", "mean"),
        HVAC_state=("HVAC_state", lambda s: s.mode().iloc[0]),
    )
    return agg


def build_figure(controller, scenario, seed, hour):
    """3D building at one hour: rooms colored by mean T_in, hover = inputs."""
    agg = room_hourly(controller, scenario, seed)
    traces = []
    first_scale = True
    for room, floor, x0, x1, y0, y1, z0, z1, simulated in ROOMS:
        if not simulated:
            traces.append(grey_box(
                x0, x1, y0, y1, z0, z1, "terrace (F3)",
                "Terrace F3<br>visual-only - not simulated",
            ))
            continue
        try:
            r = agg.loc[(room, hour)]
        except KeyError:
            continue
        hover = (
            f"{room} (F{floor}) - {scenario} {controller} seed{seed} {hour:02d}:00<br>"
            f"T_in {r['T_in_C']:.1f} C<br>RH {r['RH_pct']:.0f}%<br>"
            f"Occupancy {r['occupancy']:.0f}<br>HVAC {r['HVAC_state']}<br>"
            f"Power {r['power_kW']:.2f} kW"
        )
        traces.append(cuboid_mesh(
            x0, x1, y0, y1, z0, z1, float(r["T_in_C"]),
            f"{room} F{floor}", hover, showscale=first_scale,
        ))
        first_scale = False
    fig = go.Figure(data=traces)
    fig.update_layout(
        title=f"Building twin - {scenario} / {controller} / seed{seed} / {hour:02d}:00",
        scene=dict(
            xaxis_title="x (m)", yaxis_title="y (m)", zaxis_title="z (m)",
            aspectmode="data",
        ),
        margin=dict(l=0, r=0, t=40, b=0),
    )
    return fig


def write_html(controller, scenario, seed, hour, path):
    """Standalone HTML export (report/demo use)."""
    build_figure(controller, scenario, seed, hour).write_html(str(path))
    return path
