# Omniverse Digital Twin — Handoff Document

## What's Done (This Project)

The LeRobot SO-101 robotic arm is connected to AWS IoT Core via a Greengrass component that also runs as a ROS2 node. The edge publishes:

- **ROS2 topics** (local network): `/joint_states` (sensor_msgs/JointState), `/servo_diagnostics` (diagnostic_msgs/DiagnosticArray)
- **IoT Core MQTT**: `dt/lerobot/{device-id}/telemetry` (JSON with position, velocity, load, temperature, current for all 6 joints)

The component runs at configurable rate (default 10Hz) and gracefully falls back to IoT Core-only if ROS2 is not available on the host.

## What's Next (Omniverse Project)

### Goal

Create a digital twin of the SO-101 arm in NVIDIA Omniverse Isaac Sim, driven by live telemetry from the physical robot via ROS2.

### Architecture

```
Physical Robot (Edge)          AWS Cloud                    Workstation
+-------------------+   MQTT   +------------------+        +-------------------+
| ROS2 /joint_states|--------->| IoT Core         |        | Omniverse         |
| (via Greengrass)  |   TLS    |   |               |        | Isaac Sim         |
+-------------------+          |   v               |        |   |               |
                               | ROS2 Bridge       |  ROS2  |   v               |
                               | (EC2/ECS/Fargate) |------->| /joint_states     |
                               | ros2-mqtt-bridge  |        | drives URDF model |
                               +------------------+        +-------------------+
```

### Recommended Approach

1. **Cloud ROS2 Bridge**: Deploy a ROS2 node on EC2 (or AppStream for Omniverse) that:
   - Subscribes to IoT Core MQTT topic `dt/lerobot/+/telemetry`
   - Converts JSON payload back to `sensor_msgs/JointState`
   - Publishes to local ROS2 `/joint_states` topic
   - This bridges the gap between IoT Core MQTT and the ROS2 DDS network

2. **URDF Model**: Create or obtain a URDF/USD model of the SO-101 arm with the 6 joints:
   - `shoulder_pan`, `shoulder_lift`, `elbow_flex`, `wrist_flex`, `wrist_roll`, `gripper`
   - Joint limits and visual meshes from LeRobot CAD files

3. **Omniverse Isaac Sim**: Import URDF, connect to ROS2 bridge, drive joints from `/joint_states`

### Joint Mapping

| Joint Name | Motor ID | Position Range (ticks) | Approx. Range (degrees) |
|---|---|---|---|
| shoulder_pan | 1 | 0-4096 | 0-360 |
| shoulder_lift | 2 | 0-4096 | 0-360 |
| elbow_flex | 3 | 0-4096 | 0-360 |
| wrist_flex | 4 | 0-4096 | 0-360 |
| wrist_roll | 5 | 0-4096 | 0-360 |
| gripper | 6 | 0-4096 | 0-360 |

Position conversion: `radians = ticks * (2π / 4096)`

### AWS Services to Consider

| Service | Use Case |
|---|---|
| AppStream 2.0 | Stream Omniverse GUI to browser (already POC'd in appstream-omniverse project) |
| EC2 (GPU) | Run Isaac Sim headless or with NICE DCV |
| IoT Core Rules | Route telemetry to ROS2 bridge |
| Greengrass | Already deployed on edge, handles MQTT connectivity |

### Key Decisions for Next Phase

1. **Bridge deployment**: EC2 vs. container (ECS/Fargate) vs. co-locate with Omniverse on AppStream
2. **Latency requirements**: 10Hz telemetry is fine for visualization; control loop needs lower latency
3. **Multi-robot**: Current setup is single arm; scaling needs Thing Groups + namespaced topics
4. **Bidirectional control**: Current flow is read-only (telemetry). Sending commands back to the arm requires additional Greengrass subscription + servo write logic

### References

- [ROS2 MQTT Bridge](https://github.com/ika-rwth-aachen/ros2_mqtt_bridge)
- [Omniverse Isaac Sim ROS2 Bridge](https://docs.omniverse.nvidia.com/isaacsim/latest/installation/install_ros.html)
- [LeRobot SO-101 CAD](https://github.com/huggingface/lerobot)
- [AppStream Omniverse POC](../appstream-omniverse/) (sister project)
