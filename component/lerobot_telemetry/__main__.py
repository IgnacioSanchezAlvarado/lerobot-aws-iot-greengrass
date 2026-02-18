"""
Main entry point for lerobot-telemetry component.

Usage: python -m lerobot_telemetry
"""

import logging
import signal
import sys
import time
from typing import Dict

from .config import load_config, JOINT_NAMES
from .sensor_reader import SensorReader
from .mock_reader import MockSensorReader
from .publisher import create_publisher

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("lerobot-telemetry")

# Try to import rclpy (optional dependency for ROS2 support)
try:
    import rclpy
    from rclpy.node import Node
    from .publisher import Ros2Publisher
    ROS2_AVAILABLE = True
except ImportError:
    ROS2_AVAILABLE = False
    logger.info("ROS2 (rclpy) not available - running without ROS2 topic publishing")


# ROS2 node class and main function — only defined when rclpy is available
if ROS2_AVAILABLE:
    from .ros2_subscriber import Ros2Subscriber

    class LeRobotTelemetryNode(Node):
        """ROS2 node that reads LeRobot servo data and publishes to ROS2 topics and IoT Core."""

        def __init__(self):
            """Initialize the ROS2 node."""
            # Load configuration first to get node name
            self.config = load_config()

            # Initialize ROS2 node
            super().__init__(self.config.ros2_node_name)

            self.get_logger().info(f"Configuration loaded: device_id={self.config.device_id}, rate={self.config.polling_rate_hz}Hz, mock={self.config.mock_mode}")

            # Create reader (real or mock)
            if self.config.mock_mode:
                self.reader = MockSensorReader(self.config)
                self.get_logger().info("Using mock sensor reader (no hardware)")
            else:
                self.reader = SensorReader(self.config)
                self.get_logger().info(f"Using real sensor reader: serial_port={self.config.serial_port}")

            # Connect to hardware
            try:
                self.reader.connect()
                self.get_logger().info("Connected to sensor reader")
            except Exception as e:
                self.get_logger().error(f"Failed to connect to sensors: {e}")
                raise

            # Create IPC publisher (for AWS IoT Core)
            self.ipc_pub = create_publisher()

            # Create ROS2 publisher
            self.ros2_pub = Ros2Publisher(
                self,
                self.config.ros2_joint_states_topic,
                self.config.ros2_servo_diagnostics_topic,
                self.config.temp_warning_threshold
            )

            # Build IoT Core topic string
            self.topic = f"{self.config.topic_prefix}/{self.config.device_id}/telemetry"

            # Create timer for periodic sensor reading
            timer_period = 1.0 / self.config.polling_rate_hz
            self.timer = self.create_timer(timer_period, self.timer_callback)

            self.get_logger().info(f"Starting telemetry loop: topic={self.topic}, rate={self.config.polling_rate_hz}Hz")

        def timer_callback(self):
            """Timer callback to read sensors and publish data."""
            try:
                # Read sensor data
                data = self.reader.read_all()

                # Publish to ROS2 topics
                self.ros2_pub.publish_joint_states(data, JOINT_NAMES)
                self.ros2_pub.publish_diagnostics(data, JOINT_NAMES)

                # Publish to IoT Core
                self.ipc_pub.publish(self.topic, data)

            except Exception as e:
                self.get_logger().error(f"Error in telemetry loop: {e}", exc_info=True)

        def destroy_node(self):
            """Clean up resources before node shutdown."""
            self.get_logger().info("Shutting down node...")
            self.reader.disconnect()
            self.ipc_pub.close()
            super().destroy_node()

    class LeRobotRos2SubscriberNode(Node):
        """ROS2 node that subscribes to JointState messages and forwards to IoT Core."""

        def __init__(self, config: "ComponentConfig"):
            """Initialize the ROS2 subscriber node."""
            super().__init__(config.ros2_node_name)
            self.config = config

            self.get_logger().info(f"Configuration loaded: device_id={config.device_id}, mode=ros2, rate_limit={config.polling_rate_hz}Hz")

            # Create IPC publisher (for AWS IoT Core)
            self.ipc_pub = create_publisher()

            # Build IoT Core topic string
            self.topic = f"{config.topic_prefix}/{config.device_id}/telemetry"

            # Rate limiting state
            self.last_publish_time = 0
            self.min_publish_interval = 1.0 / config.polling_rate_hz

            # Create ROS2 subscriber
            self.subscriber = Ros2Subscriber(
                self,
                config.ros2_joint_states_topic,
                config.ros2_servo_diagnostics_topic,
                config.device_id,
                self._telemetry_callback
            )

            self.get_logger().info(f"Subscribed to {config.ros2_joint_states_topic} (JointState) and {config.ros2_servo_diagnostics_topic} (DiagnosticArray), forwarding to {self.topic}")
            self.msg_count = 0
            self.publish_count = 0

        def _telemetry_callback(self, payload: Dict):
            """
            Callback from Ros2Subscriber with telemetry payload.

            Rate-limits forwarding to IoT Core based on polling_rate_hz.
            """
            try:
                self.msg_count += 1

                # Log first message and then every 100th
                if self.msg_count == 1:
                    self.get_logger().info(f"First JointState message received! joints={list(payload.get('joints', {}).keys())}")
                elif self.msg_count % 100 == 0:
                    self.get_logger().info(f"Received {self.msg_count} messages, published {self.publish_count} to IoT Core")

                # Rate limiting - only forward if enough time has elapsed
                current_time = time.time()
                elapsed = current_time - self.last_publish_time

                if elapsed >= self.min_publish_interval:
                    # Publish to IoT Core
                    self.ipc_pub.publish(self.topic, payload)
                    self.last_publish_time = current_time
                    self.publish_count += 1
                else:
                    # Skip this message (too soon)
                    pass

            except Exception as e:
                self.get_logger().error(f"Error forwarding telemetry: {e}", exc_info=True)

        def destroy_node(self):
            """Clean up resources before node shutdown."""
            self.get_logger().info("Shutting down subscriber node...")
            self.ipc_pub.close()
            super().destroy_node()

    def main_with_ros2():
        """Main function with ROS2 support."""
        rclpy.init()
        node = None

        try:
            node = LeRobotTelemetryNode()
            rclpy.spin(node)
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        except Exception as e:
            logger.error(f"Error in main loop: {e}", exc_info=True)
            sys.exit(1)
        finally:
            if node is not None:
                node.destroy_node()
            rclpy.shutdown()
            logger.info("Shutdown complete")


