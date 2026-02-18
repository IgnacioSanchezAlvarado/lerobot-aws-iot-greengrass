# Architecture

This document details the architecture for each operating mode of the LeRobot IoT Greengrass component.

## Mode: serial (direct hardware)

In serial mode, the Greengrass component directly reads servo registers from the LeRobot SO-101 arm via USB serial. It publishes telemetry data to both local ROS2 topics (for ecosystem integration) and AWS IoT Core.

```
Robot Host                           AWS Cloud
+---------------------------------+  +---------------------------+
| LeRobot SO-101 arm              |  | AWS IoT Core              |
| (6x Feetech STS3215 servos)    |  |   MQTT Broker             |
|      | USB serial                 |  |                           |
|      v                          |  | Topic:                    |
| Greengrass Component:           |  | dt/lerobot/+/telemetry    |
|  - Reads servo registers        |  |                           |
|  - Publishes ROS2 topics ------>|  | IoT Rules (optional)      |
|  - Forwards to IoT Core --------|->| route to S3, Timestream,  |
|                            TLS  |  | Lambda, etc.              |
| Greengrass Core v2              |  |                           |
+---------------------------------+  +---------------------------+
```

## Mode: ros2 (subscriber)

In ROS2 mode, the component subscribes to ROS2 topics published by the `lerobot-ros2-teleoperate.py` wrapper script. This mode is designed for use when running lerobot teleoperation and you want to forward telemetry to AWS IoT Core.

```
Robot Host                           AWS Cloud
+---------------------------------+  +---------------------------+
| lerobot-ros2-teleoperate.py     |  |                           |
|  - Wraps lerobot teleoperate    |  | AWS IoT Core              |
|  - Publishes ROS2 topics        |  |   MQTT Broker             |
|      |                          |  |                           |
|      v                          |  | Topic:                    |
| Greengrass Component:           |  | dt/lerobot/+/telemetry    |
|  - Subscribes to:               |  |                           |
|    /joint_states                |  | IoT Rules (optional)      |
|    /servo_diagnostics           |  | route to S3, Timestream,  |
|  - Merges & forwards -----------|->| Lambda, etc.              |
|                            TLS  |  |                           |
| Greengrass Core v2              |  |                           |
+---------------------------------+  +---------------------------+
```

## Mode: mock (testing)

In mock mode, the component generates synthetic servo data without requiring physical hardware. This mode is useful for development and integration testing.

```
Robot Host                           AWS Cloud
+---------------------------------+  +---------------------------+
|                                 |  |                           |
| Greengrass Component:           |  | AWS IoT Core              |
|  - Generates synthetic data     |  |   MQTT Broker             |
|  - Forwards to IoT Core --------|->|                           |
|                            TLS  |  | Topic:                    |
|                                 |  | dt/lerobot/+/telemetry    |
| Greengrass Core v2              |  |                           |
+---------------------------------+  +---------------------------+
```
