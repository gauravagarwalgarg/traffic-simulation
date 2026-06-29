"""
Simulation engine: orchestrates IDM + MOBIL + telemetry pipeline.
Runs at configurable timestep, handles 500+ vehicles via NumPy vectorization.
"""
from __future__ import annotations
import time
import numpy as np
from typing import Optional
from collections import deque
from threading import Lock

from engine.models import (
    VehicleType, VehicleProfile, VehicleState, TelemetryRecord,
    VEHICLE_PROFILES
)
from engine.idm import compute_idm_acceleration
from engine.mobil import evaluate_lateral_move


class Simulation:
    """Core simulation engine tick-based, vectorized physics."""

    def __init__(
        self,
        road_length: float = 2000.0,   # meters
        road_width: float = 10.0,      # meters (typical Indian undivided road)
        dt: float = 0.1,               # timestep (seconds)
        max_vehicles: int = 600,
    ):
        self.road_length = road_length
        self.road_width = road_width
        self.dt = dt
        self.max_vehicles = max_vehicles
        self.time: float = 0.0
        self.vehicles: list[VehicleState] = []
        self._telemetry_buffer: deque[TelemetryRecord] = deque(maxlen=100_000)
        self._buffer_lock = Lock()
        self._next_id: int = 0

    def spawn_vehicle(self, vehicle_type: VehicleType, x: float = 0.0, y: Optional[float] = None) -> VehicleState:
        """Spawn a vehicle at given position. y=None means random lateral."""
        profile = VEHICLE_PROFILES[vehicle_type]
        if y is None:
            y = np.random.uniform(profile.width, self.road_width - profile.width)

        # Individual variation: desired speed ±15% of max
        desired_speed = profile.max_speed * np.random.uniform(0.85, 1.15)

        v = VehicleState(
            id=self._next_id,
            vehicle_type=vehicle_type,
            x=x, y=y,
            speed=np.random.uniform(0.5, profile.max_speed * 0.5),
            acceleration=0.0,
            desired_speed=desired_speed,
        )
        self._next_id += 1
        self.vehicles.append(v)
        return v

    def step(self) -> None:
        """Advance simulation by one timestep. Vectorized IDM + sequential MOBIL."""
        n = len(self.vehicles)
        if n == 0:
            self.time += self.dt
            return

        # --- Vectorize vehicle state ---
        xs = np.array([v.x for v in self.vehicles])
        ys = np.array([v.y for v in self.vehicles])
        speeds = np.array([v.speed for v in self.vehicles])
        desired_speeds = np.array([v.desired_speed for v in self.vehicles])

        profiles = [VEHICLE_PROFILES[v.vehicle_type] for v in self.vehicles]
        max_accels = np.array([p.max_accel for p in profiles])
        comf_decels = np.array([p.comfortable_decel for p in profiles])
        min_gaps = np.array([p.min_gap for p in profiles])
        headways = np.array([p.desired_headway for p in profiles])
        lengths = np.array([p.length for p in profiles])

        # --- Find leaders (nearest vehicle ahead in similar lateral band) ---
        gaps = np.full(n, 200.0)     # default: no leader seen (large gap)
        delta_vs = np.zeros(n)

        sort_idx = np.argsort(xs)
        for rank, i in enumerate(sort_idx):
            # Find next vehicle ahead in ±2m lateral band
            for ahead_rank in range(rank + 1, n):
                j = sort_idx[ahead_rank]
                if abs(ys[j] - ys[i]) < 2.0:  # in same "virtual lane"
                    gap = xs[j] - xs[i] - lengths[j]
                    gaps[i] = max(gap, 0.1)
                    delta_vs[i] = speeds[i] - speeds[j]
                    break

        # --- IDM: Compute accelerations (vectorized) ---
        accelerations = compute_idm_acceleration(
            speeds, desired_speeds, gaps, delta_vs,
            max_accels, comf_decels, min_gaps, headways
        )

        # --- MOBIL: Lateral movement (per-vehicle, not vectorized) ---
        lateral_displacements = np.zeros(n)
        for i, v in enumerate(self.vehicles):
            neighbors = [self.vehicles[j] for j in range(n) if j != i and abs(xs[j] - xs[i]) < 30]
            lateral_displacements[i] = evaluate_lateral_move(
                v, profiles[i], neighbors, self.road_width
            )

        # --- Update state ---
        new_speeds = np.maximum(0.0, speeds + accelerations * self.dt)
        new_xs = xs + new_speeds * self.dt
        new_ys = np.clip(ys + lateral_displacements * self.dt, 0.5, self.road_width - 0.5)

        for i, v in enumerate(self.vehicles):
            v.x = float(new_xs[i])
            v.y = float(new_ys[i])
            v.speed = float(new_speeds[i])
            v.acceleration = float(accelerations[i])

        # --- Telemetry ---
        self._emit_telemetry()

        # --- Remove vehicles that exited the road ---
        self.vehicles = [v for v in self.vehicles if v.x < self.road_length]

        self.time += self.dt

    def _emit_telemetry(self) -> None:
        """Push telemetry records into thread-safe buffer."""
        with self._buffer_lock:
            for v in self.vehicles:
                self._telemetry_buffer.append(TelemetryRecord(
                    timestamp=self.time,
                    vehicle_id=v.id,
                    vehicle_type=v.vehicle_type.value,
                    x=v.x, y=v.y,
                    speed=v.speed,
                    acceleration=v.acceleration,
                ))

    def drain_telemetry(self) -> list[TelemetryRecord]:
        """Drain the telemetry buffer (called by ingestion worker)."""
        with self._buffer_lock:
            records = list(self._telemetry_buffer)
            self._telemetry_buffer.clear()
        return records
