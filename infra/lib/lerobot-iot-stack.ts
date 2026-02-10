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
          {
            Effect: 'Allow',
            Action: ['iot:Publish'],
            Resource: `arn:aws:iot:${this.region}:${this.account}:topic/${config.iot.topicPrefix}/${config.iot.deviceId}/*`,
          },
          {
            Effect: 'Allow',
            Action: ['iot:Subscribe'],
            Resource: `arn:aws:iot:${this.region}:${this.account}:topicfilter/${config.iot.topicPrefix}/${config.iot.deviceId}/*`,
          },
          {
            Effect: 'Allow',
            Action: ['iot:Receive'],
            Resource: `arn:aws:iot:${this.region}:${this.account}:topic/${config.iot.topicPrefix}/${config.iot.deviceId}/*`,
          },
          {
            Effect: 'Allow',
            Action: ['iot:AssumeRoleWithCertificate'],
            Resource: `arn:aws:iot:${this.region}:${this.account}:rolealias/${thingName}-role-alias`,
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

    // Add inline policy for S3 access to CDK bootstrap bucket
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
            telemetryTopic: `${config.iot.topicPrefix}/${config.iot.deviceId}/telemetry`,
            deviceId: config.iot.deviceId,
            serialPort: '/dev/ttyUSB0',
            mockMode: 'false',
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
                Script: 'pip3 install -r {artifacts:decompressedPath}/requirements.txt',
              },
              Run: {
                Script: [
                  'export GG_DEVICE_ID="{configuration:/deviceId}"',
                  'export GG_TOPIC_PREFIX="$(echo \'{configuration:/telemetryTopic}\' | sed \'s|/[^/]*$||\')"',
                  'export GG_POLLING_RATE_HZ="{configuration:/pollingRateHz}"',
                  'export GG_SERIAL_PORT="{configuration:/serialPort}"',
                  'export GG_MOCK_MODE="{configuration:/mockMode}"',
                  'export PYTHONPATH="{artifacts:decompressedPath}:$PYTHONPATH"',
                  'cd {artifacts:decompressedPath}',
                  'python3 -u -m lerobot_telemetry',
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
              telemetryTopic: `${config.iot.topicPrefix}/${config.iot.deviceId}/telemetry`,
              deviceId: config.iot.deviceId,
              serialPort: '/dev/ttyUSB0',
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
