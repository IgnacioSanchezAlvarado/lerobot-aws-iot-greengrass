#!/usr/bin/env bash
# setup-device.sh - Provision LeRobot device with AWS IoT Greengrass v2
# Must be run as root: sudo -E ./setup-device.sh

set -euo pipefail

# Get script directory and source common utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

# Root check
if [[ $EUID -ne 0 ]]; then
  error "This script must be run as root. Use: sudo -E $0"
  exit 1
fi

# Ensure AWS credentials are available under sudo
if ! aws sts get-caller-identity &>/dev/null; then
  # Try to load credentials from the invoking user's environment
  SUDO_USER_HOME=$(eval echo "~${SUDO_USER:-}")
  if [[ -n "$SUDO_USER_HOME" && -f "$SUDO_USER_HOME/.aws/credentials" ]]; then
    export AWS_SHARED_CREDENTIALS_FILE="$SUDO_USER_HOME/.aws/credentials"
    export AWS_CONFIG_FILE="$SUDO_USER_HOME/.aws/config"
    # Also inherit region if set
    if [[ -z "${AWS_REGION:-}" && -z "${AWS_DEFAULT_REGION:-}" ]]; then
      REGION=$(aws configure get region 2>/dev/null || true)
      [[ -n "$REGION" ]] && export AWS_REGION="$REGION"
    fi
    if ! aws sts get-caller-identity &>/dev/null; then
      error "AWS credentials not available. Run with: sudo -E $0"
      exit 1
    fi
    info "Using AWS credentials from ${SUDO_USER} user profile"
  else
    error "AWS credentials not available. Run with: sudo -E $0"
    exit 1
  fi
fi

info "Starting LeRobot device provisioning..."
echo ""

# Check if Greengrass is already installed (idempotent)
if [[ -d "${GREENGRASS_ROOT}" ]]; then
  warn "Greengrass installation detected at ${GREENGRASS_ROOT}"
  read -p "Do you want to reinstall? This will remove the existing installation. (y/N): " -n 1 -r
  echo
  if [[ $REPLY =~ ^[Yy]$ ]]; then
    info "Removing existing Greengrass installation..."
    systemctl stop greengrass.service 2>/dev/null || true
    systemctl disable greengrass.service 2>/dev/null || true
    rm -f /etc/systemd/system/greengrass.service
    systemctl daemon-reload
    rm -rf "${GREENGRASS_ROOT}"
    success "Existing installation removed"
  else
    info "Keeping existing installation. Exiting."
    exit 0
  fi
fi

# Check prerequisites
info "Checking prerequisites..."

MISSING_DEPS=()

if ! check_command java; then
  MISSING_DEPS+=("default-jre")
fi

if ! check_command python3; then
  MISSING_DEPS+=("python3")
fi

if ! check_command pip3; then
  MISSING_DEPS+=("python3-pip")
fi

# python3-venv is required for component virtualenv on Ubuntu 24.04+ (PEP 668)
if ! python3 -m venv --help &>/dev/null; then
  MISSING_DEPS+=("python3-venv")
fi

if ! check_command curl; then
  MISSING_DEPS+=("curl")
fi

if ! check_command unzip; then
  MISSING_DEPS+=("unzip")
fi

if ! check_command aws; then
  error "AWS CLI is not installed. Please install it first:"
  error "  https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
  exit 1
fi

