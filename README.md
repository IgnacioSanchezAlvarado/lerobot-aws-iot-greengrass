# LeRobot SO-101 AWS IoT Integration

Stream servo sensor data from a LeRobot SO-101 robotic arm to AWS IoT Core via Greengrass v2. A single Greengrass component reads position, velocity, load, temperature, and current from all 6 servo motors and publishes JSON telemetry over MQTT.

## Prerequisites

- AWS CLI configured with appropriate credentials
- AWS CDK bootstrapped in target region
- Node.js 18+ and npm
- Java 11+ (for Greengrass installer)
- Python 3.12 (for component runtime)
- LeRobot SO-101 arm connected via USB serial (for device setup)

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
    "version": "1.0.0",
    "pollingRateHz": 10
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
Robot Host                           AWS Cloud
+---------------------------------+  +---------------------------+
|                                 |  |                           |
| LeRobot SO-101                  |  | AWS IoT Core              |
| (6x Feetech STS3215 servos)     |  |   MQTT Broker             |
|      |                          |  |                           |
|      v                          |  | Topic:                    |
| Greengrass Component:           |  | dt/lerobot/+/telemetry    |
| lerobot-telemetry               |  |                           |
| (reads sensors, publishes JSON) | MQTT | IoT Rules (optional)      |
|      |                          |---->| route to S3, Timestream,  |
| Greengrass Core v2              | TLS  | Lambda, etc.              |
| (nucleus, MQTT bridge)          |  |                           |
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
