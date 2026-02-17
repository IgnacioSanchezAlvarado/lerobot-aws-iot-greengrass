# LeRobot SO-101 AWS IoT Integration

Stream servo sensor data from a LeRobot SO-101 robotic arm to AWS IoT Core via Greengrass v2. The component also runs as a ROS2 node, publishing standard JointState and DiagnosticArray messages for local ROS2 ecosystem integration.

## Prerequisites

- AWS CLI configured with appropriate credentials
- AWS CDK bootstrapped in target region
- Node.js 18+ and npm
- Java 11+ (for Greengrass installer)
- Python 3.12 (for component runtime)
- LeRobot SO-101 arm connected via USB serial (for device setup)
- ROS2 Humble or Jazzy (optional, for local ROS2 topic publishing) — set distro in config.json

## Configuration

Edit `config.json` before deployment:

```json
{
  "project": {
    "name": "lerobot-iot",
    "environment": "dev"
  },
  "iot": {
    "deviceId": "arm-001",
    "topicPrefix": "dt/lerobot"
  },
  "component": {
    "name": "com.lerobot.telemetry",
    "version": "2.0.0",
    "pollingRateHz": 10
  },
  "ros2": {
    "nodeName": "lerobot_telemetry",
    "jointStatesTopic": "/joint_states",
    "servoDiagnosticsTopic": "/servo_diagnostics",
    "distro": "humble"
  },
  "greengrass": {
    "nucleusVersion": "2.14.2"
  }
}
```

## Deployment

### 1. Deploy Cloud Infrastructure

From your development machine:

```bash
cd infra
npm install
npx cdk synth    # Validate templates
npx cdk deploy   # Deploy to AWS
```

Note the CDK outputs (Thing name, policy name, role alias, region, endpoint).

### 2. Provision Device

On the robot host with the SO-101 arm connected:

```bash
sudo ./scripts/setup-device.sh
```

This script will:
- Install Greengrass Core v2
- Create IoT Thing certificate and private key
- Attach certificate to IoT Thing
- Configure systemd service
- Deploy the telemetry component

The component will start automatically and begin publishing telemetry.

## Testing

### Check Service Status

```bash
sudo systemctl status greengrass.service
```

### View Component Logs

```bash
sudo tail -f /greengrass/v2/logs/com.lerobot.telemetry.log
```

### Run Test Script

```bash
./scripts/test-telemetry.sh
```

### Verify ROS2 Topics (if ROS2 installed)

The component publishes ROS2 topics on the default DDS domain. From another terminal on the same machine:

```bash
source /opt/ros/jazzy/setup.bash  # or humble, matching your installation

ros2 topic list
# Should show /joint_states and /servo_diagnostics

ros2 topic echo /joint_states
# Should show JointState messages at configured rate

ros2 topic echo /servo_diagnostics
# Should show DiagnosticArray messages with servo temperature/current
```

If topics don't appear, check the component log for ROS2 initialization status:

```bash
sudo grep -i "ros2\|rclpy" /greengrass/v2/logs/com.lerobot.telemetry.log
```

### View Messages in AWS Console

1. Open [AWS IoT Core Test Client](https://console.aws.amazon.com/iot/home#/test)
2. Subscribe to topic: `dt/lerobot/arm-001/telemetry`
3. You should see JSON messages published at 10Hz with servo data

### Example Telemetry Message

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

## Cleanup

### Remove Device Provisioning

On the robot host:

```bash
sudo ./scripts/teardown-device.sh
```

This will:
- Stop and disable Greengrass service
- Remove Greengrass installation
- Delete certificates and keys

### Destroy Cloud Resources

From your development machine:

```bash
cd infra
npx cdk destroy
```

Note: You may need to manually delete the IoT Thing certificate in the AWS Console if it's still attached.

## Troubleshooting

### Component Not Starting

Check Greengrass logs:
```bash
sudo tail -f /greengrass/v2/logs/greengrass.log
```

Check component deployment status:
```bash
sudo /greengrass/v2/bin/greengrass-cli component list
sudo /greengrass/v2/bin/greengrass-cli component details --name com.lerobot.telemetry
```

### Serial Port Access Denied

Ensure `ggc_user` is in the `dialout` group:
```bash
sudo usermod -a -G dialout ggc_user
sudo systemctl restart greengrass.service
```

### No Messages in IoT Core

Verify component is publishing:
```bash
sudo grep "Published" /greengrass/v2/logs/com.lerobot.telemetry.log
```

Check IoT Thing policy allows publish to `dt/lerobot/arm-001/*`.

### Mock Mode (No Hardware)

Edit component configuration in Greengrass deployment to set `mockMode: true` for testing without a physical arm.

## Architecture

```
Robot Host (ROS2)                    AWS Cloud
+---------------------------------+  +---------------------------+
|                                 |  |                           |
| LeRobot SO-101                  |  | AWS IoT Core              |
| (6x Feetech STS3215 servos)    |  |   MQTT Broker             |
|      |                          |  |                           |
|      v                          |  | Topic:                    |
| Greengrass Component:           |  | dt/lerobot/+/telemetry    |
| lerobot-telemetry (ROS2 node)   |  |                           |
|  +----------+---------+         |  | IoT Rules (optional)      |
|  | ROS2     | IoT IPC |         |  | route to S3, Timestream,  |
|  | topics   | bridge  |-------->|  | Lambda, etc.              |
|  v          v         |    TLS  |  |                           |
| /joint_states         |         |  |                           |
| /servo_diagnostics    |         |  |                           |
| Greengrass Core v2              |  |                           |
+---------------------------------+  +---------------------------+
```

## Project Structure

```
/infra         CDK stack (TypeScript) - IoT Core, Greengrass, IAM
/component     Greengrass component (Python 3.12)
/scripts       Device provisioning and testing scripts
/plans         Implementation plans
config.json    Project configuration
```

## References

- [LeRobot Project](https://github.com/huggingface/lerobot)
- [AWS IoT Greengrass v2 Developer Guide](https://docs.aws.amazon.com/greengrass/v2/developerguide/)
- [AWS CDK TypeScript Reference](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-construct-library.html)
