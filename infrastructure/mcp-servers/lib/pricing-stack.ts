import * as cdk from 'aws-cdk-lib';
import * as agentcore from '@aws-cdk/aws-bedrock-agentcore-alpha';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';
import * as path from 'path';

export interface PricingMcpStackProps extends cdk.StackProps {
  deploymentId: string;
}

export class PricingMcpStack extends cdk.Stack {
  public readonly runtimeArn: string;

  constructor(scope: Construct, id: string, props: PricingMcpStackProps) {
    super(scope, id, props);

    const { deploymentId } = props;

    cdk.Tags.of(this).add('DeploymentId', deploymentId);

    // Execution role for pricing MCP server
    const pricingMcpRole = new iam.Role(this, 'PricingMcpRole', {
      assumedBy: new iam.ServicePrincipal('bedrock-agentcore.amazonaws.com'),
    });

    // Grant pricing API permissions
    pricingMcpRole.addToPolicy(new iam.PolicyStatement({
      actions: ['pricing:*'],
      resources: ['*'],
    }));

    pricingMcpRole.addToPolicy(new iam.PolicyStatement({
      actions: ['logs:CreateLogGroup', 'logs:CreateLogStream', 'logs:PutLogEvents'],
      resources: [`arn:aws:logs:${this.region}:${this.account}:log-group:*`],
    }));

    // Create MCP runtime for AWS Pricing
    const pricingMcpRuntime = new agentcore.Runtime(this, 'PricingMcpRuntime', {
      runtimeName: `pricingtools_mcp_pricingstack_${deploymentId.replace(/-/g, '_')}`,
      agentRuntimeArtifact: agentcore.AgentRuntimeArtifact.fromAsset(
        path.join(__dirname, '../../..', 'concierge_agent', 'pricing_mcp_tools')
      ),
      executionRole: pricingMcpRole,
      protocolConfiguration: agentcore.ProtocolType.MCP,
      networkConfiguration: agentcore.RuntimeNetworkConfiguration.usingPublicNetwork(),
      environmentVariables: {
        AWS_REGION: this.region,
        FASTMCP_LOG_LEVEL: 'ERROR',
      },
      description: 'AWS Pricing MCP Server for real-time pricing data',
    });

    this.runtimeArn = pricingMcpRuntime.agentRuntimeArn;

    // Outputs
    new cdk.CfnOutput(this, 'RuntimeArn', {
      value: pricingMcpRuntime.agentRuntimeArn,
      exportName: `PricingStack-${deploymentId}-RuntimeArn`,
    });

    new cdk.CfnOutput(this, 'RuntimeId', {
      value: pricingMcpRuntime.agentRuntimeId,
      exportName: `PricingStack-${deploymentId}-RuntimeId`,
    });
  }
}
