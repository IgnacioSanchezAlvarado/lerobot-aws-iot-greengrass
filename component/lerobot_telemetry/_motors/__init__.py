"""
Vendored motor bus code for Feetech STS3215 servos.

This module provides a simplified interface for reading sensor data from
Feetech STS3215 servos over serial. Vendored to avoid dependency on full
lerobot package.
"""

from .motors_bus import FeetechMotorsBus

__all__ = ["FeetechMotorsBus"]
