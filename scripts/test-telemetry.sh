#!/usr/bin/env bash
# test-telemetry.sh - Verify LeRobot telemetry is publishing to IoT Core
# Does NOT require root

set -euo pipefail

# Get script directory and source common utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

info "Verifying LeRobot telemetry..."
echo ""

# Load configuration
load_config

echo ""

# Check Greengrass service
info "Checking Greengrass service status..."
if systemctl is-active --quiet greengrass.service 2>/dev/null; then
  success "Greengrass service is running"
else
  error "Greengrass service is not running"
  error "Start it with: sudo systemctl start greengrass.service"
  exit 1
fi

echo ""

# Extract device ID from thing name (format: lerobot-{device-id})
DEVICE_ID="${THING_NAME#lerobot-}"
TELEMETRY_TOPIC="dt/lerobot/${DEVICE_ID}/telemetry"

# Check component log
COMPONENT_LOG="${GREENGRASS_ROOT}/logs/${COMPONENT_NAME}.log"
info "Checking component log: ${COMPONENT_LOG}"

if [[ ! -f "${COMPONENT_LOG}" ]]; then
  warn "Component log not found. Component may not be deployed yet."
  info "Check deployment status:"
  info "  sudo ${GREENGRASS_ROOT}/bin/greengrass-cli deployment list"
  echo ""
  info "Check general Greengrass logs:"
  info "  sudo tail -f ${GREENGRASS_ROOT}/logs/greengrass.log"
else
  # Show last 20 lines of component log
  info "Last 20 lines of component log:"
  echo "---"
  sudo tail -n 20 "${COMPONENT_LOG}" || warn "Could not read component log (permission denied?)"
  echo "---"
  echo ""

  # Check for common error patterns
  if sudo grep -q "ERROR" "${COMPONENT_LOG}" 2>/dev/null; then
    warn "Errors detected in component log. Review above output."
  else
    success "No errors detected in component log"
  fi
fi

echo ""

# Display MQTT topic and test instructions
info "Telemetry MQTT Topic:"
echo "  ${TELEMETRY_TOPIC}"
echo ""

info "To view messages in AWS Console:"
echo "  1. Open AWS IoT Core console: https://console.aws.amazon.com/iot/home?region=${AWS_REGION}#/test"
echo "  2. Subscribe to topic: ${TELEMETRY_TOPIC}"
echo "  3. You should see JSON messages with joint sensor data"
echo ""

# Optional: mosquitto_sub live stream
if check_command mosquitto_sub; then
  info "mosquitto_sub is available. You can stream messages locally:"
  echo ""
  echo "  mosquitto_sub \\"
  echo "    --cert ${GREENGRASS_ROOT}/thingCert.crt \\"
  echo "    --key ${GREENGRASS_ROOT}/privKey.key \\"
  echo "    --cafile ${GREENGRASS_ROOT}/rootCA.pem \\"
  echo "    -h ${DATA_ATS_ENDPOINT} \\"
  echo "    -p 8883 \\"
  echo "    -t '${TELEMETRY_TOPIC}' \\"
  echo "    -v"
  echo ""
else
  info "Install mosquitto-clients for local MQTT streaming:"
  echo "  sudo apt-get install mosquitto-clients"
  echo ""
fi

# Greengrass CLI status
info "Check component status with Greengrass CLI:"
echo "  sudo ${GREENGRASS_ROOT}/bin/greengrass-cli component list"
echo "  sudo ${GREENGRASS_ROOT}/bin/greengrass-cli component details --name ${COMPONENT_NAME}"
echo ""

success "Verification complete"
