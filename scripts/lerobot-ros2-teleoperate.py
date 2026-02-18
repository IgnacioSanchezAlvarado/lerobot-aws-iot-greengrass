#!/usr/bin/env python3
"""
ROS2 teleoperation wrapper for lerobot.

Drop-in replacement for lerobot-teleoperate that publishes:
- JointState messages (position, velocity, effort) to /joint_states at ~60Hz
- DiagnosticArray messages to /servo_diagnostics at ~10Hz

This script monkey-patches the lerobot teleop loop to intercept robot
observations and publish them as ROS2 messages with full servo telemetry.

Usage:
    python3 scripts/lerobot-ros2-teleoperate.py \
        --robot.type=so101_follower \
        --robot.port=/dev/ttyACM0 \
        --teleop.type=so101_leader \
        --teleop.port=/dev/ttyACM1

All lerobot-teleoperate arguments are supported and passed through unchanged.
"""

import functools
import logging
import sys
from typing import Any, Callable

# Initialize ROS2 BEFORE any lerobot imports
# This ensures ROS2 context is available when lerobot initializes
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile
from sensor_msgs.msg import JointState
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue


class TelemetryPublisherNode(Node):
    """ROS2 node that publishes JointState and DiagnosticArray messages."""

    def __init__(self):
        super().__init__('lerobot_telemetry_publisher')
        qos = QoSProfile(depth=10)
        self.joint_state_publisher = self.create_publisher(JointState, '/joint_states', qos)
        self.diagnostics_publisher = self.create_publisher(DiagnosticArray, '/servo_diagnostics', qos)
        self.get_logger().info('Telemetry publishers initialized on /joint_states and /servo_diagnostics')

    def publish_observation(
        self,
        observation: dict[str, Any],
        velocities: dict[str, float],
        efforts: dict[str, float]
    ) -> None:
        """
        Convert lerobot observation dict to JointState message and publish.

        Args:
            observation: Dict with keys like "shoulder_pan.pos", "gripper.pos", etc.
                        Values are normalized/calibrated floats (NOT raw servo ticks).
            velocities: Dict mapping joint names to velocity values
            efforts: Dict mapping joint names to effort (load) values
        """
        msg = JointState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = ''  # No specific frame, joints are robot-relative

        # Extract all position keys (keys ending in .pos)
        joint_names = []
        joint_positions = []
        joint_velocities = []
        joint_efforts = []

        for key, value in observation.items():
            if key.endswith('.pos'):
                # Extract joint name (everything before .pos)
                joint_name = key[:-4]  # Remove '.pos' suffix
                joint_names.append(joint_name)
                joint_positions.append(float(value))
                joint_velocities.append(velocities.get(joint_name, 0.0))
                joint_efforts.append(efforts.get(joint_name, 0.0))

        msg.name = joint_names
        msg.position = joint_positions
        msg.velocity = joint_velocities
        msg.effort = joint_efforts

        self.joint_state_publisher.publish(msg)

    def publish_diagnostics(self, diag_data: dict[str, dict[str, Any]]) -> None:
        """
        Publish servo diagnostics as DiagnosticArray message.

        Args:
            diag_data: Dict mapping joint names to dicts with keys:
                      temperature, voltage, current, status, moving
        """
        msg = DiagnosticArray()
        msg.header.stamp = self.get_clock().now().to_msg()

        for joint_name, data in diag_data.items():
            status = DiagnosticStatus()
            status.name = f"servo/{joint_name}"
            status.level = DiagnosticStatus.OK
            status.message = "OK"

            # Add each diagnostic value as a KeyValue pair
            status.values = [
                KeyValue(key="temperature", value=str(data.get("temperature", 0.0))),
                KeyValue(key="voltage", value=str(data.get("voltage", 0.0))),
                KeyValue(key="current", value=str(data.get("current", 0.0))),
                KeyValue(key="status", value=str(data.get("status", 0))),
                KeyValue(key="moving", value=str(data.get("moving", 0))),
            ]

            msg.status.append(status)

        self.diagnostics_publisher.publish(msg)


# Global node instance (initialized in main)
_ros_node: TelemetryPublisherNode | None = None

# Saved reference to the ORIGINAL teleop_loop (before monkey-patching)
_original_teleop_loop = None


