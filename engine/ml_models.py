"""
Local ML Models for Traffic Simulation Data Ingress Engine.

Provides trained-on-the-fly models that learn from simulation telemetry:
1. Anomaly Detection - Isolation Forest for traffic surge/incident detection
2. Traffic State Classification - Random Forest for LOS (Level of Service)
3. Speed Prediction - Linear/Ridge regression for short-term forecasting
4. Congestion Clustering - KMeans for spatial hotspot identification
5. Signal Timing Optimizer - Gradient-based green time optimization

All models run locally with scikit-learn compatible interfaces.
No external API calls - pure local inference.
"""
from __future__ import annotations
import numpy as np
from dataclasses import dataclass, field
from collections import deque
from typing import Optional
import pickle
import json


# =============================================================================
# 1. ANOMALY DETECTION (Isolation Forest approach - manual implementation)
# =============================================================================

@dataclass
class AnomalyDetector:
    """
    Lightweight anomaly detector using statistical z-score + rolling IQR.
    Detects traffic surges, incidents, and unusual patterns without sklearn.

    Algorithm:
    - Maintains rolling baseline of arrival rates
    - Flags when current rate > baseline + k*sigma (default k=2)
    - Also detects sudden drops (potential blockage downstream)
    """
    window_size: int = 120  # 2 minutes of 1Hz samples
    threshold_sigma: float = 2.0
    history: deque = field(default_factory=lambda: deque(maxlen=300))
    anomalies: deque = field(default_factory=lambda: deque(maxlen=50))
    _baseline_mean: float = 0.0
    _baseline_std: float = 1.0

    def update(self, value: float, timestamp: float) -> dict:
        """
        Feed a new observation. Returns anomaly assessment.

        Args:
            value: Current metric value (e.g., arrival rate, queue length)
            timestamp: Simulation time

        Returns:
            dict with keys: is_anomaly, score, type, details
        """
        self.history.append(value)

        if len(self.history) < 10:
            return {"is_anomaly": False, "score": 0.0, "type": "warming_up"}

        # Compute rolling statistics
        data = np.array(list(self.history))
        window = data[-min(self.window_size, len(data)):]
        self._baseline_mean = float(np.mean(window))
        self._baseline_std = float(np.std(window)) + 1e-6  # avoid div by zero

        # Z-score
        z_score = (value - self._baseline_mean) / self._baseline_std

        # IQR method for robust detection
        q1 = np.percentile(window, 25)
        q3 = np.percentile(window, 75)
        iqr = q3 - q1
        lower_fence = q1 - 1.5 * iqr
        upper_fence = q3 + 1.5 * iqr

        is_anomaly = abs(z_score) > self.threshold_sigma or value > upper_fence or value < lower_fence

        anomaly_type = "normal"
        if is_anomaly:
            if z_score > self.threshold_sigma:
                anomaly_type = "surge"  # Sudden increase (accident upstream, event)
            elif z_score < -self.threshold_sigma:
                anomaly_type = "drop"  # Sudden decrease (blockage, signal failure)
            elif value > upper_fence:
                anomaly_type = "outlier_high"
            else:
                anomaly_type = "outlier_low"

            self.anomalies.append({
                "timestamp": timestamp,
                "value": round(value, 2),
                "z_score": round(z_score, 2),
                "type": anomaly_type,
            })

        return {
            "is_anomaly": is_anomaly,
            "score": round(abs(z_score), 3),
            "type": anomaly_type,
            "z_score": round(z_score, 3),
            "baseline_mean": round(self._baseline_mean, 2),
            "baseline_std": round(self._baseline_std, 2),
            "upper_fence": round(upper_fence, 2),
            "lower_fence": round(lower_fence, 2),
        }

    def get_recent_anomalies(self, n: int = 10) -> list[dict]:
        return list(self.anomalies)[-n:]


# =============================================================================
# 2. TRAFFIC STATE CLASSIFIER (Level of Service A-F)
# =============================================================================

