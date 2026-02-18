import * as cdk from 'aws-cdk-lib';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as iot from 'aws-cdk-lib/aws-iot';
import * as greengrassv2 from 'aws-cdk-lib/aws-greengrassv2';
import * as s3Assets from 'aws-cdk-lib/aws-s3-assets';
import { Construct } from 'constructs';
import * as path from 'path';

interface LeRobotIotStackProps extends cdk.StackProps {
  config: any;
}

export class LeRobotIotStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: LeRobotIotStackProps) {
    super(scope, id, props);

    const { config } = props;
    const thingName = `lerobot-${config.iot.deviceId}`;

    // A. IoT Thing
    const thing = new iot.CfnThing(this, 'Thing', {
      thingName,
    });
    cdk.Tags.of(thing).add('Project', config.project.name);
    cdk.Tags.of(thing).add('Environment', config.project.environment);

    // B. IoT Policy (LEAST PRIVILEGE)
    const iotPolicy = new iot.CfnPolicy(this, 'IoTPolicy', {
      policyName: `${thingName}-policy`,
      policyDocument: {
        Version: '2012-10-17',
        Statement: [
          // Connect with certificate-based auth
          {
            Effect: 'Allow',
            Action: ['iot:Connect'],
            Resource: `arn:aws:iot:${this.region}:${this.account}:client/${thingName}`,
            Condition: {
              Bool: {
                'iot:Connection.Thing.IsAttached': ['true'],
              },
            },
          },
          // Publish: telemetry data + Greengrass system topics
          {
            Effect: 'Allow',
            Action: ['iot:Publish'],
            Resource: [
              `arn:aws:iot:${this.region}:${this.account}:topic/${config.iot.topicPrefix}/${config.iot.deviceId}/*`,
              `arn:aws:iot:${this.region}:${this.account}:topic/$aws/things/${thingName}/*`,
            ],
          },
          // Subscribe: telemetry data + Greengrass system topics
          {
            Effect: 'Allow',
            Action: ['iot:Subscribe'],
            Resource: [
              `arn:aws:iot:${this.region}:${this.account}:topicfilter/${config.iot.topicPrefix}/${config.iot.deviceId}/*`,
              `arn:aws:iot:${this.region}:${this.account}:topicfilter/$aws/things/${thingName}/*`,
            ],
          },
          // Receive: telemetry data + Greengrass system topics
          {
            Effect: 'Allow',
            Action: ['iot:Receive'],
            Resource: [
              `arn:aws:iot:${this.region}:${this.account}:topic/${config.iot.topicPrefix}/${config.iot.deviceId}/*`,
              `arn:aws:iot:${this.region}:${this.account}:topic/$aws/things/${thingName}/*`,
            ],
          },
          // Greengrass: get thing shadow for deployments
          {
            Effect: 'Allow',
            Action: [
              'iot:GetThingShadow',
              'iot:UpdateThingShadow',
              'iot:DeleteThingShadow',
            ],
            Resource: `arn:aws:iot:${this.region}:${this.account}:thing/${thingName}`,
          },
          // Token exchange for temporary credentials
          {
            Effect: 'Allow',
            Action: ['iot:AssumeRoleWithCertificate'],
            Resource: `arn:aws:iot:${this.region}:${this.account}:rolealias/${thingName}-role-alias`,
          },
          // Greengrass data plane: resolve and download components
          {
            Effect: 'Allow',
            Action: [
              'greengrass:GetComponentVersionArtifact',
              'greengrass:ResolveComponentCandidates',
              'greengrass:GetDeploymentConfiguration',
            ],
            Resource: '*',
          },
        ],
      },
    });
    cdk.Tags.of(iotPolicy).add('Project', config.project.name);
    cdk.Tags.of(iotPolicy).add('Environment', config.project.environment);

    // C. Token Exchange IAM Role
    const tokenExchangeRole = new iam.Role(this, 'TokenExchangeRole', {
      roleName: `${thingName}-token-exchange-role`,
      assumedBy: new iam.ServicePrincipal('credentials.iot.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('CloudWatchLogsFullAccess'),
      ],
    });
    cdk.Tags.of(tokenExchangeRole).add('Project', config.project.name);
    cdk.Tags.of(tokenExchangeRole).add('Environment', config.project.environment);