def create_observation_wrapper(
    original_get_observation: Callable[[], dict[str, Any]],
    robot
) -> Callable[[], dict[str, Any]]:
    """
    Create a wrapper for robot.get_observation that publishes full telemetry as a side-effect.

    Args:
        original_get_observation: The robot's original get_observation method
        robot: The robot instance (needed for robot.bus access)

    Returns:
        Wrapped version that publishes to ROS2 before returning observation
    """
    _frame_count = 0

    @functools.wraps(original_get_observation)
    def wrapped_get_observation() -> dict[str, Any]:
        nonlocal _frame_count

        # Call original method
        observation = original_get_observation()

        # Publish to ROS2 as side-effect
        if _ros_node is not None:
            try:
                # Extract joint names from observation
                joint_names = [key[:-4] for key in observation.keys() if key.endswith('.pos')]

                # Read velocity and load every frame
                velocities = {}
                efforts = {}
                try:
                    velocities = robot.bus.sync_read("Present_Velocity", normalize=False)
                except Exception as e:
                    _ros_node.get_logger().debug(f'Failed to read Present_Velocity: {e}')
                    velocities = {}

                try:
                    efforts = robot.bus.sync_read("Present_Load", normalize=False)
                except Exception as e:
                    _ros_node.get_logger().debug(f'Failed to read Present_Load: {e}')
                    efforts = {}

                # Publish JointState with position, velocity, and effort
                _ros_node.publish_observation(observation, velocities, efforts)

                # Read diagnostics every 6th frame
                if _frame_count % 6 == 0:
                    diag_data = {}

                    # Read all diagnostic registers
                    temperatures = {}
                    voltages = {}
                    currents = {}
                    statuses = {}
                    movings = {}

                    try:
                        temperatures = robot.bus.sync_read("Present_Temperature", normalize=False)
                    except Exception as e:
                        _ros_node.get_logger().debug(f'Failed to read Present_Temperature: {e}')

                    try:
                        voltages = robot.bus.sync_read("Present_Voltage", normalize=False)
                    except Exception as e:
                        _ros_node.get_logger().debug(f'Failed to read Present_Voltage: {e}')

                    try:
                        currents = robot.bus.sync_read("Present_Current", normalize=False)
                    except Exception as e:
                        _ros_node.get_logger().debug(f'Failed to read Present_Current: {e}')

                    try:
                        statuses = robot.bus.sync_read("Status", normalize=False)
                    except Exception as e:
                        _ros_node.get_logger().debug(f'Failed to read Status: {e}')

                    try:
                        movings = robot.bus.sync_read("Moving", normalize=False)
                    except Exception as e:
                        _ros_node.get_logger().debug(f'Failed to read Moving: {e}')

                    # Build per-joint diagnostic data
                    for joint_name in joint_names:
                        diag_data[joint_name] = {
                            "temperature": temperatures.get(joint_name, 0.0),
                            "voltage": voltages.get(joint_name, 0.0),
                            "current": currents.get(joint_name, 0.0),
                            "status": statuses.get(joint_name, 0),
                            "moving": movings.get(joint_name, 0),
                        }

                    # Publish diagnostics
                    _ros_node.publish_diagnostics(diag_data)

                _frame_count += 1

            except Exception as e:
                # Don't let ROS2 publishing errors crash the teleop loop
                _ros_node.get_logger().error(f'Failed to publish telemetry: {e}')

        return observation

    return wrapped_get_observation


def patched_teleop_loop(
    teleop,
    robot,
    fps: int,
    teleop_action_processor,
    robot_action_processor,
    robot_observation_processor,
    display_data: bool = False,
    duration: float | None = None,
    display_compressed_images: bool = False,
):
    """
    Patched version of lerobot's teleop_loop that wraps robot.get_observation
    to publish JointState and DiagnosticArray messages.

    All arguments are passed through to the original teleop_loop unchanged.
    """
    # Use the saved reference to avoid infinite recursion
    # (the module-level teleop_loop has been replaced with this function)
    original_teleop_loop = _original_teleop_loop

    # Wrap the robot's get_observation method
    original_get_observation = robot.get_observation
    robot.get_observation = create_observation_wrapper(original_get_observation, robot)

    try:
        # Call the original teleop_loop with the patched robot
        original_teleop_loop(
            teleop=teleop,
            robot=robot,
            fps=fps,
            teleop_action_processor=teleop_action_processor,
            robot_action_processor=robot_action_processor,
            robot_observation_processor=robot_observation_processor,
            display_data=display_data,
            duration=duration,
            display_compressed_images=display_compressed_images,
        )
    finally:
        # Restore original method on exit
        robot.get_observation = original_get_observation


def main():
    """Main entry point that initializes ROS2, patches lerobot, and runs teleoperation."""
    global _ros_node, _original_teleop_loop

    # Initialize ROS2
    rclpy.init()
    _ros_node = TelemetryPublisherNode()

    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    logger.info('ROS2 teleoperation wrapper starting')
    logger.info(f'Arguments: {sys.argv[1:]}')

    try:
        # Import lerobot modules AFTER ROS2 initialization
        from lerobot.scripts import lerobot_teleoperate

        # Save original and monkey-patch the teleop_loop function
        _original_teleop_loop = lerobot_teleoperate.teleop_loop
        lerobot_teleoperate.teleop_loop = patched_teleop_loop

        logger.info('Monkey-patched lerobot_teleoperate.teleop_loop')
        logger.info('Starting lerobot teleoperation (will publish to /joint_states and /servo_diagnostics)')

        # Call lerobot's main() which handles CLI parsing and everything else
        lerobot_teleoperate.main()

    except KeyboardInterrupt:
        logger.info('Interrupted by user')
    except Exception as e:
        logger.error(f'Error during teleoperation: {e}', exc_info=True)
        raise
    finally:
        # Clean up ROS2
        logger.info('Shutting down ROS2')
        if _ros_node is not None:
            _ros_node.destroy_node()
        rclpy.shutdown()
        logger.info('ROS2 teleoperation wrapper stopped')


if __name__ == '__main__':
    main()