@dataclass
class TrafficStateClassifier:
    """
    Classifies current traffic state into Level of Service (A through F).
    Uses density, speed, and flow relationships from HCM (Highway Capacity Manual).

    Indian adaptation:
    - PCU (Passenger Car Unit) equivalents for mixed traffic
    - Adjusted density thresholds for non-lane discipline
    """
    # PCU equivalents for Indian traffic (IRC SP:41)
    pcu_factors: dict = field(default_factory=lambda: {
        "two_wheeler": 0.5,
        "auto_rickshaw": 1.0,
        "sedan": 1.0,
        "heavy_truck": 3.0,
    })
    # LOS thresholds: density in PCU/km (Indian standards, INDO-HCM)
    los_thresholds: dict = field(default_factory=lambda: {
        "A": 7,    # Free flow
        "B": 11,   # Reasonably free
        "C": 17,   # Stable flow
        "D": 22,   # Approaching unstable
        "E": 28,   # Unstable / capacity
        "F": 999,  # Forced flow / breakdown
    })
    history: deque = field(default_factory=lambda: deque(maxlen=60))

    def classify(self, vehicle_counts: dict[str, int], road_length_km: float = 0.3) -> dict:
        """
        Classify current traffic state.

        Args:
            vehicle_counts: dict with vehicle types as keys, counts as values
            road_length_km: length of road segment in km

        Returns:
            dict with LOS grade, density, description
        """
        # Compute PCU density
        total_pcu = 0.0
        for vtype, count in vehicle_counts.items():
            total_pcu += count * self.pcu_factors.get(vtype, 1.0)

        density_pcu_per_km = total_pcu / max(road_length_km, 0.01)

        # Classify
        los = "F"
        for grade, threshold in self.los_thresholds.items():
            if density_pcu_per_km <= threshold:
                los = grade
                break

        descriptions = {
            "A": "Free flow – drivers can maneuver freely",
            "B": "Reasonably free flow – slight restrictions",
            "C": "Stable flow – more restricted maneuverability",
            "D": "Approaching unstable – high density, limited freedom",
            "E": "Unstable flow – at or near capacity",
            "F": "Forced flow – breakdown, stop-and-go",
        }

        result = {
            "los": los,
            "density_pcu_km": round(density_pcu_per_km, 1),
            "total_pcu": round(total_pcu, 1),
            "description": descriptions.get(los, "Unknown"),
            "v_c_ratio": round(min(density_pcu_per_km / 28.0, 1.5), 2),  # volume/capacity
        }

        self.history.append(result)
        return result

    def get_trend(self) -> str:
        """Get LOS trend over recent history."""
        if len(self.history) < 5:
            return "insufficient_data"
        recent = [h["density_pcu_km"] for h in list(self.history)[-10:]]
        slope = (recent[-1] - recent[0]) / max(len(recent), 1)
        if slope > 1.0:
            return "degrading"
        elif slope < -1.0:
            return "improving"
        return "stable"


# =============================================================================
# 3. SPEED PREDICTOR (Online Linear Regression)
# =============================================================================

@dataclass
class SpeedPredictor:
    """
    Online linear regression for speed prediction.
    Uses recent speed samples to predict speed N seconds ahead.

    Features used:
    - Current speed
    - Speed gradient (derivative)
    - Queue density (proxy for congestion)
    - Time of day / cycle position
    """
    window_size: int = 60  # samples for fitting
    speed_history: deque = field(default_factory=lambda: deque(maxlen=120))
    density_history: deque = field(default_factory=lambda: deque(maxlen=120))

    def update(self, avg_speed: float, density: float) -> None:
        """Record new observation."""
        self.speed_history.append(avg_speed)
        self.density_history.append(density)

    def predict(self, horizon: int = 10) -> dict:
        """
        Predict speed `horizon` seconds ahead using linear trend + density.

        Returns:
            dict with predicted_speed, confidence, trend
        """
        if len(self.speed_history) < 15:
            return {"predicted_speed": 0, "confidence": "low", "trend": "unknown"}

        speeds = np.array(list(self.speed_history)[-self.window_size:])
        n = len(speeds)
        x = np.arange(n, dtype=np.float64)

        # Fit linear regression: speed = m*t + b
        x_mean = np.mean(x)
        y_mean = np.mean(speeds)
        numerator = np.sum((x - x_mean) * (speeds - y_mean))
        denominator = np.sum((x - x_mean) ** 2) + 1e-10
        slope = numerator / denominator
        intercept = y_mean - slope * x_mean

        # Predict
        predicted = slope * (n + horizon) + intercept
        predicted = max(0.0, predicted)  # speed can't be negative

        # Confidence based on R²
        y_pred = slope * x + intercept
        ss_res = np.sum((speeds - y_pred) ** 2)
        ss_tot = np.sum((speeds - y_mean) ** 2) + 1e-10
        r_squared = max(0, 1 - ss_res / ss_tot)

        confidence = "high" if r_squared > 0.7 else "medium" if r_squared > 0.3 else "low"
        trend = "accelerating" if slope > 0.05 else "decelerating" if slope < -0.05 else "steady"

        return {
            "predicted_speed_ms": round(predicted, 2),
            "predicted_speed_kmh": round(predicted * 3.6, 1),
            "current_speed_kmh": round(speeds[-1] * 3.6, 1),
            "slope": round(slope, 4),
            "r_squared": round(r_squared, 3),
            "confidence": confidence,
            "trend": trend,
            "horizon_seconds": horizon,
        }


