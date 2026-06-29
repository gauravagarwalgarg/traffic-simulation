"""
Real-time data science & ML module for traffic simulation.

Computes:
- Arrival rate distribution fitting (Poisson, Normal, Exponential)
- Queue length prediction (linear regression on rolling window)
- Optimal green time recommendation (gradient-based optimization)
- Traffic flow fundamental diagram (density vs flow vs speed)
"""
from __future__ import annotations
from collections import deque
from dataclasses import dataclass, field
import numpy as np
from typing import Optional


@dataclass
class TrafficStats:
    """Rolling statistics for real-time ML inference."""
    # Rolling windows (last 120 seconds at 1Hz sampling)
    queue_north: deque = field(default_factory=lambda: deque(maxlen=120))
    queue_south: deque = field(default_factory=lambda: deque(maxlen=120))
    queue_east: deque = field(default_factory=lambda: deque(maxlen=120))
    queue_west: deque = field(default_factory=lambda: deque(maxlen=120))
    departures: deque = field(default_factory=lambda: deque(maxlen=120))
    avg_speeds: deque = field(default_factory=lambda: deque(maxlen=120))
    # Arrival inter-times for distribution fitting
    arrival_times: deque = field(default_factory=lambda: deque(maxlen=500))
    last_arrival: float = 0.0
    last_departed: int = 0

    def record(self, counts: dict, departed: int, avg_speed: float, sim_time: float) -> None:
        """Record one sample (called every second)."""
        self.queue_north.append(counts.get("north", 0))
        self.queue_south.append(counts.get("south", 0))
        self.queue_east.append(counts.get("east", 0))
        self.queue_west.append(counts.get("west", 0))
        new_departures = departed - self.last_departed
        self.departures.append(new_departures)
        self.last_departed = departed
        self.avg_speeds.append(avg_speed)

    def record_arrival(self, sim_time: float) -> None:
        """Record a vehicle arrival for inter-arrival time analysis."""
        if self.last_arrival > 0:
            inter_time = sim_time - self.last_arrival
            if inter_time > 0:
                self.arrival_times.append(inter_time)
        self.last_arrival = sim_time


def fit_arrival_distribution(stats: TrafficStats) -> dict:
    """
    Fit inter-arrival times to distributions.
    Returns: {"poisson_lambda", "exponential_rate", "normal_mu", "normal_sigma", "best_fit"}
    """
    if len(stats.arrival_times) < 10:
        return {"best_fit": "insufficient_data", "n_samples": len(stats.arrival_times)}

    data = np.array(stats.arrival_times)
    mu = float(np.mean(data))
    sigma = float(np.std(data))

    # Exponential: rate = 1/mean
    exp_rate = 1.0 / mu if mu > 0 else 0

    # Poisson: lambda ≈ arrivals per second = 1/mean_inter_arrival
    poisson_lambda = exp_rate

    # Coefficient of variation: CV ≈ 1 for exponential, < 1 for regular, > 1 for clustered
    cv = sigma / mu if mu > 0 else 0

    # Determine best fit
    if 0.8 < cv < 1.2:
        best_fit = "exponential"  # Random arrivals (Poisson process)
    elif cv < 0.8:
        best_fit = "normal"  # Regular/platoon arrivals
    else:
        best_fit = "clustered"  # Burst arrivals

    return {
        "poisson_lambda": round(poisson_lambda, 3),
        "exponential_rate": round(exp_rate, 3),
        "normal_mu": round(mu, 3),
        "normal_sigma": round(sigma, 3),
        "cv": round(cv, 3),
        "best_fit": best_fit,
        "n_samples": len(stats.arrival_times),
    }


def predict_queue(stats: TrafficStats, horizon: int = 30) -> dict:
    """
    Linear regression on queue lengths to predict next `horizon` seconds.
    Simple but effective for short-term traffic prediction.
    """
    predictions = {}
    for name, queue_data in [("north", stats.queue_north), ("south", stats.queue_south),
                              ("east", stats.queue_east), ("west", stats.queue_west)]:
        if len(queue_data) < 10:
            predictions[name] = {"trend": "unknown", "predicted": 0}
            continue

        y = np.array(list(queue_data)[-60:], dtype=np.float64)
        x = np.arange(len(y), dtype=np.float64)

        # Linear regression: y = mx + b
        n = len(x)
        slope = (n * np.sum(x * y) - np.sum(x) * np.sum(y)) / (n * np.sum(x**2) - np.sum(x)**2 + 1e-10)
        intercept = (np.sum(y) - slope * np.sum(x)) / n

        predicted = slope * (n + horizon) + intercept
        trend = "increasing" if slope > 0.5 else "decreasing" if slope < -0.5 else "stable"

        predictions[name] = {
            "trend": trend,
            "slope": round(float(slope), 3),
            "current": int(y[-1]),
            "predicted_30s": max(0, int(predicted)),
        }

    return predictions


