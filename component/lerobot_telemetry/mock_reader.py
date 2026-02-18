"""
Mock sensor reader for testing without hardware.

Generates realistic fake sensor data.
"""

import math
import random
import time
from typing import Dict

from .config import JOINT_NAMES, ComponentConfig


class MockSensorReader:
    """Mock sensor reader for testing without hardware."""

    def __init__(self, config: ComponentConfig):
        """
        Initialize mock reader.

        Args:
            config: Component configuration
        """
        self.config = config
        self.start_time = time.time()

    def connect(self):
        """No-op for mock reader."""
        pass

    def read_all(self) -> Dict:
        """
        Generate fake sensor data.

        Returns:
            Dict matching ARCHITECTURE.md payload structure
        """
        timestamp = int(time.time() * 1000)
        elapsed = time.time() - self.start_time
        joints = {}

        for i, joint_name in enumerate(JOINT_NAMES):
            # Generate sinusoidal position data (centered at 2048, range ±500)
            # Each joint has slightly different frequency and phase offset
            freq = 0.5 + i * 0.1
            phase = i * math.pi / 3
            position = int(2048 + 500 * math.sin(elapsed * freq + phase))

            # Random velocity (-10 to 10)
            velocity = random.randint(-10, 10)

            # Random load (5-50)
            load = random.randint(5, 50)

            # Random temperature (30-40°C)
            temp = random.randint(30, 40)

            # Random current (80-300)
            current = random.randint(80, 300)

            joints[joint_name] = {
                "position": position,
                "velocity": velocity,
                "load": load,
                "temp": temp,
                "current": current,
                "voltage": round(random.uniform(6.0, 8.4), 1),
                "status": 0,
                "moving": random.choice([0, 1]),
            }

        return {
            "device_id": self.config.device_id,
            "timestamp": timestamp,
            "joints": joints,
        }

    def disconnect(self):
        """No-op for mock reader."""
        pass
