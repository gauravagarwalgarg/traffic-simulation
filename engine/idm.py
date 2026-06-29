"""
Intelligent Driver Model (IDM) Longitudinal acceleration model.
Adapted for Indian traffic: reduced safe gaps, asymmetric acceleration.

IDM Formula:
  a = a_max * [1 - (v/v0)^delta - (s*(v, dv) / s)^2]

Where:
  s*(v, dv) = s0 + max(0, v*T + v*dv / (2*sqrt(a_max * b)))
  s0 = minimum gap
  T  = desired time headway
  v0 = desired speed
  delta = acceleration exponent (4 = smooth, lower = more aggressive)

Indian adaptation:
  - s0 reduced 30-50% vs European calibration (tighter following)
  - T reduced (0.8-1.2s vs 1.5-2.0s in Europe)
  - delta = 3 (more aggressive acceleration profile)
"""
import numpy as np
from numpy.typing import NDArray


def compute_idm_acceleration(
    speeds: NDArray[np.float64],         # current speed of each vehicle
    desired_speeds: NDArray[np.float64], # v0 for each vehicle
    gaps: NDArray[np.float64],           # net gap to leader (bumper-to-bumper)
    delta_v: NDArray[np.float64],        # speed difference (self - leader)
    max_accel: NDArray[np.float64],      # a_max per vehicle
    comfortable_decel: NDArray[np.float64],  # b per vehicle
    min_gap: NDArray[np.float64],        # s0 per vehicle
    desired_headway: NDArray[np.float64], # T per vehicle
    delta: float = 3.0,                  # Indian traffic: more aggressive than 4.0
) -> NDArray[np.float64]:
    """Vectorized IDM acceleration for N vehicles simultaneously."""

    # Desired dynamic gap: s*(v, dv)
    interaction_term = (speeds * delta_v) / (2.0 * np.sqrt(max_accel * comfortable_decel))
    desired_gap = min_gap + np.maximum(0.0, speeds * desired_headway + interaction_term)

    # IDM acceleration
    free_road_term = 1.0 - np.power(speeds / np.maximum(desired_speeds, 0.1), delta)
    interaction_gap_term = np.power(desired_gap / np.maximum(gaps, 0.1), 2.0)

    acceleration = max_accel * (free_road_term - interaction_gap_term)

    # Clip to physical limits (no teleportation)
    return np.clip(acceleration, -comfortable_decel * 2.0, max_accel)