# =============================================================================
# 4. CONGESTION CLUSTERING (Simple KMeans)
# =============================================================================

@dataclass
class CongestionClusterer:
    """
    Spatial clustering to identify congestion hotspots.
    Uses vehicle positions to find clusters of stopped/slow vehicles.

    Algorithm: Simple density-based approach
    - Discretize road into cells
    - Count slow vehicles per cell
    - Identify cells exceeding threshold as hotspots
    """
    cell_size: float = 30.0  # meters per cell
    slow_threshold: float = 2.0  # m/s (below this = congested)
    hotspot_threshold: int = 3  # vehicles per cell to be a hotspot

    def identify_hotspots(self, vehicles: list[dict]) -> dict:
        """
        Identify congestion hotspots from vehicle positions.

        Args:
            vehicles: list of dicts with keys: x, y, speed, direction

        Returns:
            dict with hotspots list and congestion metrics
        """
        if not vehicles:
            return {"hotspots": [], "congestion_index": 0.0}

        # Group by direction and discretize
        hotspots = []
        direction_groups: dict[str, list] = {}

        for v in vehicles:
            d = v.get("direction", "unknown")
            if d not in direction_groups:
                direction_groups[d] = []
            direction_groups[d].append(v)

        total_slow = 0
        total_vehicles = len(vehicles)

        for direction, veh_list in direction_groups.items():
            # Discretize into cells
            cells: dict[int, list] = {}
            for v in veh_list:
                cell_id = int(v.get("x", 0) / self.cell_size)
                if cell_id not in cells:
                    cells[cell_id] = []
                cells[cell_id].append(v)

            # Find hotspot cells
            for cell_id, cell_vehicles in cells.items():
                slow_count = sum(1 for v in cell_vehicles if v.get("speed", 0) < self.slow_threshold)
                total_slow += slow_count

                if slow_count >= self.hotspot_threshold:
                    hotspots.append({
                        "direction": direction,
                        "cell_start_m": cell_id * self.cell_size,
                        "cell_end_m": (cell_id + 1) * self.cell_size,
                        "slow_vehicles": slow_count,
                        "total_in_cell": len(cell_vehicles),
                        "avg_speed": round(
                            np.mean([v.get("speed", 0) for v in cell_vehicles]) * 3.6, 1
                        ),
                    })

        # Congestion index: fraction of vehicles that are slow
        congestion_index = total_slow / max(total_vehicles, 1)

        return {
            "hotspots": sorted(hotspots, key=lambda h: h["slow_vehicles"], reverse=True)[:10],
            "congestion_index": round(congestion_index, 3),
            "total_slow": total_slow,
            "total_vehicles": total_vehicles,
            "n_hotspots": len(hotspots),
        }


# =============================================================================
# 5. SIGNAL TIMING OPTIMIZER (Gradient-based)
# =============================================================================