def main_ros2_subscriber(config: "ComponentConfig"):
    """Main function for ROS2 subscriber mode."""
    if not ROS2_AVAILABLE:
        logger.error("ROS2 subscriber mode requires rclpy, but it is not available")
        sys.exit(1)

    rclpy.init()
    node = None

    try:
        node = LeRobotRos2SubscriberNode(config)
        rclpy.spin(node)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Error in ROS2 subscriber: {e}", exc_info=True)
        sys.exit(1)
    finally:
        if node is not None:
            node.destroy_node()
        rclpy.shutdown()
        logger.info("Shutdown complete")


def main_without_ros2():
    """Fallback main function without ROS2 (original behavior)."""
    # Global flag for graceful shutdown
    running = True

    def shutdown_handler(signum, frame):
        """Handle shutdown signals (SIGTERM, SIGINT)."""
        nonlocal running
        logger.info(f"Received signal {signum}, shutting down...")
        running = False

    # Register signal handlers
    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)

    # Load configuration
    config = load_config()
    logger.info(f"Configuration loaded: device_id={config.device_id}, rate={config.polling_rate_hz}Hz, mock={config.mock_mode}")

    # Create reader (real or mock)
    if config.mock_mode:
        reader = MockSensorReader(config)
        logger.info("Using mock sensor reader (no hardware)")
    else:
        reader = SensorReader(config)
        logger.info(f"Using real sensor reader: serial_port={config.serial_port}")

    # Create publisher (IPC or console)
    publisher = create_publisher()

    # Build topic name
    topic = f"{config.topic_prefix}/{config.device_id}/telemetry"

    # Calculate loop interval
    interval = 1.0 / config.polling_rate_hz

    # Connect to hardware
    try:
        reader.connect()
        logger.info(f"Starting telemetry loop: topic={topic}, rate={config.polling_rate_hz}Hz")
    except Exception as e:
        logger.error(f"Failed to connect to sensors: {e}")
        sys.exit(1)

    # Main loop
    try:
        while running:
            loop_start = time.time()

            try:
                # Read sensor data
                payload = reader.read_all()

                # Publish to IoT Core
                publisher.publish(topic, payload)

            except Exception as e:
                logger.error(f"Error in telemetry loop: {e}", exc_info=True)

            # Sleep to maintain polling rate
            elapsed = time.time() - loop_start
            sleep_time = max(0, interval - elapsed)
            if sleep_time > 0:
                time.sleep(sleep_time)

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        # Cleanup
        reader.disconnect()
        publisher.close()
        logger.info("Shutdown complete")


def main():
    """Main entry point - check mode and dispatch to appropriate handler."""
    config = load_config()

    if config.mode == "ros2":
        logger.info("Running in ROS2 subscriber mode")
        main_ros2_subscriber(config)
    elif ROS2_AVAILABLE:
        logger.info("Running in serial mode with ROS2 support")
        main_with_ros2()
    else:
        logger.warning("Running without ROS2 support - only publishing to IoT Core")
        main_without_ros2()


if __name__ == "__main__":
    main()
