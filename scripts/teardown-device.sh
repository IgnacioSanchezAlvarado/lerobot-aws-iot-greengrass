#!/usr/bin/env bash
# teardown-device.sh - Remove Greengrass installation and clean up device
# Must be run as root: sudo ./teardown-device.sh

set -euo pipefail

# Get script directory and source common utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

# Root check
if [[ $EUID -ne 0 ]]; then
  error "This script must be run as root. Use: sudo $0"
  exit 1
fi

warn "This will remove the Greengrass installation from this device."
warn "The following will be deleted:"
warn "  - Greengrass installation directory: ${GREENGRASS_ROOT}"
warn "  - Greengrass systemd service"
warn "  - ggc_user and ggc_group (optional)"
echo ""
warn "This does NOT remove cloud resources (IoT Thing, certificates, deployments)."
warn "To remove cloud resources, run: cd infra && npx cdk destroy"
echo ""

read -p "Are you sure you want to continue? (yes/NO): " -r
echo

if [[ ! "$REPLY" =~ ^[Yy][Ee][Ss]$ ]]; then
  info "Teardown cancelled"
  exit 0
fi

echo ""
info "Starting device teardown..."

# Stop Greengrass service
if systemctl is-active --quiet greengrass.service 2>/dev/null; then
  info "Stopping Greengrass service..."
  systemctl stop greengrass.service
  success "Greengrass service stopped"
else
  info "Greengrass service is not running"
fi

# Disable Greengrass service
if systemctl is-enabled --quiet greengrass.service 2>/dev/null; then
  info "Disabling Greengrass service..."
  systemctl disable greengrass.service
  success "Greengrass service disabled"
fi

# Remove systemd unit file
if [[ -f /etc/systemd/system/greengrass.service ]]; then
  info "Removing systemd unit file..."
  rm -f /etc/systemd/system/greengrass.service
  systemctl daemon-reload
  success "Systemd unit file removed"
fi

# Remove Greengrass installation directory
if [[ -d "${GREENGRASS_ROOT}" ]]; then
  info "Removing Greengrass installation: ${GREENGRASS_ROOT}..."
  rm -rf "${GREENGRASS_ROOT}"
  success "Greengrass installation removed"
else
  info "Greengrass installation directory not found, skipping"
fi

# Remove ggc_user and ggc_group (optional)
read -p "Remove ggc_user and ggc_group? (y/N): " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
  info "Removing ggc_user and ggc_group..."
  userdel ggc_user 2>/dev/null || warn "Could not remove ggc_user (may not exist)"
  groupdel ggc_group 2>/dev/null || warn "Could not remove ggc_group (may not exist)"
  success "User and group cleanup complete"
else
  info "Keeping ggc_user and ggc_group"
fi

# Clean up temporary files
info "Cleaning up temporary files..."
rm -f /tmp/greengrass-nucleus-latest.zip
rm -rf /tmp/GreengrassInstaller
success "Temporary files removed"

echo ""
echo "=========================================="
success "Device teardown completed successfully!"
echo "=========================================="
echo ""
info "The Greengrass installation has been removed from this device."
echo ""
warn "Cloud resources still exist. To remove them:"
info "  cd infra"
info "  npx cdk destroy"
echo ""
info "This will delete:"
info "  - IoT Thing and certificates"
info "  - IoT Policy"
info "  - Greengrass deployment and component"
info "  - IAM roles"
echo ""