# Install missing dependencies
if [[ ${#MISSING_DEPS[@]} -gt 0 ]]; then
  info "Installing missing dependencies: ${MISSING_DEPS[*]}"

  if check_command apt-get; then
    apt-get update -qq
    apt-get install -y -qq "${MISSING_DEPS[@]}"
  elif check_command yum; then
    yum install -y "${MISSING_DEPS[@]}"
  else
    error "Unsupported package manager. Please install manually: ${MISSING_DEPS[*]}"
    exit 1
  fi

  success "Dependencies installed"
else
  success "All prerequisites satisfied"
fi

# Verify Java version
JAVA_VERSION=$(java -version 2>&1 | awk -F '"' '/version/ {print $2}' | cut -d'.' -f1)
if [[ $JAVA_VERSION -lt 11 ]]; then
  error "Java 11 or later is required. Found version: $JAVA_VERSION"
  exit 1
fi

echo ""

# Check for ROS2 installation (optional but recommended)
info "Checking ROS2 installation..."
ROS2_DISTRO=""
for distro in humble jazzy iron; do
  if [[ -f "/opt/ros/${distro}/setup.bash" ]]; then
    ROS2_DISTRO="${distro}"
    break
  fi
done

if [[ -n "${ROS2_DISTRO}" ]]; then
  success "ROS2 ${ROS2_DISTRO} found at /opt/ros/${ROS2_DISTRO}"
else
  warn "ROS2 not found. The telemetry component will run without ROS2 support."
  warn "To install ROS2 (Humble or Jazzy):"
  warn "  https://docs.ros.org/en/jazzy/Installation.html"
  warn ""
  warn "ROS2 enables local topic publishing for digital twin and simulation use cases."
  warn "The component will still publish telemetry to IoT Core without ROS2."
fi

echo ""

# Load configuration from CDK stack outputs
load_config

echo ""

# Download Greengrass installer
info "Downloading AWS IoT Greengrass v2 installer..."

INSTALLER_URL="https://d2s8p88vqu9w66.cloudfront.net/releases/greengrass-nucleus-latest.zip"
INSTALLER_ZIP="/tmp/greengrass-nucleus-latest.zip"
INSTALLER_DIR="/tmp/GreengrassInstaller"

if [[ -f "${INSTALLER_ZIP}" ]]; then
  info "Installer already downloaded, using cached version"
else
  curl -s -o "${INSTALLER_ZIP}" "${INSTALLER_URL}"
  success "Installer downloaded"
fi

# Extract installer
info "Extracting installer..."
rm -rf "${INSTALLER_DIR}"
unzip -q -o "${INSTALLER_ZIP}" -d "${INSTALLER_DIR}"
success "Installer extracted to ${INSTALLER_DIR}"

echo ""

# Run Greengrass installer
info "Installing AWS IoT Greengrass v2..."
info "This will:"
info "  - Create IoT Thing certificate and private key"
info "  - Attach certificate to IoT Thing: ${THING_NAME}"
info "  - Install Greengrass Core at ${GREENGRASS_ROOT}"
info "  - Configure systemd service"
echo ""

java -Droot="${GREENGRASS_ROOT}" \
  -Dlog.store=FILE \
  -jar "${INSTALLER_DIR}/lib/Greengrass.jar" \
  --aws-region "${AWS_REGION}" \
  --thing-name "${THING_NAME}" \
  --thing-policy-name "${IOT_POLICY_NAME}" \
  --tes-role-name "${TES_ROLE_NAME}" \
  --tes-role-alias-name "${ROLE_ALIAS_NAME}" \
  --component-default-user ggc_user:ggc_group \
  --provision true \
  --setup-system-service true

echo ""
success "Greengrass Core installed successfully"

# Add ggc_user to dialout group for USB serial access
info "Adding ggc_user to dialout group for serial port access..."
if getent group dialout > /dev/null; then
  usermod -a -G dialout ggc_user || warn "Failed to add ggc_user to dialout group"
  success "ggc_user added to dialout group"
else
  warn "dialout group not found. You may need to manually grant serial port access."
fi

echo ""

# Verify Greengrass service
info "Verifying Greengrass service..."
sleep 3  # Give service a moment to start

if systemctl is-active --quiet greengrass.service; then
  success "Greengrass service is running"
else
  error "Greengrass service is not running. Check logs at ${GREENGRASS_ROOT}/logs/greengrass.log"
  exit 1
fi

echo ""
echo "============================================"
success "Device provisioning completed successfully!"
echo "============================================"
echo ""
info "Thing Name: ${THING_NAME}"
info "AWS Region: ${AWS_REGION}"
info "Greengrass Root: ${GREENGRASS_ROOT}"
echo ""
info "Next steps:"
info "  1. Verify component deployment: systemctl status greengrass.service"
info "  2. Check component logs: tail -f ${GREENGRASS_ROOT}/logs/${COMPONENT_NAME}.log"
info "  3. Test telemetry: ./scripts/test-telemetry.sh"
echo ""
info "Note: It may take a few minutes for the component to deploy and start."
echo ""