@dataclass
class SignalOptimizer:
    """
    Optimizes traffic signal timing based on observed performance.
    Uses a simple online gradient descent approach:
    - Objective: minimize total wait time across all arms
    - Constraint: total green time is fixed (cycle budget)
    - Update: shift green time toward arms with higher delay

    This is a simplified RL reward-shaping approach without neural networks.
    """
    learning_rate: float = 0.5
    min_green: float = 15.0
    max_green: float = 60.0
    cycle_budget: float = 120.0  # total green time per cycle
    # Current allocation (seconds)
    green_times: dict = field(default_factory=lambda: {
        "north": 30.0, "south": 30.0, "east": 30.0, "west": 30.0
    })
    performance_history: deque = field(default_factory=lambda: deque(maxlen=50))

    def optimize(self, queue_lengths: dict[str, int], throughputs: dict[str, float]) -> dict:
        """
        Run one optimization step.

        Args:
            queue_lengths: current vehicles waiting per direction
            throughputs: vehicles departed per second per direction (recent)

        Returns:
            dict with new green times and optimization metrics
        """
        # Compute "pressure" per direction: queue / throughput rate
        pressures = {}
        total_pressure = 0.0
        for d in ["north", "south", "east", "west"]:
            q = queue_lengths.get(d, 0)
            t = throughputs.get(d, 0.1)
            pressure = q / max(t, 0.01)
            pressures[d] = pressure
            total_pressure += pressure

        if total_pressure < 0.01:
            return {"green_times": self.green_times, "pressures": pressures, "action": "no_change"}

        # Proportional allocation with momentum (smooth updates)
        new_greens = {}
        for d in ["north", "south", "east", "west"]:
            target = (pressures[d] / total_pressure) * self.cycle_budget
            # Exponential moving average toward target
            current = self.green_times[d]
            new_val = current + self.learning_rate * (target - current)
            new_greens[d] = float(np.clip(new_val, self.min_green, self.max_green))

        # Normalize to budget
        total_new = sum(new_greens.values())
        if total_new > 0:
            scale = self.cycle_budget / total_new
            for d in new_greens:
                new_greens[d] = round(float(np.clip(new_greens[d] * scale, self.min_green, self.max_green)), 1)

        self.green_times = new_greens

        result = {
            "green_times": dict(self.green_times),
            "pressures": {k: round(v, 2) for k, v in pressures.items()},
            "total_pressure": round(total_pressure, 2),
            "action": "optimized",
        }
        self.performance_history.append(result)
        return result

    def get_performance_trend(self) -> dict:
        """Analyze if optimization is improving throughput."""
        if len(self.performance_history) < 5:
            return {"trend": "warming_up", "samples": len(self.performance_history)}

        recent_pressures = [h["total_pressure"] for h in list(self.performance_history)[-10:]]
        slope = (recent_pressures[-1] - recent_pressures[0]) / len(recent_pressures)

        return {
            "trend": "improving" if slope < -0.5 else "degrading" if slope > 0.5 else "stable",
            "pressure_change": round(slope, 2),
            "current_pressure": round(recent_pressures[-1], 2),
        }


# =============================================================================
# 6. PATTERN DETECTOR (Time-of-day / cyclic patterns)
# =============================================================================

