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
    ros2_node_name: str = "lerobot_telemetry"
    ros2_joint_states_topic: str = "/joint_states"
    ros2_servo_diagnostics_topic: str = "/servo_diagnostics"
    ros2_distro: str = "humble"


def load_config() -> ComponentConfig:
    """
    Load configuration from CLI args (if provided) or environment variables.

    Environment variables (set by Greengrass):
    - GG_DEVICE_ID
    - GG_TOPIC_PREFIX
    - GG_POLLING_RATE_HZ
    - GG_SERIAL_PORT
    - GG_MOCK_MODE
    - GG_ROS2_NODE_NAME
    - GG_ROS2_JOINT_STATES_TOPIC
    - GG_ROS2_SERVO_DIAGNOSTICS_TOPIC
    - GG_ROS2_DISTRO

    Returns:
        ComponentConfig instance
    """
    parser = argparse.ArgumentParser(description="LeRobot telemetry component")
    parser.add_argument("--device-id", help="Device ID (e.g., arm-001)")
    parser.add_argument("--topic-prefix", help="MQTT topic prefix (e.g., dt/lerobot)")
    parser.add_argument("--polling-rate", type=int, help="Polling rate in Hz")
    parser.add_argument("--serial-port", help="Serial port (e.g., /dev/ttyUSB0)")
    parser.add_argument("--mock", action="store_true", help="Use mock sensor data")
    parser.add_argument("--ros2-node-name", help="ROS2 node name")
    parser.add_argument("--ros2-joint-states-topic", help="ROS2 joint_states topic")
    parser.add_argument("--ros2-servo-diagnostics-topic", help="ROS2 servo diagnostics topic")
    parser.add_argument("--ros2-distro", help="ROS2 distribution (e.g., humble)")

    args = parser.parse_args()

    # Priority: CLI args > env vars > defaults
    device_id = args.device_id or os.getenv("GG_DEVICE_ID", "arm-001")
    topic_prefix = args.topic_prefix or os.getenv("GG_TOPIC_PREFIX", "dt/lerobot")
    polling_rate_hz = args.polling_rate or int(os.getenv("GG_POLLING_RATE_HZ", "10"))
    serial_port = args.serial_port or os.getenv("GG_SERIAL_PORT", "/dev/ttyUSB0")

    # Handle mock mode (env var is string "true"/"false")
    mock_mode = args.mock or os.getenv("GG_MOCK_MODE", "false").lower() == "true"

    # ROS2 configuration
    ros2_node_name = args.ros2_node_name or os.getenv("GG_ROS2_NODE_NAME", "lerobot_telemetry")
    ros2_joint_states_topic = args.ros2_joint_states_topic or os.getenv("GG_ROS2_JOINT_STATES_TOPIC", "/joint_states")
    ros2_servo_diagnostics_topic = args.ros2_servo_diagnostics_topic or os.getenv("GG_ROS2_SERVO_DIAGNOSTICS_TOPIC", "/servo_diagnostics")
    ros2_distro = args.ros2_distro or os.getenv("GG_ROS2_DISTRO", "humble")

    return ComponentConfig(
        device_id=device_id,
        topic_prefix=topic_prefix,
        polling_rate_hz=polling_rate_hz,
        serial_port=serial_port,
        mock_mode=mock_mode,
        ros2_node_name=ros2_node_name,
        ros2_joint_states_topic=ros2_joint_states_topic,
        ros2_servo_diagnostics_topic=ros2_servo_diagnostics_topic,
        ros2_distro=ros2_distro,
    )
