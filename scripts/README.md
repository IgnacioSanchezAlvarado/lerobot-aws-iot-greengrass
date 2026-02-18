# Device Provisioning Scripts

Scripts to provision, test, and teardown LeRobot SO-101 devices with AWS IoT Greengrass v2.

## Prerequisites

1. CDK stack deployed: `cd ../infra && npx cdk deploy`
2. AWS CLI configured with appropriate credentials
3. Root/sudo access on the device

**Note:** The setup script requires AWS credentials to retrieve stack outputs. Use `sudo -E` to preserve your environment variables (including AWS credentials), or the script will auto-detect credentials from the invoking user's AWS CLI profile.

## Files

### `common.sh`
Shared utilities sourced by all scripts:
- Color output functions
- Configuration loading from CDK stack outputs
- Command checks

### `setup-device.sh`
Main provisioning script. Installs and configures Greengrass on the device.

**Usage:**
```bash
sudo -E ./setup-device.sh
```

**What it does:**
1. Checks prerequisites (Java, Python, AWS CLI)
2. Installs missing dependencies
3. Downloads Greengrass v2 installer
4. Provisions device with IoT Core (creates certificates)
5. Installs Greengrass as systemd service
6. Adds ggc_user to dialout group for serial access

**Idempotent:** Safe to re-run. Will prompt before reinstalling.

### `test-telemetry.sh`
Verification script. Checks that telemetry is publishing to IoT Core.

**Usage:**
```bash
./test-telemetry.sh
```

**What it does:**
1. Checks Greengrass service status
2. Shows component log tail
3. Displays MQTT topic and AWS Console URL
4. Provides mosquitto_sub command for local streaming

**Does not require root.**

### `teardown-device.sh`
Cleanup script. Removes Greengrass installation from device.

**Usage:**
```bash
sudo ./teardown-device.sh
```

**What it does:**
1. Stops and disables Greengrass service
2. Removes Greengrass installation directory
3. Removes systemd unit file
4. Optionally removes ggc_user and ggc_group
5. Cleans up temp files

**Note:** This does NOT remove cloud resources. Run `npx cdk destroy` to clean up AWS resources.

## Quick Start

On your robot device (with SO-101 arm connected):

```bash
# 1. Make scripts executable
chmod +x *.sh

# 2. Provision device
sudo -E ./setup-device.sh

# 3. Wait a few minutes for component deployment

# 4. Test telemetry
./test-telemetry.sh

# 5. View in AWS Console (URL printed by test script)
```

## Troubleshooting

### Greengrass won't start
Check logs:
```bash
sudo tail -f /greengrass/v2/logs/greengrass.log
```

### Component not deploying
List deployments:
```bash
sudo /greengrass/v2/bin/greengrass-cli deployment list
```

Check component status:
```bash
sudo /greengrass/v2/bin/greengrass-cli component list
```

### Serial port permission denied
Ensure ggc_user is in dialout group:
```bash
groups ggc_user
```

Add to group if missing:
```bash
sudo usermod -a -G dialout ggc_user
sudo systemctl restart greengrass.service
```

### Component errors
View component logs:
```bash
sudo tail -f /greengrass/v2/logs/com.lerobot.telemetry.log
```

## Clean Up

**Device only:**
```bash
sudo ./teardown-device.sh
```

**Cloud resources:**
```bash
cd ../infra
npx cdk destroy
```