def compute_fundamental_diagram(stats: TrafficStats) -> dict:
    """
    Traffic flow fundamental diagram: density vs flow vs speed.
    Density = vehicles/length, Flow = departures/time, Speed = avg speed
    """
    if len(stats.avg_speeds) < 5:
        return {"points": []}

    # Use rolling averages
    speeds = np.array(list(stats.avg_speeds)[-30:])
    n_q = np.array(list(stats.queue_north)[-30:])
    s_q = np.array(list(stats.queue_south)[-30:])
    e_q = np.array(list(stats.queue_east)[-30:])
    w_q = np.array(list(stats.queue_west)[-30:])
    total_density = (n_q + s_q + e_q + w_q) / 4.0  # avg vehicles per arm

    deps = np.array(list(stats.departures)[-30:]) if len(stats.departures) >= 30 else np.zeros(len(speeds))

    points = []
    for i in range(len(speeds)):
        points.append({
            "density": round(float(total_density[i]) if i < len(total_density) else 0, 1),
            "flow": round(float(deps[i]) if i < len(deps) else 0, 1),
            "speed": round(float(speeds[i]) * 3.6, 1),  # km/h
        })

    return {"points": points[-30:]}


def recommend_green_time(stats: TrafficStats) -> dict:
    """
    ML-based recommendation: optimal green split based on demand patterns.
    Uses exponential moving average of queue lengths to weight allocation.
    """
    if len(stats.queue_north) < 5:
        return {"ns_pct": 50, "ew_pct": 50, "confidence": "low"}

    # Exponential moving average (recent data weighted more)
    alpha = 0.3
    def ema(data):
        if not data:
            return 0
        arr = list(data)
        result = arr[0]
        for v in arr[1:]:
            result = alpha * v + (1 - alpha) * result
        return result

    ns_demand = ema(stats.queue_north) + ema(stats.queue_south)
    ew_demand = ema(stats.queue_east) + ema(stats.queue_west)
    total = ns_demand + ew_demand

    if total < 1:
        return {"ns_pct": 50, "ew_pct": 50, "confidence": "low"}

    ns_pct = round(ns_demand / total * 100, 1)
    ew_pct = round(ew_demand / total * 100, 1)

    confidence = "high" if len(stats.queue_north) > 30 else "medium" if len(stats.queue_north) > 10 else "low"

    return {
        "ns_pct": ns_pct,
        "ew_pct": ew_pct,
        "ns_demand_ema": round(ns_demand, 1),
        "ew_demand_ema": round(ew_demand, 1),
        "confidence": confidence,
    }


# =============================================================================
# WAIT TIME TRACKING
# =============================================================================

@dataclass
class WaitTimeTracker:
    """Tracks per-vehicle wait times (spawn → departure)."""
    wait_times: deque = field(default_factory=lambda: deque(maxlen=500))
    wait_by_type: dict = field(default_factory=lambda: {
        "two_wheeler": deque(maxlen=200),
        "auto_rickshaw": deque(maxlen=200),
        "sedan": deque(maxlen=200),
        "heavy_truck": deque(maxlen=200),
    })

    def record_departure(self, spawn_time: float, depart_time: float, vehicle_type: str) -> None:
        wait = depart_time - spawn_time
        self.wait_times.append(wait)
        if vehicle_type in self.wait_by_type:
            self.wait_by_type[vehicle_type].append(wait)

    def get_stats(self) -> dict:
        if not self.wait_times:
            return {"avg": 0, "p50": 0, "p95": 0, "by_type": {}}

        data = np.array(self.wait_times)
        by_type = {}
        for vtype, times in self.wait_by_type.items():
            if times:
                arr = np.array(times)
                by_type[vtype] = round(float(np.mean(arr)), 1)
            else:
                by_type[vtype] = 0

        return {
            "avg": round(float(np.mean(data)), 1),
            "p50": round(float(np.percentile(data, 50)), 1),
            "p95": round(float(np.percentile(data, 95)), 1),
            "p99": round(float(np.percentile(data, 99)), 1) if len(data) > 10 else 0,
            "min": round(float(np.min(data)), 1),
            "max": round(float(np.max(data)), 1),
            "n_samples": len(data),
            "by_type": by_type,
        }


# =============================================================================
# PHASE PERFORMANCE SCORING
# =============================================================================

@dataclass
class PhaseScorer:
    """Scores each green phase by throughput efficiency."""
    phase_scores: deque = field(default_factory=lambda: deque(maxlen=50))
    current_phase_departed: int = 0
    current_phase_start: float = 0.0
    current_phase_direction: str = ""

    def start_phase(self, direction: str, time: float) -> None:
        """Called when a new green phase begins."""
        if self.current_phase_direction and self.current_phase_start > 0:
            # Score the completed phase
            duration = time - self.current_phase_start
            if duration > 0:
                efficiency = self.current_phase_departed / duration  # vehicles/second
                self.phase_scores.append({
                    "direction": self.current_phase_direction,
                    "departed": self.current_phase_departed,
                    "duration": round(duration, 1),
                    "efficiency": round(efficiency, 2),
                })
        self.current_phase_direction = direction
        self.current_phase_start = time
        self.current_phase_departed = 0

    def record_departure(self) -> None:
        self.current_phase_departed += 1

    def get_stats(self) -> dict:
        if not self.phase_scores:
            return {"avg_efficiency": 0, "phases": []}
        efficiencies = [p["efficiency"] for p in self.phase_scores]
        return {
            "avg_efficiency": round(float(np.mean(efficiencies)), 2),
            "best_phase": max(self.phase_scores, key=lambda p: p["efficiency"]) if self.phase_scores else None,
            "worst_phase": min(self.phase_scores, key=lambda p: p["efficiency"]) if self.phase_scores else None,
            "recent_phases": list(self.phase_scores)[-10:],
        }
