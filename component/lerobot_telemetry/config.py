"""
Configuration module for lerobot-telemetry component.

Loads configuration from environment variables (set by Greengrass) or CLI arguments.
"""

import argparse
import os
from dataclasses import dataclass
from typing import Optional


# LeRobot SO-101 joint names (6 servos)
JOINT_NAMES = [
    "shoulder_pan",
    "shoulder_lift",
    "elbow_flex",
    "wrist_flex",
    "wrist_roll",
    "gripper",
]

# Motor IDs for each joint (1-6)
MOTOR_IDS = {
    "shoulder_pan": 1,
    "shoulder_lift": 2,
    "elbow_flex": 3,
    "wrist_flex": 4,
    "wrist_roll": 5,
    "gripper": 6,
}

# Feetech STS3215 registers to read
REGISTERS = [
    "Present_Position",
    "Present_Velocity",
    "Present_Load",
    "Present_Temperature",
    "Present_Current",
]


@dataclass
class ComponentConfig:
    """Configuration for the lerobot-telemetry component."""

    device_id: str
    topic_prefix: str
    polling_rate_hz: int
    serial_port: str
    mock_mode: bool


def load_config() -> ComponentConfig:
    """
    Load configuration from CLI args (if provided) or environment variables.

    Environment variables (set by Greengrass):
    - GG_DEVICE_ID
    - GG_TOPIC_PREFIX
    - GG_POLLING_RATE_HZ
    - GG_SERIAL_PORT
    - GG_MOCK_MODE

    Returns:
        ComponentConfig instance
    """
    parser = argparse.ArgumentParser(description="LeRobot telemetry component")
    parser.add_argument("--device-id", help="Device ID (e.g., arm-001)")
    parser.add_argument("--topic-prefix", help="MQTT topic prefix (e.g., dt/lerobot)")
    parser.add_argument("--polling-rate", type=int, help="Polling rate in Hz")
    parser.add_argument("--serial-port", help="Serial port (e.g., /dev/ttyUSB0)")
    parser.add_argument("--mock", action="store_true", help="Use mock sensor data")

    args = parser.parse_args()

    # Priority: CLI args > env vars > defaults
    device_id = args.device_id or os.getenv("GG_DEVICE_ID", "arm-001")
    topic_prefix = args.topic_prefix or os.getenv("GG_TOPIC_PREFIX", "dt/lerobot")
    polling_rate_hz = args.polling_rate or int(os.getenv("GG_POLLING_RATE_HZ", "10"))
    serial_port = args.serial_port or os.getenv("GG_SERIAL_PORT", "/dev/ttyUSB0")

    # Handle mock mode (env var is string "true"/"false")
    mock_mode = args.mock or os.getenv("GG_MOCK_MODE", "false").lower() == "true"

    return ComponentConfig(
        device_id=device_id,
        topic_prefix=topic_prefix,
        polling_rate_hz=polling_rate_hz,
        serial_port=serial_port,
        mock_mode=mock_mode,
    )
