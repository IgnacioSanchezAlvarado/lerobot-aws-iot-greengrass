"""
Sensor reader module for LeRobot SO-101 servos.

Reads all sensor registers from Feetech STS3215 motors via serial bus.
"""

import time
from typing import Dict

from .config import JOINT_NAMES, MOTOR_IDS, REGISTERS, ComponentConfig
from ._motors import FeetechMotorsBus


class SensorReader:
    """Reads sensor data from LeRobot SO-101 servo motors."""

    def __init__(self, config: ComponentConfig):
        """
        Initialize sensor reader.

        Args:
            config: Component configuration
        """
        self.config = config
        # Create motor_names -> motor_id mapping for FeetechMotorsBus
        self.motors = MOTOR_IDS.copy()
        self.bus = FeetechMotorsBus(port=config.serial_port, motors=self.motors)

    def connect(self):
        """Open serial connection to servo bus."""
        self.bus.connect()

    def read_all(self) -> Dict:
        """
        Read all sensor registers from all motors.

        Returns:
            Dict matching ARCHITECTURE.md payload structure:
            {
                "device_id": "arm-001",
                "timestamp": 1706000000000,
                "joints": {
                    "shoulder_pan": {"position": 2048, "velocity": 0, ...},
                    ...
                }
            }
        """
        timestamp = int(time.time() * 1000)
        joints = {}

        # Read each register across all motors
        register_data = {}
        for register in REGISTERS:
            try:
                values = self.bus.sync_read(register, JOINT_NAMES)
                register_data[register] = values
            except Exception as e:
                # If read fails, log and continue with zeros
                print(f"Warning: Failed to read {register}: {e}")
                register_data[register] = {name: 0 for name in JOINT_NAMES}

        # Build joint data structure
        for joint_name in JOINT_NAMES:
            joints[joint_name] = {
                "position": register_data["Present_Position"].get(joint_name, 0),
                "velocity": register_data["Present_Velocity"].get(joint_name, 0),
                "load": register_data["Present_Load"].get(joint_name, 0),
                "temp": register_data["Present_Temperature"].get(joint_name, 0),
                "current": register_data["Present_Current"].get(joint_name, 0),
            }

        return {
            "device_id": self.config.device_id,
            "timestamp": timestamp,
            "joints": joints,
        }

    def disconnect(self):
        """Close serial connection."""
        self.bus.disconnect()
