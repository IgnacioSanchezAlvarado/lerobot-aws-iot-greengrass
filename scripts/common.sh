#!/usr/bin/env bash
# common.sh - Shared utilities for LeRobot IoT provisioning scripts

set -euo pipefail

# Constants
GREENGRASS_ROOT="/greengrass/v2"
STACK_NAME="LeRobotIotStack"

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Output functions
info() {
  echo -e "${BLUE}[INFO]${NC} $*"
}

success() {
  echo -e "${GREEN}[SUCCESS]${NC} $*"
}

warn() {
  echo -e "${YELLOW}[WARN]${NC} $*"
}

error() {
  echo -e "${RED}[ERROR]${NC} $*" >&2
}

# Check if a command exists
check_command() {
  local cmd="$1"
  if command -v "$cmd" &>/dev/null; then
    return 0
  else
    return 1
  fi
}

# Load configuration from CDK stack outputs
load_config() {
  info "Loading configuration from CloudFormation stack: ${STACK_NAME}..."

  # Check AWS CLI is available
  if ! check_command aws; then
    error "AWS CLI not found. Please install it first."
    exit 1
  fi

  # Get stack outputs
  local stack_outputs
  if ! stack_outputs=$(aws cloudformation describe-stacks \
    --stack-name "${STACK_NAME}" \
    --query 'Stacks[0].Outputs' \
    --output json 2>/dev/null); then
    error "Failed to retrieve CloudFormation stack outputs."
    error "Make sure the stack '${STACK_NAME}' is deployed and AWS CLI is configured."
    exit 1
  fi

  # Parse outputs using jq
  if ! check_command jq; then
    error "jq not found. Installing jq..."
    if check_command apt-get; then
      sudo apt-get update -qq && sudo apt-get install -y -qq jq
    elif check_command yum; then
      sudo yum install -y jq
    else
      error "Could not install jq. Please install it manually."
      exit 1
    fi
  fi

  # Extract values
  export THING_NAME=$(echo "$stack_outputs" | jq -r '.[] | select(.OutputKey=="ThingName") | .OutputValue')
  export IOT_POLICY_NAME=$(echo "$stack_outputs" | jq -r '.[] | select(.OutputKey=="IoTPolicyName") | .OutputValue')
  export TES_ROLE_NAME=$(echo "$stack_outputs" | jq -r '.[] | select(.OutputKey=="TokenExchangeRoleName") | .OutputValue')
  export ROLE_ALIAS_NAME=$(echo "$stack_outputs" | jq -r '.[] | select(.OutputKey=="RoleAliasName") | .OutputValue')
  export AWS_REGION=$(echo "$stack_outputs" | jq -r '.[] | select(.OutputKey=="Region") | .OutputValue')
  export DATA_ATS_ENDPOINT=$(echo "$stack_outputs" | jq -r '.[] | select(.OutputKey=="DataAtsEndpoint") | .OutputValue')
  export COMPONENT_NAME=$(echo "$stack_outputs" | jq -r '.[] | select(.OutputKey=="ComponentName") | .OutputValue')

  # Validate required values
  if [[ -z "$THING_NAME" || "$THING_NAME" == "null" ]]; then
    error "Failed to retrieve ThingName from stack outputs."
    exit 1
  fi

  if [[ -z "$IOT_POLICY_NAME" || "$IOT_POLICY_NAME" == "null" ]]; then
    error "Failed to retrieve IoTPolicyName from stack outputs."
    exit 1
  fi

  if [[ -z "$TES_ROLE_NAME" || "$TES_ROLE_NAME" == "null" ]]; then
    error "Failed to retrieve TokenExchangeRoleName from stack outputs."
    exit 1
  fi

  if [[ -z "$ROLE_ALIAS_NAME" || "$ROLE_ALIAS_NAME" == "null" ]]; then
    error "Failed to retrieve RoleAliasName from stack outputs."
    exit 1
  fi

  if [[ -z "$AWS_REGION" || "$AWS_REGION" == "null" ]]; then
    error "Failed to retrieve Region from stack outputs."
    exit 1
  fi

  success "Configuration loaded successfully"
  info "Thing Name: ${THING_NAME}"
  info "IoT Policy: ${IOT_POLICY_NAME}"
  info "AWS Region: ${AWS_REGION}"
}