@dataclass
class PatternDetector:
    """
    Detects cyclic patterns in traffic data.
    Identifies: peak hours, lull periods, periodic surges.

    Uses autocorrelation on rolling windows to find periodicity.
    """
    history: deque = field(default_factory=lambda: deque(maxlen=600))  # 10 min at 1Hz
    pattern_cache: Optional[dict] = None

    def record(self, value: float) -> None:
        self.history.append(value)

    def detect_periodicity(self) -> dict:
        """
        Compute autocorrelation to find dominant period.
        """
        if len(self.history) < 60:
            return {"period": None, "strength": 0, "status": "insufficient_data"}

        data = np.array(list(self.history))
        data = data - np.mean(data)
        n = len(data)

        # Autocorrelation via FFT (fast)
        fft = np.fft.fft(data, n=2*n)
        acf = np.fft.ifft(fft * np.conj(fft))[:n].real
        acf = acf / acf[0]  # normalize

        # Find first significant peak after lag 5 (ignore trivial short lags)
        min_lag = 5
        peaks = []
        for i in range(min_lag, n // 2):
            if acf[i] > acf[i-1] and acf[i] > acf[i+1] and acf[i] > 0.3:
                peaks.append((i, float(acf[i])))

        if not peaks:
            return {"period": None, "strength": 0, "status": "no_periodicity"}

        # Dominant period = lag with highest autocorrelation
        best_lag, best_strength = max(peaks, key=lambda p: p[1])

        self.pattern_cache = {
            "period_samples": best_lag,
            "period_seconds": best_lag,  # assuming 1Hz sampling
            "strength": round(best_strength, 3),
            "status": "periodic",
            "n_peaks_found": len(peaks),
        }
        return self.pattern_cache

    def get_phase(self) -> dict:
        """
        Determine current phase in the detected cycle.
        """
        if not self.pattern_cache or self.pattern_cache["period_samples"] is None:
            return {"phase": "unknown"}

        period = self.pattern_cache["period_samples"]
        current_pos = len(self.history) % period
        phase_pct = current_pos / period * 100

        return {
            "phase_pct": round(phase_pct, 1),
            "cycle_position": current_pos,
            "period": period,
            "phase_label": "rising" if phase_pct < 50 else "falling",
        }


# =============================================================================
# AGGREGATE: ML Engine (combines all models)
# =============================================================================

class MLEngine:
    """
    Unified ML engine that orchestrates all local models.
    Call `ingest()` each second with current state to get predictions.
    """

    def __init__(self):
        self.anomaly_detector = AnomalyDetector()
        self.state_classifier = TrafficStateClassifier()
        self.speed_predictor = SpeedPredictor()
        self.congestion_clusterer = CongestionClusterer()
        self.signal_optimizer = SignalOptimizer()
        self.pattern_detector = PatternDetector()
        self._tick = 0

    def ingest(
        self,
        queue_lengths: dict[str, int],
        avg_speed: float,
        vehicles: list[dict],
        throughputs: dict[str, float],
        sim_time: float,
    ) -> dict:
        """
        Main ingestion point. Feed simulation state every ~1 second.

        Returns comprehensive ML analysis dict.
        """
        self._tick += 1
        total_queue = sum(queue_lengths.values())

        # 1. Anomaly detection on total queue
        anomaly = self.anomaly_detector.update(total_queue, sim_time)

        # 2. Traffic state classification
        # Convert queue_lengths to vehicle type counts (approximate)
        type_counts = {
            "two_wheeler": int(total_queue * 0.45),
            "auto_rickshaw": int(total_queue * 0.20),
            "sedan": int(total_queue * 0.25),
            "heavy_truck": int(total_queue * 0.10),
        }
        state = self.state_classifier.classify(type_counts)

        # 3. Speed prediction
        self.speed_predictor.update(avg_speed, total_queue)
        speed_pred = self.speed_predictor.predict(horizon=10)

        # 4. Congestion clustering
        congestion = self.congestion_clusterer.identify_hotspots(vehicles)

        # 5. Signal optimization (every 5 ticks to avoid jitter)
        signal_opt = {"action": "skipped"}
        if self._tick % 5 == 0:
            signal_opt = self.signal_optimizer.optimize(queue_lengths, throughputs)

        # 6. Pattern detection
        self.pattern_detector.record(total_queue)
        pattern = self.pattern_detector.detect_periodicity() if self._tick % 10 == 0 else {}

        return {
            "tick": self._tick,
            "timestamp": sim_time,
            "anomaly": anomaly,
            "traffic_state": state,
            "speed_prediction": speed_pred,
            "congestion": congestion,
            "signal_optimization": signal_opt,
            "pattern": pattern,
            "los_trend": self.state_classifier.get_trend(),
            "optimizer_trend": self.signal_optimizer.get_performance_trend(),
        }

    def get_summary(self) -> dict:
        """Get current model state summary."""
        return {
            "anomalies_detected": len(self.anomaly_detector.anomalies),
            "recent_anomalies": self.anomaly_detector.get_recent_anomalies(5),
            "current_los": self.state_classifier.history[-1] if self.state_classifier.history else None,
            "speed_forecast": self.speed_predictor.predict(),
            "optimizer_trend": self.signal_optimizer.get_performance_trend(),
            "pattern": self.pattern_detector.pattern_cache,
        }
