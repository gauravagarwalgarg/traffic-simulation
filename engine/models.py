"""
Vehicle types, physical profiles, and simulation state models.
Maps Indian traffic heterogeneity to IDM parameters.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import numpy as np


class VehicleType(Enum):
    TWO_WHEELER = "two_wheeler"      # Bikes, scooters
    AUTO_RICKSHAW = "auto_rickshaw"  # 3-wheelers
    SEDAN = "sedan"                  # Cars, SUVs
    HEAVY_TRUCK = "heavy_truck"      # Buses, trucks


@dataclass(frozen=True)
class VehicleProfile:
    """Physical characteristics per vehicle type.
    Indian traffic calibration: smaller gaps, higher impatience."""
    length: float          # meters
    width: float           # meters
    max_speed: float       # m/s
    max_accel: float       # m/s²
    comfortable_decel: float  # m/s² (braking)
    min_gap: float         # meters (bumper-to-bumper minimum)
    desired_headway: float # seconds
    impatience: float      # 0-1, higher = more aggressive lane-splitting


# Indian traffic calibration (based on IRC standards and field studies)
VEHICLE_PROFILES: dict[VehicleType, VehicleProfile] = {
    VehicleType.TWO_WHEELER: VehicleProfile(
        length=2.0, width=0.7, max_speed=16.7, max_accel=3.0,
        comfortable_decel=4.0, min_gap=0.5, desired_headway=0.8, impatience=0.9
    ),
    VehicleType.AUTO_RICKSHAW: VehicleProfile(
        length=2.7, width=1.4, max_speed=11.1, max_accel=2.0,
        comfortable_decel=3.0, min_gap=0.8, desired_headway=1.0, impatience=0.7
    ),
    VehicleType.SEDAN: VehicleProfile(
        length=4.5, width=1.8, max_speed=22.2, max_accel=2.5,
        comfortable_decel=3.5, min_gap=1.5, desired_headway=1.2, impatience=0.4
    ),
    VehicleType.HEAVY_TRUCK: VehicleProfile(
        length=10.0, width=2.5, max_speed=16.7, max_accel=1.0,
        comfortable_decel=2.0, min_gap=3.0, desired_headway=2.0, impatience=0.2
    ),
}


@dataclass
class VehicleState:
    """Runtime state of a single vehicle (continuous lateral positioning)."""
    id: int
    vehicle_type: VehicleType
    x: float              # longitudinal position (meters along road)
    y: float              # lateral position (continuous, not discrete lane)
    speed: float          # m/s (longitudinal)
    acceleration: float   # m/s² (current)
    desired_speed: float  # m/s (individual variation around max)
    spawn_time: float = 0.0  # when this vehicle entered the simulation


@dataclass
class TelemetryRecord:
    """Single telemetry frame pushed per simulation step per vehicle."""
    timestamp: float
    vehicle_id: int
    vehicle_type: str
    x: float
    y: float
    speed: float
    acceleration: float
