"""
Simulation Data Ingress Engine.

Consumes real-time telemetry from the simulation, processes through ML models,
and exposes results for the UI layer. Runs as a background pipeline.

Architecture:
    Simulation (tick loop)
        → Ingress Buffer (thread-safe deque)
            → Preprocessor (aggregation, windowing)
                → ML Models (anomaly, classification, prediction, optimization)
                    → Results Store (latest predictions, accessible by UI)

This is the "brain" that connects raw simulation output to actionable ML insights.
"""
from __future__ import annotations
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional, Callable
import numpy as np

from engine.ml_models import MLEngine


@dataclass
class IngressRecord:
    """A single snapshot of simulation state for ingestion."""
    timestamp: float
    queue_lengths: dict  # {"north": int, "south": int, ...}
    avg_speed: float
    vehicles: list[dict]  # [{x, y, speed, direction, type}, ...]
    total_departed: int
    cycle_count: int


@dataclass
class IngressConfig:
    """Configuration for the data ingress pipeline."""
    sample_interval: float = 1.0  # seconds between ML updates
    buffer_size: int = 1000
    enable_anomaly: bool = True
    enable_classification: bool = True
    enable_prediction: bool = True
    enable_optimization: bool = True
    enable_clustering: bool = True


class DataIngressEngine:
    """
    Real-time data ingress engine with local ML model pipeline.

    Usage:
        engine = DataIngressEngine()
        engine.start()

        # Each simulation tick:
        engine.feed(IngressRecord(...))

        # UI reads:
        results = engine.get_latest_results()
        summary = engine.get_ml_summary()

        engine.stop()
    """

    def __init__(self, config: Optional[IngressConfig] = None):
        self.config = config or IngressConfig()
        self.ml_engine = MLEngine()

        # Thread-safe buffer
        self._buffer: deque[IngressRecord] = deque(maxlen=self.config.buffer_size)
        self._lock = threading.Lock()

        # Results store
        self._latest_results: Optional[dict] = None
        self._results_lock = threading.Lock()
        self._results_history: deque = deque(maxlen=300)  # 5 min at 1Hz

        # Background processing
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._processed_count = 0

        # Throughput tracking
        self._departure_history: deque = deque(maxlen=60)
        self._last_departed: int = 0

    def start(self) -> None:
        """Start the background ingress processing thread."""
        self._running = True
        self._thread = threading.Thread(target=self._process_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the ingress engine."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5.0)

    def feed(self, record: IngressRecord) -> None:
        """
        Feed a simulation state snapshot into the ingress pipeline.
        Thread-safe, non-blocking.
        """
        with self._lock:
            self._buffer.append(record)

    def feed_from_state(self, state: dict, sim_time: float) -> None:
        """
        Convenience method: feed directly from Intersection.step() output.
        """
        vehicles = []
        for v in state.get("vehicles", []):
            vehicles.append({
                "x": v.get("x", 0),
                "y": v.get("y", 0),
                "speed": v.get("speed", 0),
                "direction": v.get("direction", ""),
                "type": v.get("type", "sedan"),
            })

        record = IngressRecord(
            timestamp=sim_time,
            queue_lengths=state.get("counts", {}),
            avg_speed=self._compute_avg_speed(vehicles),
            vehicles=vehicles,
            total_departed=state.get("total_departed", 0),
            cycle_count=state.get("cycles", 0),
        )
        self.feed(record)

    def get_latest_results(self) -> Optional[dict]:
        """Get the most recent ML analysis results. Thread-safe."""
        with self._results_lock:
            return self._latest_results

    def get_results_history(self) -> list[dict]:
        """Get history of results for trend analysis."""
        with self._results_lock:
            return list(self._results_history)

    def get_ml_summary(self) -> dict:
        """Get aggregate summary of all ML models."""
        return self.ml_engine.get_summary()

    @property
    def processed_count(self) -> int:
        return self._processed_count

    @property
    def buffer_size(self) -> int:
        with self._lock:
            return len(self._buffer)

    def _process_loop(self) -> None:
        """Background processing loop."""
        while self._running:
            time.sleep(self.config.sample_interval)
            self._process_batch()

    def _process_batch(self) -> None:
        """Process buffered records through ML pipeline."""
        with self._lock:
            if not self._buffer:
                return
            # Take the latest record (most recent state)
            record = self._buffer[-1]
            self._buffer.clear()

        # Compute throughputs
        throughputs = self._compute_throughputs(record)

        # Run ML pipeline
        results = self.ml_engine.ingest(
            queue_lengths=record.queue_lengths,
            avg_speed=record.avg_speed,
            vehicles=record.vehicles,
            throughputs=throughputs,
            sim_time=record.timestamp,
        )

        # Add metadata
        results["ingress_meta"] = {
            "processed_at": time.time(),
            "sim_time": record.timestamp,
            "buffer_was": 0,  # already cleared
            "total_processed": self._processed_count,
        }

        # Store results
        with self._results_lock:
            self._latest_results = results
            self._results_history.append(results)

        self._processed_count += 1

    def _compute_throughputs(self, record: IngressRecord) -> dict[str, float]:
        """Compute per-direction throughput (vehicles/second)."""
        departed_now = record.total_departed
        departed_diff = departed_now - self._last_departed
        self._last_departed = departed_now
        self._departure_history.append(departed_diff)

        # Approximate per-direction throughput
        # (In real implementation, track per-direction departures)
        total_queue = sum(record.queue_lengths.values())
        if total_queue == 0:
            return {"north": 0.1, "south": 0.1, "east": 0.1, "west": 0.1}

        # Weight by inverse queue (directions with less queue had more throughput)
        throughputs = {}
        for d, q in record.queue_lengths.items():
            weight = 1.0 - (q / max(total_queue, 1))
            throughputs[d] = max(0.01, departed_diff * weight / 4.0)

        return throughputs

    @staticmethod
    def _compute_avg_speed(vehicles: list[dict]) -> float:
        if not vehicles:
            return 0.0
        speeds = [v.get("speed", 0) for v in vehicles]
        return float(np.mean(speeds)) if speeds else 0.0


# =============================================================================
# Synchronous ingress (for Streamlit / non-threaded use)
# =============================================================================

class SyncIngressEngine:
    """
    Synchronous version of the ingress engine for use in Streamlit.
    No background threads - call process() explicitly.
    """

    def __init__(self):
        self.ml_engine = MLEngine()
        self._results_history: list[dict] = []
        self._last_departed: int = 0

    def process(
        self,
        queue_lengths: dict[str, int],
        avg_speed: float,
        vehicles: list[dict],
        total_departed: int,
        sim_time: float,
    ) -> dict:
        """
        Process one snapshot synchronously. Returns ML results immediately.
        """
        # Compute throughput
        departed_diff = total_departed - self._last_departed
        self._last_departed = total_departed

        total_queue = sum(queue_lengths.values())
        throughputs = {}
        for d, q in queue_lengths.items():
            weight = 1.0 - (q / max(total_queue, 1)) if total_queue > 0 else 0.25
            throughputs[d] = max(0.01, departed_diff * weight / 4.0)

        results = self.ml_engine.ingest(
            queue_lengths=queue_lengths,
            avg_speed=avg_speed,
            vehicles=vehicles,
            throughputs=throughputs,
            sim_time=sim_time,
        )

        self._results_history.append(results)
        return results

    def get_history(self) -> list[dict]:
        return self._results_history

    def get_summary(self) -> dict:
        return self.ml_engine.get_summary()
