# Architecture: LeRobot SO-101 → AWS IoT Core

## Summary

Connect a LeRobot SO-101 robotic arm to AWS IoT Core via Greengrass v2. A single Greengrass component reads servo sensor data using the LeRobot Python API and publishes it to IoT Core over MQTT. That's it.

Greengrass v2 provides the edge runtime: device identity, MQTT connectivity, store-and-forward, component lifecycle, and a foundation for future edge ML.

```
Robot Host                                  AWS Cloud
+------------------------------------+      +-------------------------+
|                                    |      |                         |
|  LeRobot SO-101                    |      |  AWS IoT Core           |
|  (6x Feetech STS3215, USB serial) |      |    MQTT Broker          |
|       |                            |      |                         |
|       v                            |      |  Receives messages on:  |
|  Greengrass Component:             |      |  dt/lerobot/+/telemetry |
|  lerobot-telemetry                 |      |                         |
|  (Python: reads sensors,           | MQTT |  IoT Rules can route    |
|   publishes to IoT Core via IPC)   |----->|  to any AWS service     |
|       |                            | TLS  |  (Timestream, S3, etc.) |
|  Greengrass Core v2                |      |  when needed later      |
|  (nucleus, MQTT bridge)            |      |                         |
+------------------------------------+      +-------------------------+
```

## Hardware

- **LeRobot SO-101**: 6-DOF arm, ~$110, 3D-printed, open-source (HuggingFace)
- **6x Feetech STS3215** servo motors on USB serial bus (1Mbps)
- **Joints**: shoulder_pan, shoulder_lift, elbow_flex, wrist_flex, wrist_roll, gripper

### Sensor Data Per Motor

| Register | Description |
|---|---|
| Present_Position | Current joint angle |
| Present_Velocity | Angular velocity |
| Present_Load | Load/torque |
| Present_Temperature | Motor temp (°C) |
| Present_Current | Current draw |

LeRobot's `get_observation()` only reads position. Our component uses `sync_read` for all registers.

## Components

### 1. Greengrass Component: lerobot-telemetry (Python)

Single component that:
- Initializes SO-101 via LeRobot Python API (`SO101Follower`)
- Reads all sensor registers at configurable rate (default: 10Hz)
- Publishes JSON to IoT Core via Greengrass IPC
- No ROS2, no Docker — just Python + LeRobot + awsiotsdk

### 2. Greengrass Core v2 (on robot host)

- **Nucleus**: Component lifecycle
- **MQTT Bridge**: Routes IPC publishes to IoT Core
- **Token Exchange**: IAM credentials on device
- Device provisioned via installer script (not CDK)

### 3. AWS IoT Core

- **IoT Thing**: `lerobot-{device-id}` (Greengrass core device)
- **IoT Policy**: Publish to `dt/lerobot/{device-id}/*`
- **MQTT Topic**: `dt/lerobot/{device-id}/telemetry`

### MQTT Payload

```json
{
  "device_id": "arm-001",
  "timestamp": 1706000000000,
  "joints": {
    "shoulder_pan": {"position": 2048, "velocity": 0, "load": 12, "temp": 35, "current": 150},
    "shoulder_lift": {"position": 1800, "velocity": 5, "load": 45, "temp": 38, "current": 280},
    "elbow_flex": {"position": 2200, "velocity": 3, "load": 30, "temp": 36, "current": 200},
    "wrist_flex": {"position": 2100, "velocity": 0, "load": 8, "temp": 33, "current": 120},
    "wrist_roll": {"position": 2048, "velocity": 0, "load": 5, "temp": 32, "current": 100},
    "gripper": {"position": 1500, "velocity": 0, "load": 15, "temp": 34, "current": 160}
  }
}
```

## AWS Services

| Service | Purpose |
|---|---|
| IoT Core | MQTT broker, device auth, rules engine |
| IoT Greengrass v2 | Edge runtime, component deployment, MQTT bridge |
| IAM | Greengrass device role (Token Exchange) |

Three services. IoT Rules can route to any downstream service (Timestream, S3, Lambda, etc.) when needed — no changes to the edge required.

## Security

- X.509 mutual TLS via Greengrass provisioning (no passwords or API keys)
- IoT Policy: least privilege, device publishes only to its own topic prefix
- Token Exchange: temporary IAM credentials on device
- No public endpoints

## CDK Notes

- Greengrass: L1 only (`CfnComponentVersion`, `CfnDeployment`) — sufficient
- IoT Core: L2 constructs available
- Greengrass device provisioning happens on the device via installer script
- CDK outputs (IoT endpoint, Thing name, role alias) feed into provisioning script
- Ref: `aws-samples/aws-iot-greengrass-v2-using-aws-cdk`

## Open Questions

1. **Polling rate**: 5 registers × 6 motors at 10Hz over 1Mbps serial — needs validation
2. **LeRobot API stability**: Library under active development, motor APIs may change
3. **Multi-robot**: Current design is single arm. Scaling needs Thing Groups + parameterized deployments

## References

| Resource | Link |
|---|---|
| HuggingFace LeRobot | https://github.com/huggingface/lerobot |
| Greengrass v2 CDK sample | https://github.com/aws-samples/aws-iot-greengrass-v2-using-aws-cdk |
| Greengrass ROS2 Docker demo | https://github.com/aws-samples/greengrass-v2-docker-ros-demo |

## Implementation Phases

### Phase 1: Cloud Infrastructure (CDK)
- IoT Core: Thing, Certificate, Policy, Role Alias
- Greengrass: Component Version, Deployment
- IAM: Token Exchange role
- **Independent — no edge dependency**

### Phase 2: Greengrass Component (Python)
- LeRobot sensor reading (all registers)
- JSON serialization + IPC publish
- Greengrass component recipe
- **Independent — can develop/test locally**

### Phase 3: Device Provisioning & E2E Test
- Install Greengrass on robot host
- Provision device with CDK outputs
- Deploy component, verify telemetry in IoT Core MQTT test client
- **Depends on Phase 1 + Phase 2**

Phase 1 and Phase 2 run in parallel. Phase 3 is the integration step.
