"""
ROS2 subscriber module for LeRobot telemetry.

Subscribes to JointState and DiagnosticArray messages from the LeRobot wrapper
and converts them to the telemetry JSON format for forwarding to AWS IoT Core.

IMPORTANT: Position values from the LeRobot wrapper are NORMALIZED FLOATS
(lerobot's calibrated values in degrees or radians), NOT raw servo ticks (0-4096).
This differs from the 'serial' mode which reads raw hardware registers.
"""

import logging
import time
from typing import Callable, Dict

from sensor_msgs.msg import JointState
from diagnostic_msgs.msg import DiagnosticArray

logger = logging.getLogger(__name__)


class Ros2Subscriber:
    """Subscribes to ROS2 JointState and DiagnosticArray topics and converts to telemetry format."""

    def __init__(self, node, topic: str, diagnostics_topic: str, device_id: str, callback: Callable[[Dict], None]):
        """
        Initialize ROS2 subscriber.

        Args:
            node: ROS2 node instance (rclpy.node.Node)
            topic: JointState topic name (e.g., "/joint_states")
            diagnostics_topic: DiagnosticArray topic name (e.g., "/servo_diagnostics")
            device_id: Device identifier (e.g., "arm-001")
            callback: Function to call with telemetry payload dict
        """
        self.node = node
        self.device_id = device_id
        self.callback = callback

        # Storage for latest diagnostic data per joint
        self._latest_diagnostics: Dict = {}

        # Create subscription to JointState topic
        self.subscription = node.create_subscription(
            JointState,
            topic,
            self._joint_state_callback,
            10  # QoS depth
        )

        # Create subscription to DiagnosticArray topic
        self.diagnostics_subscription = node.create_subscription(
            DiagnosticArray,
            diagnostics_topic,
            self._diagnostics_callback,
            10  # QoS depth
        )

        logger.info(f"Subscribed to {topic} (JointState) and {diagnostics_topic} (DiagnosticArray) for device {device_id}")

    def _diagnostics_callback(self, msg: DiagnosticArray):
        """
        ROS2 callback for DiagnosticArray messages.

        Extracts servo diagnostic data (temperature, voltage, current, status, moving)
        and stores it for merging with JointState data.

        DiagnosticStatus format:
        - name: "servo/<joint_name>" (e.g., "servo/shoulder_pan")
        - values: List of KeyValue pairs with diagnostic data
        """
        try:
            for status in msg.status:
                # Extract joint name from "servo/<joint_name>" format
                if status.name.startswith("servo/"):
                    joint_name = status.name[len("servo/"):]

                    # Parse KeyValue pairs
                    diag_data = {}
                    for kv in status.values:
                        # Convert string values to appropriate numeric types
                        if kv.key in ["temperature", "voltage", "current"]:
                            diag_data[kv.key] = float(kv.value) if kv.value else 0.0
                        elif kv.key in ["status", "moving"]:
                            diag_data[kv.key] = int(kv.value) if kv.value else 0
                        else:
                            diag_data[kv.key] = kv.value

                    # Store latest diagnostics for this joint
                    self._latest_diagnostics[joint_name] = diag_data

        except Exception as e:
            logger.error(f"Error in DiagnosticArray callback: {e}", exc_info=True)

    def _joint_state_callback(self, msg: JointState):
        """
        ROS2 callback for JointState messages.

        Converts JointState to telemetry format, merges with latest diagnostics,
        and calls user callback.

        JointState fields:
        - name: List of joint names
        - position: List of joint positions (normalized floats, NOT raw servo ticks)
        - velocity: List of joint velocities
        - effort: List of joint efforts (maps to "load" in telemetry)

        Diagnostic fields (merged from DiagnosticArray):
        - temp: Temperature from diagnostics
        - voltage: Voltage from diagnostics
        - current: Current from diagnostics
        - status: Hardware status from diagnostics
        - moving: Moving flag from diagnostics
        """
        try:
            # Build joints dict from JointState message
            joints = {}

            for i, joint_name in enumerate(msg.name):
                # Extract values (use 0 if index out of bounds)
                position = msg.position[i] if i < len(msg.position) else 0.0
                velocity = msg.velocity[i] if i < len(msg.velocity) else 0.0
                effort = msg.effort[i] if i < len(msg.effort) else 0.0

                # Merge with latest diagnostics for this joint
                diag = self._latest_diagnostics.get(joint_name, {})

                joints[joint_name] = {
                    "position": position,
                    "velocity": velocity,
                    "load": effort,
                    "temp": diag.get("temperature", 0),
                    "voltage": diag.get("voltage", 0),
                    "current": diag.get("current", 0),
                    "status": diag.get("status", 0),
                    "moving": diag.get("moving", 0),
                }

            # Build telemetry payload
            timestamp = int(time.time() * 1000)
            payload = {
                "device_id": self.device_id,
                "timestamp": timestamp,
                "joints": joints,
            }

            # Call user callback with payload
            self.callback(payload)

        except Exception as e:
            logger.error(f"Error in JointState callback: {e}", exc_info=True)
