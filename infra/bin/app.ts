#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib';
import { LeRobotIotStack } from '../lib/lerobot-iot-stack';
import * as fs from 'fs';
import * as path from 'path';

const app = new cdk.App();

// Read config from project root
const configPath = path.resolve(__dirname, '../../config.json');
const config = JSON.parse(fs.readFileSync(configPath, 'utf-8'));

new LeRobotIotStack(app, config.infrastructure.stackName, {
  config,
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: config.project.region || process.env.CDK_DEFAULT_REGION,
  },
  tags: {
    Project: config.project.name,
    Environment: config.project.environment,
  },
});
