"""
Indian Traffic Simulation Engine
================================
Microscopic traffic flow using IDM + MOBIL, calibrated for Indian roads.
Includes 4-way intersection with adaptive traffic light control.
Features ML-powered data ingress engine for real-time analytics.

Usage:
    python -m engine          # Headless with telemetry DB
    python -m engine --viz    # Terminal visualization
    python -m engine --web    # Browser UI (4-way intersection)
    streamlit run app.py      # Full dashboard with Traffic UI + ML Ingress
"""
from engine.models import VehicleType, VehicleProfile, VehicleState, TelemetryRecord, VEHICLE_PROFILES
from engine.simulation import Simulation
from engine.intersection import Intersection, Direction, AdaptiveController
from engine.telemetry import TelemetryWriter
from engine.ml_models import MLEngine
from engine.ingress import DataIngressEngine, SyncIngressEngine

__all__ = [
    "Simulation", "Intersection", "Direction", "AdaptiveController",
    "TelemetryWriter", "VehicleType", "VehicleProfile", "VehicleState",
    "TelemetryRecord", "VEHICLE_PROFILES",
    "MLEngine", "DataIngressEngine", "SyncIngressEngine",
]