    // Add inline policy for Greengrass component resolution and S3 artifact access
    tokenExchangeRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          'greengrass:ResolveComponentCandidates',
          'greengrass:GetComponentVersionArtifact',
          'greengrass:GetDeploymentConfiguration',
        ],
        resources: ['*'],
      })
    );
    tokenExchangeRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: ['s3:GetObject'],
        resources: [
          `arn:aws:s3:::cdk-*-assets-${this.account}-${this.region}/*`,
        ],
      })
    );

    // D. IoT Role Alias
    const roleAlias = new iot.CfnRoleAlias(this, 'RoleAlias', {
      roleAlias: `${thingName}-role-alias`,
      roleArn: tokenExchangeRole.roleArn,
    });
    cdk.Tags.of(roleAlias).add('Project', config.project.name);
    cdk.Tags.of(roleAlias).add('Environment', config.project.environment);

    // E. Component Asset (S3 packaging of /component directory)
    const componentAsset = new s3Assets.Asset(this, 'ComponentAsset', {
      path: path.resolve(__dirname, '../../component'),
    });
    componentAsset.grantRead(tokenExchangeRole);

    // F. CfnComponentVersion with inline recipe
    const componentVersion = new greengrassv2.CfnComponentVersion(this, 'ComponentVersion', {
      inlineRecipe: JSON.stringify({
        RecipeFormatVersion: '2020-01-25',
        ComponentName: config.component.name,
        ComponentVersion: config.component.version,
        ComponentDescription: 'LeRobot SO-101 telemetry component',
        ComponentPublisher: 'AWS Solutions Architect',
        ComponentConfiguration: {
          DefaultConfiguration: {
            pollingRateHz: config.component.pollingRateHz,
            topicPrefix: config.iot.topicPrefix,
            deviceId: config.iot.deviceId,
            serialPort: config.component.serialPort,
            mockMode: String(config.component.mockMode),
            serialBaudRate: config.component.serialBaudRate,
            serialTimeout: config.component.serialTimeout,
            tempWarningThreshold: config.component.tempWarningThreshold,
            ros2NodeName: config.ros2.nodeName,
            ros2JointStatesTopic: config.ros2.jointStatesTopic,
            ros2ServoDiagnosticsTopic: config.ros2.servoDiagnosticsTopic,
            ros2Distro: config.ros2.distro,
            mode: config.component.mode,
            accessControl: {
              'aws.greengrass.ipc.mqttproxy': {
                [`${config.component.name}:pubsub:1`]: {
                  policyDescription: 'Allow publishing telemetry to IoT Core',
                  operations: ['aws.greengrass#PublishToIoTCore'],
                  resources: [`${config.iot.topicPrefix}/${config.iot.deviceId}/*`],
                },
              },
            },
          },
        },
        ComponentDependencies: {
          'aws.greengrass.Nucleus': {
            VersionRequirement: '>=2.0.0',
          },
        },
        Manifests: [
          {
            Platform: {
              os: 'linux',
            },
            Lifecycle: {
              Install: {
                Script: [
                  `. /opt/ros/\${ROS_DISTRO:-${config.ros2?.distro ?? 'jazzy'}}/setup.sh 2>/dev/null || true`,
                  '# CDK Asset ZIP extracts into a hash subdirectory',
                  'COMP_DIR=$(find {artifacts:decompressedPath} -name requirements.txt -exec dirname {} \\;)',
                  'python3 -m venv --system-site-packages {work:path}/venv',
                  '{work:path}/venv/bin/pip install -r "$COMP_DIR/requirements.txt"',
                  '# Store resolved path for Run lifecycle',
                  'echo "$COMP_DIR" > {work:path}/comp_dir.txt',
                ].join('\n'),
              },
              Run: {
                Script: [
                  `. /opt/ros/\${ROS_DISTRO:-${config.ros2?.distro ?? 'jazzy'}}/setup.sh 2>/dev/null || echo "ROS2 not found, running without ROS2 support"`,
                  'COMP_DIR=$(cat {work:path}/comp_dir.txt)',
                  'export GG_DEVICE_ID="{configuration:/deviceId}"',
                  'export GG_TOPIC_PREFIX="{configuration:/topicPrefix}"',
                  'export GG_POLLING_RATE_HZ="{configuration:/pollingRateHz}"',
                  'export GG_SERIAL_PORT="{configuration:/serialPort}"',
                  'export GG_MOCK_MODE="{configuration:/mockMode}"',
                  'export GG_SERIAL_BAUDRATE="{configuration:/serialBaudRate}"',
                  'export GG_SERIAL_TIMEOUT="{configuration:/serialTimeout}"',
                  'export GG_TEMP_WARNING_THRESHOLD="{configuration:/tempWarningThreshold}"',
                  'export GG_ROS2_NODE_NAME="{configuration:/ros2NodeName}"',
                  'export GG_ROS2_JOINT_STATES_TOPIC="{configuration:/ros2JointStatesTopic}"',
                  'export GG_ROS2_SERVO_DIAGNOSTICS_TOPIC="{configuration:/ros2ServoDiagnosticsTopic}"',
                  'export GG_ROS2_DISTRO="{configuration:/ros2Distro}"',
                  'export GG_MODE="{configuration:/mode}"',
                  'export ROS_DISTRO="{configuration:/ros2Distro}"',
                  '# Disable Fast DDS shared memory transport so cross-user DDS discovery works',
                  'export FASTDDS_BUILTIN_TRANSPORTS=UDPv4',
                  'export PYTHONPATH="$COMP_DIR:$PYTHONPATH"',
                  'cd "$COMP_DIR"',
                  '{work:path}/venv/bin/python3 -u -m lerobot_telemetry',
                ].join('\n'),
              },
            },
            Artifacts: [
              {
                Uri: `s3://${componentAsset.s3BucketName}/${componentAsset.s3ObjectKey}`,
                Unarchive: 'ZIP',
              },
            ],
          },
        ],
      }),
    });
    cdk.Tags.of(componentVersion).add('Project', config.project.name);
    cdk.Tags.of(componentVersion).add('Environment', config.project.environment);

    // G. CfnDeployment targeting the thing
    const deployment = new greengrassv2.CfnDeployment(this, 'Deployment', {
      targetArn: thing.attrArn,
      deploymentName: `${thingName}-initial-deployment`,
      components: {
        'aws.greengrass.Nucleus': {
          componentVersion: config.greengrass.nucleusVersion,
        },
        'aws.greengrass.TokenExchangeService': {
          componentVersion: '2.0.3',
          configurationUpdate: {
            merge: JSON.stringify({
              iotRoleAlias: roleAlias.roleAlias,
            }),
          },
        },
        [config.component.name]: {
          componentVersion: config.component.version,
          configurationUpdate: {
            merge: JSON.stringify({
              pollingRateHz: config.component.pollingRateHz,
              topicPrefix: config.iot.topicPrefix,
              deviceId: config.iot.deviceId,
              serialPort: config.component.serialPort,
              serialBaudRate: config.component.serialBaudRate,
              serialTimeout: config.component.serialTimeout,
              tempWarningThreshold: config.component.tempWarningThreshold,
              ros2NodeName: config.ros2.nodeName,
              ros2JointStatesTopic: config.ros2.jointStatesTopic,
              ros2ServoDiagnosticsTopic: config.ros2.servoDiagnosticsTopic,
              ros2Distro: config.ros2.distro,
              mode: config.component.mode,
            }),
          },
        },
      },
      deploymentPolicies: {
        failureHandlingPolicy: 'ROLLBACK',
        componentUpdatePolicy: {
          timeoutInSeconds: 60,
          action: 'NOTIFY_COMPONENTS',
        },
        configurationValidationPolicy: {
          timeoutInSeconds: 30,
        },
      },
    });
    deployment.addDependency(componentVersion);
    cdk.Tags.of(deployment).add('Project', config.project.name);
    cdk.Tags.of(deployment).add('Environment', config.project.environment);

    // H. CDK Outputs
    new cdk.CfnOutput(this, 'ThingName', {
      value: thingName,
      description: 'IoT Thing name',
    });

    new cdk.CfnOutput(this, 'IoTPolicyName', {
      value: iotPolicy.policyName!,
      description: 'IoT Policy name',
    });

    new cdk.CfnOutput(this, 'TokenExchangeRoleName', {
      value: tokenExchangeRole.roleName,
      description: 'Token Exchange Role name',
    });

    new cdk.CfnOutput(this, 'RoleAliasName', {
      value: roleAlias.roleAlias!,
      description: 'IoT Role Alias name',
    });

    new cdk.CfnOutput(this, 'Region', {
      value: this.region,
      description: 'AWS Region',
    });

    new cdk.CfnOutput(this, 'DataAtsEndpoint', {
      value: `iot.${this.region}.amazonaws.com`,
      description: 'IoT Data ATS Endpoint',
    });

    new cdk.CfnOutput(this, 'ComponentName', {
      value: config.component.name,
      description: 'Greengrass Component name',
    });

    new cdk.CfnOutput(this, 'ComponentVersionOutput', {
      value: config.component.version,
      description: 'Greengrass Component version',
    });
  }
}
