"""
Runner: spawns vehicles, runs simulation loop, starts telemetry writer.
Usage: python -m engine.runner
"""
from __future__ import annotations
import time
import random
import numpy as np
from engine.models import VehicleType
from engine.simulation import Simulation
from engine.telemetry import TelemetryWriter


def main() -> None:
    """Run a 60-second simulation with heterogeneous Indian traffic."""
    sim = Simulation(road_length=2000.0, road_width=10.0, dt=0.1)
    writer = TelemetryWriter(db_path="telemetry.db", batch_interval=0.5)
    writer.start(sim.drain_telemetry)

    # Vehicle type distribution (Indian traffic composition)
    # Source: IRC SP:41 typical urban composition
    type_weights = {
        VehicleType.TWO_WHEELER: 0.45,    # 45% dominant in Indian cities
        VehicleType.AUTO_RICKSHAW: 0.20,  # 20%
        VehicleType.SEDAN: 0.25,          # 25% (cars + SUVs)
        VehicleType.HEAVY_TRUCK: 0.10,    # 10% (buses + trucks)
    }
    types = list(type_weights.keys())
    weights = list(type_weights.values())

    # Simulation loop
    spawn_rate = 5  # vehicles per second
    sim_duration = 30.0  # seconds
    steps = int(sim_duration / sim.dt)

    print(f"Starting simulation: {sim_duration}s, dt={sim.dt}s, {steps} steps")
    print(f"Road: {sim.road_length}m x {sim.road_width}m")

    t_start = time.perf_counter()

    for step in range(steps):
        # Spawn vehicles at entry point
        if len(sim.vehicles) < sim.max_vehicles and random.random() < spawn_rate * sim.dt:
            vtype = random.choices(types, weights=weights, k=1)[0]
            sim.spawn_vehicle(vtype, x=0.0)

        sim.step()

        # Progress reporting every 5 simulated seconds
        if step % int(5.0 / sim.dt) == 0:
            elapsed_real = time.perf_counter() - t_start
            print(f"  t={sim.time:.1f}s | vehicles={len(sim.vehicles)} | "
                  f"telemetry={writer.record_count} records | "
                  f"real_time={elapsed_real:.2f}s")

    writer.stop()
    elapsed = time.perf_counter() - t_start

    print(f"\nSimulation complete:")
    print(f"  Simulated time: {sim_duration}s")
    print(f"  Real time: {elapsed:.2f}s")
    print(f"  Speedup: {sim_duration/elapsed:.1f}x real-time")
    print(f"  Total telemetry records: {writer.record_count}")
    print(f"  Database: telemetry.db")
    print(f"\nQuery example:")
    print(f"  sqlite3 telemetry.db \"SELECT vehicle_type, AVG(speed), COUNT(*) FROM telemetry GROUP BY vehicle_type\"")


if __name__ == "__main__":
    main()
