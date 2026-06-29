"""
MOBIL (Minimizing Overall Braking Induced by Lane changes) model.
Adapted for Indian traffic: continuous lateral positioning (not discrete lanes).

In Indian traffic, vehicles don't stick to lanes. A two-wheeler
can filter between two sedans. MOBIL is adapted to check if there's
a lateral gap sufficient for the vehicle's width + safety margin.

Decision: Change lateral position if:
  1. Safety criterion: new follower's deceleration < b_safe
  2. Incentive criterion:
     a_new_lane - a_current > Delta_a_threshold + p * (a_new_follower_after - a_new_follower_before)

  Where p = politeness factor (low in Indian traffic, 0.1-0.3)
"""
import numpy as np
from numpy.typing import NDArray
from engine.models import VehicleState, VehicleProfile, VEHICLE_PROFILES


def evaluate_lateral_move(
    ego: VehicleState,
    ego_profile: VehicleProfile,
    neighbors: list[VehicleState],
    road_width: float = 10.0,         # meters (typical Indian 2-lane road)
    safety_margin: float = 0.3,       # meters (Indian: very tight)
    politeness: float = 0.2,          # Indian traffic: low politeness
    threshold: float = 0.1,           # m/s² advantage needed to move
) -> float:
    """
    Returns lateral displacement suggestion (meters).
    Positive = move right, negative = move left, 0 = stay.

    Indian-specific: allows lane-splitting for two-wheelers
    (width < gap between adjacent vehicles).
    """
    ego_half_width = ego_profile.width / 2.0 + safety_margin

    # Find lateral gaps
    best_displacement = 0.0
    best_advantage = 0.0

    for direction in [-1.0, 1.0]:  # left, right
        target_y = ego.y + direction * ego_profile.width

        # Check road boundary
        if target_y - ego_half_width < 0 or target_y + ego_half_width > road_width:
            continue

        # Check if gap at target_y is wide enough for this vehicle
        gap_available = _lateral_gap_at(target_y, ego, neighbors)

        if gap_available < ego_profile.width + safety_margin * 2:
            continue  # Not enough space

        # Impatience factor: two-wheelers accept smaller gaps
        advantage = ego_profile.impatience * direction * 0.5

        if advantage > best_advantage + threshold:
            best_advantage = advantage
            best_displacement = direction * min(ego_profile.width * 0.5, 1.0)

    return best_displacement


def _lateral_gap_at(target_y: float, ego: VehicleState, neighbors: list[VehicleState]) -> float:
    """Find the smallest lateral gap at target_y position considering nearby vehicles."""
    min_gap = float('inf')
    for n in neighbors:
        if abs(n.x - ego.x) < 20.0:  # only consider longitudinally close vehicles
            lateral_dist = abs(n.y - target_y)
            if lateral_dist < min_gap:
                min_gap = lateral_dist
    return min_gap if min_gap != float('inf') else 10.0
