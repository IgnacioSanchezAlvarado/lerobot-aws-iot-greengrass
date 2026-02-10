"""
Main entry point for lerobot-telemetry component.

Usage: python -m lerobot_telemetry
"""

import logging
import signal
import sys
import time

from .config import load_config
from .sensor_reader import SensorReader
from .mock_reader import MockSensorReader
from .publisher import create_publisher

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("lerobot-telemetry")

# Global flag for graceful shutdown
running = True


def shutdown_handler(signum, frame):
    """Handle shutdown signals (SIGTERM, SIGINT)."""
    global running
    logger.info(f"Received signal {signum}, shutting down...")
    running = False


# Register signal handlers
signal.signal(signal.SIGTERM, shutdown_handler)
signal.signal(signal.SIGINT, shutdown_handler)


def main():
    """Main loop: read sensors and publish telemetry."""
    global running

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


if __name__ == "__main__":
    main()
