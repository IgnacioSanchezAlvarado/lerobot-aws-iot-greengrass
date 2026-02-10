"""
Publisher module for sending telemetry to AWS IoT Core.

Provides IpcPublisher (Greengrass IPC) and ConsolePublisher (stdout fallback).
"""

import json
import logging
from typing import Dict

logger = logging.getLogger(__name__)


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
