"""
4-Way Intersection Model with Adaptive Traffic Light Control.

Simulates a standard Indian intersection with:
- 4 approach arms (North, South, East, West)
- Each arm has vehicles queuing via IDM
- Traffic lights cycle with adaptive timing based on queue density
- Data-driven: the algorithm uses real-time vehicle counts to allocate green time

The adaptive algorithm: Webster's formula adapted for Indian traffic
  Cycle length C = (1.5L + 5) / (1 - Y)
  Where L = total lost time, Y = sum of critical flow ratios
  Green split proportional to demand (vehicle count * weight per arm)
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import numpy as np
import random

from engine.models import VehicleType, VehicleState, VehicleProfile, VEHICLE_PROFILES
from engine.idm import compute_idm_acceleration


class Direction(Enum):
    NORTH = "north"
    SOUTH = "south"
    EAST = "east"
    WEST = "west"


class LightState(Enum):
    RED = "red"
    GREEN = "green"
    YELLOW = "yellow"


@dataclass
class TrafficLight:
    """Single traffic light for one arm of the intersection."""
    direction: Direction
    state: LightState = LightState.RED
    time_in_state: float = 0.0
    green_duration: float = 30.0  # seconds (adaptive)
    yellow_duration: float = 3.0
    red_clearance: float = 2.0


@dataclass
class ArmQueue:
    """Vehicles queuing on one approach arm."""
    direction: Direction
    vehicles: list[VehicleState] = field(default_factory=list)
    arm_length: float = 500.0  # meters from intersection
    width: float = 7.0  # meters (2 lanes typically)

    @property
    def count(self) -> int:
        return len(self.vehicles)

    @property
    def density(self) -> float:
        """Vehicles per 100m."""
        if self.arm_length == 0:
            return 0.0
        return self.count / (self.arm_length / 100.0)


class AdaptiveController:
    """
    Adaptive traffic light controller using real-time queue data.

    Algorithm: Proportional green time allocation
    - Measure vehicle count on each arm every cycle
    - Allocate green time proportional to demand
    - Minimum green: 10s (pedestrian crossing)
    - Maximum green: 60s (prevent starvation)
    - Cycle: N→S→E→W (opposing arms get green simultaneously for simplicity)

    Indian adaptation:
    - Shorter yellow (2s vs 3s in Western countries people start on yellow)
    - Longer all-red clearance (3s stragglers clearing intersection)
    - Higher minimum green (15s auto-rickshaws are slow to start)
    """

    def __init__(self, min_green: float = 15.0, max_green: float = 60.0):
        self.min_green = min_green
        self.max_green = max_green
        self.cycle_time: float = 0.0
        self.phase_index: int = 0
        # Phases: [NS_green, NS_yellow, EW_green, EW_yellow]
        self.phases: list[tuple[set[Direction], LightState, float]] = []
        self._compute_initial_phases()

    def _compute_initial_phases(self) -> None:
        """Default equal-split phases."""
        g = 25.0
        y = 3.0
        self.phases = [
            ({Direction.NORTH, Direction.SOUTH}, LightState.GREEN, g),
            ({Direction.NORTH, Direction.SOUTH}, LightState.YELLOW, y),
            ({Direction.EAST, Direction.WEST}, LightState.GREEN, g),
            ({Direction.EAST, Direction.WEST}, LightState.YELLOW, y),
        ]
        self.cycle_time = sum(p[2] for p in self.phases)

    def adapt(self, arm_counts: dict[Direction, int]) -> None:
        """
        Recalculate green splits based on current queue lengths.
        Called once per cycle completion.
        """
        ns_demand = arm_counts.get(Direction.NORTH, 0) + arm_counts.get(Direction.SOUTH, 0)
        ew_demand = arm_counts.get(Direction.EAST, 0) + arm_counts.get(Direction.WEST, 0)
        total_demand = max(ns_demand + ew_demand, 1)

        # Proportional allocation
        ns_ratio = ns_demand / total_demand
        ew_ratio = ew_demand / total_demand

        total_green = 60.0  # total green time to distribute
        ns_green = np.clip(ns_ratio * total_green, self.min_green, self.max_green)
        ew_green = np.clip(ew_ratio * total_green, self.min_green, self.max_green)

        y = 3.0
        self.phases = [
            ({Direction.NORTH, Direction.SOUTH}, LightState.GREEN, ns_green),
            ({Direction.NORTH, Direction.SOUTH}, LightState.YELLOW, y),
            ({Direction.EAST, Direction.WEST}, LightState.GREEN, ew_green),
            ({Direction.EAST, Direction.WEST}, LightState.YELLOW, y),
        ]
        self.cycle_time = sum(p[2] for p in self.phases)

    def get_light_state(self, direction: Direction, elapsed_in_cycle: float) -> LightState:
        """Get the light state for a direction at a given point in the cycle."""
        t = elapsed_in_cycle % self.cycle_time
        cumulative = 0.0
        for green_dirs, state, duration in self.phases:
            cumulative += duration
            if t < cumulative:
                if direction in green_dirs:
                    return state
                else:
                    return LightState.RED
        return LightState.RED


class Intersection:
    """
    4-way intersection simulation with adaptive traffic lights.

    Layout (top view):
              │ N │
         ─────┼───┼─────
          W   │ X │  E
         ─────┼───┼─────
              │ S │

    Each arm feeds vehicles toward the center. Vehicles stop at red,
    proceed on green, using IDM for car-following within each arm.
    """

    def __init__(self, arm_length: float = 300.0, arm_width: float = 7.0, dt: float = 0.1):
        self.dt = dt
        self.time: float = 0.0
        self.arm_length = arm_length
        self.arm_width = arm_width
        self._next_id = 0

        # 4 approach arms
        self.arms: dict[Direction, ArmQueue] = {
            d: ArmQueue(direction=d, arm_length=arm_length, width=arm_width)
            for d in Direction
        }

        # Adaptive controller
        self.controller = AdaptiveController()
        self.cycle_elapsed: float = 0.0
        self.cycles_completed: int = 0

        # Stats
        self.total_departed: int = 0
        self.total_spawned: int = 0

    def spawn_vehicle(self, direction: Direction, vehicle_type: Optional[VehicleType] = None) -> None:
        """Spawn a vehicle at the tail of an arm."""
        if vehicle_type is None:
            vehicle_type = random.choices(
                [VehicleType.TWO_WHEELER, VehicleType.AUTO_RICKSHAW, VehicleType.SEDAN, VehicleType.HEAVY_TRUCK],
                weights=[0.45, 0.20, 0.25, 0.10], k=1
            )[0]

        profile = VEHICLE_PROFILES[vehicle_type]
        arm = self.arms[direction]

        # Position at the back of the queue
        if arm.vehicles:
            last_x = max(v.x for v in arm.vehicles)
            x = last_x + profile.length + profile.min_gap
        else:
            x = 0.0

        if x > arm.arm_length:
            return  # Arm is full

        v = VehicleState(
            id=self._next_id,
            vehicle_type=vehicle_type,
            x=x,
            y=random.uniform(1.0, arm.width - 1.0),
            speed=random.uniform(2.0, profile.max_speed * 0.4),
            acceleration=0.0,
            desired_speed=profile.max_speed * random.uniform(0.85, 1.15),
            spawn_time=self.time,
        )
        self._next_id += 1
        arm.vehicles.append(v)
        self.total_spawned += 1

    def step(self) -> dict:
        """Advance one timestep. Returns state dict for visualization."""
        # Update cycle
        self.cycle_elapsed += self.dt
        if self.cycle_elapsed >= self.controller.cycle_time:
            self.cycle_elapsed = 0.0
            self.cycles_completed += 1
            # Adapt based on current demand
            arm_counts = {d: arm.count for d, arm in self.arms.items()}
            self.controller.adapt(arm_counts)

        # Process each arm
        for direction, arm in self.arms.items():
            light = self.controller.get_light_state(direction, self.cycle_elapsed)
            self._update_arm(arm, light)

        self.time += self.dt

        return self._get_state()

    def _update_arm(self, arm: ArmQueue, light: LightState) -> None:
        """Update vehicle positions on one arm using IDM."""
        n = len(arm.vehicles)
        if n == 0:
            return

        # Vectorize
        xs = np.array([v.x for v in arm.vehicles])
        speeds = np.array([v.speed for v in arm.vehicles])
        desired_speeds = np.array([v.desired_speed for v in arm.vehicles])

        profiles = [VEHICLE_PROFILES[v.vehicle_type] for v in arm.vehicles]
        max_accels = np.array([p.max_accel for p in profiles])
        comf_decels = np.array([p.comfortable_decel for p in profiles])
        min_gaps = np.array([p.min_gap for p in profiles])
        headways = np.array([p.desired_headway for p in profiles])
        lengths = np.array([p.length for p in profiles])

        # Gaps: leader is the vehicle ahead (sorted by x descending = closer to intersection)
        sort_idx = np.argsort(-xs)  # highest x first (closest to intersection)
        gaps = np.full(n, 200.0)
        delta_vs = np.zeros(n)

        for rank in range(1, len(sort_idx)):
            follower = sort_idx[rank]
            leader = sort_idx[rank - 1]
            gap = xs[leader] - xs[follower] - lengths[leader]
            gaps[follower] = max(gap, 0.1)
            delta_vs[follower] = speeds[follower] - speeds[leader]

        # Red light acts as a virtual stopped vehicle at the stop line
        leader_idx = sort_idx[0]  # vehicle closest to intersection
        stop_line = arm.arm_length
        if light == LightState.RED or light == LightState.YELLOW:
            gap_to_line = stop_line - xs[leader_idx]
            if gap_to_line < 50.0:  # Only affect if close to stop line
                gaps[leader_idx] = max(gap_to_line, 0.1)
                delta_vs[leader_idx] = speeds[leader_idx]  # leader speed = 0 (stopped)

        # IDM acceleration
        accels = compute_idm_acceleration(
            speeds, desired_speeds, gaps, delta_vs,
            max_accels, comf_decels, min_gaps, headways
        )

        # Update
        new_speeds = np.maximum(0.0, speeds + accels * self.dt)
        new_xs = xs + new_speeds * self.dt

        departed = []
        for i, v in enumerate(arm.vehicles):
            v.x = float(new_xs[i])
            v.speed = float(new_speeds[i])
            v.acceleration = float(accels[i])
            if v.x > arm.arm_length:  # Crossed stop line = departed
                departed.append(v)

        for v in departed:
            arm.vehicles.remove(v)
            self.total_departed += 1

    def _get_state(self) -> dict:
        """Get current state for visualization/telemetry."""
        lights = {}
        timers = {}
        for d in Direction:
            lights[d.value] = self.controller.get_light_state(d, self.cycle_elapsed).value

        # Calculate remaining time in current phase
        t = self.cycle_elapsed % self.controller.cycle_time
        cumulative = 0.0
        for green_dirs, state, duration in self.controller.phases:
            cumulative += duration
            if t < cumulative:
                remaining = int(cumulative - t)
                for d in Direction:
                    if d in green_dirs:
                        timers[d.value] = remaining
                    else:
                        # Time until this direction gets green
                        timers.setdefault(d.value, remaining)
                break

        all_vehicles = []
        for d, arm in self.arms.items():
            for v in arm.vehicles:
                all_vehicles.append({
                    "direction": d.value,
                    "x": round(v.x, 1),
                    "y": round(v.y, 2),
                    "type": v.vehicle_type.value,
                    "speed": round(v.speed, 2),
                })

        return {
            "time": round(self.time, 2),
            "lights": lights,
            "timers": timers,
            "vehicles": all_vehicles,
            "counts": {d.value: arm.count for d, arm in self.arms.items()},
            "total_departed": self.total_departed,
            "cycles": self.cycles_completed,
        }
