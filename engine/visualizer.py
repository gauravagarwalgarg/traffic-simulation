"""
Real-time terminal visualizer for the traffic simulation.
Uses Unicode block characters to render vehicles on the road.

No external dependencies pure terminal output with ANSI colors.
Run: python -m engine --viz
"""
from __future__ import annotations
import os
import sys
import time
from engine.models import VehicleType, VehicleState, VEHICLE_PROFILES
from engine.simulation import Simulation


# ANSI color codes per vehicle type
COLORS = {
    VehicleType.TWO_WHEELER: "\033[93m",    # Yellow
    VehicleType.AUTO_RICKSHAW: "\033[92m",  # Green
    VehicleType.SEDAN: "\033[96m",          # Cyan
    VehicleType.HEAVY_TRUCK: "\033[91m",    # Red
}
RESET = "\033[0m"
DIM = "\033[2m"
BOLD = "\033[1m"

# Vehicle symbols
SYMBOLS = {
    VehicleType.TWO_WHEELER: "·",
    VehicleType.AUTO_RICKSHAW: "▪",
    VehicleType.SEDAN: "■",
    VehicleType.HEAVY_TRUCK: "█",
}


def render_frame(sim: Simulation, term_width: int = 120, term_height: int = 20) -> str:
    """Render current simulation state as a terminal frame."""
    road_cols = term_width - 10  # leave room for stats
    road_rows = max(5, int(sim.road_width))  # 1 row per meter of road width

    # Create empty road grid
    grid: list[list[str]] = [[DIM + "·" + RESET for _ in range(road_cols)] for _ in range(road_rows)]

    # Map vehicles to grid positions
    for v in sim.vehicles:
        col = int((v.x / sim.road_length) * road_cols)
        row = int((v.y / sim.road_width) * road_rows)

        if 0 <= col < road_cols and 0 <= row < road_rows:
            color = COLORS.get(v.vehicle_type, "")
            symbol = SYMBOLS.get(v.vehicle_type, "?")
            grid[row][col] = color + symbol + RESET

    # Build frame
    lines: list[str] = []
    lines.append(f"{BOLD}{'─' * road_cols}{RESET}  t={sim.time:.1f}s")

    for row in range(road_rows):
        road_line = "".join(grid[row])
        lines.append(f"│{road_line}│")

    lines.append(f"{BOLD}{'─' * road_cols}{RESET}  n={len(sim.vehicles)}")

    # Legend
    legend_parts = []
    for vt in VehicleType:
        color = COLORS[vt]
        sym = SYMBOLS[vt]
        count = sum(1 for v in sim.vehicles if v.vehicle_type == vt)
        legend_parts.append(f"{color}{sym}{RESET} {vt.value}({count})")
    lines.append("  ".join(legend_parts))

    # Speed stats
    if sim.vehicles:
        speeds_kmph = [v.speed * 3.6 for v in sim.vehicles]
        avg = sum(speeds_kmph) / len(speeds_kmph)
        mx = max(speeds_kmph)
        lines.append(f"  avg: {avg:.0f} km/h | max: {mx:.0f} km/h | road: {sim.road_length}m")

    return "\n".join(lines)


def clear_screen() -> None:
    """Clear terminal using ANSI escape."""
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()


def run_visual(duration: float = 30.0, dt: float = 0.1, fps: float = 15.0) -> None:
    """Run simulation with real-time terminal visualization."""
    import random
    from engine.models import VehicleType

    sim = Simulation(road_length=2000.0, road_width=10.0, dt=dt)

    type_weights = {
        VehicleType.TWO_WHEELER: 0.45,
        VehicleType.AUTO_RICKSHAW: 0.20,
        VehicleType.SEDAN: 0.25,
        VehicleType.HEAVY_TRUCK: 0.10,
    }
    types = list(type_weights.keys())
    weights = list(type_weights.values())

    steps = int(duration / dt)
    frame_interval = 1.0 / fps
    last_frame_time = 0.0

    # Get terminal size
    try:
        term_size = os.get_terminal_size()
        term_width = min(term_size.columns, 160)
        term_height = term_size.lines - 5
    except OSError:
        term_width = 120
        term_height = 20

    clear_screen()
    print(f"{BOLD}Indian Traffic Simulation IDM + MOBIL{RESET}")
    print(f"Road: {sim.road_length}m × {sim.road_width}m | Duration: {duration}s | Press Ctrl+C to stop\n")

    try:
        for step in range(steps):
            # Spawn
            if len(sim.vehicles) < 400 and random.random() < 5 * dt:
                vtype = random.choices(types, weights=weights, k=1)[0]
                sim.spawn_vehicle(vtype, x=0.0)

            sim.step()

            # Render at target FPS
            now = time.perf_counter()
            if now - last_frame_time >= frame_interval:
                frame = render_frame(sim, term_width, 10)
                # Move cursor to line 3 and overwrite
                sys.stdout.write(f"\033[4;1H{frame}\n")
                sys.stdout.flush()
                last_frame_time = now

            # Pace to real-time (or slower for visibility)
            time.sleep(max(0, dt - 0.001))

    except KeyboardInterrupt:
        pass

    print(f"\n{BOLD}Simulation ended at t={sim.time:.1f}s with {len(sim.vehicles)} vehicles.{RESET}")
