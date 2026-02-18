"""
Publisher module for sending telemetry to AWS IoT Core.

Provides IpcPublisher (Greengrass IPC) and ConsolePublisher (stdout fallback).
Also provides Ros2Publisher for ROS2 topic publishing.
"""

import json
import logging
import math
from typing import Dict, List

logger = logging.getLogger(__name__)

# Try to import ROS2 message types (optional dependency)
try:
    from sensor_msgs.msg import JointState
    from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
    from builtin_interfaces.msg import Time
    ROS2_AVAILABLE = True
except ImportError:
    ROS2_AVAILABLE = False
    logger.debug("ROS2 message types not available (rclpy not installed)")


class IpcPublisher:
    """Publishes telemetry to AWS IoT Core via Greengrass IPC."""

    def __init__(self):
        """Initialize Greengrass IPC client."""
        from awsiot.greengrasscoreipc.clientv2 import GreengrassCoreIPCClientV2

        self.client = GreengrassCoreIPCClientV2()
        logger.info("Initialized Greengrass IPC publisher")

    def publish(self, topic: str, payload: Dict):
        """
        Publish message to IoT Core via IPC.

        Args:
            topic: MQTT topic
            payload: Message payload (dict)
        """
        message = json.dumps(payload)
        self.client.publish_to_iot_core(topic_name=topic, qos="0", payload=message)

    def close(self):
        """Close IPC client."""
        if hasattr(self, "client"):
            self.client.close()


class ConsolePublisher:
    """Fallback publisher that prints to stdout (for local testing)."""

    def __init__(self):
        """Initialize console publisher."""
        logger.info("Initialized console publisher (not running in Greengrass)")

    def publish(self, topic: str, payload: Dict):
        """
        Print message to stdout.

        Args:
            topic: MQTT topic
            payload: Message payload (dict)
        """
        output = {
            "topic": topic,
            "payload": payload,
        }
        print(json.dumps(output, indent=2))

    def close(self):
        """No-op for console publisher."""
        pass


class Ros2Publisher:
    """Publishes telemetry to ROS2 topics (JointState and DiagnosticArray)."""

    def __init__(self, node, joint_states_topic: str, servo_diagnostics_topic: str, temp_warning_threshold: int = 50):
        """
        Initialize ROS2 publishers.

        Args:
            node: rclpy.node.Node instance
            joint_states_topic: Topic for JointState messages
            servo_diagnostics_topic: Topic for DiagnosticArray messages
            temp_warning_threshold: Temperature warning threshold in Celsius (default: 50)
        """
        if not ROS2_AVAILABLE:
            raise ImportError("ROS2 message types not available (rclpy not installed)")

        self.node = node
        self.temp_warning_threshold = temp_warning_threshold
        self.joint_pub = node.create_publisher(JointState, joint_states_topic, 10)
        self.diag_pub = node.create_publisher(DiagnosticArray, servo_diagnostics_topic, 10)
        logger.info(f"Initialized ROS2 publishers: joint_states={joint_states_topic}, diagnostics={servo_diagnostics_topic}")

    def publish_joint_states(self, data: Dict, joint_names: List[str]):
        """
        Publish JointState message.

        Args:
            data: Sensor data dict with "joints" key
            joint_names: List of joint names in order
        """
        msg = JointState()
        msg.header.stamp = self.node.get_clock().now().to_msg()
        msg.header.frame_id = "base_link"
        msg.name = joint_names

        # Convert raw servo values to radians and extract velocity/load
        positions = []
        velocities = []
        efforts = []

        for joint_name in joint_names:
            joint_data = data["joints"].get(joint_name, {})

            # Convert position: servo ticks (0-4096) to radians (0-2π)
            position_ticks = joint_data.get("position", 0)
            position_rad = position_ticks * (2 * math.pi / 4096)
            positions.append(position_rad)

            # Convert velocity: servo ticks/s to rad/s
            velocity_ticks = joint_data.get("velocity", 0)
            velocity_rad = velocity_ticks * (2 * math.pi / 4096)
            velocities.append(velocity_rad)

            # Load as effort (float)
            load = float(joint_data.get("load", 0))
            efforts.append(load)

        msg.position = positions
        msg.velocity = velocities
        msg.effort = efforts

        self.joint_pub.publish(msg)

    def publish_diagnostics(self, data: Dict, joint_names: List[str]):
        """
        Publish DiagnosticArray message with servo status.

        Args:
            data: Sensor data dict with "joints" key
            joint_names: List of joint names
        """
        msg = DiagnosticArray()
        msg.header.stamp = self.node.get_clock().now().to_msg()

        for joint_name in joint_names:
            joint_data = data["joints"].get(joint_name, {})

            temp = joint_data.get("temp", 0)
            current = joint_data.get("current", 0)
            voltage = joint_data.get("voltage", 0)
            hw_status = joint_data.get("status", 0)
            moving = joint_data.get("moving", 0)

            status = DiagnosticStatus()
            status.name = f"servo/{joint_name}"

            # Set level and message based on temperature
            if temp > self.temp_warning_threshold:
                status.level = DiagnosticStatus.WARN
                status.message = "High temperature"
            else:
                status.level = DiagnosticStatus.OK
                status.message = "OK"

            # Add temperature, current, voltage, status, and moving as key-value pairs
            status.values = [
                KeyValue(key="temperature", value=str(temp)),
                KeyValue(key="current", value=str(current)),
                KeyValue(key="voltage", value=str(voltage)),
                KeyValue(key="status", value=str(hw_status)),
                KeyValue(key="moving", value=str(moving)),
            ]

            msg.status.append(status)

        self.diag_pub.publish(msg)

    def close(self):
        """No-op for ROS2 publisher (node handles cleanup)."""
        pass


def create_publisher():
    """
    Create appropriate publisher instance.

    Returns IpcPublisher if running in Greengrass, otherwise ConsolePublisher.

    Returns:
        Publisher instance
    """
    try:
        return IpcPublisher()
    except Exception as e:
        logger.warning(f"Failed to create IPC publisher: {e}")
        logger.info("Using console publisher instead")
        return ConsolePublisher()
